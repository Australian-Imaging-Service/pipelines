from pathlib import Path
from datetime import datetime
from click.testing import CliRunner
import json
import xnat4tests
from arcana.cli.deploy import build
from arcana.test.utils import show_cli_trace
from arcana.core.deploy.utils import load_yaml_spec
from arcana.test.stores.medimage.xnat import (
    install_and_launch_xnat_cs_command)

# Root package dir
pkg_dir = Path(__file__).parent.parent

# Customisable parameters of the debug run
spec_path = pkg_dir / 'pipeline-specs' / 'mri' / 'neuro' / 'bids' / 'fmriprep.yaml'
data_dir = pkg_dir / 'tests' / 'data' / 'specific-cases' / 'FTD1028'
inputs_json = {
    'T1w': '3d COR T1 a',
    'T2w': 'T2 FLAIR',
    'fMRI': 'Resting State.*',
    'Dataset_config': 'default'}
command_index = 0

# Relative directories
license_dir = pkg_dir / 'licenses'
build_dir = pkg_dir / 'scripts' / '.build' / spec_path.stem
build_dir.mkdir(exist_ok=True, parents=True)
run_prefix = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')
project_id = f'{run_prefix}_{spec_path.stem}_specific'


def build_image():
    runner = CliRunner()
    result = runner.invoke(
        build,
        [str(spec_path),
        'pipelines-core-specific-test',
        '--build_dir', str(build_dir),
        '--use-test-config',
        '--use-local-packages',
        '--raise-errors',
        '--license-dir', str(license_dir)],
        catch_exceptions=False)

    if result.exit_code != 0:
        raise Exception(show_cli_trace(result))


def upload_data():
    """
    Creates dataset for each entry in dataset_structures
    """

    with xnat4tests.connect() as login:
        login.put(f'/data/archive/projects/{project_id}')
    
    with xnat4tests.connect() as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label='testsubj',
                                        parent=xproject)
        xsession = xclasses.MrSessionData(label='testsession',
                                          parent=xsubject)
        for scan_path in data_dir.iterdir():
            if scan_path.name.startswith('.'):
                continue  # skip hidden files
            # Create scan
            xscan = xclasses.MrScanData(id=scan_path.stem, type=scan_path.stem,
                                        parent=xsession)
            
            for resource_path in scan_path.iterdir():
                # Create the resource
                xresource = xscan.create_resource(resource_path.stem)
                # Create the dummy files
                xresource.upload_dir(resource_path, method='tar_file')
        login.put(f'/data/experiments/{xsession.id}?pullDataFromHeaders=true')
        for xscan in xsession.scans.values():
            xscan.type = xscan.series_description


def run_container():
    spec = load_yaml_spec(spec_path)
    cmd_spec = spec['commands'][command_index]
    cmd_name = cmd_spec['name']

    with xnat4tests.connect() as xlogin:

        with open(build_dir / 'xnat_commands' / (cmd_spec['name'] + '.json')) as f:
            xnat_command = json.load(f)
        xnat_command['name'] = xnat_command['label'] = cmd_name + run_prefix
            
        test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))                

        workflow_id, status, out_str = install_and_launch_xnat_cs_command(
            command_json=xnat_command,
            project_id=project_id,
            session_id=test_xsession.id,
            inputs=inputs_json,
            xlogin=xlogin,
            timeout=30000)
        assert (
            status == "Complete"
        ), f"Workflow {workflow_id} failed.\n{out_str}"


if __name__ == '__main__':
    
    xnat4tests.launch_xnat()
    build_image()
    upload_data()
    run_container()
    