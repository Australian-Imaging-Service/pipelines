import os
import logging
from pathlib import Path
import tempfile
import typing as ty
from datetime import datetime
from dataclasses import dataclass
from arcana.core.utils.misc import varname2path
import pytest
from click.testing import CliRunner
import xnat4tests

# Set DEBUG logging for unittests

debug_level = logging.WARNING

logger = logging.getLogger("arcana")
logger.setLevel(debug_level)

sch = logging.StreamHandler()
sch.setLevel(debug_level)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sch.setFormatter(formatter)
logger.addHandler(sch)


TEST_NIFTI_DATA_DIR = Path(__file__).parent / "tests" / "data" / "nifti"


@pytest.fixture(scope="session")
def license_src():
    return Path(__file__).parent / "licenses"


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


@dataclass
class BidsAppTestBlueprint:

    spec_path: str
    project_id: str
    parameters: ty.Dict[str, str]
    test_data: Path


BIDS_APP_PARAMETERS = {
    'fmriprep': {'json_edits': "func/.*bold \".SliceTiming[] /= 1000.0\""},
    'qsiprep': {'qsiprep_flags': '--output-resolution 2.5'}}


bids_apps_dir = Path(__file__).parent / "specs" / "mri" / "human" / "neuro" / "bidsapps"
test_bids_data_dir = (
    Path(__file__).parent / "tests" / "data" / "mri" / "human" / "neuro" / "bidsapps"
)

bids_specs = [str(p.stem) for p in bids_apps_dir.glob("*.yaml")]


@pytest.fixture(params=bids_specs)
def bids_app_blueprint(run_prefix, xnat_connect, request):
    bids_app_name = request.param
    project_id = make_project_id(bids_app_name, run_prefix=run_prefix)
    test_data = test_bids_data_dir / bids_app_name
    upload_test_dataset_to_xnat(project_id, test_data, xnat_connect)
    return BidsAppTestBlueprint(
        spec_path=bids_apps_dir / (bids_app_name + ".yaml"),
        project_id=project_id,
        parameters=BIDS_APP_PARAMETERS.get(bids_app_name, {}),
        test_data=test_data,
    )


@pytest.fixture(scope="session")
def xnat_connect():
    xnat4tests.start_xnat()
    yield xnat4tests.connect
    # xnat4tests.stop_xnat()


@pytest.fixture(scope="session")
def run_prefix():
    "A datetime string used to avoid stale data left over from previous tests"
    return datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")


# For debugging in IDE's don't catch raised exceptions and let the IDE
# break at it
if os.getenv("_PYTEST_RAISE", "0") != "0":

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
        result = runner.invoke(*args, catch_exceptions=catch_cli_exceptions, **kwargs)
        return result

    return invoke


TEST_SUBJECT_LABEL = "TESTSUBJ"
TEST_SESSION_LABEL = "TESTSUBJ_01"


def make_project_id(dataset_name: str, run_prefix: str = None):
    return (run_prefix if run_prefix else "") + dataset_name


def upload_test_dataset_to_xnat(project_id: str, source_data_dir: Path, xnat_connect):
    """
    Creates dataset for each entry in dataset_structures
    """

    with xnat_connect() as login:
        login.put(f"/data/archive/projects/{project_id}")

    with xnat_connect() as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label=TEST_SUBJECT_LABEL, parent=xproject)
        xsession = xclasses.MrSessionData(label=TEST_SESSION_LABEL, parent=xsubject)
        for test_scan_dir in source_data_dir.iterdir():
            if test_scan_dir.name.startswith("."):
                continue
            scan_id = test_scan_dir.stem
            scan_path = varname2path(scan_id)
            # Create scan
            xscan = xclasses.MrScanData(id=scan_id, type=scan_path, parent=xsession)

            for resource_path in test_scan_dir.iterdir():

                # Create the resource
                xresource = xscan.create_resource(resource_path.stem)
                # Create the dummy files
                xresource.upload_dir(resource_path, method="tar_file")

        # Populate metadata from DICOM headers
        # login.put(f'/data/experiments/{xsession.id}?pullDataFromHeaders=true')
