from pathlib import Path
from datetime import datetime
import json
import xnat
import shlex
import click
from click.testing import CliRunner
import xnat4tests
from arcana.test.utils import show_cli_trace
from arcana.cli.deploy import run_pipeline
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
    'Json_edits': '',
    'Dataset_config': 'default'}
command_index = 0

# Relative directories
image_tag = 'pipelines-core-specific-test/' + spec_path.stem
license_dir = pkg_dir / 'licenses'
build_dir = pkg_dir / 'scripts' / '.build' / 'specific-test-case'
build_dir.mkdir(exist_ok=True, parents=True)
run_prefix = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')
project_id = data_dir.stem  # f'{run_prefix}_{spec_path.stem}_specific'
pipelines_core_docker_dest = Path('/python-packages/pipelines-core')
session_label = 'testsession'
subject_label = 'testsubj'


def xnat_connect(in_docker):
    if in_docker:
        xlogin = xnat.connect(server="http://host.docker.internal:8080",
                              user=xnat4tests.config.XNAT_USER,
                              password=xnat4tests.config.XNAT_PASSWORD)
    else:
        xlogin = xnat4tests.connect()
    return xlogin


def build_image():

    spec = load_yaml_spec(spec_path, base_dir=spec_path)

    spec = {k: v for k, v in spec.items() if not k.startswith('_')}
    python_packages = spec['python_packages'] = spec.get('python_packages', [])
    python_packages.append({'name': 'pydra'})
    python_packages.append({'name': 'pydra-dcm2niix'})

    dockerfile = build_xnat_cs_image(
        image_tag=image_tag,
        build_dir=build_dir,
        use_local_packages=True,
        test_config=True,
        license_dir=license_dir,
        arcana_install_extras=['test'],
        generate_only=True,
        **spec)

    pkg_build_path = copy_package_into_build_dir('pipelines-core', pkg_dir,
                                                 build_dir)
    dockerfile.copy(source=[str(pkg_build_path.relative_to(build_dir))],
                    destination=str(pipelines_core_docker_dest))

    dockerfile_build(dockerfile, build_dir, image_tag)


def upload_data(in_docker=False):
    """
    Creates dataset for each entry in dataset_structures
    """

    with xnat_connect(in_docker) as login:
        if project_id in login.projects:
            return
        login.put(f'/data/archive/projects/{project_id}')
    
    with xnat_connect(in_docker) as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label=subject_label,
                                        parent=xproject)
        xsession = xclasses.MrSessionData(label=session_label,
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


def run_in_container_service():
    spec = load_yaml_spec(spec_path)
    cmd_spec = spec['commands'][command_index]
    cmd_name = cmd_spec['name']

    with xnat_connect(in_docker=False) as xlogin:

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


def run_directly():
    spec = load_yaml_spec(spec_path)
    cmd_spec = spec['commands'][command_index]

    with open(Path('/xnat_commands') / (cmd_spec['name'] + '.json')) as f:
        xnat_command = json.load(f)

    cmdline = xnat_command["command-line"].split('run-arcana-pipeline')[-1]

    # Do XNAT replacements
    cmdline = cmdline.replace('[PROJECT_ID]', project_id)
    cmdline = cmdline.replace('#DATASET_NAME#', inputs_json['Dataset_config'])
    cmdline = cmdline.replace('[SUBJECT_LABEL]', subject_label)
    cmdline = cmdline.replace('[SESSION_LABEL]', session_label)

    for k, v in inputs_json.items():
        if k != 'Dataset_config':
            cmdline = cmdline.replace(f'[{k.upper()}_INPUT]', f"{v}")

    runner = CliRunner()
    result = runner.invoke(
        run_pipeline,
        shlex.split(cmdline),
        catch_exceptions=False)

    assert result.exit_code == 0, show_cli_trace(result)


@click.command(help="run the test")
@click.option('--in_docker/--out-of-docker', type=bool, default=False,
              help="Whether the test is being run inside or out of docker")
@click.option('--build-only/--build-and-run', type=bool, default=False,
              help="Whether to just build the image instead of build and running")
def run(in_docker, build_only):

    if not in_docker:
        xnat4tests.launch_xnat()
        build_image()
    upload_data(in_docker=in_docker)
    if not build_only:
        if in_docker:
            run_directly()
        else:
            run_in_container_service()




if __name__ == '__main__':
    run()