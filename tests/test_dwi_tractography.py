import json
import typing as ty
from pathlib import Path
from fileformats.core import to_mime
from fileformats.generic import Directory
from pydra2app.core.cli import make
from pydra2app.xnat import XnatApp
from frametree.core.utils import show_cli_trace
from frametree.xnat import Xnat
from pydra2app.xnat.deploy import install_and_launch_xnat_cs_command
from conftest import test_data_dir, TEST_SUBJECT_LABEL, TEST_SESSION_LABEL

PKG_DIR = Path(__file__).parent.parent

SPEC_PATH = (
    PKG_DIR
    / "specs"
    / "australian-imaging-service"
    / "mri"
    / "human"
    / "neuro"
    / "dwi"
    / "tractography.yaml"
)

RESOURCES_DIR = PKG_DIR / "resources"

SKIP_BUILD = False

# Bundled outputs of the two upstream pipelines for the same session, as
# written by dwi/preprocess.yaml's `dwi_preprocess` sink and t1w/preprocess.yaml's
# all_parcs `t1w_preprocess` sink. Each sub-directory is uploaded as a
# session-level resource of that name, which is how those sinks store them.
TEST_DATA = test_data_dir / "specs" / "mri" / "human" / "neuro" / "dwi" / "tractography"
UPSTREAM_DERIVATIVES = ("dwi_preprocess", "t1w_preprocess")

# Kept small so the test exercises every step without the hours a realistic
# (10M streamline) run takes
NUM_STREAMLINES = "10000"


def upload_derivatives_to_xnat(
    project_id: str, source_data_dir: Path, xnat_connect: ty.Any
) -> None:
    """Create a session holding each upstream bundle as a session-level resource,
    formatted as a directory, the same way frametree-xnat creates them when the
    upstream pipelines sink their outputs"""
    with xnat_connect() as login:
        login.put(f"/data/archive/projects/{project_id}")

    with xnat_connect() as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label=TEST_SUBJECT_LABEL, parent=xproject)
        xsession = xclasses.MrSessionData(label=TEST_SESSION_LABEL, parent=xsubject)
        for label in UPSTREAM_DERIVATIVES:
            src = source_data_dir / label
            assert src.is_dir(), f"Missing test data directory {src}"
            xresource = xclasses.ResourceCatalog(
                parent=xsession,
                label=label,
                format=to_mime(Directory, official=False),
            )
            xresource.upload_dir(src, method="tar_file")


def test_dwi_tractography_app(
    run_prefix: str,
    xnat_connect: ty.Any,
    xnat_repository: Xnat,
    cli_runner: ty.Callable[..., ty.Any],
    tmp_path: Path,
):

    build_dir = tmp_path / "build"
    build_dir.mkdir(exist_ok=True, parents=True)

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

    project_id = f"{run_prefix}mrihumanneurodwitractography"
    upload_derivatives_to_xnat(project_id, TEST_DATA, xnat_connect)
    xnat_repository.define_frameset(project_id)

    # Sources referring to session-level derivatives are given as "<label>@"
    # (frametree's path syntax for a derivative in the default frameset),
    # rather than a scan type
    inputs = {
        "DWI_PREPROC": "dwi_preprocess@",
        "T1_PREPROC": "t1w_preprocess@",
        "FodAlgorithm": "msmt_csd",
        "FttMethod": "hsvs",
        "NumStreamlines": NUM_STREAMLINES,
        "pydra2app_flags": (
            "--worker debug "
            "--work /work "  # NB: work dir moved inside container due to file-locking issue on some mounted volumes (see https://github.com/tox-dev/py-filelock/issues/147)
            "--dataset-name default "
            "--logger frametree debug "
            "--logger frametree-xnat debug "
            "--logger pydra2app debug "
            "--logger pydra2app-xnat debug "
        ),
    }

    with xnat_connect() as xlogin:
        test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))

        for command_obj in image_spec.commands:
            with open(build_dir / "xnat_commands" / (command_obj.name + ".json")) as f:
                command_json = json.load(f)
            command_json["name"] = command_json["label"] = (
                image_spec.name + command_obj.name + run_prefix
            )

            workflow_id, status, out_str = install_and_launch_xnat_cs_command(
                command_json=command_json,
                project_id=project_id,
                session_id=test_xsession.id,
                inputs=inputs,
                xlogin=xlogin,
                timeout=30000,
            )
            assert status == "Complete", f"Workflow {workflow_id} failed.\n{out_str}"
