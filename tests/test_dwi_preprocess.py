import json
import typing as ty
from pathlib import Path
from pydra2app.core.cli import make
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
    / "dwi"
    / "preprocess.yaml"
)

FREESURFER_LICENSE_PATH = Path(
    PKG_DIR / "tests" / "data" / "licenses" / "freesurfer_license.txt"
)

RESOURCES_DIR = PKG_DIR / "resources"

SKIP_BUILD = False

# These must match the DICOM SeriesDescription of the corresponding scan
# directories under tests/data/specs/mri/human/neuro/dwi/preprocess/ (see
# conftest.py:upload_test_dataset_to_xnat, which derives the XNAT scan "type"
# from that header).
DWI_SCAN_TYPE = "dwi_AP"
RPE_SCAN_TYPE = "dwi_PA"


def test_dwi_preprocess_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    xnat_repository: Xnat,
    cli_runner: ty.Callable[..., ty.Any],
    tmp_path: Path,
):

    build_dir = tmp_path / "build"

    build_dir.mkdir(exist_ok=True, parents=True)

    project_id = f"{run_prefix}mrihumanneurodwipreprocess"

    test_data = (
        test_data_dir / "specs" / "mri" / "human" / "neuro" / "dwi" / "preprocess"
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

    # Two scenarios exercising the "RPE image may not always be provided" case:
    # rpe_none (DWI only) and rpe_pair (DWI + reverse phase-encode companion).
    scenarios = {
        "no_rpe": {
            "DWI": DWI_SCAN_TYPE,
            "RpeMode": "rpe_none",
        },
        "with_rpe": {
            "DWI": DWI_SCAN_TYPE,
            "RPE": RPE_SCAN_TYPE,
            "RpeMode": "rpe_pair",
        },
    }

    with xnat_connect() as xlogin:

        for command_obj in image_spec.commands:
            with open(build_dir / "xnat_commands" / (command_obj.name + ".json")) as f:
                command_json_template = json.load(f)

            test_xsession = next(
                iter(xlogin.projects[project_id].experiments.values())
            )

            for scenario_name, scenario_inputs in scenarios.items():
                command_json = dict(command_json_template)
                command_json["name"] = command_json["label"] = (
                    image_spec.name + command_obj.name + scenario_name + run_prefix
                )

                inputs_json = dict(scenario_inputs)
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
                assert (
                    status == "Complete"
                ), f"Workflow {workflow_id} ({scenario_name}) failed.\n{out_str}"
