import os
from pathlib import Path
from click.testing import CliRunner
from pydra2app.core.cli import make_docs

PKG_PATH = Path(__file__).parent.parent.absolute()

runner = CliRunner()


def test_make_docs():
    os.chdir(PKG_PATH)

    results = runner.invoke(
        make_docs,
        [
            "australian-imaging-service",
            "docs/pipelines",
            "--flatten",
            "--default-axes",
            "medimage",
        ],
        catch_exceptions=False,
    )
