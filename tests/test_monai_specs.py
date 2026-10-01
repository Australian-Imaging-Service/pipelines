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
    # the task is declared inline rather than referencing a generated module,
    # and points straight at the in-image bundle path
    assert cmd["task"] == {
        "type": "monai",
        "bundle": "/monai-bundles/spleen_ct_segmentation",
    }
    # no redirect is needed any more, so there is no configuration block
    assert "configuration" not in cmd
    assert cmd["operates_on"] == "session"
    assert cmd["sources"]["image"]["datatype"] == "medimage/nifti-gz-x"
    # sink path rewritten to the frametree store path
    assert cmd["sinks"]["pred"]["path"] == "monai/spleen_ct_segmentation/pred"


def test_generate_spec_points_bundle_at_runtime_resource(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """The task's ``bundle`` and its ``resources`` entry must name one path.

    The resource is unpacked to that path inside the image and the task reads
    the bundle from it, so if the two ever drifted the image would build but
    fail at run time.
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
    assert cmd["task"]["bundle"] == runtime_path

    # a matching resource delivers the bundle to exactly that path
    assert spec["resources"][mm.resource_name(entry)]["path"] == runtime_path


@pytest.mark.xfail(
    reason=(
        "pydra2app's task_converter defers a task given as a dotted string, but "
        "an inline dict goes to structure(), which calls monai.define() -> "
        "parse_monai_spec() and reads configs/metadata.json from the bundle path "
        "immediately. That path only exists inside the built image, so the spec "
        "cannot be loaded on the build host. Needs deferral for the dict form "
        "when sources and sinks are already defined -- raised with @tclose. "
        "Same root cause as #496."
    ),
    raises=ValueError,
    strict=True,
)
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
    # nothing is vendored or generated beside the spec any more
    assert not (tmp_path / "src").exists()
    # the downloaded bundle is read and discarded, never committed
    assert not list((tmp_path / "specs").glob("**/*_bundle"))

    # Second run: version unchanged -> nothing written
    written2 = mm.sync(download_bundle=lambda entry: fake_bundle)
    assert written2 == []


def test_fetch_resources_reads_specs_and_populates_resources_dir(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """``fetch-resources`` stages each spec's full bundle for --resources-dir.

    The generated spec declares a resource that nothing supplies, so a build
    fails until this runs. It must key off the spec on disk (not the
    whitelist) so it reflects exactly what will be built, and pin to the
    spec's version so the image cannot drift from the spec describing it.
    """
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {"sources": {}, "sinks": {}, "parameters": {}},
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    mm.write_spec(entry, mm.generate_spec(entry, bundle_dir=tmp_path / "b"))

    downloaded: list = []

    def fake_download(name: str, version: str, dest: Path) -> Path:
        downloaded.append((name, version))
        bundle = dest / name
        (bundle / "configs").mkdir(parents=True)
        (bundle / "configs" / "metadata.json").write_text("{}")
        (bundle / "models").mkdir(parents=True)
        (bundle / "models" / "model.pt").write_bytes(b"\x00" * 512)
        return bundle

    resources_dir = tmp_path / "resources"
    staged = mm.fetch_resources(resources_dir, download=fake_download)

    # pinned to the spec's version, not "latest"
    assert downloaded == [("spleen_ct_segmentation", "0.5.3")]
    # staged under the resource name the spec declares
    target = resources_dir / "spleen_ct_segmentation-bundle"
    assert staged == [target]
    # the full bundle: weights AND configs, since _resolve_bundle_dir needs both
    assert (target / "models" / "model.pt").is_file()
    assert (target / "configs" / "metadata.json").is_file()


def test_fetch_resources_is_idempotent(
    tmp_path, whitelist_file, overlay_dir, monkeypatch
):
    """Re-running replaces the staged copy rather than merging into it."""
    import scripts.monai_specs as ms

    monkeypatch.setattr(
        ms, "spec_fragment",
        lambda bundle: {"sources": {}, "sinks": {}, "parameters": {}},
    )
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    entry = mm.whitelist()[0]._replace(version="0.5.3")
    mm.write_spec(entry, mm.generate_spec(entry, bundle_dir=tmp_path / "b"))

    def fake_download(name: str, version: str, dest: Path) -> Path:
        bundle = dest / name
        (bundle / "configs").mkdir(parents=True, exist_ok=True)
        (bundle / "configs" / "metadata.json").write_text("{}")
        return bundle

    resources_dir = tmp_path / "resources"
    target = resources_dir / "spleen_ct_segmentation-bundle"
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("from an older version")

    mm.fetch_resources(resources_dir, download=fake_download)
    assert not (target / "stale.txt").exists()
    assert (target / "configs" / "metadata.json").is_file()


def test_fetch_resources_ignores_non_monai_specs(tmp_path, whitelist_file):
    """Only MONAI specs declare a bundle resource; others must be skipped."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    other = tmp_path / "specs" / "australian-imaging-service" / "quality-control"
    other.mkdir(parents=True)
    (other / "phi-finder.yaml").write_text(
        yaml.safe_dump({"name": "phi-finder", "version": "1.0", "commands": {}})
    )

    def fail_download(name, version, dest):  # pragma: no cover - must not run
        raise AssertionError("should not download for a non-MONAI spec")

    assert mm.fetch_resources(tmp_path / "resources", download=fail_download) == []


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


@pytest.mark.xfail(
    reason=(
        "pydra2app's task_converter defers a task given as a dotted string, but "
        "an inline dict goes to structure(), which calls monai.define() -> "
        "parse_monai_spec() and reads configs/metadata.json from the bundle path "
        "immediately. That path only exists inside the built image, so the spec "
        "cannot be loaded on the build host. Needs deferral for the dict form "
        "when sources and sinks are already defined -- raised with @tclose. "
        "Same root cause as #496."
    ),
    raises=ValueError,
    strict=True,
)
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


# ---------------------------------------------------------------------------
# Triage: candidates / declined / withdrawn (#485)
# ---------------------------------------------------------------------------


@pytest.fixture
def triage_whitelist_file(tmp_path: Path) -> Path:
    """Whitelist exercising every triage state at once."""
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
                    },
                    "withdrawn_model": {
                        "version": None,
                        "modality": "mri",
                        "species": "human",
                        "region": "neuro",
                    },
                },
                "declined": {
                    "mednist_gan": {
                        "reason": "synthetic image GAN, not a clinical pipeline",
                        "at_version": "0.4.4",
                    },
                    "classification_template": {
                        "reason": "a template, not a model",
                    },
                },
            }
        )
    )
    return p


AVAILABLE = {
    "spleen_ct_segmentation": "0.6.1",
    "mednist_gan": "0.5.0",           # declined at 0.4.4 -> stale
    "classification_template": "0.0.4",  # declined with no at_version -> never stale
    "brand_new_model": "1.0.0",       # neither approved nor declined -> candidate
}


def test_declined_parses_entries(tmp_path: Path, triage_whitelist_file: Path):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    by_name = {e.name: e for e in mm.declined()}
    assert set(by_name) == {"mednist_gan", "classification_template"}
    assert by_name["mednist_gan"].at_version == "0.4.4"
    assert by_name["classification_template"].at_version is None


def test_declined_absent_is_empty(tmp_path: Path, whitelist_file: Path):
    """A whitelist with no `declined:` block is valid, not an error."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    assert mm.declined() == []


def test_candidates_excludes_approved_and_declined(
    tmp_path: Path, triage_whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    assert mm.candidates(AVAILABLE) == [("brand_new_model", "1.0.0")]


def test_stale_declines_detects_newer_version(
    tmp_path: Path, triage_whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    stale = mm.stale_declines(AVAILABLE)
    assert [s.name for s in stale] == ["mednist_gan"]
    assert stale[0].at_version == "0.4.4"
    assert stale[0].available_version == "0.5.0"


def test_decline_without_at_version_never_goes_stale(
    tmp_path: Path, triage_whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    assert "classification_template" not in {s.name for s in mm.stale_declines(AVAILABLE)}


def test_withdrawn_reports_approved_models_missing_from_zoo(
    tmp_path: Path, triage_whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    assert mm.withdrawn(AVAILABLE) == ["withdrawn_model"]


def test_triage_report_covers_all_three_sections(
    tmp_path: Path, triage_whitelist_file: Path
):
    mm = MonaiModels(root=tmp_path, whitelist_path=triage_whitelist_file)
    needs_attention, body = mm.triage_report(AVAILABLE)
    assert needs_attention
    assert "brand_new_model" in body
    assert "mednist_gan" in body and "0.4.4" in body and "0.5.0" in body
    assert "withdrawn_model" in body
    # candidates are emitted paste-ready, with the anatomy fields to fill in
    assert "modality:" in body and "species:" in body and "region:" in body


def test_triage_report_quiet_when_nothing_to_do(
    tmp_path: Path, whitelist_file: Path
):
    """Nothing to triage is a normal outcome, not a failure."""
    mm = MonaiModels(root=tmp_path, whitelist_path=whitelist_file)
    needs_attention, body = mm.triage_report({"spleen_ct_segmentation": "0.6.1"})
    assert not needs_attention
    assert "No MONAI models need triage" in body
