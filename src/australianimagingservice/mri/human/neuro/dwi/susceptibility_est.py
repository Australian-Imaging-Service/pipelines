import logging
import typing as ty
from pathlib import Path
import pydra.mark
from pydra.engine.task import ShellCommandTask
from pydra.engine.specs import SpecInfo, ShellSpec, ShellOutSpec
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3 import mrtransform, mrcat, mrconvert, dwiextract, mrgrid
from pydra.tasks.fsl import TOPUP


logger = logging.getLogger(__name__)

# This is a duplicate of the contents of $FSLDIR/etc/flirtsch/b02b0_4.cnf
# Note that 'scale' is changed from an int (0 or 1) to a boolean
TOPUP_CONFIG = {
    "warp_res": [20, 16, 14, 12, 10, 6, 4, 4, 4],
    # Subsampling level (a value of 2 indicates that a 2x2x2 neighbourhood is collapsed to 1 voxel)
    "subsamp": [4, 4, 2, 2, 2, 1, 1, 1, 1],
    # FWHM of gaussian smoothing
    "fwhm": [8, 6, 4, 3, 3, 2, 1, 0, 0],
    # Maximum number of iterations
    "miter": [5, 5, 5, 5, 5, 10, 10, 20, 20],
    # Relative weight of regularisation
    "reg_lambda": [
        0.035,
        0.006,
        0.0001,
        0.000015,
        0.000005,
        0.0000005,
        0.00000005,
        0.0000000005,
        0.00000000001,
    ],
    # If set to 1 lambda is multiplied by the current average squared difference
    "ssqlambda": 1,
    # Regularisation model
    "regmod": "bending_energy",
    # If set to 1 movements are estimated along with the field
    "estmov": [1, 1, 1, 1, 1, 0, 0, 0, 0],
    # "0": Levenberg-Marquardt, 1=Scaled Conjugate Gradient
    "minmet": [0, 0, 0, 0, 0, 1, 1, 1, 1],
    # Quadratic or cubic splines
    "splineorder": 3,
    # Precision for calculation and storage of Hessian
    "numprec": "double",
    # Linear or spline interpolation
    "interp": "spline",
    # If set to 1 the images are individually scaled to a common mean intensity
    "scale": True,
}


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
    assert field_estimation_data_formation_strategy != "none"

    wf = pydra.Workflow(
        name="susceptibility_estimation_wf",
        input_spec=["input", "dwi_first_bzero_index", "se_epi"],
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

    @pydra.mark.task
    def merge_list(in_1, in_2) -> list:
        return [in_1, in_2]

    # Done regridding if necessary
    field_estimation_input = None
    if field_estimation_data_formation_strategy == "se_epi_standalone":
        assert not requires_regrid
        field_estimation_input = wf.lzin.se_epi

    elif field_estimation_data_formation_strategy == "se_epi_concat_first_bzero":
        wf.add(
            mrconvert(
                input=wf.lzin.input,
                coord=(3, wf.lzin.dwi_first_bzero_index),
                name="dwi_extract_first_bzero",
            )
        )

        wf.add(
            merge_list(
                in_1=wf.dwi_extract_first_bzero.lzout.out,
                in_2=se_epi_for_concatenation,
                name="merge_bzero_se_epi",
            )
        )

        wf.add(
            mrcat(
                inputs=wf.merge_bzero_se_epi.lzout.out,
                axis=3,
                name="concat_bzero_se_epi",
            )
        )
        field_estimation_input = wf.concat_bzero_se_epi.lzout.out

    elif field_estimation_data_formation_strategy == "se_epi_concat_all_bzeros":
        wf.add(dwiextract(input=wf.lzin.input, bzero=True, name="dwi_extract_bzeros"))
        wf.add(
            merge_list(
                in_1=wf.dwi_extract_bzeros.lzout.out,
                in_2=se_epi_for_concatenation,
                name="merge_bzero_se_epi",
            )
        )
        wf.add(
            mrcat(inputs=wf.merge_bzero_se_epi.out, axis=3, name="concat_bzero_se_epi")
        )
        field_estimation_input = wf.concat_bzero_se_epi.lzout.out

    elif field_estimation_data_formation_strategy == "bzeros":
        wf.add(dwiextract(input=wf.lzin.input, bzero=True, name="dwi_extract_bzeros"))
        field_estimation_input = wf.dwi_extract_bzeros.lzout.out

    else:
        assert False

    # TODO Padding
    # Since we are committing to always pad, let's pad every axis to a multiple of 4
    # For axis 2 (I-S), make sure we always pad at the positive end
    # For axes 0 and 1, could hytpthetically try to pad from both ends,
    #   but for simplicity let's just pad everything at the upper end

    @pydra.mark.task
    def calculate_mrgrid_spatial_padding(in_image: Mif) -> ty.List[ty.Tuple[int, str]]:
        padding = [(4 - (dim % 4)) % 4 for dim in in_image.dims()[0:3]]
        axis_args = [
            (axis_index, "0:%d" % pad_size)
            for axis_index, pad_size in enumerate(padding)
            if pad_size
        ]
        # TODO Does mrgrid need up to omit from command-line inputs any axes to which padding is not being applied?
        # Believe not
        return axis_args

    wf.add(
        calculate_mrgrid_spatial_padding(
            in_image=field_estimation_input, name="calculate_mrgrid_spatial_padding"
        )
    )

    # TODO Will this crash if the set of axis paddings to be applied is empty?
    wf.add(
        mrgrid(
            input=field_estimation_input,
            operation="pad",
            axis=wf.calculate_mrgrid_spatial_padding.lzout.out,
            name="mrgrid_pad_axes",
        )
    )

    wf.add(
        mrconvert(
            input=field_estimation_input,
            export_pe_table=True,
            strides=[1, 2, 3, 4],
            name="generate_topup_inputs",
        )
    )

    wf.add(
        TOPUP(
            in_file=wf.generate_topup_inputs.lzout.output,
            encoding_file=wf.generate_topup_inputs.lzout.export_pe_table,
            **TOPUP_CONFIG,
            name="topup",
        )
    )

    wf.set_output(
        [
            ("susceptibility_field_image", wf.topup.lzout.out_field),
            ("topup_fieldcoeff", wf.topup.lzout.out_fieldcoef)
        ],
    )

    return wf


@pydra.mark.task
@pydra.mark.annotate({"return": {}})
def a() -> bool:
    pass
