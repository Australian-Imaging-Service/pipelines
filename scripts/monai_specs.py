"""Generate pipeline2app XNAT specs from whitelisted MONAI Model Zoo bundles."""
import json
import os
import re
import typing as ty
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml
from monai.bundle import get_all_bundles_list
from pydra.compose.monai import spec_fragment


#: Directory inside the built image that model bundles are copied into.
RUNTIME_BUNDLE_ROOT = "/monai-bundles"


#: Fields that are the same for every MONAI Model Zoo bundle, so they are
#: defaults here rather than repeated in a per-model file. A model that ever
#: needs a different value should gain a whitelist field, not an overlay.
MONAI_BASE_IMAGE = "projectmonai/monai"

#: Pinned rather than `latest`: the base image tag is part of the spec checksum
#: `plan-builds` compares against the published image to decide whether to
#: rebuild. With `latest` the checksum stays constant while the image beneath
#: it changes, so a new MONAI release would not trigger a rebuild and the
#: published image would silently drift from the spec describing it.
MONAI_BASE_IMAGE_TAG = "1.6.1"

MONAI_AUTHORS = [{"name": "MONAI Consortium", "email": "monai.contact@gmail.com"}]
MONAI_INFO_URL = "https://monai.io/model-zoo.html"
MONAI_OPERATES_ON = "medimage/session"

#: >=0.1.5 loads the bundle's checkpoint via ConfigWorkflow; earlier versions
#: never ran the bundle's `initialize` section, so inference ran with
#: randomly-initialised weights and produced plausible but meaningless output.
#: >=0.2.0 raises FileNotFoundError carrying the bundle path when the bundle
#: isn't on the host, which is what pydra2app's `can_defer_task` keys on.
PYDRA_COMPOSE_MONAI_REQ = ">=0.2.0"


class WhitelistEntry(ty.NamedTuple):
    name: str
    version: Optional[str]
    modality: str
    species: str
    region: str
    #: pip requirements that override what the bundle declares in its
    #: `required_packages_version`, for pins that don't work in the image.
    package_overrides: Dict[str, str] = {}


class DeclinedEntry(ty.NamedTuple):
    """A model reviewed and deliberately not published.

    ``at_version`` scopes the decision to what was actually reviewed, so a
    model declined as immature resurfaces once the Zoo moves past it. A
    decision that will never change is re-declined by bumping ``at_version``.
    """

    name: str
    reason: str
    at_version: Optional[str]


class StaleDecline(ty.NamedTuple):
    """A declined model whose Zoo version has moved past the declined one."""

    name: str
    reason: str
    at_version: Optional[str]
    available_version: str


class MonaiModels:
    """Fetch, filter, generate and write MONAI-bundle pipeline specs."""

    def __init__(self, root: Path, whitelist_path: Path) -> None:
        self.root = Path(root)
        self.whitelist_path = Path(whitelist_path)

    def whitelist(self) -> List[WhitelistEntry]:
        data = yaml.safe_load(self.whitelist_path.read_text()) or {}
        models: Dict[str, dict] = data.get("models", {})
        entries: List[WhitelistEntry] = []
        for name, cfg in models.items():
            entries.append(
                WhitelistEntry(
                    name=name,
                    version=cfg.get("version"),
                    modality=cfg["modality"],
                    species=cfg["species"],
                    region=cfg["region"],
                    package_overrides={
                        str(k): str(v)
                        for k, v in (cfg.get("package_overrides") or {}).items()
                    },
                )
            )
        return entries

    def fetch_available(self) -> Dict[str, str]:
        """Return ``{bundle_name: latest_version}`` from the MONAI Model Zoo.

        ``monai.bundle.get_all_bundles_list()`` returns one
        ``(bundle_name, latest_version)`` tuple per bundle (already reduced to
        the latest version per bundle), so we build the mapping directly.
        """
        return {name: version for name, version in get_all_bundles_list()}

    def declined(self) -> List[DeclinedEntry]:
        """Models reviewed and deliberately not published.

        Sibling of ``models:`` in the whitelist file rather than nested within
        it: the two carry different fields (anatomy placement vs a reason) and
        are read independently.
        """
        data = yaml.safe_load(self.whitelist_path.read_text()) or {}
        declined: Dict[str, dict] = data.get("declined") or {}
        entries: List[DeclinedEntry] = []
        for name, cfg in declined.items():
            cfg = cfg or {}
            at_version = cfg.get("at_version")
            entries.append(
                DeclinedEntry(
                    name=name,
                    reason=cfg.get("reason", ""),
                    at_version=str(at_version) if at_version is not None else None,
                )
            )
        return entries

    def filter_whitelist(self, available: Dict[str, str]) -> List[WhitelistEntry]:
        """Keep whitelist entries present in ``available``; fill unpinned versions."""
        kept: List[WhitelistEntry] = []
        for entry in self.whitelist():
            if entry.name not in available:
                continue
            version = entry.version or available[entry.name]
            kept.append(entry._replace(version=version))
        return kept

    def candidates(self, available: Dict[str, str]) -> List[ty.Tuple[str, str]]:
        """Zoo bundles that are neither approved nor declined, as (name, version).

        Derived rather than stored, so the whitelist file only ever records
        human decisions and needs no edit when the Zoo changes.
        """
        known = {e.name for e in self.whitelist()} | {e.name for e in self.declined()}
        return sorted(
            (name, version)
            for name, version in available.items()
            if name not in known
        )

    def stale_declines(self, available: Dict[str, str]) -> List[StaleDecline]:
        """Declined models whose Zoo version differs from the one declined.

        An entry with no ``at_version`` is a decline for all versions and never
        goes stale.
        """
        stale: List[StaleDecline] = []
        for entry in self.declined():
            if entry.at_version is None or entry.name not in available:
                continue
            current = available[entry.name]
            if current != entry.at_version:
                stale.append(
                    StaleDecline(
                        name=entry.name,
                        reason=entry.reason,
                        at_version=entry.at_version,
                        available_version=current,
                    )
                )
        return sorted(stale)

    def withdrawn(self, available: Dict[str, str]) -> List[str]:
        """Approved models no longer present in the Zoo.

        ``filter_whitelist`` drops these silently, which would otherwise leave a
        spec in the tree building against a model that no longer exists.
        """
        return sorted(e.name for e in self.whitelist() if e.name not in available)

    def spec_path(self, entry: WhitelistEntry) -> Path:
        return (
            self.root
            / "specs"
            / "australian-imaging-service"
            / entry.modality
            / entry.species
            / entry.region
            / "monai"
            / f"{entry.name}.yaml"
        )

    def existing_version(self, entry: WhitelistEntry) -> Optional[str]:
        path = self.spec_path(entry)
        if not path.is_file():
            return None
        data = yaml.safe_load(path.read_text()) or {}
        version = data.get("version")
        return str(version) if version is not None else None

    def existing_spec(self, entry: WhitelistEntry) -> Optional[dict]:
        """The spec currently on disk for ``entry``, or None if there isn't one."""
        path = self.spec_path(entry)
        if not path.is_file():
            return None
        return yaml.safe_load(path.read_text()) or {}

    def is_changed(self, entry: WhitelistEntry, spec: dict) -> bool:
        """Whether a freshly generated ``spec`` differs from the one on disk.

        A generated spec is a function of three inputs -- the Zoo version, the
        model's whitelist entry, and the generator code -- so comparing the
        output covers all three. The previous check compared only the version
        recorded in the spec, which left whitelist and generator changes
        silently unapplied: correcting a pin, adding ``package_overrides`` and
        moving a model's ``region`` each produced no regeneration during #532
        and had to be forced by deleting the spec by hand (#495).

        Comparing output was originally rejected as costing a bundle download
        per model per run. Since #494 sync already downloads every bundle to
        read its metadata, so that cost is already being paid.
        """
        return self.existing_spec(entry) != spec

    def orphaned_specs(self, entries: List[WhitelistEntry]) -> List[Path]:
        """Specs for whitelisted models that sit somewhere other than their path.

        ``spec_path`` is derived from the entry's anatomy fields, so changing
        ``region`` (or ``modality``/``species``) makes the generator write to a
        new path and leave the old spec behind. The stale copy still builds, so
        it is worse than one that is merely out of date -- the Zoo would be
        serving two images for one model.

        Only models in ``entries`` are considered. A spec whose model has been
        removed from the whitelist entirely is a withdrawal, reported by
        ``withdrawn()`` for a human to act on, not something to delete here.
        """
        wanted = {self.spec_path(e) for e in entries}
        names = {e.name for e in entries}
        return [
            path
            for path in self.monai_specs()
            if path.stem in names and path not in wanted
        ]

    def resource_name(self, entry: WhitelistEntry) -> str:
        """Name of the build-time resource carrying the model's full bundle.

        Matches the sub-directory of ``--resources-dir`` that CI downloads the
        bundle into, which pipeline2app copies into the image.
        """
        return f"{entry.name}-bundle"

    def runtime_bundle_path(self, entry: WhitelistEntry) -> str:
        """Path the full bundle occupies *inside the built image*.

        Both the ``resources`` entry (where the bundle is unpacked to) and the
        command's inline task (where it reads the bundle from) point here, so
        the two cannot drift apart.
        """
        return f"{RUNTIME_BUNDLE_ROOT}/{entry.name}"

    @staticmethod
    def bundle_metadata(bundle_dir: Path) -> dict:
        """The bundle's parsed ``configs/metadata.json``, or ``{}`` if absent."""
        metadata_path = bundle_dir / "configs" / "metadata.json"
        if not metadata_path.is_file():
            return {}
        return json.loads(metadata_path.read_text()) or {}

    @staticmethod
    def required_packages(bundle_dir: Path) -> Dict[str, str]:
        """The bundle's own declared runtime requirements, as a pip mapping.

        Bundles record what they need to run in metadata.json's
        ``required_packages_version``. These are not optional extras: without
        them the bundle's own inference config fails to instantiate. The
        wholeBody_ct_segmentation image built cleanly and then died at
        inference with ``OptionalImportError: from ignite.engine import
        State``, because SupervisedEvaluator needs pytorch-ignite and nothing
        installed it.

        Versions are propagated exactly as the bundle pins them, since that is
        what the model was validated against. A pin that does not work in the
        image is overridden per-model via the whitelist's
        ``package_overrides``.
        """
        required = (
            MonaiModels.bundle_metadata(bundle_dir).get("required_packages_version")
            or {}
        )
        return {str(name): str(version) for name, version in required.items()}

    #: Words to keep upper-cased in a generated title; without these, "ct"
    #: becomes "Ct" rather than "CT".
    TITLE_ACRONYMS = {
        "ct", "mri", "mr", "pet", "spect", "us", "xray", "dwi", "3d", "2d",
    }

    @classmethod
    def title_for(cls, entry: WhitelistEntry, metadata: dict) -> str:
        """A human-readable title, from the bundle's own name.

        Most bundles already give a spaced, correctly-capitalised name (e.g.
        "Whole Body CT Segmentation"), which is used as-is -- re-splitting it
        would turn "CT" into "C T". Only an unspaced name (snake_case or
        CamelCase, or a fallback to the whitelist key) needs breaking up.
        """
        raw = str(metadata.get("name") or entry.name).strip()
        if " " in raw:
            return f"MONAI {raw}"
        words = re.sub(r"(?<!^)(?=[A-Z])", " ", raw.replace("_", " ")).split()
        return "MONAI " + " ".join(
            w.upper() if w.lower() in cls.TITLE_ACRONYMS else w.capitalize()
            for w in words
        )

    def generate_spec(self, entry: WhitelistEntry, bundle_dir: Path) -> dict:
        """Build a full pipeline2app XNAT spec dict for a model.

        Everything is either derived from the bundle (title, description,
        sources, sinks, required packages) or a MONAI-wide default (authors,
        base image, info_url, operates_on). The only per-model human input is
        in the whitelist: anatomy placement, an optional version pin, and
        ``package_overrides`` for a bundle pin that does not work in the image.

        The command declares its task inline (``type: monai``) pointing at the
        in-image bundle path, rather than referencing a generated Python class.
        pipeline2app >=0.22 defers resolution of a task it cannot import, and a
        command whose sources and sinks are already defined -- as they are here,
        derived from the bundle at generation time -- never needs the task
        resolved on the build host. So nothing reads the path until the image
        runs, by which point ``resources`` guarantees it exists.
        """
        metadata = self.bundle_metadata(bundle_dir)
        fragment = spec_fragment(bundle_dir)
        # The bundle's own pins first, then the whitelist's overrides.
        pip = self.required_packages(bundle_dir)
        pip.update(entry.package_overrides)
        pip["pydra-compose-monai"] = PYDRA_COMPOSE_MONAI_REQ

        # Rewrite sink paths from bundle metadata paths to frametree store paths.
        sinks = {}
        for out_name, sink in fragment["sinks"].items():
            sink = dict(sink)
            sink["path"] = f"monai/{entry.name}/{out_name}"
            sinks[out_name] = sink

        command = {
            "task": {
                "type": "monai",
                "bundle": self.runtime_bundle_path(entry),
            },
            "operates_on": MONAI_OPERATES_ON,
            "sources": fragment["sources"],
            "sinks": sinks,
            "parameters": fragment["parameters"],
        }

        # ``commands`` is a mapping keyed by command name, matching the
        # hand-written specs. pipeline2app accepts either form (its
        # ObjectListConverter takes the key as the command name), but the
        # release workflow reads command names via ``yq '.commands | keys'``,
        # which only works on a mapping.
        spec = {
            "title": self.title_for(entry, metadata),
            "authors": MONAI_AUTHORS,
            "docs": {
                "info_url": MONAI_INFO_URL,
                "description": str(
                    metadata.get("description")
                    or f"MONAI Model Zoo bundle '{entry.name}', wrapped as a Pydra "
                    "task and packaged for the Australian Imaging Service."
                ),
            },
            "base_image": {
                "name": MONAI_BASE_IMAGE,
                "tag": MONAI_BASE_IMAGE_TAG,
                "package_manager": "apt",
            },
            "packages": {"pip": pip},
            "name": entry.name,
            "version": entry.version,
            # The full bundle (weights included) is delivered at build time and
            # unpacked to the path the command's task points at. ``url`` is a
            # default that ``--resources-dir``/``--resource`` override, so CI
            # can supply a locally fetched bundle instead -- which it does,
            # because the Model Zoo no longer publishes bundle archives (see
            # #507): NGC's archive endpoint 404s and Hugging Face serves the
            # files individually, so there is no URL to point at today.
            "resources": {
                self.resource_name(entry): {
                    "path": self.runtime_bundle_path(entry),
                },
            },
            "commands": {entry.name: command},
        }
        return spec

    def write_spec(self, entry: WhitelistEntry, spec: dict) -> Path:
        path = self.spec_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False))
        return path

    def sync(
        self, download_bundle: Callable[[WhitelistEntry], Path]
    ) -> ty.Tuple[List[Path], List[Path]]:
        """Full pipeline: fetch → filter → generate → compare → write.

        For each whitelisted model, download the bundle, read its metadata to
        derive the command's sources and sinks, and generate the spec. The spec
        is written only if it differs from what is already on disk, so a run
        that changes nothing touches no files and produces no commit.

        Generating before comparing, rather than gating on the version first, is
        what makes whitelist and generator changes visible to the comparison
        (#495). It costs nothing extra: since #494 the bundle is downloaded for
        its metadata either way.

        The bundle is read here and then discarded -- nothing from it is
        committed. Deriving sources/sinks at generation time is what lets the
        spec stand alone, so the build host never needs the bundle or the task.

        ``download_bundle`` maps an entry to a local bundle root directory
        (injected so tests need no network; production passes ``self._download``).

        Returns ``(written, removed)`` -- the specs written, and the stale specs
        deleted after a model moved in the tree.
        """
        available = self.fetch_available()
        whitelisted = self.filter_whitelist(available)

        written: List[Path] = []
        for entry in whitelisted:
            bundle_dir = download_bundle(entry)
            spec = self.generate_spec(entry, bundle_dir)
            if self.is_changed(entry, spec):
                written.append(self.write_spec(entry, spec))

        # After writing, so a model that moved has its spec at the new path
        # before the old one goes -- never a window with neither.
        removed: List[Path] = []
        for path in self.orphaned_specs(whitelisted):
            path.unlink()
            removed.append(path)
            self._prune_empty_dirs(path.parent)
        return written, removed

    def _prune_empty_dirs(self, directory: Path) -> None:
        """Remove ``directory`` and empty ancestors, stopping at the specs root.

        A relocated model otherwise leaves its old ``<region>/monai/`` behind as
        an empty directory. Git does not track those, but they are noise in a
        working tree and make the anatomy layout misleading to read.
        """
        specs_root = self.root / "specs" / "australian-imaging-service"
        while (
            directory != specs_root
            and specs_root in directory.parents
            and directory.is_dir()
            and not any(directory.iterdir())
        ):
            directory.rmdir()
            directory = directory.parent

    def _download(self, entry: WhitelistEntry) -> Path:
        """Download a bundle from the Model Zoo into ``<root>/.monai-bundles``."""
        return self._download_bundle(entry.name, entry.version, self.root / ".monai-bundles")

    @staticmethod
    def _download_bundle(name: str, version: Optional[str], dest: Path) -> Path:
        """Download ``name`` at ``version`` into ``dest``; return the bundle root."""
        from monai.bundle import download

        dest.mkdir(parents=True, exist_ok=True)
        download(name=name, version=version, bundle_dir=str(dest))
        return dest / name

    def monai_specs(self) -> List[Path]:
        """Every generated MONAI spec on disk, i.e. those under a ``monai`` dir."""
        specs_root = self.root / "specs" / "australian-imaging-service"
        if not specs_root.is_dir():
            return []
        return sorted(specs_root.glob("**/monai/*.yaml"))

    def triage_report(self, available: Dict[str, str]) -> ty.Tuple[bool, str]:
        """Markdown summary of everything needing a human decision.

        Returns ``(needs_attention, body)``. ``needs_attention`` is False when
        there is nothing to triage, so the caller can skip opening an issue.
        """
        candidates = self.candidates(available)
        stale = self.stale_declines(available)
        withdrawn = self.withdrawn(available)

        lines: List[str] = []
        if candidates:
            lines.append(f"### New bundles to triage ({len(candidates)})\n")
            lines.append(
                "Add to `models:` with `modality`/`species`/`region` to publish, "
                "or to `declined:` with a reason. Paste-ready:\n"
            )
            lines.append("```yaml")
            for name, version in candidates:
                lines.append(f"  {name}:")
                lines.append(f"    version: null  # latest is {version}")
                lines.append("    modality:  # ct | mri | ...")
                lines.append("    species:   # human | ...")
                lines.append("    region:    # abdomen | neuro | ...")
            lines.append("```\n")

        if stale:
            lines.append(f"### Declined models with a newer version ({len(stale)})\n")
            for entry in stale:
                lines.append(
                    f"- **{entry.name}** {entry.at_version} → {entry.available_version}"
                    f" — _declined: {entry.reason or 'no reason recorded'}_"
                )
            lines.append(
                "\nStill not wanted? Bump `at_version` to re-decline at the new "
                "version.\n"
            )

        if withdrawn:
            lines.append(f"### Approved models missing from the Zoo ({len(withdrawn)})\n")
            for name in withdrawn:
                lines.append(f"- **{name}** — its spec will build against a model "
                             "that is no longer published")
            lines.append("")

        if not lines:
            return False, "No MONAI models need triage."

        lines.append("---")
        lines.append(
            "Generated by `scripts/monai_specs.py triage`. Edit "
            "`scripts/monai_whitelist.yaml` to record a decision."
        )
        return True, "\n".join(lines)

    def fetch_resources(
        self,
        resources_dir: Path,
        download: Optional[Callable[[str, Optional[str], Path], Path]] = None,
    ) -> List[Path]:
        """Stage each MONAI spec's full bundle into ``resources_dir``.

        The generated specs declare a ``resources`` entry for their bundle but
        the weights are deliberately not committed, so a build fails until this
        has run. Reads the specs on disk rather than the whitelist, so what is
        staged matches exactly what will be built, and pins the download to the
        version recorded in the spec so the image cannot drift from it.

        Returns the staged resource directories.
        """
        import shutil
        import tempfile

        if download is None:
            download = self._download_bundle

        staged: List[Path] = []
        for spec_path in self.monai_specs():
            spec = yaml.safe_load(spec_path.read_text()) or {}
            resources = spec.get("resources") or {}
            if not resources:
                continue
            name = spec["name"]
            version = spec.get("version")
            for resource_name in resources:
                target = resources_dir / resource_name
                with tempfile.TemporaryDirectory() as tmp:
                    bundle = download(name, version, Path(tmp))
                    if target.exists():
                        shutil.rmtree(target)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # copytree rather than move: the temp dir is removed on exit
                    shutil.copytree(bundle, target)
                staged.append(target)
        return staged


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Sync MONAI Model Zoo specs")
    parser.add_argument(
        "command",
        choices=["sync", "fetch-resources", "triage"],
        help=(
            "sync: regenerate specs from the Model Zoo. "
            "fetch-resources: download the full bundles (weights included) "
            "that the generated specs declare, ready for --resources-dir. "
            "Required before building, as weights are not committed. "
            "triage: report Zoo bundles awaiting a publish/decline decision."
        ),
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).parent.parent)
    parser.add_argument(
        "--whitelist", type=Path,
        default=Path(__file__).parent / "monai_whitelist.yaml",
    )
    parser.add_argument(
        "--resources-dir", type=Path, default=None,
        help="destination for fetch-resources (default: <root>/resources)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="write the triage report here instead of stdout",
    )
    args = parser.parse_args(argv)

    mm = MonaiModels(root=args.root, whitelist_path=args.whitelist)

    if args.command == "triage":
        needs_attention, body = mm.triage_report(mm.fetch_available())
        if args.output:
            args.output.write_text(body)
        else:
            print(body)
        # exit 0 either way: nothing to triage is a normal outcome, not a failure.
        # The workflow reads NEEDS_TRIAGE to decide whether to open an issue.
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"needs-triage={'true' if needs_attention else 'false'}\n")
        return 0

    if args.command == "fetch-resources":
        resources_dir = args.resources_dir or (args.root / "resources")
        staged = mm.fetch_resources(resources_dir)
        for path in staged:
            print(f"staged {path}")
        if not staged:
            print("no MONAI specs declaring bundle resources found")
        return 0

    written, removed = mm.sync(download_bundle=mm._download)
    for path in written:
        print(f"wrote {path}")
    for path in removed:
        print(f"removed {path} (model moved in the tree)")
    if not written and not removed:
        print("all specs up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
