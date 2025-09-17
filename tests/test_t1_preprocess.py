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
    / "mri"
    / "human"
    / "neuro"
    / "t1w"
    / "preprocess.yaml"
)

RESOURCES_DIR = PKG_DIR / "resources"

SKIP_BUILD = False


def test_t1_preprocess_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    cli_runner: ty.Callable[..., ty.Any],
    tmp_path: Path,
):

    build_dir = tmp_path / "build"

    build_dir.mkdir(exist_ok=True, parents=True)

    project_id = f"{run_prefix}mrihumanneurot1wpreprocess"
    test_data = (
        test_data_dir / "specs" / "mri" / "human" / "neuro" / "t1w" / "preprocess"
    )
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
            "--resources-dir",
            str(RESOURCES_DIR),
            "--for-localhost",
            "--use-local-packages",
            "--raise-errors",
        ],
    )

    assert result.exit_code == 0, show_cli_trace(result)

    image_spec = XnatApp.load(SPEC_PATH)

    with xnat_connect() as xlogin:

        with open(
            build_dir / image_spec.name / "xnat_commands" / (image_spec.name + ".json")
        ) as f:
            xnat_command = json.load(f)
        xnat_command.name = xnat_command.label = image_spec.name + run_prefix

        test_xsession = next(
            iter(xnat_connect.projects[project_id].experiments.values())
        )

        inputs_json = {
            "T1w": test_data / "T1w",
            "Parcellation": "desikan",
            "pydra2app_flags": (
                "--worker serial "
                "--work /work "  # NB: work dir moved inside container due to file-locking issue on some mounted volumes (see https://github.com/tox-dev/py-filelock/issues/147)
                "--dataset-name default "
                "--loglevel debug "
            ),
        }

        workflow_id, status, out_str = install_and_launch_xnat_cs_command(
            command_json=xnat_command,
            project_id=project_id,
            session_id=test_xsession.id,
            inputs=inputs_json,
            xlogin=xnat_connect,
            timeout=30000,
        )
        assert status == "Complete", f"Workflow {workflow_id} failed.\n{out_str}"
