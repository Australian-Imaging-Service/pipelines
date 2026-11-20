import copy
import hashlib
import json
import sys

import pytest

from scripts import zenodo


class FakeZenodo:
    def __init__(self):
        self.records = []
        self.contents = {}
        self.actions = []

    def deposits(self):
        return copy.deepcopy(self.records)

    def json(self, method, url, body=None):
        path = url.split("/api/")[1].split("/")
        if path == ["deposit", "depositions"]:
            record = {
                "id": len(self.records) + 1,
                "conceptrecid": len(self.records) + 1,
                "created": "2026-01-01T00:00:00+00:00",
                "submitted": False,
                "metadata": copy.deepcopy(body["metadata"]),
            }
            record["metadata"]["prereserve_doi"] = {
                "doi": f"10.5072/zenodo.{record['id']}"
            }
            record["links"] = {"bucket": f"{zenodo.API}/files/{record['id']}"}
            self.records.append(record)
            self.contents[record["id"]] = {}
            return copy.deepcopy(record)
        record = next(d for d in self.records if d["id"] == int(path[2]))
        if path[3:] == ["files"]:
            return [
                {
                    "id": name,
                    "filename": name,
                    "checksum": hashlib.md5(data).hexdigest(),
                }
                for name, data in self.contents[record["id"]].items()
            ]
        if path[3:] == ["actions", "newversion"]:
            new = copy.deepcopy(record)
            new["id"] = len(self.records) + 1
            new["created"] = "2026-01-02T00:00:00+00:00"
            new["submitted"] = False
            new["links"] = {"bucket": f"{zenodo.API}/files/{new['id']}"}
            self.records.append(new)
            self.contents[new["id"]] = copy.deepcopy(self.contents[record["id"]])
            return {
                "links": {
                    "latest_draft": f"{zenodo.API}/deposit/depositions/{new['id']}"
                }
            }
        if path[3:] == ["actions", "publish"]:
            record["submitted"] = True
            self.actions.append(("publish", record["id"]))
        elif method == "PUT":
            doi = record["metadata"].get("prereserve_doi")
            record["metadata"] = copy.deepcopy(body["metadata"])
            if doi:
                record["metadata"]["prereserve_doi"] = doi
        return copy.deepcopy(record)

    def request(self, method, url, data=None, content_type=None):
        path = url.split("/api/")[1].split("/")
        if method == "PUT":
            self.contents[int(path[1])][path[2]] = data
        elif method == "DELETE":
            del self.contents[int(path[2])][path[4]]
        else:
            raise AssertionError((method, url))


@pytest.fixture
def spec_dir(tmp_path):
    root = tmp_path / "specs"
    (root / "quality-control").mkdir(parents=True)
    (root / "quality-control" / "example.yaml").write_text(
        "title: Example\nversion: '1.0'\nlicense: mit\n"
        "authors:\n  - name: Example Author\ndocs:\n"
        "  info_url: https://example.org\n  description: Test description\n"
        "extra: !join ['a', 'b']\n"
    )
    return root


@pytest.fixture
def entry():
    return {
        "id": "quality-control.example",
        "spec": "quality-control/example",
        "version": "1.0",
        "image": "ghcr.io/ais/example@sha256:" + "a" * 64,
    }


def test_dry_run_without_token_checks_only_selected_specs(
    spec_dir, tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("ZENODO_SANDBOX_TOKEN", raising=False)
    selected = tmp_path / "selected-specs.txt"
    selected.write_text("quality-control/example\n")
    (spec_dir / "excluded.yaml").write_text("title: No licence\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "zenodo",
            "validate-specs",
            "--selected-specs",
            str(selected),
            "--spec-dir",
            str(spec_dir),
        ],
    )
    assert zenodo.main() == 0
    assert "1 selected pipelines" in capsys.readouterr().out

    example = spec_dir / "quality-control/example.yaml"
    example.write_text(example.read_text().replace("license: mit\n", ""))
    selected.write_text("quality-control/example\nexcluded\n")
    assert zenodo.main() == 1
    errors = capsys.readouterr().err
    assert "quality-control/example: missing license" in errors
    assert "excluded: missing version" in errors


def test_draft_and_new_version_are_reused(spec_dir, entry):
    client = FakeZenodo()
    commit = "b" * 40
    draft = zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)
    assert not draft["submitted"]
    assert len(client.records) == 1
    assert (
        zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)["id"]
        == draft["id"]
    )
    client.json(
        "POST", f"{zenodo.API}/deposit/depositions/{draft['id']}/actions/publish"
    )
    assert zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)["submitted"]
    path = spec_dir / "quality-control/example.yaml"
    path.write_text(path.read_text().replace("version: '1.0'", "version: '1.1'"))
    entry["version"] = "1.1"
    next_draft = zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)
    assert next_draft["conceptrecid"] == draft["conceptrecid"]
    assert next_draft["metadata"]["version"] == "1.1"
    assert len(client.records) == 2
    assert (
        zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)["id"]
        == next_draft["id"]
    )


def test_rejects_missing_licence_and_changed_published_content(spec_dir, entry):
    path = spec_dir / "quality-control/example.yaml"
    original = path.read_text()
    path.write_text(original.replace("license: mit\n", ""))
    with pytest.raises(zenodo.ZenodoError, match="missing license"):
        zenodo.build_metadata(entry, "ais/pipelines", "b" * 40, spec_dir)
    path.write_text(original)
    client = FakeZenodo()
    draft = zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)
    client.json(
        "POST", f"{zenodo.API}/deposit/depositions/{draft['id']}/actions/publish"
    )
    path.write_text(original.replace("Test description", "Changed description"))
    with pytest.raises(zenodo.ZenodoError, match="checksum mismatch"):
        zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)


def test_rejects_duplicate_concepts(spec_dir, entry):
    client = FakeZenodo()
    zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)
    duplicate = copy.deepcopy(client.records[0])
    duplicate["id"] = 2
    duplicate["conceptrecid"] = 2
    client.records.append(duplicate)
    with pytest.raises(zenodo.ZenodoError, match="Multiple Zenodo records"):
        zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)


def test_client_refuses_non_sandbox_urls_and_missing_token():
    with pytest.raises(zenodo.ZenodoError, match="TOKEN"):
        zenodo.Client("")
    with pytest.raises(zenodo.ZenodoError, match="outside Zenodo Sandbox"):
        zenodo.Client("unused").json(
            "GET", "https://zenodo.org/api/deposit/depositions"
        )


def test_retry_does_not_replace_changed_draft(spec_dir, entry):
    client = FakeZenodo()
    zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)
    original = copy.deepcopy(client.contents)
    path = spec_dir / "quality-control/example.yaml"
    path.write_text(path.read_text().replace("Test description", "Changed description"))
    with pytest.raises(zenodo.ZenodoError, match="draft metadata differs"):
        zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)
    assert client.contents == original


@pytest.mark.parametrize(
    ("declared", "returned"),
    [
        ("cc0-1.0", "cc-zero"),
        ("CC-BY-4.0", "cc-by"),
        ("Apache-2.0", "apache2.0"),
        ("mit", "mit-license"),
    ],
)
def test_retry_accepts_zenodo_alias_but_rejects_different_license(
    spec_dir, entry, monkeypatch, declared, returned
):
    monkeypatch.setattr(
        zenodo,
        "license_aliases",
        lambda: {
            "cc-zero": "cc0-1.0",
            "cc-by": "cc-by-4.0",
            "apache2.0": "apache-2.0",
            "mit-license": "mit",
        },
    )
    path = spec_dir / "quality-control/example.yaml"
    path.write_text(path.read_text().replace("license: mit", f"license: {declared}"))
    client = FakeZenodo()
    draft = zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)
    client.records[0]["metadata"]["license"] = returned
    assert (
        zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)["id"]
        == draft["id"]
    )
    client.records[0]["metadata"]["license"] = "unrelated-license"
    with pytest.raises(zenodo.ZenodoError, match="draft metadata differs"):
        zenodo.prepare(client, entry, "ais/pipelines", "b" * 40, spec_dir)


def test_license_mapping_checks_integrity_and_rejects_unknown_alias(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"cc-zero": "CC0-1.0", "apache": "Apache-2.0"}'

    class Opener:
        def open(self, url, timeout):
            assert url == zenodo.LICENSE_MAP_URL
            return Response()

    data = Response().read()
    monkeypatch.setattr(zenodo, "build_opener", lambda *_: Opener())
    monkeypatch.setattr(zenodo, "LICENSE_MAP_SHA256", hashlib.sha256(data).hexdigest())
    zenodo.license_aliases.cache_clear()
    try:
        assert zenodo.licenses_match("CC-ZERO", "cc0-1.0")
        assert zenodo.licenses_match("apache", "apache-2.0")
        assert not zenodo.licenses_match("unknown", "cc0-1.0")
        zenodo.license_aliases.cache_clear()
        monkeypatch.setattr(zenodo, "LICENSE_MAP_SHA256", "0" * 64)
        with pytest.raises(zenodo.ZenodoError, match="checksum mismatch"):
            zenodo.license_aliases()
    finally:
        zenodo.license_aliases.cache_clear()


def test_retry_replaces_inherited_files_after_interrupted_new_version(spec_dir, entry):
    client = FakeZenodo()
    commit = "b" * 40
    draft = zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)
    client.json(
        "POST", f"{zenodo.API}/deposit/depositions/{draft['id']}/actions/publish"
    )
    path = spec_dir / "quality-control/example.yaml"
    path.write_text(path.read_text().replace("version: '1.0'", "version: '1.1'"))
    entry["version"] = "1.1"
    _, metadata, _ = zenodo.build_metadata(entry, "ais/pipelines", commit, spec_dir)
    response = client.json(
        "POST", f"{zenodo.API}/deposit/depositions/1/actions/newversion"
    )
    client.json("PUT", response["links"]["latest_draft"], {"metadata": metadata})
    recovered = zenodo.prepare(client, entry, "ais/pipelines", commit, spec_dir)
    assert recovered["id"] == 2
    assert b"version: '1.1'" in client.contents[2]["pipeline-spec.yaml"]


def test_catalogue_skips_unchanged_and_publishes_changed(
    spec_dir, entry, tmp_path, monkeypatch
):
    client = FakeZenodo()
    monkeypatch.setattr(zenodo, "Client", lambda _: client)
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps({"pipelines": [entry]}))
    previous = tmp_path / "previous"
    previous.mkdir()
    args = type(
        "Args",
        (),
        {
            "catalogue": str(catalogue),
            "previous": str(previous),
            "entry": None,
            "action": "prepare",
            "repository": "ais/pipelines",
            "commit": "b" * 40,
            "spec_dir": str(spec_dir),
        },
    )()
    zenodo.process(args)
    assert not client.actions
    args.action = "publish"
    zenodo.process(args)
    assert client.actions == [("publish", 1)]
    zenodo.process(args)
    assert client.actions == [("publish", 1)]
    (previous / "pipeline-release.json").write_text(catalogue.read_text())
    args.action = "prepare"
    zenodo.process(args)
    assert len(client.records) == 1
