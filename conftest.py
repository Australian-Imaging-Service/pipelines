import os
import logging
from pathlib import Path
import tempfile
import pytest
from click.testing import CliRunner

# Set DEBUG logging for unittests

debug_level = logging.WARNING

logger = logging.getLogger('arcana')
logger.setLevel(debug_level)

sch = logging.StreamHandler()
sch.setLevel(debug_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sch.setFormatter(formatter)
logger.addHandler(sch)


TEST_NIFTI_DATA_DIR = Path(__file__).parent / 'tests' / 'data' / 'nifti'


@pytest.fixture
def nifti_data():
    return TEST_NIFTI_DATA_DIR


@pytest.fixture
def work_dir():
    # work_dir = Path.home() / '.arcana-tests'
    # work_dir.mkdir(exist_ok=True)
    # return work_dir
    work_dir = tempfile.mkdtemp()
    yield Path(work_dir)
    # shutil.rmtree(work_dir)
    

bids_apps_dir = Path(__file__).parent / 'pipeline-specs' / 'mri' / 'neuro' / 'bids'

bids_specs = [str(p.stem) for p in bids_apps_dir.glob('*.yaml')]


@pytest.fixture(params=bids_specs)
def bids_app_spec_path(request):
    return str(bids_apps_dir / request.param) + '.yaml'
    


# For debugging in IDE's don't catch raised exceptions and let the IDE
# break at it
if os.getenv('_PYTEST_RAISE', "0") != "0":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call):
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo):
        raise excinfo.value

    catch_cli_exceptions = False
else:
    catch_cli_exceptions = True


@pytest.fixture
def cli_runner():
    def invoke(*args, **kwargs):
        runner = CliRunner()
        result = runner.invoke(*args, catch_exceptions=catch_cli_exceptions,
                               **kwargs)
        return result
    return invoke
