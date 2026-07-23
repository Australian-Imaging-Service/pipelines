# MONAI Model Registry + Spec Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `MonaiModels` generator (in `scripts/`) that fetches MONAI Model Zoo bundles, filters by a whitelist, detects version changes, generates pipeline2app XNAT specs (using `pydra-compose-monai`), and writes them into a `monai/` spec namespace — driven by a scheduled GitHub Action that opens a PR.

**Architecture:** A single orchestrator class `MonaiModels` with focused, independently-testable methods (fetch → filter → detect → generate → write → sync). MONAI→fileformats field serialization is delegated to `pydra_compose_monai.spec_fragment`; catalog/build metadata comes from a hand-authored per-model overlay deep-merged with the fragment. Generated specs are `pydra2app`/`pipeline2app` 2.x `XnatApp` specs.

**Tech Stack:** Python ≥3.8, PyYAML, monai.bundle, pydra-compose-monai (from PyPI), pydra2app/pydra2app-xnat, pytest. Work lands on the existing `monai-test` branch.

## Global Constraints

- Depends on **`pydra-compose-monai`** providing `spec_fragment()` and `BundleTask` (Plan `2026-07-10-monai-spec-fragment.md` in the pydra-compose-monai repo). That must ship first; add `pydra-compose-monai` to the `test` deps of `pyproject.toml`.
- `requires-python >=3.8` (repo target) — this repo targets py38, so **use `Optional[...]`/`Dict[...]` typing imports, NOT `X | Y` syntax**, in `scripts/`.
- Generated specs target the **pydra2app/pipeline2app 2.x schema** consumed by `XnatApp.load(...)` (see `tests/test_monai.py`): top-level `commands:` is a **list**; per-command keys `task`, `operates_on`, `sources`, `sinks`, `parameters`, `configuration`.
- `command.task` = `"pydra.compose.monai:BundleTask"`; bundle fixed via `configuration: {bundle: /opt/bundles/<model>}`.
- Datatypes are fileformats MIME-like strings.
- Generator lives in top-level `scripts/` (already excluded from mypy/package in `pyproject.toml`). Tests live in `tests/`.
- Generated specs written under `specs/australian-imaging-service/<modality>/<species>/<region>/monai/<model>.yaml`.
- The Action opens a **PR**, never pushes to a protected branch directly.

## File Structure

- `scripts/monai_specs.py` — `MonaiModels` class + a `__main__` entry point (`python -m scripts.monai_specs sync`).
- `scripts/monai_whitelist.yaml` — control surface: models, optional version pins, anatomy placement.
- `scripts/overlays/<model>.yaml` — per-model hand-authored catalog/build metadata.
- `tests/test_monai_specs.py` — unit tests for each method against synthetic bundles.
- `.github/workflows/monai-sync.yml` — scheduled sync Action.

---

### Task 1: Whitelist loader + model placement resolution

**Files:**
- Create: `scripts/monai_specs.py`
- Create: `scripts/monai_whitelist.yaml`
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Produces:
  ```python
  class WhitelistEntry(ty.NamedTuple):
      name: str
      version: Optional[str]          # pin, or None for latest
      modality: str
      species: str
      region: str
  class MonaiModels:
      def __init__(self, root: Path, whitelist_path: Path): ...
      def whitelist(self) -> List[WhitelistEntry]: ...
      def spec_path(self, entry: WhitelistEntry) -> Path: ...  # <root>/specs/australian-imaging-service/<modality>/<species>/<region>/monai/<name>.yaml
  ```

- [ ] **Step 1: Write the whitelist fixture file**

Create `scripts/monai_whitelist.yaml`:

```yaml
# MONAI Model Zoo models to publish as AIS pipelines.
# Each entry: version pin (null = latest) and anatomy placement in specs/ tree.
models:
  spleen_ct_segmentation:
    version: null
    modality: ct
    species: human
    region: abdomen
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_monai_specs.py`:

```python
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts.monai_specs import MonaiModels, WhitelistEntry  # noqa: E402


@pytest.fixture
def whitelist_file(tmp_path: Path) -> Path:
    p = tmp_path / "monai_whitelist.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "spleen_ct_segmentation": {
                        "version": None,
                        "modality": "ct",
                        "species": "human",
                        "region": "abdomen",
                    }
                }
            }
        )
    )
    return p


def test_whitelist_parses_entries(tmp_path: Path, whitelist_file: Path):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entries = mm.whitelist()
    assert len(entries) == 1
    e = entries[0]
    assert e == WhitelistEntry("spleen_ct_segmentation", None, "ct", "human", "abdomen")


def test_spec_path_follows_monai_namespace(tmp_path: Path, whitelist_file: Path):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    expected = (
        tmp_path
        / "specs"
        / "australian-imaging-service"
        / "ct"
        / "human"
        / "abdomen"
        / "monai"
        / "spleen_ct_segmentation.yaml"
    )
    assert mm.spec_path(entry) == expected
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/gbro5457/code/pipelines && .venv/bin/pytest tests/test_monai_specs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.monai_specs'`

- [ ] **Step 4: Write minimal implementation**

Create `scripts/monai_specs.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_monai_specs.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/monai_specs.py scripts/monai_whitelist.yaml tests/test_monai_specs.py
git commit -m "feat(monai): whitelist loader and spec-path resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Fetch available models + versions from the Model Zoo

**Files:**
- Modify: `scripts/monai_specs.py`
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Consumes: `monai.bundle.get_all_bundles_list()`, `monai.bundle.get_bundle_versions(name)`.
- Produces:
  ```python
  def fetch_available(self) -> Dict[str, str]:  # {bundle_name: latest_version}
  def filter_whitelist(self, available: Dict[str, str]) -> List[WhitelistEntry]:
      # entries whose name is in `available`; version pin kept if set else latest
  ```

- [ ] **Step 1: Write the failing test** (monkeypatch the network calls)

Append to `tests/test_monai_specs.py`:

```python
def test_filter_whitelist_keeps_available_and_fills_latest(
    tmp_path: Path, whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    available = {"spleen_ct_segmentation": "0.5.3", "other_model": "1.0.0"}
    kept = mm.filter_whitelist(available)
    assert len(kept) == 1
    assert kept[0].name == "spleen_ct_segmentation"
    assert kept[0].version == "0.5.3"  # pin was None -> latest filled in


def test_filter_whitelist_respects_pin(tmp_path: Path):
    wl = tmp_path / "wl.yaml"
    wl.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "spleen_ct_segmentation": {
                        "version": "0.5.0",
                        "modality": "ct",
                        "species": "human",
                        "region": "abdomen",
                    }
                }
            }
        )
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=wl)
    kept = mm.filter_whitelist({"spleen_ct_segmentation": "0.5.3"})
    assert kept[0].version == "0.5.0"


def test_fetch_available_uses_monai_api(tmp_path, whitelist_file, monkeypatch):
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "get_all_bundles_list",
        lambda **kw: [("spleen_ct_segmentation", "0.5.3")],
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    available = mm.fetch_available()
    assert available["spleen_ct_segmentation"] == "0.5.3"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "filter_whitelist or fetch_available" -v`
Expected: FAIL (`AttributeError`/`ImportError` — names not defined)

- [ ] **Step 3: Write minimal implementation**

At the top of `scripts/monai_specs.py`, add the import (module-level so tests can monkeypatch it):

```python
from monai.bundle import get_all_bundles_list
```

Add methods to `MonaiModels`:

```python
    def fetch_available(self) -> Dict[str, str]:
        """Return ``{bundle_name: latest_version}`` from the MONAI Model Zoo.

        ``get_all_bundles_list`` returns ``(name, version)`` pairs newest-first;
        the first occurrence of each name is its latest version.
        """
        available: Dict[str, str] = {}
        for name, version in get_all_bundles_list():
            available.setdefault(name, version)
        return available

    def filter_whitelist(self, available: Dict[str, str]) -> List[WhitelistEntry]:
        """Keep whitelist entries present in ``available``; fill unpinned versions."""
        kept: List[WhitelistEntry] = []
        for entry in self.whitelist():
            if entry.name not in available:
                continue
            version = entry.version or available[entry.name]
            kept.append(entry._replace(version=version))
        return kept
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "filter_whitelist or fetch_available" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/monai_specs.py tests/test_monai_specs.py
git commit -m "feat(monai): fetch Model Zoo listing and filter by whitelist

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Detect version changes vs existing specs

**Files:**
- Modify: `scripts/monai_specs.py`
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Consumes: `self.spec_path(entry)` (Task 1); existing spec YAML with a top-level `version:` string.
- Produces:
  ```python
  def existing_version(self, entry: WhitelistEntry) -> Optional[str]:  # None if no spec
  def detect_changes(self, entries: List[WhitelistEntry]) -> List[WhitelistEntry]:
      # entries whose resolved version != existing spec version (new or updated)
  ```

- [ ] **Step 1: Write the failing test**

Append to `tests/test_monai_specs.py`:

```python
def _write_spec(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"name": path.stem, "version": version}))


def test_existing_version_none_when_missing(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    assert mm.existing_version(entry) is None


def test_detect_changes_flags_new_and_updated(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")

    # No spec yet -> flagged as changed (new)
    assert mm.detect_changes([entry]) == [entry]

    # Spec at same version -> not flagged
    _write_spec(mm.spec_path(entry), "0.5.3")
    assert mm.detect_changes([entry]) == []

    # Spec at older version -> flagged (updated)
    _write_spec(mm.spec_path(entry), "0.5.0")
    assert mm.detect_changes([entry]) == [entry]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "existing_version or detect_changes" -v`
Expected: FAIL (`AttributeError: 'MonaiModels' object has no attribute ...`)

- [ ] **Step 3: Write minimal implementation**

Add to `MonaiModels`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "existing_version or detect_changes" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/monai_specs.py tests/test_monai_specs.py
git commit -m "feat(monai): detect new/updated models vs existing specs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Generate a full spec (fragment + overlay merge)

**Files:**
- Modify: `scripts/monai_specs.py`
- Create: `scripts/overlays/spleen_ct_segmentation.yaml`
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Consumes: `pydra_compose_monai.spec_fragment(bundle_dir) -> {"sources","sinks","parameters"}` (Plan A, Task 1); a per-model overlay YAML.
- Produces:
  ```python
  def overlay_path(self, entry: WhitelistEntry) -> Path:      # scripts/overlays/<name>.yaml
  def generate_spec(self, entry: WhitelistEntry, bundle_dir: Path) -> dict:
      # full XnatApp 2.x spec dict
  ```
- The merge rewrites each sink's `path` from the bundle metadata path (`network_data_format/outputs/<x>`) to the frametree store path `monai/<name>/<x>`.

- [ ] **Step 1: Write the overlay fixture**

Create `scripts/overlays/spleen_ct_segmentation.yaml`:

```yaml
title: MONAI Spleen CT Segmentation
authors:
  - name: MONAI Consortium
    email: monai.contact@gmail.com
docs:
  info_url: https://monai.io/model-zoo.html
base_image:
  name: projectmonai/monai
  tag: latest
  package_manager: apt
packages:
  pip:
    pydra-compose-monai:
operates_on: session
```

- [ ] **Step 2: Write the failing test** (stub `spec_fragment` via monkeypatch — no real bundle needed)

Append to `tests/test_monai_specs.py`:

```python
@pytest.fixture
def overlay_dir(tmp_path: Path, monkeypatch) -> Path:
    import scripts.monai_specs as ms

    d = tmp_path / "overlays"
    d.mkdir()
    (d / "spleen_ct_segmentation.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "MONAI Spleen CT Segmentation",
                "authors": [{"name": "MONAI Consortium", "email": "x@example.org"}],
                "docs": {"info_url": "https://monai.io/model-zoo.html"},
                "base_image": {"name": "projectmonai/monai", "tag": "latest",
                               "package_manager": "apt"},
                "packages": {"pip": {"pydra-compose-monai": None}},
                "operates_on": "session",
            }
        )
    )
    monkeypatch.setattr(ms, "OVERLAYS_DIR", d)
    return d


def test_generate_spec_shape(tmp_path, whitelist_file, overlay_dir, monkeypatch):
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {
            "sources": {"image": {"datatype": "medimage/nifti-gz-x",
                                  "help": "in", "path": "network_data_format/inputs/image"}},
            "sinks": {"pred": {"datatype": "medimage/nifti-gz-x",
                               "help": "out", "path": "network_data_format/outputs/pred"}},
            "parameters": {},
        },
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    spec = mm.generate_spec(entry, bundle_dir=tmp_path / "bundle")

    assert spec["title"] == "MONAI Spleen CT Segmentation"
    assert spec["version"] == "0.5.3"
    assert isinstance(spec["commands"], list) and len(spec["commands"]) == 1
    cmd = spec["commands"][0]
    assert cmd["task"] == "pydra.compose.monai:BundleTask"
    assert cmd["configuration"]["bundle"] == "/opt/bundles/spleen_ct_segmentation"
    assert cmd["operates_on"] == "session"
    assert cmd["sources"]["image"]["datatype"] == "medimage/nifti-gz-x"
    # sink path rewritten to the frametree store path
    assert cmd["sinks"]["pred"]["path"] == "monai/spleen_ct_segmentation/pred"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k generate_spec -v`
Expected: FAIL (`AttributeError`/`ImportError` — `spec_fragment`/`OVERLAYS_DIR`/`generate_spec` not defined)

- [ ] **Step 4: Write minimal implementation**

At module top of `scripts/monai_specs.py` add:

```python
from pydra.compose.monai import spec_fragment

OVERLAYS_DIR = Path(__file__).parent / "overlays"
BAKED_BUNDLE_ROOT = "/opt/bundles"
TASK_REF = "pydra.compose.monai:BundleTask"
```

Add a module-level deep-merge helper and the methods:

```python
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive merge; ``override`` wins on scalar conflicts."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

```python
    def overlay_path(self, entry: WhitelistEntry) -> Path:
        return OVERLAYS_DIR / f"{entry.name}.yaml"

    def generate_spec(self, entry: WhitelistEntry, bundle_dir: Path) -> dict:
        """Build a full pipeline2app XNAT spec dict for a model.

        Combines the bundle-derived field fragment with the hand-authored
        overlay (title/authors/docs/base_image/packages/operates_on).
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
        command = {
            "task": TASK_REF,
            "operates_on": operates_on,
            "configuration": {"bundle": f"{BAKED_BUNDLE_ROOT}/{entry.name}"},
            "sources": fragment["sources"],
            "sinks": sinks,
            "parameters": fragment["parameters"],
        }

        spec = {
            "name": entry.name,
            "version": entry.version,
            "commands": [command],
        }
        # overlay supplies title/authors/docs/base_image/packages; it must not
        # override name/version/commands, so merge overlay UNDER the core spec.
        merged = _deep_merge(overlay, spec)
        merged.pop("operates_on", None)  # consumed into the command
        return merged
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k generate_spec -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/monai_specs.py scripts/overlays/spleen_ct_segmentation.yaml tests/test_monai_specs.py
git commit -m "feat(monai): generate full XNAT spec from bundle fragment + overlay

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Write spec to disk + `sync()` orchestration + CLI entry point

**Files:**
- Modify: `scripts/monai_specs.py`
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Consumes: all prior methods; `monai.bundle.download` to fetch a bundle for generation.
- Produces:
  ```python
  def write_spec(self, entry: WhitelistEntry, spec: dict) -> Path:   # writes YAML, returns path
  def sync(self, download_bundle: Callable[[WhitelistEntry], Path]) -> List[Path]:
      # fetch -> filter -> detect_changes -> for each: download, generate, write
  # module: def main(argv=None) -> int   (argparse: subcommand "sync")
  ```

- [ ] **Step 1: Write the failing test**

Append to `tests/test_monai_specs.py`:

```python
def test_write_spec_creates_yaml(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    path = mm.write_spec(entry, {"name": entry.name, "version": "0.5.3", "commands": []})
    assert path == mm.spec_path(entry)
    reloaded = yaml.safe_load(path.read_text())
    assert reloaded["version"] == "0.5.3"


def test_sync_writes_only_changed(tmp_path, whitelist_file, overlay_dir, monkeypatch):
    import scripts.monai_specs as ms

    monkeypatch.setattr(ms, "get_all_bundles_list",
                        lambda **kw: [("spleen_ct_segmentation", "0.5.3")])
    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {"sources": {}, "sinks": {}, "parameters": {}},
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)

    written = mm.sync(download_bundle=lambda entry: tmp_path / "bundle")
    assert len(written) == 1
    assert written[0].is_file()

    # Second run: version unchanged -> nothing written
    written2 = mm.sync(download_bundle=lambda entry: tmp_path / "bundle")
    assert written2 == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "write_spec or sync" -v`
Expected: FAIL (`AttributeError` — `write_spec`/`sync` not defined)

- [ ] **Step 3: Write minimal implementation**

Add `from typing import Callable` to the typing imports, then add to `MonaiModels`:

```python
    def write_spec(self, entry: WhitelistEntry, spec: dict) -> Path:
        path = self.spec_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False))
        return path

    def sync(self, download_bundle: Callable[[WhitelistEntry], Path]) -> List[Path]:
        """Full pipeline: fetch → filter → detect → generate → write.

        ``download_bundle`` maps an entry to a local bundle root directory
        (injected so tests need no network; production passes ``self._download``).
        """
        available = self.fetch_available()
        whitelisted = self.filter_whitelist(available)
        changed = self.detect_changes(whitelisted)
        written: List[Path] = []
        for entry in changed:
            bundle_dir = download_bundle(entry)
            spec = self.generate_spec(entry, bundle_dir)
            written.append(self.write_spec(entry, spec))
        return written

    def _download(self, entry: WhitelistEntry) -> Path:
        """Download a bundle from the Model Zoo into ``<root>/.monai-bundles``."""
        from monai.bundle import download

        dest = self.root / ".monai-bundles"
        dest.mkdir(parents=True, exist_ok=True)
        download(name=entry.name, version=entry.version, bundle_dir=str(dest))
        return dest / entry.name
```

At the end of `scripts/monai_specs.py` add the CLI entry point:

```python
def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Sync MONAI Model Zoo specs")
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--root", type=Path, default=Path(__file__).parent.parent)
    parser.add_argument(
        "--whitelist", type=Path,
        default=Path(__file__).parent / "monai_whitelist.yaml",
    )
    args = parser.parse_args(argv)

    mm = MonaiModels(root=args.root, whitelist_path=args.whitelist)
    written = mm.sync(download_bundle=mm._download)
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k "write_spec or sync" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full new test file**

Run: `.venv/bin/pytest tests/test_monai_specs.py -v`
Expected: PASS (all tasks' tests green)

- [ ] **Step 6: Commit**

```bash
git add scripts/monai_specs.py tests/test_monai_specs.py
git commit -m "feat(monai): write specs, sync orchestration and CLI entry point

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Contract check — generated spec loads as an XnatApp

**Files:**
- Test: `tests/test_monai_specs.py`

**Interfaces:**
- Consumes: `pydra2app.xnat.XnatApp.load` (already a test dep); a generated spec file.

This is the go/no-go for Option B (generic `BundleTask`) vs Option A (per-model generated class). If `XnatApp.load` rejects the spec because `command.sources`/`sinks` name fields that are not static attrs fields on `BundleTask`, escalate to Option A (see design doc "Open items").

- [ ] **Step 1: Write the test**

Append to `tests/test_monai_specs.py`:

```python
def test_generated_spec_loads_as_xnatapp(tmp_path, whitelist_file, overlay_dir, monkeypatch):
    import scripts.monai_specs as ms
    from pydra2app.xnat import XnatApp

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {
            "sources": {"image": {"datatype": "medimage/nifti-gz-x",
                                  "help": "in", "path": "network_data_format/inputs/image"}},
            "sinks": {"pred": {"datatype": "medimage/nifti-gz-x",
                               "help": "out", "path": "network_data_format/outputs/pred"}},
            "parameters": {},
        },
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    spec = mm.generate_spec(entry, bundle_dir=tmp_path / "bundle")
    path = mm.write_spec(entry, spec)

    image_spec = XnatApp.load(path)
    assert image_spec.commands
    assert image_spec.commands[0].name
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_monai_specs.py -k xnatapp -v`
Expected: PASS. If it FAILS on field resolution, record the error and escalate to Option A per the design doc before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_monai_specs.py
git commit -m "test(monai): assert generated spec loads as an XnatApp (Option B go/no-go)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Add dependency + scheduled GitHub Action

**Files:**
- Modify: `pyproject.toml:41` (add `pydra-compose-monai` to `test` deps)
- Create: `.github/workflows/monai-sync.yml`

**Interfaces:** none (CI wiring).

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, in the `[project.optional-dependencies]` `test = [...]` list, add `"pydra-compose-monai"` so the sync + tests can import it:

```toml
test = ["pytest >=6.2.5", "pytest-env>=0.6.2", "pytest-cov>=2.12.1", "frametree>=0.14.5", "xnat4tests>=0.3.14", "pydra2app>=0.18.8", "pydra2app-xnat>=0.8.2", "pydra-compose-monai"]
```

- [ ] **Step 2: Create the workflow**

Create `.github/workflows/monai-sync.yml`:

```yaml
name: Sync MONAI model specs

on:
  schedule:
    - cron: "0 3 * * 1"   # 03:00 UTC every Monday
  workflow_dispatch: {}

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: monai-test
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[test]"
      - name: Generate/update MONAI specs
        run: python -m scripts.monai_specs sync
      - name: Open PR with changes
        uses: peter-evans/create-pull-request@v6
        with:
          branch: monai-spec-sync
          base: monai-test
          title: "Update MONAI model specs"
          commit-message: "chore(monai): sync model specs from Model Zoo"
          body: "Automated MONAI Model Zoo spec sync. Review generated specs before merge."
          add-paths: |
            specs/**/monai/**
```

- [ ] **Step 3: Validate the workflow YAML**

Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/monai-sync.yml'))"`
Expected: no output (valid YAML).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .github/workflows/monai-sync.yml
git commit -m "ci(monai): add pydra-compose-monai dep and scheduled spec-sync workflow

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Full regression + lint

**Files:** none (verification only)

- [ ] **Step 1: Run the new test module**

Run: `.venv/bin/pytest tests/test_monai_specs.py -v`
Expected: all tests pass.

- [ ] **Step 2: Confirm the existing suite is unaffected**

Run: `.venv/bin/pytest tests/test_monai.py -v` (this is the network/XNAT test; expect it to be skipped/collected as before — it must not be newly broken by our changes).
Expected: same collection/skip behavior as before this work; no new import errors from `scripts/`.

## Self-Review

- **Spec coverage:** Component 2 (`MonaiModels` methods `fetch`/`filter`/`detect`/`generate`/`write`/`sync`) → Tasks 1–5. Whitelist + overlay control surfaces → Tasks 1 & 4. `monai/` namespace output → Task 1 `spec_path` + Task 5 `write_spec`. Option B go/no-go (`XnatApp.load`) → Task 6. Component 3 (scheduled PR-opening Action) → Task 7. Regression → Task 8. Depends-on Plan A's `spec_fragment`/`BundleTask` → Global Constraints + Task 7 dep. Complete.
- **Placeholder scan:** No TBD/TODO; every code step shows full code and exact commands. The overlay email uses a generic placeholder address (no PII).
- **Type consistency:** `WhitelistEntry` fields (`name/version/modality/species/region`) used consistently; `spec_fragment` return shape (`sources`/`sinks`/`parameters`) matches Plan A and every consumer here; `TASK_REF`/`configuration.bundle` strings match between impl and tests; `sync(download_bundle=...)` signature consistent between Task 5 impl, tests, and CLI (`mm._download`).
- **py38 constraint:** `scripts/` uses `Optional`/`List`/`Dict`/`Callable` from `typing`, no `X | Y` unions — consistent with repo target.
