"""Generate pipeline2app XNAT specs from whitelisted MONAI Model Zoo bundles."""
import re
import typing as ty
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml
from monai.bundle import get_all_bundles_list
from pydra.compose.monai import spec_fragment

PACKAGE = "australianimagingservice"
OVERLAYS_DIR = Path(__file__).parent / "overlays"

#: Download-provenance artefacts to strip when vendoring a fetched bundle.
VENDOR_EXCLUDE = (".cache", ".gitattributes", ".git", ".huggingface")

#: Bundle entries committed beside the generated module. Only ``configs`` is
#: functionally required — ``parse_monai_spec`` reads ``configs/metadata.json``
#: and nothing else — but the licence and docs are small and make a synced
#: bundle reviewable. Model weights are deliberately absent: they are large,
#: re-downloadable, and already versioned in the Model Zoo, so they reach the
#: image via ``resources`` instead (see notes/monai-weights-plan.md).
VENDOR_INCLUDE = ("configs", "docs", "LICENSE")

#: Directory inside the built image that model bundles are copied into.
RUNTIME_BUNDLE_ROOT = "/monai-bundles"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive merge; ``override`` wins on scalar conflicts."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class WhitelistEntry(ty.NamedTuple):
    name: str
    version: Optional[str]
    modality: str
    species: str
    region: str


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

    def filter_whitelist(self, available: Dict[str, str]) -> List[WhitelistEntry]:
        """Keep whitelist entries present in ``available``; fill unpinned versions."""
        kept: List[WhitelistEntry] = []
        for entry in self.whitelist():
            if entry.name not in available:
                continue
            version = entry.version or available[entry.name]
            kept.append(entry._replace(version=version))
        return kept

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

    def detect_changes(self, entries: List[WhitelistEntry]) -> List[WhitelistEntry]:
        """Return entries with no spec yet, or whose version differs from the spec."""
        changed: List[WhitelistEntry] = []
        for entry in entries:
            if self.existing_version(entry) != entry.version:
                changed.append(entry)
        return changed

    def class_name(self, entry: WhitelistEntry) -> str:
        """CamelCase Python class name derived from the model name."""
        words = re.split(r"[^a-zA-Z0-9]+", entry.name)
        return "".join(w.capitalize() for w in words if w)

    def _module_parts(self, entry: WhitelistEntry) -> List[str]:
        return [PACKAGE, entry.modality, entry.species, entry.region, "monai", entry.name]

    def task_module_path(self, entry: WhitelistEntry) -> Path:
        parts = self._module_parts(entry)
        return self.root.joinpath("src", *parts).with_suffix(".py")

    def task_module_ref(self, entry: WhitelistEntry) -> str:
        dotted = ".".join(self._module_parts(entry))
        return f"{dotted}:{self.class_name(entry)}"

    def bundle_vendor_dir(self, entry: WhitelistEntry) -> Path:
        """Directory where the model's bundle is vendored, beside its module."""
        return self.task_module_path(entry).parent / f"{entry.name}_bundle"

    def resource_name(self, entry: WhitelistEntry) -> str:
        """Name of the build-time resource carrying the model's full bundle.

        Matches the sub-directory of ``--resources-dir`` that CI downloads the
        bundle into, which pipeline2app copies into the image.
        """
        return f"{entry.name}-bundle"

    def runtime_bundle_path(self, entry: WhitelistEntry) -> str:
        """Path the full bundle occupies *inside the built image*.

        The committed bundle is configs-only, so the module-relative path baked
        into the generated class is valid only on the build host. At runtime the
        task is redirected here via ``configuration.bundle``.
        """
        return f"{RUNTIME_BUNDLE_ROOT}/{entry.name}"

    def write_task_module(self, entry: WhitelistEntry) -> Path:
        """Generate a committed per-model task module (define()-built class).

        The class builds itself from the bundle vendored beside this module
        (``<model>_bundle/``), using a module-relative path so it resolves
        identically on the build host (CI / --generate-only) and inside the
        built image. pipeline2app imports and introspects this class eagerly
        at spec-load / Dockerfile-generation time, so the bundle must be
        present next to the module — which is why sync() vendors it (Task 6).
        """
        path = self.task_module_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure every generated package directory is importable. ``src`` is the
        # import root rather than a package, so stop before adding one there.
        src_root = self.root / "src"
        pkg_dirs = list(path.parent.relative_to(src_root).parents)[:-1]
        pkg_dirs = [src_root / p for p in pkg_dirs]
        pkg_dirs.append(path.parent)
        for d in pkg_dirs:
            init = d / "__init__.py"
            if not init.exists():
                init.write_text("")

        cls = self.class_name(entry)
        bundle_dirname = f"{entry.name}_bundle"
        path.write_text(
            '"""Auto-generated MONAI task module. Do not edit by hand."""\n'
            "from pathlib import Path\n"
            "from pydra.compose import monai\n\n"
            f'BUNDLE_PATH = Path(__file__).parent / "{bundle_dirname}"\n\n'
            f'{cls} = monai.define(BUNDLE_PATH, name="{cls}")\n'
        )
        return path

    def overlay_path(self, entry: WhitelistEntry) -> Path:
        return OVERLAYS_DIR / f"{entry.name}.yaml"

    def generate_spec(self, entry: WhitelistEntry, bundle_dir: Path) -> dict:
        """Build a full pipeline2app XNAT spec dict for a model.

        Combines the bundle-derived field fragment with the hand-authored
        overlay (title/authors/docs/base_image/packages/operates_on).
        command.task references the committed generated per-model class
        (see write_task_module); the bundle is baked into that class, so
        the command needs no configuration.
        """
        overlay = yaml.safe_load(self.overlay_path(entry).read_text()) or {}
        fragment = spec_fragment(bundle_dir)

        # Rewrite sink paths from bundle metadata paths to frametree store paths.
        sinks = {}
        for out_name, sink in fragment["sinks"].items():
            sink = dict(sink)
            sink["path"] = f"monai/{entry.name}/{out_name}"
            sinks[out_name] = sink

        operates_on = overlay.get("operates_on", "session")
        # The generated class bakes in a module-relative bundle path, which is
        # configs-only and therefore sufficient for build-host introspection but
        # not for inference. Redirect the task to the full bundle delivered as a
        # resource. Setting it here (rather than as a parameter) also keeps it
        # out of the user-facing UI: pipeline2app excludes configuration keys
        # from both sources and parameters.
        command = {
            "task": self.task_module_ref(entry),
            "operates_on": operates_on,
            "configuration": {"bundle": self.runtime_bundle_path(entry)},
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
            "name": entry.name,
            "version": entry.version,
            # Declares that the full bundle (weights included) must be supplied
            # at build time under this name in ``--resources-dir``, and copied
            # to the path the command's ``configuration.bundle`` points at.
            "resources": {self.resource_name(entry): self.runtime_bundle_path(entry)},
            "commands": {entry.name: command},
        }
        # overlay supplies title/authors/docs/base_image/packages; it must not
        # override name/version/commands, so merge overlay UNDER the core spec.
        merged = _deep_merge(overlay, spec)
        merged.pop("operates_on", None)  # consumed into the command
        return merged

    def write_spec(self, entry: WhitelistEntry, spec: dict) -> Path:
        path = self.spec_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False))
        return path

    def vendor_bundle(self, entry: WhitelistEntry, bundle_dir: Path) -> Path:
        """Copy the introspectable part of a downloaded bundle beside its module.

        The generated task module reads the bundle via a module-relative path
        (``Path(__file__).parent / "<model>_bundle"``), so what is committed
        there must be enough for pipeline2app to introspect the class at
        spec-load time — which is ``configs/metadata.json`` and nothing more.
        Idempotent: replaces any existing vendored copy.

        Only ``VENDOR_INCLUDE`` entries are copied — an allowlist rather than
        an exclude-list, so a new large directory appearing in a future bundle
        cannot silently end up committed. In particular model weights are not
        vendored; they are delivered to the image as a resource at build time
        and the task is pointed at them via ``configuration.bundle``.

        Download-provenance artefacts left behind by the fetch (the Hugging
        Face ``.cache`` tree, ``.gitattributes``) are excluded by the same
        allowlist.
        """
        import shutil

        dest = self.bundle_vendor_dir(entry)
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for name in VENDOR_INCLUDE:
            source = bundle_dir / name
            if not source.exists():
                continue
            if source.is_dir():
                shutil.copytree(
                    source,
                    dest / name,
                    ignore=shutil.ignore_patterns(*VENDOR_EXCLUDE),
                )
            else:
                shutil.copy2(source, dest / name)
        return dest

    def sync(self, download_bundle: Callable[[WhitelistEntry], Path]) -> List[Path]:
        """Full pipeline: fetch → filter → detect → vendor + codegen + generate → write.

        For each changed model: download the bundle, vendor it beside the
        generated module, write the committed per-model task module, generate
        the spec (which references that module + vendored bundle), and write
        the spec. Returns the spec paths written.

        ``download_bundle`` maps an entry to a local bundle root directory
        (injected so tests need no network; production passes ``self._download``).
        """
        available = self.fetch_available()
        whitelisted = self.filter_whitelist(available)
        changed = self.detect_changes(whitelisted)
        written: List[Path] = []
        for entry in changed:
            bundle_dir = download_bundle(entry)
            self.write_task_module(entry)
            self.vendor_bundle(entry, bundle_dir)
            spec = self.generate_spec(entry, bundle_dir)
            written.append(self.write_spec(entry, spec))
        return written

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
        choices=["sync", "fetch-resources"],
        help=(
            "sync: regenerate specs/task modules from the Model Zoo. "
            "fetch-resources: download the full bundles (weights included) "
            "that the generated specs declare, ready for --resources-dir. "
            "Required before building, as weights are not committed."
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
    args = parser.parse_args(argv)

    mm = MonaiModels(root=args.root, whitelist_path=args.whitelist)

    if args.command == "fetch-resources":
        resources_dir = args.resources_dir or (args.root / "resources")
        staged = mm.fetch_resources(resources_dir)
        for path in staged:
            print(f"staged {path}")
        if not staged:
            print("no MONAI specs declaring bundle resources found")
        return 0

    written = mm.sync(download_bundle=mm._download)
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
