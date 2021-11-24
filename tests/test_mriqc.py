from arcana2.data.sets.bids import BidsFormat
from ais_pipelines.mri.neuro.mriqc import INPUTS, task
from ais_pipelines.utils import test_data_dir


def test_mriqc():

    kwargs = {}
    for inpt in INPUTS:
        esc_inpt = BidsFormat.escape_name(inpt)
        kwargs[esc_inpt] = test_data_dir / esc_inpt

    result = task(id='1', plugin='serial', **kwargs)
    print(result)