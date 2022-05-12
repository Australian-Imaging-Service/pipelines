from pathlib import Path
import pytest
from arcana.test.utils import show_cli_trace
from arcana.cli.deploy import build

neuro_dir = Path(__file__).parent.parent / 'docker-specs' / 'mri' / 'neuro'

specs = [str(p.stem) for p in neuro_dir.glob('*.yml')]


@pytest.fixture(params=specs)
def spec_path(request):
    return str(neuro_dir / request.param) + '.yaml'


def test_bids_app_build(spec_path, cli_runner):
    result = cli_runner(
        build,
        [spec_path,
         'docker-specs/mri/neuro',
        '--use-local-packages', '--raise-errors'])

    assert result.exit_code == 0, show_cli_trace(result)
    
    
def test_bids_app_run(nifti_data, spec_path, cli_runner):
    pass