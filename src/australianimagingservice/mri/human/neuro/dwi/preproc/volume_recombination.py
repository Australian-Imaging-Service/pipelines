import typing as ty
from logging import getLogger
import pydra.mark
from pydra.tasks.mrtrix3.v3_2 import DwiRecon


logger = getLogger(__name__)


def volume_recombination_wf(
    volume_pairs: ty.List[ty.Tuple[int, int]] = None,
):
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    wf = pydra.Workflow(name="qc_wf", input_spec=["input", "volume_pairs"])

    wf.add(
        DwiRecon(
            in_file=wf.lzin.input,
            volume_pairs=wf.lzin.volume_pairs,
            name="dwi_recon",
        )
    )

    wf.set_output(
        [
            ("output", wf.dwi_recon.lzout.out_file),
        ],
    )

    return wf
