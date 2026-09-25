"""Checks the catalogue producer's GitHub Actions handoff without publishing."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/release.yml"


@pytest.fixture
def jobs():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def step(job, name):
    return next(item for item in job["steps"] if item.get("name") == name)


def test_release_gating_permissions_and_queue(jobs):
    assert (
        jobs["build-and-deploy"]["if"]
        == "needs.discover-specs.outputs.has-builds == 'true'"
    )
    publisher = jobs["publish-catalogue"]
    assert publisher["needs"] == ["discover-specs", "build-and-deploy"]
    condition = publisher["if"]
    for required in (
        "always()",
        "!cancelled()",
        "github.event_name == 'push'",
        "startsWith(github.ref, 'refs/tags/')",
        "needs.discover-specs.result == 'success'",
        "needs.build-and-deploy.result == 'success' || needs.build-and-deploy.result == 'skipped'",
    ):
        assert required in condition
    assert step(publisher, "Download built entries")["if"] == (
        "needs.discover-specs.outputs.has-builds == 'true'"
    )
    for name in (
        "Push built Docker image",
        "Record immutable image and commands",
        "Upload immutable release entry",
    ):
        condition = step(jobs["build-and-deploy"], name)["if"]
        assert "github.event_name == 'push'" in condition
        assert "startsWith(github.ref, 'refs/tags/')" in condition
    assert publisher["steps"][-1]["name"] == "Publish complete GitHub Release"
    assert publisher["permissions"]["contents"] == "write"
    assert jobs["build-and-deploy"]["permissions"]["contents"] == "read"
    assert (
        "git merge-base --is-ancestor"
        in step(publisher, "Retrieve previous published catalogue")["run"]
    )
    concurrency = yaml.safe_load(WORKFLOW.read_text())["concurrency"]
    assert concurrency["queue"] == "max"
    assert concurrency["cancel-in-progress"] is False


def test_inventory_is_shared_with_builds_and_publication(jobs):
    assert jobs["discover-specs"]["needs"] == "validate-catalogue"
    upload = step(jobs["discover-specs"], "Upload release plan")["with"]
    assert set(upload["path"].split()) == {
        "release-plan.json",
        "release-inventory.json",
    }
    for job, name in (
        ("build-and-deploy", "Download release inventory"),
        ("publish-catalogue", "Download release plan and inventory"),
    ):
        assert step(jobs[job], name)["with"]["name"] == upload["name"]
    assert (
        'spec_args+=(--spec "$spec")'
        in step(jobs["discover-specs"], "Plan pipeline builds")["run"]
    )
    assert (
        "pip install ."
        in step(jobs["discover-specs"], "Install release planning dependencies")["run"]
    )


def test_matrix_artifacts_feed_publication(jobs):
    assert step(jobs["build-and-deploy"], "Upload immutable release entry")["with"][
        "name"
    ].startswith("pipeline-entry-")
    assert step(jobs["publish-catalogue"], "Download built entries")["with"] == {
        "pattern": "pipeline-entry-*",
        "path": "built-entries",
    }


def test_run_steps_have_valid_bash_syntax(jobs):
    for job in jobs.values():
        for item in job["steps"]:
            if "run" in item:
                result = subprocess.run(
                    ["bash", "-n"],
                    input=item["run"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                assert result.returncode == 0, (
                    item.get("name"),
                    result.stderr,
                )


@pytest.mark.parametrize("builds", [[], ["quality-control/phi-finder"]])
def test_planning_shell_hands_off_changed_and_unchanged_candidates(
    jobs, tmp_path, builds
):
    bash = shutil.which("bash")
    if Path("/opt/homebrew/bin/bash").exists():
        bash = "/opt/homebrew/bin/bash"
    assert bash
    major = subprocess.check_output([bash, "-c", "echo ${BASH_VERSINFO[0]}"], text=True)
    if int(major) < 4:
        pytest.skip("The workflow runs under Bash 4+ on Ubuntu")
    if not shutil.which("jq"):
        pytest.skip("The workflow's JSON handoff requires jq")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, body in {
        "pydra2app": 'printf "%s\\n" "$@" > cli-args.txt\nprintf "%s" "$TEST_PLAN"\n',
        "python": 'printf "%s\\n" "$@" > inventory-args.txt\n',
    }.items():
        executable = fake_bin / name
        executable.write_text("#!/bin/sh\nset -eu\n" + body)
        executable.chmod(0o755)
    selected = ["quality-control/phi-finder", "ct/human/abdomen/monai/spleen"]
    plan = {
        "build": builds,
        "unchanged": [spec for spec in selected if spec not in builds],
    }
    (tmp_path / "selected-specs.txt").write_text("\n".join(selected) + "\n")
    output = tmp_path / "github-output"
    env = {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        "GITHUB_OUTPUT": str(output),
        "TEST_PLAN": json.dumps(plan),
    }
    subprocess.run(
        [
            bash,
            "-e",
            "-o",
            "pipefail",
            "-c",
            step(jobs["discover-specs"], "Plan pipeline builds")["run"],
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert json.loads(outputs["specs"]) == builds
    assert outputs["has-builds"] == str(bool(builds)).lower()
    assert json.loads((tmp_path / "release-plan.json").read_text()) == plan
    assert (tmp_path / "cli-args.txt").read_text().splitlines()[-4:] == [
        "--spec",
        selected[0],
        "--spec",
        selected[1],
    ]
    assert (tmp_path / "inventory-args.txt").read_text().splitlines()[:3] == [
        "-m",
        "scripts.release_catalogue",
        "inventory",
    ]
