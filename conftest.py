import os
import logging
import shutil
from pathlib import Path
from tempfile import mkdtemp
import pytest


# Set DEBUG logging for unittests

debug_level = logging.WARNING

logger = logging.getLogger('arcana')
logger.setLevel(debug_level)
sch = logging.StreamHandler()
sch.setLevel(debug_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sch.setFormatter(formatter)
logger.addHandler(sch)


TEST_DATA_DIR = Path(__file__).parent / 'tests' / 'data'

@pytest.fixture
def test_data_dir():
    return TEST_DATA_DIR


@pytest.fixture
def work_dir():
    # We need to use a directory in the repository tree to make sure it is
    # available from Docker on Mac (and Windows?) where only certain directories
    # are accessible
    yield TEST_DATA_DIR / 'work_dir'
    # shutil.rmtree(work_dir)

# For debugging in IDE's don't catch raised exceptions and let the IDE
# break at it
if os.getenv('_PYTEST_RAISE', "0") != "0":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call):
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo):
        raise excinfo.value
