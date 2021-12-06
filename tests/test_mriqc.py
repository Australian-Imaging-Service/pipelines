import shutil
from pathlib import Path
from arcana2.data.sets.bids import BidsFormat
from ais.mri.neuro.mriqc import INPUTS, metadata, task, docker_task


def test_mriqc(test_data_dir: Path, work_dir: Path):

    kwargs = {}
    for inpt, dtype in INPUTS.items():
        esc_inpt = BidsFormat.escape_name(inpt)
        kwargs[esc_inpt] = test_data_dir / 'ses-01' / (esc_inpt  + dtype.ext)

    print(f"Running MRIQC on {work_dir}/bids dataset")

    work_dir.mkdir(exist_ok=True)
    bids_dir = work_dir / (metadata['name'] + '-bids')

    shutil.rmtree(bids_dir, ignore_errors=True)

    result = task(plugin='serial',
                         dataset=bids_dir,
                         id='test',
                         **kwargs)

    assert (Path(result.output.mriqc) / 'sub-test_T1w.html').exists()
