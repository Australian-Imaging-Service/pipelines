from pathlib import Path
from click.testing import CliRunner
from pydra2app.core.cli import make
from frametree.core.utils import show_cli_trace
import xnat4tests
from pydra2app.xnat.deploy import install_cs_command, launch_cs_command

PKG_PATH = Path(__file__).parent.parent.absolute()

runner = CliRunner()


def test_phi_finder():
    result = runner.invoke(
        make,
        [
            "xnat",
            (
                f"{PKG_PATH}/specs/"
                "australian-imaging-service/quality-control/phi-finder.yaml"
            ),
            "--spec-root",
            f"{PKG_PATH}/specs",
            "--registry",
            "ghcr.io",
            "--for-localhost",
            "--use-local-packages",
            "--raise-errors",
        ],
    )

    assert not result.exit_code, show_cli_trace(result)

    xlogin = xnat4tests.connect()

    cmd_id = install_cs_command(
        "ghcr.io/australian-imaging-service/quality-control.phi-finder:2025.8.1",
        xlogin,
        enable=True,
        projects_to_enable=["dummydicomproject"],
        replace_existing=True,
        command_name="phi-finder",
    )

    launch_cs_command(
        cmd_id,
        xlogin=xlogin,
        inputs={},
        project_id="dummydicomproject",
        session_id="dummydicomsession",
    )
