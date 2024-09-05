import logging
import typing as ty
from pathlib import Path
import pydra.mark
from pydra.engine.specs import SpecInfo, ShellSpec, ShellOutSpec
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3 import mrtransform


logger = logging.getLogger(__name__)


def susceptibility_estimation_wf(have_se_epi: bool, se_epi_to_dwi_merge: str):
    """Estimate susceptibility-induced field inhomogeneity

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    wf = pydra.Workflow(
        name="susceptibility_estimation_wf", input_spec=["input, se_epi, se_dims_match"]
    )

    if have_se_epi:
        # Newest version of eddy requires that topup field be on the same grid as the eddy input DWI
        if not image.match(dwi_header, se_epi_header, up_to_dim=3):
            logger.info(
                "DWIs and SE-EPI images used for inhomogeneity field estimation are defined on different image grids; "
                "the latter will be automatically re-gridded to match the former"
            )
            new_se_epi_path = "se_epi_regrid.mif"
            wf.add(
                mrtransform(
                    input=wf.lzin.se_epi,
                    tempate=wf.import_dwi.lzout.output,
                    reorient_fod="no",
                    interp="sinc",
                    name="regrid_seepi_to_dwi_transform",
                )
            )

            regrid_seepi_to_dwi_input_spec = SpecInfo(
                name="Input",
                fields=[
                    (
                        "input",
                        Mif,
                        {
                            "help_string": "input image",
                            "argstr": "",
                            "position": 0,
                            "mandatory": True,
                        },
                    ),
                    (
                        "operand",
                        float,
                        {
                            "help_string": "operand",
                            "argstr": "",
                            "position": 1,
                            "mandatory": True,
                        },
                    ),
                    (
                        "operator",
                        str,
                        {
                            "help_string": "the operation to apply",
                            "argstr": "-{operator}",
                            "position": 2,
                            "mandatory": True,
                        },
                    ),
                    (
                        "output",
                        Path,
                        {
                            "help_string": "the operation to apply",
                            "argstr": "",
                            "position": -1,
                            "output_file_template": "output.mif",
                            "mandatory": True,
                        },
                    ),
                ],
                bases=(ShellSpec,),
            )

            regrid_seepi_to_dwi_output_spec = SpecInfo(
                name="Output",
                fields=[
                    (
                        "output",
                        Mif,
                        {
                            "help_string": "the output file",
                            "argstr": "--tval",
                            "position": -1,
                            "mandatory": True,
                        },
                    ),
                ],
                bases=(ShellOutSpec,),
            )

            ###########################
            # mri_surf2surf task - lh #
            ###########################

            wf.add(
                ShellCommandTask(
                    name="regrid_seepi_to_dwi_nonnegative",
                    executable="mrcalc",
                    input_spec=regrid_seepi_to_dwi_input_spec,
                    output_spec=regrid_seepi_to_dwi_output_spec,
                    input=wf.regrid_seepi_to_dwi_transform.lzout.output,
                    operand=0.0,
                    operator="max",
                )
            )

    wf.set_output(
        [("", wf.num_encodings.lzout.num_encodings)],
    )

    return wf


@pydra.mark.task
@pydra.mark.annotate(
    {
        "return": {
            
        }
    }
)
def a(
    
) -> bool:
    pass