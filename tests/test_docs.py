from arcana.core.testing.utils import show_cli_trace
from arcana.cli.deploy import build_docs


def test_build_docs(bids_app_spec_path, cli_runner, work_dir):
    result = cli_runner(build_docs, [bids_app_spec_path, str(work_dir)])

    assert result.exit_code == 0, show_cli_trace(result)
