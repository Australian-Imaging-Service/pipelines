"""Generate pipeline2app XNAT specs from whitelisted MONAI Model Zoo bundles."""
import typing as ty
from pathlib import Path
from typing import Dict, List, Optional

import yaml


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
