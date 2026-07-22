import json
import typing as ty
from pathlib import Path
from pydra2app.core.cli import make
from pydra2app.xnat import XnatApp
from frametree.core.utils import show_cli_trace
from frametree.xnat import Xnat
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
    / "dwi"
    / "tractography_connectomics.yaml"
)

SKIP_BUILD = False


def test_tractography_connectomics_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    xnat_repository: Xnat,
    cli_runner: ty.Callable[..., ty.Any],
    tmp_path: Path,
):
    # NOTE: This test requires pre-processed outputs from both the DWI
    # preprocessing and T1 preprocessing pipelines to be available in the test
    # data directory (tests/data/specs/mri/human/neuro/dwi/tractography_connectomics/).
    # Upload those outputs as NIfTI/MIF scan resources so XNAT can source them.

    build_dir = tmp_path / "build"
    build_dir.mkdir(exist_ok=True, parents=True)

    project_id = f"{run_prefix}mrihumanneurodwitractography"

    test_data = (
        test_data_dir
        / "specs"
        / "mri"
        / "human"
        / "neuro"
        / "dwi"
        / "tractography_connectomics"
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
            "--for-localhost",
            "--use-local-packages",
            "--raise-errors",
        ],
    )

    assert result.exit_code == 0, show_cli_trace(result)

    image_spec = XnatApp.load(SPEC_PATH)

    # Scan-type names must match the SeriesDescription (DICOM) or folder name
    # (NIfTI) of the resources uploaded by upload_test_dataset_to_xnat.
    # The tractography command consumes outputs produced by the DWI and T1
    # preprocessing pipelines; update these names to match whatever resource
    # labels those pipelines write back to XNAT.
    command_inputs = {
        "tractography": {
            "DwiPreprocessed": "dwi_processed",
            "DwiMask": "dwimask_processed",
            "FSDir": "FS_outputs",
            "FTTvisImage": "5TTvis_hsvs",
            "FTTImage": "5TT_hsvs",
            "ResponseWM": "response_wm",
            "ResponseGM": "response_gm",
            "ResponseCSF": "response_csf",
            "FodAlgorithm": "msmt_csd",
        },
        "connectomics": {
            "Tracks": "tracks",
            "OutWeights": "sift2_weights",
            "OutMu": "sift2_mu",
            "ParcellationImageT1space": "Atlas_desikan",
            "ParcellationStem": "desikan",
            "DwiT1space": "DWI_T1space",
            "DwiMaskT1space": "DWImask_T1space",
            "WmFodNorm": "wmfod_norm",
            "GmFodNorm": "gmfod_norm",
            "CsfFodNorm": "csffod_norm",
            "TDIFile": "TDI",
            "DECTDIFile": "DECTDI",
            "FodAlgorithm": "msmt_csd",
            "FTTMethod": "hsvs",
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
                "--work /work "
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
