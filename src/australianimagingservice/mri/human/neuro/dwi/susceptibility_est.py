import logging
import typing as ty
from pathlib import Path
import pydra.mark
from pydra.engine.task import ShellCommandTask
from pydra.engine.specs import SpecInfo, ShellSpec, ShellOutSpec
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3 import mrtransform


logger = logging.getLogger(__name__)


def susceptibility_estimation_wf(
    field_estimation_data_formation_strategy: str,
    requires_regrid: bool, 
):
    """Estimate susceptibility-induced field inhomogeneity

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """
    assert field_estimation_data_formation_strategy != 'none'
    
    wf = pydra.Workflow(
        name="susceptibility_estimation_wf", input_spec=["input", "dwi_first_bzero_index", "se_epi"]
    )

    if requires_regrid:
        wf.add(
            mrtransform(
                input=wf.lzin.se_epi,
                tempate=wf.lzin.input,
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
        se_epi_for_concatenation = wf.regrid_seepi_to_dwi_nonnegative.lzout.output
    else:
        se_epi_for_concatenation = wf.lzin.se_epi

    # Done regridding if necessary



    if field_estimation_data_formation_strategy == "se_epi_standalone":

        wf.add(mrconvert(input=wf.lzin.se_epi, export_pe_table="...", name='convert_se_epi_nifti'))

    elif field_estimation_data_formation_strategy == "se_epi_concat_bzero_unbalanced":

        wf.add(mrconvert(input=wf.lzin.input, coord=(3, dwi_first_bzero_index), name='dwi_extract_first_bzero'))
        wf.add(mrcat(inputs=[wf.dwi_extract_first_bzero.lzout.out], wf.lzin.se_epi, axis=3, name='concat_bzero_se_epi'))

    elif field_estimation_data_formation_strategy == "se_epi_concat_bzero_balanced":

        pass

    elif field_estimation_data_formation_strategy == "bzeros":

        wf.add(dwiextract(input=wf.lzin.input, bzero=True, name='dwi_extract_bzeros'))

    else:

        assert False

        




        

    wf.set_output(
        [("", wf.num_encodings.lzout.num_encodings)],
    )

    return wf


@pydra.mark.task
@pydra.mark.annotate({"return": {}})
def a() -> bool:
    pass
