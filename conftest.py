import os
import logging
from pathlib import Path
import tempfile
from datetime import datetime
import pytest
from click.testing import CliRunner
import xnat4tests

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
test_bids_data_dir = Path(__file__).parent / 'tests' / 'data' / 'mri' / 'neuro' / 'bids'

bids_specs = [str(p.stem) for p in bids_apps_dir.glob('*.yaml')]


@pytest.fixture(params=bids_specs)
def bids_app_spec_and_project(run_prefix, xnat_connect, request):
    bids_app_name = request.param
    project_id = make_project_name(bids_app_name, run_prefix=run_prefix)
    upload_test_dataset_to_xnat(project_id, test_bids_data_dir / bids_app_name,
                                xnat_connect)
    return bids_apps_dir / (bids_app_name+ '.yaml'), project_id


@pytest.fixture(scope='session')
def xnat_connect():
    xnat4tests.launch_xnat()
    yield xnat4tests.connect
    #xnat4tests.stop_xnat()


@pytest.fixture(scope='session')
def run_prefix():
    "A datetime string used to avoid stale data left over from previous tests"
    return datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')


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

TEST_SUBJECT_LABEL = 'TESTSUBJ'
TEST_SESSION_LABEL = 'TESTSUBJ_01'


def make_project_name(dataset_name: str, run_prefix: str=None):
    return (run_prefix if run_prefix else '') + dataset_name


def upload_test_dataset_to_xnat(project_id: str, source_data_dir: Path,
                                xnat_connect):
    """
    Creates dataset for each entry in dataset_structures
    """

    with xnat_connect() as login:
        login.put(f'/data/archive/projects/{project_id}')
    
    with xnat_connect() as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label=TEST_SUBJECT_LABEL,
                                        parent=xproject)
        xsession = xclasses.MrSessionData(label=TEST_SESSION_LABEL,
                                          parent=xsubject)
        for scan_path in source_data_dir.iterdir():
            # Create scan
            xscan = xclasses.MrScanData(id=scan_path.stem, type=scan_path.stem,
                                        parent=xsession)
            
            for resource_path in scan_path.iterdir():

                # Create the resource
                xresource = xscan.create_resource(resource_path.stem)
                # Create the dummy files
                xresource.upload_dir(resource_path, method='tar_file')

        # Populate metadata from DICOM headers
        # login.put(f'/data/experiments/{xsession.id}?pullDataFromHeaders=true')