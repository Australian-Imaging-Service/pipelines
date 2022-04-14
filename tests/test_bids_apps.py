from pathlib import Path
import pytest
from click.testing import CliRunner
from arcana.test.utils import show_cli_trace
from arcana.cli.deploy import build

neuro_dir = Path(__file__).parent.parent / 'australianimagingservice' / 'mri' / 'neuro'

specs = [str(p.stem) for p in neuro_dir.glob('*.yaml')]


@pytest.fixture(params=specs)
def spec_path(request):
    return str(neuro_dir / request.param) + '.yaml'


def test_bids_app_build(spec_path, cli_runner):
    result = cli_runner(
        build,
        [spec_path,
         'australianimagingservice',
        '--use-local-packages', '--raise-errors'])

    assert result.exit_code == 0, show_cli_trace(result)
    