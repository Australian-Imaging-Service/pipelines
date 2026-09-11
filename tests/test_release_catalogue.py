"""Offline release tests: no builds, registry writes, or GitHub publication."""

import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import release_catalogue as rc

REPO = "example/pipelines"
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64


@pytest.fixture
def work():
    with tempfile.TemporaryDirectory(
        prefix=".test-release-", dir=Path.cwd()
    ) as directory:
        yield Path(directory)


def item(spec="mri/test", version="1.0"):
    return {
        "spec": spec,
        "id": spec.replace("/", "."),
        "version": version,
        "image_tag": f"ghcr.io/example/{spec.replace('/', '.')}:{version}",
        "commands": ["run"],
    }


def args(**kwargs):
    return SimpleNamespace(**kwargs)


def write(path, value):
    rc.write_json(path, value)
    return path


def inventory(work, items):
    return write(work / "inventory.json", {"schema_version": "1.0", "pipelines": items})


def commands(work, pipeline):
    work.mkdir(parents=True, exist_ok=True)
    for name in pipeline["commands"]:
        write(
            work / f"{name}.json",
            {
                "name": pipeline["id"] + "." + name,
                "image": pipeline["image_tag"],
                "command-line": "preserved",
                "xnat": [{"nested": True}],
            },
        )
    return work


def pinned(pipeline):
    return rc.image_repository(pipeline["image_tag"]) + "@" + DIGEST


def entry(work, pipeline, monkeypatch):
    monkeypatch.setattr(
        rc, "inspect_image", lambda tag: rc.image_repository(tag) + "@" + DIGEST
    )
    source = commands(work / "commands", pipeline)
    output = work / "entry"
    output.mkdir(parents=True)
    result = rc.materialize(pipeline, source, output)
    write(output / "entry.json", result)
    return output, result


def catalogue(work, pipelines, monkeypatch, tag="v1"):
    output = work / "catalogue"
    output.mkdir(parents=True)
    entries = []
    for index, pipeline in enumerate(pipelines):
        directory, result = entry(work / str(index), pipeline, monkeypatch)
        for command in result["commands"]:
            shutil.copyfile(directory / command["path"], output / command["path"])
            command["url"] = rc.asset_url(REPO, tag, command["path"])
        entries.append(result)
    value = {
        "schema_version": "1.0",
        "release": {"tag": tag},
        "source": {"repository": REPO, "commit": COMMIT},
        "pipelines": entries,
    }
    write(output / rc.CATALOGUE, value)
    return output, value


@pytest.mark.parametrize(
    "value",
    [
        {"build": []},
        {"build": ["x"], "unchanged": ["x"]},
    ],
)
def test_invalid_plan(work, value):
    with pytest.raises(rc.CatalogueError):
        rc.plan_file(write(work / "plan.json", value))


@pytest.mark.parametrize(
    "change",
    [
        lambda second: second.update(id="mri.test", spec="mri.test"),
        lambda second: second.update(commands=["../run"]),
    ],
)
def test_inventory_collisions_and_unsafe_values(change):
    second = item("other/test")
    change(second)
    with pytest.raises(rc.CatalogueError):
        rc.validate_inventory({"schema_version": "1.0", "pipelines": [item(), second]})


def test_inventory_uses_loaded_reference_and_version(work, monkeypatch):
    root = work / "specs"
    directory = root / "org"
    directory.mkdir(parents=True)
    (directory / "test.yaml").write_text("version: 1\n")
    loaded = []

    def load(path, **kwargs):
        loaded.append((path, kwargs))
        return args(
            reference="ghcr.io/custom/explicit:1.0-post1",
            version="1.0-post1",
            commands=[args(name="run")],
        )

    monkeypatch.setattr(rc, "load_app", load)
    plan = write(work / "plan.json", {"build": [], "unchanged": ["test"]})
    output = work / "inventory.json"
    rc.inventory(args(plan=plan, spec_root=root, spec_dir=directory, output=output))
    result = rc.read_json(output)["pipelines"][0]
    assert result["version"] == "1.0-post1"
    assert result["image_tag"] == "ghcr.io/custom/explicit:1.0-post1"
    assert result["commands"] == ["run"]
    assert loaded == [(directory / "test.yaml", {"root_dir": root})]


def test_image_env_appends_safe_stable_values(work):
    names = ["second-command", "first_command"]
    output = work / "env"
    output.write_text("EXISTING=1\n")
    pipeline = {**item(), "commands": names}
    options = args(
        inventory=inventory(work, [pipeline]), spec="mri/test", output=output
    )
    rc.image_env(options)
    contents = output.read_text()
    assert contents.startswith(
        "EXISTING=1\nIMAGE_TAG=ghcr.io/example/mri.test:1.0\nPIPELINE_ID="
    )
    environment = dict(line.split("=", 1) for line in contents.splitlines())
    assert len(environment["PIPELINE_ID"]) == 24
    assert json.loads(environment["COMMAND_NAMES_JSON"]) == sorted(names)
    assert len(environment) == 4


def test_image_env_rejects_command_injection_before_appending(work):
    output = work / "env"
    output.write_text("EXISTING=1\n")
    pipeline = {**item(), "commands": ["run\nINJECT=1"]}
    options = args(
        inventory=inventory(work, [pipeline]), spec="mri/test", output=output
    )
    with pytest.raises(rc.CatalogueError):
        rc.image_env(options)
    assert output.read_text() == "EXISTING=1\n"


def test_remote_digest_uses_manifest_descriptor(monkeypatch):
    calls = []

    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return args(stdout=json.dumps({"digest": DIGEST}))

    monkeypatch.setattr(subprocess, "run", execute)
    assert rc.inspect_image(item()["image_tag"]) == pinned(item())
    assert calls[0][0] == [
        "docker",
        "buildx",
        "imagetools",
        "inspect",
        item()["image_tag"],
        "--format",
        "{{json .Manifest}}",
    ]
    assert calls[0][1]["check"] is True


def test_invalid_registry_descriptor(monkeypatch):
    monkeypatch.setattr(rc, "run", lambda *args: json.dumps({"digest": "wrong"}))
    with pytest.raises(rc.CatalogueError):
        rc.inspect_image(item()["image_tag"])


def test_record_pins_hashes_and_preserves_command(work, monkeypatch):
    pipeline = item()
    directory, result = entry(work, pipeline, monkeypatch)
    command = result["commands"][0]
    data = (directory / command["path"]).read_bytes()
    value = json.loads(data)
    assert result["image"] == pinned(pipeline)
    assert value["image"] == pinned(pipeline)
    assert value["name"] == "mri.test.run"
    assert value["command-line"] == "preserved"
    assert value["xnat"] == [{"nested": True}]
    assert rc.hashlib.sha256(data).hexdigest() == command["sha256"]


def test_record_rejects_bad_commands(work, monkeypatch):
    pipeline = item()
    source = commands(work / "commands", pipeline)
    value = rc.read_json(source / "run.json")
    value["image"] = "wrong"
    write(source / "run.json", value)
    monkeypatch.setattr(rc, "inspect_image", lambda _: pinned(pipeline))
    monkeypatch.setattr(rc, "verify_local_image", lambda *_: None)
    with pytest.raises(rc.CatalogueError):
        rc.record(
            args(
                inventory=inventory(work, [pipeline]),
                spec=pipeline["spec"],
                commands_dir=source,
                output_dir=work / "output",
            )
        )
    assert not (work / "output").exists()


@pytest.mark.parametrize("local", ["matching", "retargeted"])
def test_record_requires_digest_of_locally_pushed_image(work, monkeypatch, local):
    pipeline = item()
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True
        if command[1:3] == ["buildx", "imagetools"]:
            return args(stdout=json.dumps({"digest": DIGEST}))
        assert command == [
            "docker",
            "image",
            "inspect",
            pipeline["image_tag"],
            "--format",
            "{{json .RepoDigests}}",
        ]
        digests = {
            "matching": [pinned(pipeline)],
            "retargeted": [pinned(pipeline).replace("b" * 64, "c" * 64)],
        }
        return args(stdout=json.dumps(digests[local]))

    monkeypatch.setattr(subprocess, "run", execute)
    options = args(
        inventory=inventory(work, [pipeline]),
        spec=pipeline["spec"],
        commands_dir=commands(work / "commands", pipeline),
        output_dir=work / "output",
    )
    if local == "matching":
        rc.record(options)
        assert rc.read_json(options.output_dir / "entry.json")["image"] == pinned(
            pipeline
        )
    else:
        with pytest.raises(rc.CatalogueError):
            rc.record(options)
        assert not options.output_dir.exists()
    assert len(calls) == 2


def assemble_args(work, items, build, unchanged, previous):
    return args(
        inventory=inventory(work, items),
        plan=write(work / "plan.json", {"build": build, "unchanged": unchanged}),
        entries_dir=work / "built",
        previous_dir=previous,
        repository=REPO,
        tag="v2",
        commit=COMMIT,
        output_dir=work / "output",
    )


def test_assemble_changed_unchanged_and_removed_is_deterministic(work, monkeypatch):
    old, kept, removed = item(), item("kept"), item("removed")
    previous, _ = catalogue(work / "previous", [old, kept, removed], monkeypatch)
    changed = item(version="2.0")
    entry(work / "built" / "artifact-id", changed, monkeypatch)
    options = assemble_args(
        work, [changed, kept], [changed["spec"]], [kept["spec"]], previous
    )
    rc.assemble(options)
    first = (options.output_dir / rc.CATALOGUE).read_bytes()
    rc.assemble(options)
    assert first == (options.output_dir / rc.CATALOGUE).read_bytes()
    value = json.loads(first)
    assert [entry["id"] for entry in value["pipelines"]] == ["kept", "mri.test"]
    assert value["previous_release"] == {"tag": "v1", "commit": COMMIT}
    assert all(
        "/v2/" in command["url"]
        for entry in value["pipelines"]
        for command in entry["commands"]
    )
    rc.validate_catalogue(value, options.output_dir, REPO, "v2", COMMIT)


def test_assemble_all_unchanged(work, monkeypatch):
    pipeline = item()
    previous, _ = catalogue(work / "previous", [pipeline], monkeypatch)
    options = assemble_args(work, [pipeline], [], [pipeline["spec"]], previous)
    monkeypatch.setattr(
        rc, "bootstrap", lambda *_: pytest.fail("Must reuse prior commands")
    )
    rc.assemble(options)
    assert len(rc.read_json(options.output_dir / rc.CATALOGUE)["pipelines"]) == 1


@pytest.mark.parametrize("failure", ["missing", "checksum"])
def test_assemble_rejects_incomplete_or_corrupt_builds(work, monkeypatch, failure):
    pipeline = item()
    previous = work / "previous"
    previous.mkdir()
    if failure != "missing":
        directory, result = entry(work / "built" / "one", pipeline, monkeypatch)
        if failure == "checksum":
            (directory / result["commands"][0]["path"]).write_text("{}")
        write(directory / "entry.json", result)
    options = assemble_args(work, [pipeline], [pipeline["spec"]], [], previous)
    with pytest.raises(rc.CatalogueError):
        rc.assemble(options)
    assert not options.output_dir.exists()


def test_assemble_rejects_retargeted_previous(work, monkeypatch):
    pipeline = item()
    previous, _ = catalogue(work / "previous", [pipeline], monkeypatch)
    monkeypatch.setattr(
        rc, "inspect_image", lambda _: pinned(pipeline).replace("b" * 64, "c" * 64)
    )
    options = assemble_args(work, [pipeline], [], [pipeline["spec"]], previous)
    with pytest.raises(rc.CatalogueError):
        rc.assemble(options)


def test_first_catalogue_bootstraps_without_running_or_building(work, monkeypatch):
    pipeline = item()
    previous = work / "previous"
    previous.mkdir()
    calls = []

    def execute(*command):
        calls.append(command)
        if command[1] == "buildx":
            return json.dumps({"digest": DIGEST})
        if command[1] == "create":
            return "c" * 64
        if command[1] == "cp":
            write(
                Path(command[-1]),
                {"name": "mri.test.run", "image": pipeline["image_tag"]},
            )
        return ""

    monkeypatch.setattr(rc, "run", execute)
    options = assemble_args(work, [pipeline], [], [pipeline["spec"]], previous)
    rc.assemble(options)
    assert [command[1] for command in calls] == ["buildx", "pull", "create", "cp", "rm"]
    assert calls[1][-1] == pinned(pipeline)
    assert calls[2][2:4] == ("--entrypoint", "/bin/true")
    assert "previous_release" not in rc.read_json(options.output_dir / rc.CATALOGUE)


def release(
    tag="v1", names=(), draft=False, prerelease=False, published="2026-01-01T00:00:00Z"
):
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": published,
        "target_commitish": COMMIT,
        "assets": [{"name": name} for name in names],
    }


def test_previous_selects_latest_catalogued_stable_release(work, monkeypatch):
    source, value = catalogue(work / "source", [item()], monkeypatch, tag="v2")
    downloads = []
    records = [
        release("v1", [rc.CATALOGUE]),
        release(
            "v2",
            [path.name for path in source.iterdir()],
            published="2026-02-01T00:00:00Z",
        ),
        release("v3", [], published="2026-03-01T00:00:00Z"),
        release("v4", [rc.CATALOGUE], draft=True),
        release("v5", [rc.CATALOGUE], prerelease=True),
        release("current", [rc.CATALOGUE], published="2026-09-01T00:00:00Z"),
    ]
    monkeypatch.setattr(rc, "release_list", lambda _: records)

    def download(repo, tag, name, directory):
        downloads.append((repo, tag, name))
        shutil.copyfile(source / name, Path(directory) / name)

    monkeypatch.setattr(rc, "download", download)
    rc.previous(args(repository=REPO, tag="current", output_dir=work / "previous"))
    assert rc.read_json(work / "previous" / rc.CATALOGUE) == value
    assert {tag for _, tag, _ in downloads} == {"v2"}
    assert len(downloads) == 2


def test_previous_bootstrap_empty_only_when_no_catalogue(work, monkeypatch):
    release_list = rc.release_list
    monkeypatch.setattr(rc, "release_list", lambda _: [release()])
    rc.previous(args(repository=REPO, tag="v2", output_dir=work / "previous"))
    assert list((work / "previous").iterdir()) == []
    monkeypatch.setattr(rc, "run", lambda *args: "{}")
    with pytest.raises(rc.CatalogueError, match="Malformed"):
        release_list(REPO)


@pytest.mark.parametrize("status", [403, 404])
def test_release_lookup_only_404_is_absent(monkeypatch, status):
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True
        if "--paginate" in command and status == 404:
            assert "--slurp" in command
            return args(stdout="[[]]")
        raise subprocess.CalledProcessError(
            1, command, stderr=f"gh: request failed (HTTP {status})"
        )

    monkeypatch.setattr(subprocess, "run", execute)
    if status == 404:
        assert rc.release_lookup(REPO, "v1") is None
    else:
        with pytest.raises(rc.CatalogueError, match="Release lookup failed"):
            rc.release_lookup(REPO, "v1")
    assert len(calls) == (2 if status == 404 else 1)


def test_release_lookup_finds_draft_in_paginated_listing(monkeypatch):
    draft = {**release("v2", draft=True), "id": 42}
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True
        if "/releases/tags/" in command[-1]:
            raise subprocess.CalledProcessError(
                1, command, stderr="gh: Not Found (HTTP 404)"
            )
        if "--paginate" in command:
            pages = [[release("v1")], [draft]]
            return args(stdout=json.dumps(pages))
        assert command == ["gh", "api", f"repos/{REPO}/releases/42"]
        return args(stdout=json.dumps(draft))

    monkeypatch.setattr(subprocess, "run", execute)
    assert rc.release_lookup(REPO, "v2") == draft
    assert len(calls) == 3


class GitHub:
    def __init__(self, monkeypatch, existing=None, assets=None):
        self.release = existing
        self.assets = assets or {}
        self.calls = []
        self.corrupt = False
        self.fail_upload = False
        monkeypatch.setattr(rc, "release_lookup", self.lookup)
        monkeypatch.setattr(rc, "run", self.run)
        monkeypatch.setattr(rc, "download", self.download)
        monkeypatch.setattr(rc, "verify_tag_commit", lambda *_: None)

    def lookup(self, repository, tag):
        if self.release is not None:
            self.release["assets"] = [{"name": name} for name in self.assets]
        return copy.deepcopy(self.release)

    def download(self, repository, tag, name, directory):
        (Path(directory) / name).write_bytes(
            b"corrupt" if self.corrupt else self.assets[name]
        )

    def run(self, *command):
        self.calls.append(command)
        operation = command[2]
        if operation == "create":
            self.release = release("v2", draft=True)
        elif operation == "upload":
            if self.fail_upload:
                raise rc.CatalogueError("upload failure")
            assert self.release is not None
            assert self.release["draft"]
            path = Path(command[4])
            self.assets[path.name] = path.read_bytes()
        elif operation == "edit":
            assert self.release is not None
            self.release["draft"] = False
        else:
            pytest.fail(f"Unexpected operation: {command}")
        return ""


def publish_args(directory):
    return args(repository=REPO, tag="v2", commit=COMMIT, assets_dir=directory)


def test_publish_verifies_before_last_operation_and_is_idempotent(work, monkeypatch):
    directory, _ = catalogue(work, [item()], monkeypatch, tag="v2")
    github = GitHub(monkeypatch)
    rc.publish(publish_args(directory))
    assert [call[2] for call in github.calls] == ["create", "upload", "upload", "edit"]
    assert github.calls[-1][-2:] == ("--draft=false", "--latest")
    before = list(github.calls)
    rc.publish(publish_args(directory))
    assert github.calls == before


def test_publish_uses_real_draft_aware_lookup(work, monkeypatch):
    directory, _ = catalogue(work, [item()], monkeypatch, tag="v2")
    lookup, run = rc.release_lookup, rc.run
    github = GitHub(monkeypatch)
    monkeypatch.setattr(rc, "release_lookup", lookup)
    monkeypatch.setattr(rc, "run", run)
    api_calls = []

    def execute(command, **kwargs):
        assert kwargs["check"] is True
        if command[1] != "api":
            return args(stdout=github.run(*command))
        api_calls.append(command)
        current = github.lookup(REPO, "v2")
        if current is not None:
            current["id"] = 42
        if "/releases/tags/" in command[-1]:
            if current is None or current["draft"]:
                raise subprocess.CalledProcessError(
                    1, command, stderr="gh: Not Found (HTTP 404)"
                )
            return args(stdout=json.dumps(current))
        if "--paginate" in command:
            return args(
                stdout=json.dumps([[release("v1")], [current] if current else []])
            )
        assert command[-1] == f"repos/{REPO}/releases/42"
        return args(stdout=json.dumps(current))

    monkeypatch.setattr(subprocess, "run", execute)
    rc.publish(publish_args(directory))
    assert github.calls[-1][2] == "edit"
    assert sum(call[2] == "create" for call in github.calls) == 1
    assert any(call[-1] == f"repos/{REPO}/releases/42" for call in api_calls)
    before = list(github.calls)
    rc.publish(publish_args(directory))
    assert github.calls == before


def test_publish_never_publishes_corrupt_assets(work, monkeypatch):
    directory, _ = catalogue(work, [item()], monkeypatch, tag="v2")
    existing = release("v2", draft=True)
    github = GitHub(monkeypatch, existing)
    github.corrupt = True
    with pytest.raises(rc.CatalogueError):
        rc.publish(publish_args(directory))
    assert github.release is not None
    assert github.release["draft"]
    assert not any(call[2] == "edit" for call in github.calls)


def test_resume_partial_draft_and_preserve_unrelated_assets(work, monkeypatch):
    directory, _ = catalogue(work, [item()], monkeypatch, tag="v2")
    github = GitHub(
        monkeypatch, release("v2", draft=True), {"notes.txt": b"user asset"}
    )
    rc.publish(publish_args(directory))
    assert github.assets["notes.txt"] == b"user asset"
    assert not any(call[2] == "create" for call in github.calls)


def test_published_mismatch_never_modified(work, monkeypatch):
    directory, _ = catalogue(work, [item()], monkeypatch, tag="v2")
    assets = {path.name: path.read_bytes() for path in directory.iterdir()}
    assets[rc.CATALOGUE] = b"{}"
    github = GitHub(monkeypatch, release("v2"), assets)
    with pytest.raises(rc.CatalogueError, match="differs"):
        rc.publish(publish_args(directory))
    assert github.calls == []


def test_reject_url_provenance(work, monkeypatch):
    directory, value = catalogue(work, [item()], monkeypatch)
    value["pipelines"][0]["commands"][0][
        "url"
    ] = "https://github.com/other/repo/releases/download/v1/command.json"
    with pytest.raises(rc.CatalogueError, match="provenance"):
        rc.validate_catalogue(value, directory)


def test_schema_is_valid():
    rc.jsonschema.Draft202012Validator.check_schema(rc.read_json(rc.SCHEMA))


def test_tag_commit_verification(monkeypatch):
    calls = []

    def execute(*command):
        calls.append(command)
        if len(calls) == 1:
            return json.dumps({"object": {"type": "tag", "sha": "d" * 40}})
        return json.dumps({"object": {"type": "commit", "sha": COMMIT}})

    monkeypatch.setattr(rc, "run", execute)
    rc.verify_tag_commit(REPO, "v1", COMMIT)
    assert len(calls) == 2
    with pytest.raises(rc.CatalogueError, match="source commit"):
        rc.verify_tag_commit(REPO, "v1", "c" * 40)


def test_previous_invalid_catalogue_never_becomes_bootstrap(work, monkeypatch):
    directory, value = catalogue(work / "source", [item()], monkeypatch)
    asset = value["pipelines"][0]["commands"][0]["path"]
    (directory / asset).write_text("{}")
    monkeypatch.setattr(
        rc,
        "release_list",
        lambda _: [release("v1", [path.name for path in directory.iterdir()])],
    )
    monkeypatch.setattr(
        rc,
        "download",
        lambda repo, tag, name, destination: shutil.copyfile(
            directory / name, Path(destination) / name
        ),
    )
    with pytest.raises(rc.CatalogueError):
        rc.previous(args(repository=REPO, tag="v2", output_dir=work / "previous"))
    assert not (work / "previous").exists()


def test_duplicate_runtime_command_names_rejected(work, monkeypatch):
    directory, value = catalogue(work, [item(), item("other")], monkeypatch)
    for pipeline in value["pipelines"]:
        command = pipeline["commands"][0]
        document = rc.read_json(directory / command["path"])
        document["name"] = "common.run"
        data = rc.json_bytes(document)
        (directory / command["path"]).write_bytes(data)
        command["sha256"] = rc.hashlib.sha256(data).hexdigest()
    with pytest.raises(rc.CatalogueError, match="Duplicate runtime"):
        rc.validate_catalogue(value, directory)


def test_invalid_local_assets_cannot_even_create_draft(work, monkeypatch):
    directory, value = catalogue(work, [item()], monkeypatch, tag="v2")
    asset = value["pipelines"][0]["commands"][0]["path"]
    (directory / asset).write_text("{}")
    github = GitHub(monkeypatch)
    with pytest.raises(rc.CatalogueError):
        rc.publish(publish_args(directory))
    assert github.release is None
    assert github.calls == []
