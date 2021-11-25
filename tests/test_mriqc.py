from arcana2.data.sets.bids import BidsFormat
from ais_pipelines.mri.neuro.mriqc import INPUTS, task


def test_mriqc(test_data_dir):

    kwargs = {}
    for inpt in INPUTS:
        esc_inpt = BidsFormat.escape_name(inpt)
        kwargs[esc_inpt] = test_data_dir / 'ses-01' / esc_inpt

    result = task(plugin='serial', **kwargs)
    print(result)