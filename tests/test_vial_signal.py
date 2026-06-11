import json
import typing as ty
from pathlib import Path
from pydra2app.core.cli import make
from pydra2app.xnat import XnatApp
from frametree.core.utils import show_cli_trace
from pydra2app.xnat.deploy import install_and_launch_xnat_cs_command
from conftest import upload_test_dataset_to_xnat, test_data_dir

PKG_DIR = Path(__file__).parent.parent

SPEC_PATH = (
    PKG_DIR
    / "specs"
    / "australian-imaging-service"
    / "quality-control"
    / "phantoms"
    / "gsp-spirit.yaml"
)

SKIP_BUILD = False


def test_vial_signal_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    cli_runner: ty.Callable[..., ty.Any],
    tmp_path: Path,
):

    build_dir = tmp_path / "build"

    build_dir.mkdir(exist_ok=True, parents=True)

    project_id = f"{run_prefix}qualitycontrolgspspirit"

    test_data = test_data_dir / "specs" / "quality-control" / "phantoms" / "gsp-spirit"
    upload_test_dataset_to_xnat(project_id, test_data, xnat_connect)

    if SKIP_BUILD:
        build_arg = "--generate-only"
    else:
        build_arg = "--build"

    result = cli_runner(
        make,
        [
            "xnat",
            str(SPEC_PATH),
            "--build-dir",
            str(build_dir),
            build_arg,
            "--for-localhost",
            "--use-local-packages",
            "--raise-errors",
        ],
    )

    assert result.exit_code == 0, show_cli_trace(result)

    image_spec = XnatApp.load(SPEC_PATH)

    command_inputs = {
        "gsp_spirit": {
            "in_file": "foo_bar",
        }
    }

    with xnat_connect() as xlogin:

        for command_obj in image_spec.commands:
            with open(build_dir / "xnat_commands" / (command_obj.name + ".json")) as f:
                command_json = json.load(f)
            command_json["name"] = command_json["label"] = (
                image_spec.name + command_obj.name + run_prefix
            )

            test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))

            inputs_json = command_inputs[command_obj.name]
            inputs_json["pydra2app_flags"] = (
                "--worker debug "
                "--work /work "  # NB: work dir moved inside container due to file-locking issue on some mounted volumes (see https://github.com/tox-dev/py-filelock/issues/147)
                "--dataset-name default "
                "--logger frametree debug "
                "--logger frametree-xnat debug "
                "--logger pydra2app debug "
                "--logger pydra2app-xnat debug "
            )

            workflow_id, status, out_str = install_and_launch_xnat_cs_command(
                command_json=command_json,
                project_id=project_id,
                session_id=test_xsession.id,
                inputs=inputs_json,
                xlogin=xlogin,
                timeout=30000,
            )
            assert status == "Complete", f"Workflow {workflow_id} failed.\n{out_str}"
