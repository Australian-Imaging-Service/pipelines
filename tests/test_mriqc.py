import shutil
from pathlib import Path
from arcana2.core.utils import path2name
from ais.mri.neuro.mriqc import INPUTS, metadata, task



def test_mriqc_task(test_data_dir: Path, work_dir: Path):

    kwargs = {}
    for inpt, dtype in INPUTS.items():
        esc_inpt = path2name(inpt)
        kwargs[esc_inpt] = test_data_dir / 'nifti' / 'ses-01' / (esc_inpt  + dtype.ext)

    print(f"Running MRIQC on {work_dir}/bids dataset")

    work_dir.mkdir(exist_ok=True)
    bids_dir = work_dir / (metadata['name'] + '-bids')

    shutil.rmtree(bids_dir, ignore_errors=True)

    result = task(dataset=bids_dir)(plugin='serial', id='DEFAULT', **kwargs)

    assert (Path(result.output.mriqc) / 'sub-DEFAULT_T1w.html').exists()
