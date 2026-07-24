"""Generate pipeline2app XNAT specs from whitelisted MONAI Model Zoo bundles."""
import re
import typing as ty
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from monai.bundle import get_all_bundles_list

BAKED_BUNDLE_ROOT = "/opt/bundles"
PACKAGE = "australianimagingservice"


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

    def write_task_module(self, entry: WhitelistEntry) -> Path:
        """Generate a committed per-model task module (define()-built class).

        The class bakes in the in-image bundle path so command.task can
        reference it directly with no runtime configuration.
        """
        path = self.task_module_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure every generated package directory from the model's package
        # dir up to (and including) <root>/src/ is importable.
        src_root = self.root / "src"
        pkg_dir = path.parent
        package_dirs = [pkg_dir]
        while pkg_dir != src_root:
            pkg_dir = pkg_dir.parent
            package_dirs.append(pkg_dir)
        for pkg_dir in package_dirs:
            init = pkg_dir / "__init__.py"
            if not init.exists():
                init.write_text("")

        bundle_path = f"{BAKED_BUNDLE_ROOT}/{entry.name}"
        cls = self.class_name(entry)
        path.write_text(
            '"""Auto-generated MONAI task module. Do not edit by hand."""\n'
            "from pydra.compose import monai\n\n"
            f'BUNDLE_PATH = "{bundle_path}"\n\n'
            f'{cls} = monai.define(BUNDLE_PATH, name="{cls}")\n'
        )
        return path
