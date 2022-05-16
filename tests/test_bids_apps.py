import json
from arcana.cli.deploy import build
from arcana.core.utils import path2varname
from arcana.test.utils import show_cli_trace
from arcana.deploy.medimage.xnat import path2xnatname
from arcana.core.deploy.utils import load_yaml_spec
from arcana.test.stores.medimage.xnat import (
    install_and_launch_xnat_cs_command)


SKIP_BUILD = True
    
def test_bids_app(bids_app_spec_and_project, run_prefix, xnat_connect, cli_runner):

    bids_app_spec_path, project_id = bids_app_spec_and_project

    build_dir = bids_app_spec_path.parent / '.build' / bids_app_spec_path.stem
    
    build_dir.mkdir(exist_ok=True, parents=True)

    if SKIP_BUILD:
        build_arg = '--generate-only'
    else:
        build_arg = '--build'

    result = cli_runner(
        build,
        [str(bids_app_spec_path),
        'australianimagingservice',
        '--build_dir', str(build_dir),
        build_arg,
        '--use-test-config',
        '--use-local-packages', '--raise-errors'])

    assert result.exit_code == 0, show_cli_trace(result)
    
    spec = load_yaml_spec(bids_app_spec_path)
    
    for cmd_spec in spec['commands']:

        cmd_name = cmd_spec['name']
        
        project_id = run_prefix + cmd_name

        with xnat_connect() as xlogin:

            with open(build_dir / 'xnat_commands' / (cmd_spec['name'] + '.json')) as f:
                xnat_command = json.load(f)
            xnat_command['name'] = xnat_command['label'] = cmd_name + run_prefix
                
            test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))                
                
            inputs_json = {}

            for inpt in cmd_spec['inputs']:
                inputs_json[path2xnatname(inpt['path'])] = path2varname(inpt['path'])

            # for pname in cmd_spec['parameters']:
            #     launch_json[pname] = pval
                
            workflow_id, status, out_str = install_and_launch_xnat_cs_command(
                command_json=xnat_command,
                project_id=project_id,
                session_id=test_xsession.id,
                inputs=inputs_json,
                xlogin=xlogin)

            assert (
                status == "Complete"
            ), f"Workflow {workflow_id} failed.\n{out_str}"

            # for deriv in blueprint.derivatives:
            #     assert list(test_xsession.resources[deriv.name].files) == deriv.filenames
    