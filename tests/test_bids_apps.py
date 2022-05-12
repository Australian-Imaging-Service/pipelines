from pathlib import Path
import pytest
from arcana.test.utils import show_cli_trace
from arcana.cli.deploy import build

neuro_dir = Path(__file__).parent.parent / 'pipeline-specs' / 'mri' / 'neuro'

specs = [str(p.stem) for p in neuro_dir.glob('*.yaml')]


@pytest.fixture(params=specs)
def spec_path(request):
    return str(neuro_dir / request.param) + '.yaml'


def test_bids_app_build(spec_path, cli_runner, work_dir):
    result = cli_runner(
        build,
        [spec_path,
         'docker-specs/mri/neuro',
         '--build_dir', work_dir,
         '--use-local-packages', '--raise-errors'])

    assert result.exit_code == 0, show_cli_trace(result)
    
    
def test_bids_app_run(nifti_data, spec_path, cli_runner):

    pass
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
