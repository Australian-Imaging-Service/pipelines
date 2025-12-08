import json
import typing as ty
from pathlib import Path
from pydra2app.core.cli import make
from frametree.core.cli import install_license
from pydra2app.xnat import XnatApp
from frametree.core.utils import show_cli_trace
from frametree.xnat import Xnat
from pydra2app.xnat.deploy import install_and_launch_xnat_cs_command
from fileformats.text import Plain as PlainText
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

FREESURFER_LICENSE_PATH = Path(
    PKG_DIR / "tests" / "data" / "licenses" / "freesurfer_license.txt"
)


RESOURCES_DIR = PKG_DIR / "resources"

SKIP_BUILD = False


def test_t1_preprocess_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    xnat_repository: Xnat,
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

    frameset = xnat_repository.define_frameset(project_id)
    frameset.install_license("freesurfer", PlainText(FREESURFER_LICENSE_PATH))

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

    command_inputs = {
        "single_parc": {
            "T1w": "t1_mprage_sag_p2_iso_1_ADNI",
            "Parcellation": "desikan",
            "FastSurferBatchSize": 4,
            "FastSurferNThreads": 4,
        },
        "all_parcs": {
            "T1w": "t1_mprage_sag_p2_iso_1_ADNI",
            "FastSurferBatchSize": 4,
            "FastSurferNThreads": 4,
        },
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
