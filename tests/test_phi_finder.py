from pathlib import Path
from click.testing import CliRunner
from pipeline2app.core.cli import make
from frametree.core.utils import show_cli_trace

PKG_PATH = Path(__file__).parent.parent.absolute()

runner = CliRunner()


result = runner.invoke(
    make,
    [
        "xnat",
        (
            "{PKG_PATH}/specs/"
            "australian-imaging-service/quality-control/phi-finder.yaml"
        ),
        "--spec-root",
        "{PKG_PATH}/specs",
        "--registry",
        "ghcr.io",
        "--for-localhost",
        "--use-local-packages",
        "--raise-errors",
    ],
)

print(show_cli_trace(result))
