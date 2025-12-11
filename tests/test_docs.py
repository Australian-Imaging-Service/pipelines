from pathlib import Path
from frametree.core.utils import show_cli_trace
from pydra2app.core.cli import make_docs
from conftest import specs_dir


def test_make_docs(bids_app_spec_path, cli_runner, work_dir: Path):
    result = cli_runner(make_docs, [bids_app_spec_path, str(work_dir)])

    assert result.exit_code == 0, show_cli_trace(result)


def test_make_all_docs(cli_runner, tmp_path: Path):
    result = cli_runner(
        make_docs,
        [
            str(specs_dir),
            "--spec-root",
            str(specs_dir),
            str(tmp_path / "output"),
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)
