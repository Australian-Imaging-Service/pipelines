from frametree.core.utils import show_cli_trace
from pydra2app.core.cli import make_docs
from conftest import specs_dir


def test_make_docs(bids_app_spec_path, cli_runner, work_dir):
    result = cli_runner(make_docs, [str(specs_dir), str(work_dir)])

    assert result.exit_code == 0, show_cli_trace(result)
