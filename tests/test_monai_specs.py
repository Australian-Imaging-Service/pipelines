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

    # get_all_bundles_list() returns one (bundle_name, latest_version) tuple
    # per bundle, already reduced to the latest version.
    monkeypatch.setattr(
        ms, "get_all_bundles_list",
        lambda **kw: [("spleen_ct_segmentation", "0.5.3")],
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    available = mm.fetch_available()
    assert available["spleen_ct_segmentation"] == "0.5.3"


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


def test_class_name_is_camelcase(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    assert mm.class_name(entry) == "SpleenCtSegmentation"


def test_task_module_ref_and_path(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    assert mm.task_module_ref(entry) == (
        "australianimagingservice.ct.human.abdomen.monai."
        "spleen_ct_segmentation:SpleenCtSegmentation"
    )
    assert mm.task_module_path(entry) == (
        tmp_path / "src" / "australianimagingservice" / "ct" / "human"
        / "abdomen" / "monai" / "spleen_ct_segmentation.py"
    )


def test_write_task_module_emits_importable_define_call(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    path = mm.write_task_module(entry)
    assert path == mm.task_module_path(entry)
    text = path.read_text()
    # references pydra-compose-monai define, bakes the bundle path, names the class
    assert "from pydra.compose import monai" in text
    assert '"/opt/bundles/spleen_ct_segmentation"' in text
    assert "SpleenCtSegmentation = monai.define(" in text
    # every generated package dir has an __init__.py so the dotted ref imports
    assert (path.parent / "__init__.py").is_file()
    # intermediate directories up to src/ are also importable packages
    assert (tmp_path / "src" / "australianimagingservice" / "__init__.py").is_file()


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
    assert cmd["task"] == (
        "australianimagingservice.ct.human.abdomen.monai."
        "spleen_ct_segmentation:SpleenCtSegmentation"
    )
    # bundle is baked into the generated class, so configuration is empty
    assert cmd["configuration"] == {}
    assert cmd["operates_on"] == "session"
    assert cmd["sources"]["image"]["datatype"] == "medimage/nifti-gz-x"
    # sink path rewritten to the frametree store path
    assert cmd["sinks"]["pred"]["path"] == "monai/spleen_ct_segmentation/pred"


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
    # sync also emitted the committed per-model task module
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    assert mm.task_module_path(entry).is_file()

    # Second run: version unchanged -> nothing written
    written2 = mm.sync(download_bundle=lambda entry: tmp_path / "bundle")
    assert written2 == []
