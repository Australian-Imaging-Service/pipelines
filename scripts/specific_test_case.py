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
from arcana.core.deploy.build import copy_package_into_build_dir
from arcana.deploy.medimage.xnat import build_xnat_cs_image, dockerfile_build

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
image_tag = 'pipelines-core-specific-test/' + spec_path.stem
license_dir = pkg_dir / 'licenses'
build_dir = pkg_dir / 'scripts' / '.build' / 'specific-test-case'
build_dir.mkdir(exist_ok=True, parents=True)
run_prefix = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')
project_id = run_prefix + '_' + data_dir.stem  # f'{run_prefix}_{spec_path.stem}_specific'
pipelines_core_docker_dest = Path('/python-packages/pipelines-core')



def build_image():

    spec = load_yaml_spec(spec_path, base_dir=spec_path)

    dockerfile = build_xnat_cs_image(
        image_tag=image_tag,
        build_dir=build_dir,
        use_local_packages=True,
        test_config=True,
        license_dir=license_dir,
        generate_only=True,
        **{k: v for k, v in spec.items() if not k.startswith('_')})

    pkg_build_path = copy_package_into_build_dir('pipelines-core', pkg_dir,
                                                 build_dir)
    dockerfile.copy(source=[str(pkg_build_path.relative_to(build_dir))],
                    destination=str(pipelines_core_docker_dest))

    dockerfile_build(dockerfile, build_dir, image_tag)


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
    