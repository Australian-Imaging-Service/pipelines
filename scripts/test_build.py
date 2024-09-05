from pathlib import Path
from click.testing import CliRunner
from pipeline2app.core.cli import make
from frametree.core.utils import show_cli_trace

PKG_PATH = Path(__file__).parent.parent.absolute()

runner = CliRunner()

results = runner.invoke(
    make,
    [
        f"{PKG_PATH}/australian-imaging-service/mri/human/neuro/bidsapps/fmriprep.yaml",
        "xnat:XnatApp",
        "--raise-errors",
    ],
    catch_exceptions=False,
)

print(show_cli_trace(results))
