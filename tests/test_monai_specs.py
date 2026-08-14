import json
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


def test_bundle_vendor_dir_beside_module(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    assert mm.bundle_vendor_dir(entry) == (
        mm.task_module_path(entry).parent / "spleen_ct_segmentation_bundle"
    )


def test_write_task_module_uses_module_relative_bundle(tmp_path, whitelist_file):
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    path = mm.write_task_module(entry)
    assert path == mm.task_module_path(entry)
    text = path.read_text()
    # references pydra-compose-monai define, uses a module-relative bundle path
    # (NOT an absolute /opt/bundles path), and names the class
    assert "from pydra.compose import monai" in text
    assert "Path(__file__).parent" in text
    assert '"spleen_ct_segmentation_bundle"' in text
    assert "/opt/bundles" not in text
    assert "SpleenCtSegmentation = monai.define(" in text
    # every generated package dir has an __init__.py so the dotted ref imports
    assert (path.parent / "__init__.py").is_file()


def test_write_task_module_does_not_package_src_root(tmp_path, whitelist_file):
    """``src/`` is the import root, not a package: it must not get an __init__.py."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    mm.write_task_module(entry)
    assert not (tmp_path / "src" / "__init__.py").exists()
    # ... but the package dirs below it are all importable
    pkg = tmp_path / "src" / "australianimagingservice"
    assert (pkg / "__init__.py").is_file()
    assert (pkg / "ct" / "human" / "abdomen" / "monai" / "__init__.py").is_file()


def _write_downloaded_bundle(dest: Path) -> Path:
    """A downloaded bundle as it arrives from the Model Zoo, weights included."""
    (dest / "configs").mkdir(parents=True, exist_ok=True)
    (dest / "configs" / "metadata.json").write_text("{}")
    (dest / "configs" / "inference.json").write_text("{}")
    (dest / "models").mkdir(parents=True, exist_ok=True)
    (dest / "models" / "model.pt").write_bytes(b"\x00" * 2048)
    (dest / "models" / "model.ts").write_bytes(b"\x00" * 2048)
    (dest / "docs").mkdir(parents=True, exist_ok=True)
    (dest / "docs" / "README.md").write_text("# docs\n")
    (dest / "LICENSE").write_text("license\n")
    (dest / ".cache" / "huggingface").mkdir(parents=True, exist_ok=True)
    (dest / ".cache" / "huggingface" / "CACHEDIR.TAG").write_text("x")
    (dest / ".gitattributes").write_text("* text=auto\n")
    return dest


def test_vendor_bundle_excludes_download_cache(tmp_path, whitelist_file):
    """HF download-provenance dirs are not part of the bundle and must not vendor."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    src_bundle = _write_downloaded_bundle(tmp_path / "downloaded")

    dest = mm.vendor_bundle(entry, src_bundle)
    assert (dest / "configs" / "metadata.json").is_file()
    assert not (dest / ".cache").exists()
    assert not (dest / ".gitattributes").exists()


def test_vendor_bundle_excludes_model_weights(tmp_path, whitelist_file):
    """Weights are never committed: only build-host introspection data vendors.

    ``parse_monai_spec`` reads only ``configs/metadata.json``, so configs are
    sufficient for spec-load / Dockerfile generation. Weights reach the image
    via the ``resources`` mechanism instead (see notes/monai-weights-plan.md).
    """
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    src_bundle = _write_downloaded_bundle(tmp_path / "downloaded")

    dest = mm.vendor_bundle(entry, src_bundle)
    # configs kept — this is what define()/spec_fragment introspect
    assert (dest / "configs" / "metadata.json").is_file()
    assert (dest / "configs" / "inference.json").is_file()
    # weights excluded entirely
    assert not (dest / "models").exists()
    # provenance kept: small, and useful when reviewing a sync PR
    assert (dest / "LICENSE").is_file()


def test_vendor_bundle_is_idempotent_and_drops_stale_weights(
    tmp_path, whitelist_file
):
    """A re-vendor over an older copy that had weights must remove them."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]
    src_bundle = _write_downloaded_bundle(tmp_path / "downloaded")

    # Simulate a previously-vendored bundle that still carries weights.
    stale = mm.bundle_vendor_dir(entry)
    (stale / "models").mkdir(parents=True)
    (stale / "models" / "model.pt").write_bytes(b"\x00")

    dest = mm.vendor_bundle(entry, src_bundle)
    assert not (dest / "models").exists()


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
    # commands is a mapping keyed by command name, matching the convention in
    # the hand-written specs and the `yq '.commands | keys'` step in release.yml
    assert isinstance(spec["commands"], dict)
    assert list(spec["commands"]) == ["spleen_ct_segmentation"]
    cmd = spec["commands"]["spleen_ct_segmentation"]
    assert cmd["task"] == (
        "australianimagingservice.ct.human.abdomen.monai."
        "spleen_ct_segmentation:SpleenCtSegmentation"
    )
    # the class bakes in a configs-only bundle path for build-host introspection;
    # configuration redirects the task to the full bundle at runtime
    assert cmd["configuration"] == {"bundle": "/monai-bundles/spleen_ct_segmentation"}
    assert cmd["operates_on"] == "session"
    assert cmd["sources"]["image"]["datatype"] == "medimage/nifti-gz-x"
    # sink path rewritten to the frametree store path
    assert cmd["sinks"]["pred"]["path"] == "monai/spleen_ct_segmentation/pred"


def test_generate_spec_points_bundle_at_runtime_resource(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """The task's ``bundle`` must resolve to the in-container weights path.

    The committed bundle is configs-only, so the module-relative path is only
    valid on the build host. At runtime the full bundle arrives as a resource,
    and ``configuration.bundle`` redirects the task there.
    """
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {"sources": {}, "sinks": {}, "parameters": {}},
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    spec = mm.generate_spec(entry, bundle_dir=tmp_path / "b")

    cmd = spec["commands"]["spleen_ct_segmentation"]
    runtime_path = mm.runtime_bundle_path(entry)
    assert cmd["configuration"]["bundle"] == runtime_path

    # a matching resource delivers the bundle to exactly that path
    assert spec["resources"][mm.resource_name(entry)] == runtime_path


def test_generated_spec_bundle_is_not_a_user_parameter(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """``bundle`` is set via configuration, so it must not be user-facing."""
    import importlib
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
    bundle = _make_synthetic_bundle(tmp_path / "downloaded")
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    written = mm.sync(download_bundle=lambda entry: bundle)

    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    importlib.invalidate_caches()

    image_spec = XnatApp.load(written[0])
    command = image_spec.commands[0]
    assert "bundle" not in [getattr(p, "name", p) for p in command.parameters]
    assert "bundle" not in [getattr(s, "name", s) for s in command.sources]


def test_generated_spec_commands_match_release_workflow_contract(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """release.yml runs ``yq '.commands | keys'``, which requires a mapping.

    Guards the generated spec against regressing to a list, which would break
    the "Dump XNAT command JSON to file" step for every MONAI pipeline.
    """
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {"sources": {}, "sinks": {}, "parameters": {}},
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    path = mm.write_spec(entry, mm.generate_spec(entry, bundle_dir=tmp_path / "b"))

    # Round-trip through YAML the way yq would read it off disk.
    reloaded = yaml.safe_load(path.read_text())
    assert isinstance(reloaded["commands"], dict)
    # `yq -r '.commands | keys | join(" ")'` yields the command names
    assert list(reloaded["commands"].keys()) == ["spleen_ct_segmentation"]


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

    # A fake downloaded bundle dir for vendor_bundle to copy.
    fake_bundle = tmp_path / "downloaded_bundle"
    (fake_bundle / "configs").mkdir(parents=True)
    (fake_bundle / "configs" / "metadata.json").write_text("{}")

    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)

    written = mm.sync(download_bundle=lambda entry: fake_bundle)
    assert len(written) == 1
    assert written[0].is_file()
    # sync also emitted the committed per-model task module ...
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    assert mm.task_module_path(entry).is_file()
    # ... and vendored the bundle beside it
    assert (mm.bundle_vendor_dir(entry) / "configs" / "metadata.json").is_file()

    # Second run: version unchanged -> nothing written
    written2 = mm.sync(download_bundle=lambda entry: fake_bundle)
    assert written2 == []


def _make_synthetic_bundle(dest: Path) -> Path:
    configs = dest / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    (configs / "metadata.json").write_text(json.dumps({
        "name": "SpleenCtSegmentation",
        "network_data_format": {
            "inputs": {"image": {"type": "image", "modality": "CT"}},
            "outputs": {"pred": {"type": "image", "format": "segmentation"}},
        },
    }))
    (configs / "inference.json").write_text(json.dumps({
        "postprocessing": {"_target_": "Compose", "transforms": [
            {"_target_": "SaveImaged", "keys": ["pred"], "output_postfix": "seg"}
        ]}
    }))
    return dest


def test_generated_spec_loads_as_xnatapp(tmp_path, whitelist_file, overlay_dir, monkeypatch):
    import importlib
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
    bundle = _make_synthetic_bundle(tmp_path / "downloaded")
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)

    # Full sync path: writes the module, vendors the bundle beside it, writes the spec.
    written = mm.sync(download_bundle=lambda entry: bundle)
    assert len(written) == 1
    spec_path = written[0]

    # Make the generated module importable, then load the spec (eager task import).
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    importlib.invalidate_caches()

    image_spec = XnatApp.load(spec_path)
    assert image_spec.commands
    assert image_spec.commands[0].name
    # command.task resolved to an actual class (not left as an unresolved string)
    assert not isinstance(image_spec.commands[0].task, str)
