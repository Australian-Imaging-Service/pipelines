import typing as ty
from logging import getLogger
from fileformats.vendor.mrtrix3 import ImageFormat as Mif
from pydra.compose import workflow
from pydra.tasks.mrtrix3.v3_1 import DwiRecon


logger = getLogger(__name__)


@workflow.define(outputs=["output"])
def VolumeRecombination(
    in_file: Mif,
    volume_pairs: ty.List[ty.Tuple[int, int]] | None = None,
) -> Mif:
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    dwi_recon = workflow.add(
        DwiRecon(
            in_file=in_file,
            volume_pairs=volume_pairs,
        )
    )

    return dwi_recon.out_file
