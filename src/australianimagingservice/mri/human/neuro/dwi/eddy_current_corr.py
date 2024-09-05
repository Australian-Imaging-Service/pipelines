import pydra.mark
import logging
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3 import mrinfo, dirstat


logger = logging.getLogger(__name__)


def eddy_current_corr_wf(slice_to_volume: bool):
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    wf = pydra.Workflow(name="eddy_current_corr_wf", input_spec=["input"])

    wf.add(mrinfo(image_=wf.lzin.input, shell_bvalues=True, name="mrinfo"))

    wf.add(dirstat(image_=wf.lzin.input, output="asym", name="dirstat"))

    wf.add(
        eddy_requires_slm(
            mrinfo_shell_bvalues_out=wf.mrinfo_shell_bvalues_out.lzout.stdout,
            dirstat_asym_out=wf.dirstat_asym_out.lzout.stdout,
            name="eddy_requires_slm",
        )
    )

    wf.set_output()

    return wf


@pydra.mark.task
def eddy_requires_slm(mrinfo_shell_bvalues_out: str, dirstat_asym_out: str) -> bool:
    shell_bvalues = [
        int(round(float(value)))
        for value in mrinfo_shell_bvalues_out.split()
    ]
    shell_asymmetries = [
        float(value)
        for value in dirstat_asym_out.splitlines()
    ]
    # dirstat will skip any b=0 shell by default; therefore for correspondence between
    #   shell_bvalues and shell_symmetry, need to remove any b=0 from the former
    if len(shell_bvalues) == len(shell_asymmetries) + 1:
        shell_bvalues = shell_bvalues[1:]
    elif len(shell_bvalues) != len(shell_asymmetries):
        raise RuntimeError(
            "Number of b-values reported by mrinfo ("
            + str(len(shell_bvalues))
            + ") does not match number of outputs provided by dirstat ("
            + str(len(shell_asymmetries))
            + ")"
        )
    requires_slm = False
    for bvalue, asymmetry in zip(shell_bvalues, shell_asymmetries):
        if asymmetry >= 0.1:
            requires_slm = True
            logger.warning(
                "sampling of b="
                + str(bvalue)
                + " shell is "
                + ("strongly" if asymmetry >= 0.4 else "moderately")
                + " asymmetric; distortion correction may benefit from use of: "
                + '-eddy_options " ... --slm=linear ... "'
            )
    return requires_slm
