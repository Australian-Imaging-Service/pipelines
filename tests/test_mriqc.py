import shutil
from pathlib import Path
from arcana2.core.utils import resolve_class
from australianimagingservice.mri.neuro.mriqc import spec



def test_mriqc_task(test_data_dir: Path, work_dir: Path):

    kwargs = {}

    cmd_spec = spec['commands'][0]

    task_location = 'australianimagingservice.mri.neuro.mriqc' + ':' + cmd_spec['pydra_task']
    task = resolve_class(task_location)

    for inpt, dtype in cmd_spec['inputs']:
        esc_inpt = inpt
        kwargs[esc_inpt] = test_data_dir / 'nifti' / 'ses-01' / (esc_inpt  + dtype.ext)

    print(f"Running MRIQC on {work_dir}/bids dataset")

    work_dir.mkdir(exist_ok=True)
    bids_dir = work_dir / (spec['package_name'] + '-bids')

    shutil.rmtree(bids_dir, ignore_errors=True)

    result = task(dataset=bids_dir,
                  virtualisation='docker')(plugin='serial', id='DEFAULT', **kwargs)

    assert (Path(result.output.mriqc) / 'sub-DEFAULT_T1w.html').exists()
