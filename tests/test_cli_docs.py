import os
from pathlib import Path
from click.testing import CliRunner
from pydra2app.core.cli import make_docs
from frametree.core.utils import show_cli_trace

PKG_PATH = Path(__file__).parent.parent.absolute()

runner = CliRunner()


def test_make_docs(tmp_path: Path) -> None:
    os.chdir(PKG_PATH)

    results = runner.invoke(
        make_docs,
        [
            str(PKG_PATH / "specs" / "australian-imaging-service"),
            str(tmp_path),
            "--flatten",
            "--default-axes",
            "medimage",
        ],
        catch_exceptions=False,
    )

    assert results.exit_code == 0, show_cli_trace(results)
    docs = list(tmp_path.glob("**/*.md"))
    assert len(docs) > 0
