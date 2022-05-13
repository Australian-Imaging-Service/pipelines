import time
import json
from pathlib import Path
import xnat4tests
from arcana.test.utils import show_cli_trace
from arcana.core.utils import resolve_class
from arcana.cli.deploy import build
from arcana.core.deploy.utils import load_yaml_spec
from arcana.test.fixtures.medimage import (
    create_dataset_data_in_repo,
    TestXnatDatasetBlueprint,
    ResourceBlueprint,
    ScanBlueprint)



# def test_bids_app_build(bids_app_spec_path, cli_runner, work_dir):
#     result = cli_runner(
#         build,
#         [bids_app_spec_path,
#          'australianimagingservice',
#          '--build_dir', str(work_dir),
#          '--use-local-packages', '--raise-errors'])

#     assert result.exit_code == 0, show_cli_trace(result)
    
    
def test_bids_app(nifti_data, bids_app_spec_path, cli_runner, run_prefix, xnat_host):

    bids_app_spec_path = Path(bids_app_spec_path)

    build_dir = bids_app_spec_path.parent / '.build' / bids_app_spec_path.stem
    
    build_dir.mkdir(exist_ok=True, parents=True)

    # result = cli_runner(
    #     build,
    #     [str(bids_app_spec_path),
    #      'australianimagingservice',
    #      '--build_dir', str(build_dir),
    #      '--use-local-packages', '--raise-errors'])

    # assert result.exit_code == 0, show_cli_trace(result)
    
    spec = load_yaml_spec(bids_app_spec_path)
    
    for cmd_spec in spec['commands']:
        cmd_name = cmd_spec['name']
        scan_blueprints = []
        for inpt in cmd_spec['inputs']:
            format_loc = inpt['format']
            format = resolve_class(format_loc, prefixes=['arcana.data.formats'])
            resource_name = format_loc.split(':')[-1]
            scan_blueprints.append(
                ScanBlueprint(
                    inpt['path'],
                    [ResourceBlueprint(
                        resource_name, format,
                        [inpt['path'] + '.' + e for e in format.all_exts()])]))
        
        blueprint = TestXnatDatasetBlueprint([1, 1, 1], scan_blueprints, {}, [])
        
        create_dataset_data_in_repo(cmd_name, blueprint,
                                    run_prefix=run_prefix, source_data=nifti_data)
        
        project_id = run_prefix + cmd_name

        with xnat4tests.connect() as xlogin:

            with open(build_dir / 'xnat_commands' / (cmd_name + '.json')) as f:
                xnat_command = json.load(f)

            cmd_id = xlogin.post("/xapi/commands", json=xnat_command).json()

            # Enable the command globally and in the project
            xlogin.put(f"/xapi/commands/{cmd_id}/wrappers/{cmd_name}/enabled")
            xlogin.put(
                f"/xapi/projects/{project_id}/commands/{cmd_id}/wrappers/{cmd_name}/enabled"
            )

            test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))

            launch_json = {"SESSION": f"/archive/experiments/{test_xsession.id}"}

            for inpt in cmd_spec['inputs']:
                launch_json[inpt['name']] = inpt['name']

            # for pname in cmd_spec['parameters']:
            #     launch_json[pname] = pval

            launch_result = xlogin.post(
                f"/xapi/projects/{project_id}/wrappers/{cmd_id}/root/SESSION/launch",
                json=launch_json
            ).json()

            assert launch_result["status"] == "success"
            workflow_id = launch_result["workflow-id"]
            assert workflow_id != "To be assigned"

            NUM_ATTEMPTS = 100
            SLEEP_PERIOD = 10
            max_runtime = NUM_ATTEMPTS * SLEEP_PERIOD

            INCOMPLETE_STATES = (
                "Pending",
                "Running",
                "_Queued",
                "Staging",
                "Finalizing",
                "Created",
            )

            for i in range(NUM_ATTEMPTS):
                wf_result = xlogin.get(f"/xapi/workflows/{workflow_id}").json()
                if wf_result["status"] not in INCOMPLETE_STATES:
                    break
                time.sleep(SLEEP_PERIOD)

            # Get workflow stdout/stderr for error messages if required
            out_str = ""
            stdout_result = xlogin.get(
                f"/xapi/workflows/{workflow_id}/logs/stdout", accepted_status=[200, 204]
            )
            if stdout_result.status_code == 200:
                out_str = f"stdout:\n{stdout_result.content.decode('utf-8')}\n"
            stderr_result = xlogin.get(
                f"/xapi/workflows/{workflow_id}/logs/stderr", accepted_status=[200, 204]
            )
            if stderr_result.status_code == 200:
                out_str += f"\nstderr:\n{stderr_result.content.decode('utf-8')}"

            assert (
                i != 99
            ), f"Workflow {workflow_id} did not complete in {max_runtime}.\n{out_str}"
            assert (
                wf_result["status"] == "Complete"
            ), f"Workflow {workflow_id} failed.\n{out_str}"

            # for deriv in blueprint.derivatives:
            #     assert list(test_xsession.resources[deriv.name].files) == deriv.filenames
    
    # blueprint = TestDatasetBlueprint(
    # hierarchy=[Clinical.subject, Clinical.session],
    # dim_lengths=[1, 1, 1],
    # files=["anat/T1w.nii.gz", "anat/T1w.json", "anat/T2w.nii.gz", "anat/T2w.json",
    #         "dwi/dwi.nii.gz", "dwi/dwi.json", "dwi/dwi.bvec", "dwi/dwi.bval"],
    # expected_formats={
    #     "anat/T1w": (NiftiGzX, ["T1w.nii.gz", "T1w.json"]),
    #     "anat/T2w": (NiftiGzX, ["T2w.nii.gz", "T2w.json"]),
    #     "dwi/dwi": (NiftiGzX, ["dwi.nii.gz", "dwi.json", "dwi.bvec", "dwi.bval"])},
    # derivatives=[('file1', Clinical.session, Text, ['file1.txt']),
    #                 ('file2', Clinical.session, Text, ['file2.txt'])])
        
    # dataset_path = work_dir / 'bids-dataset'
    
    # dataset = make_dataset(
    #     dataset_path=dataset_path,
    #     blueprint=blueprint,
    #     source_data=nifti_sample_dir)

    # dataset_id_str = f'file//{dataset_path}'
    # # Start generating the arguments for the CLI
    # # Add source to loaded dataset
    # args = [dataset_id_str, 'a_bids_app', 'arcana.tasks.bids.app:bids_app',
    #         '--plugin', 'serial',
    #         '--work', str(work_dir),
    #         '--configuration', 'executable', str(mock_bids_app_executable),
    #         '--dataset_space', class_location(blueprint.space),
    #         '--dataset_hierarchy', ','.join([str(l) for l in blueprint.hierarchy])]
    # inputs_config = []
    # for path, (format, _) in blueprint.expected_formats.items():
    #     format_str = class_location(format)
    #     args.extend(['--input', path2varname(path), format_str, path2varname(path), format_str])
    #     inputs_config.append({'path': path, 'format': format_str})
    # args.extend(['--configuration', 'inputs', json.dumps(inputs_config).replace('"', '\\"')])
    # outputs_config = []
    # for path, _, format, _ in blueprint.derivatives:
    #     format_str = class_location(format)
    #     args.extend(['--output', path, format_str, path2varname(path), format_str])
    #     outputs_config.append({'path': path, 'format': format_str})
    # args.extend(['--configuration', 'outputs', json.dumps(outputs_config).replace('"', '\\"')])
    
    # result = cli_runner(run_pipeline, args)
    # assert result.exit_code == 0, show_cli_trace(result)
    # # Add source column to saved dataset
    # for fname in ['file1', 'file2']:
    #     sink = dataset.add_sink(fname, Text)
    #     assert len(sink) == reduce(mul, dataset.blueprint.dim_lengths)
    #     for item in sink:
    #         item.get(assume_exists=True)
    #         with open(item.fs_path) as f:
    #             contents = f.read()
    #         assert contents == fname + '\n'
