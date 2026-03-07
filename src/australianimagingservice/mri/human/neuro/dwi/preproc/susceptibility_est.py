import logging
from pydra.compose import workflow, python, shell
from fileformats.vendor.mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3.v3_1 import MrTransform, MrCat, MrConvert, DwiExtract, MrGrid
from pydra.tasks.fsl.v6 import TOPUP
from .utils import CalculateMrgridSpatialPadding


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


@workflow.define(outputs=["susceptibility_field_image", "topup_fieldcoeff"])
def SusceptibilityEstimation(
    in_file: Mif,
    dwi_first_bzero_index: int,
    se_epi: Mif,
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

    if requires_regrid:
        regrid_seepi_to_dwi_transform = workflow.add(
            MrTransform(
                input=se_epi,
                tempate=in_file,
                reorient_fod="no",
                interp="sinc",
            )
        )

        @shell.define
        class MrCalcRegrid(shell.Task):

            executable = "mrcalc"
            input: Mif = shell.arg(
                help="input image",
                argstr="",
                position=0,
            )
            operand: float = shell.arg(
                help="operand",
                argstr="",
                position=1,
            )
            operator: str = shell.arg(
                help="the operation to apply",
                argstr="-{operator}",
                position=2,
            )

            class Outputs(shell.Outputs):
                output: Mif = shell.outarg(
                    help="the output file",
                    argstr="--tval",
                    position=-1,
                    path_template="output.mif",
                )

        regrid_seepi_to_dwi_nonnegative = workflow.add(
            MrCalcRegrid(
                input=regrid_seepi_to_dwi_transform.output,
                operand=0.0,
                operator="max",
            )
        )
        se_epi_for_concatenation = regrid_seepi_to_dwi_nonnegative.output
    else:
        se_epi_for_concatenation = se_epi

    @python.define
    def MergeList(in_1, in_2) -> list:
        return [in_1, in_2]

    # Done regridding if necessary
    field_estimation_input = None
    if field_estimation_data_formation_strategy == "se_epi_standalone":
        assert not requires_regrid
        field_estimation_input = se_epi

    elif field_estimation_data_formation_strategy == "se_epi_concat_first_bzero":
        dwi_extract_first_bzero = workflow.add(
            MrConvert(
                input=in_file,
                coord=(3, dwi_first_bzero_index),
            )
        )

        merge_bzero_se_epi = workflow.add(
            MergeList(
                in_1=dwi_extract_first_bzero.out,
                in_2=se_epi_for_concatenation,
            )
        )

        concat_bzero_se_epi = workflow.add(
            MrCat(
                inputs=merge_bzero_se_epi.out,
                axis=3,
            )
        )
        field_estimation_input = concat_bzero_se_epi.out

    elif field_estimation_data_formation_strategy == "se_epi_concat_all_bzeros":
        dwi_extract_bzeros = workflow.add(DwiExtract(input=in_file, bzero=True))
        merge_bzero_se_epi = workflow.add(
            MergeList(
                in_1=dwi_extract_bzeros.out,
                in_2=se_epi_for_concatenation,
            )
        )
        concat_bzero_se_epi = workflow.add(MrCat(inputs=merge_bzero_se_epi.out, axis=3))
        field_estimation_input = concat_bzero_se_epi.out

    elif field_estimation_data_formation_strategy == "bzeros":
        dwi_extract_bzeros = workflow.add(DwiExtract(input=in_file, bzero=True))
        field_estimation_input = dwi_extract_bzeros.out

    else:
        assert False

    # TODO Padding
    # Since we are committing to always pad, let's pad every axis to a multiple of 4
    # For axis 2 (I-S), make sure we always pad at the positive end
    # For axes 0 and 1, could hytpthetically try to pad from both ends,
    #   but for simplicity let's just pad everything at the upper end

    calculate_mrgrid_spatial_padding = workflow.add(
        CalculateMrgridSpatialPadding(in_image=field_estimation_input)
    )

    # TODO Will this crash if the set of axis paddings to be applied is empty?
    # Believe not
    # TODO Slice timings will no longer be valid after padding
    # (If capability to pad via duplication is added, then this should involve
    # header concatenation, which should concatenate the timing data also)
    mrgrid_pad_axes = workflow.add(
        MrGrid(
            input=field_estimation_input,
            operation="pad",
            axis=calculate_mrgrid_spatial_padding.out,
        )
    )

    generate_topup_inputs = workflow.add(
        MrConvert(
            input=field_estimation_input,
            export_pe_table=True,
            strides=[1, 2, 3, 4],
        )
    )

    topup = workflow.add(
        TOPUP(
            in_file=generate_topup_inputs.output,
            encoding_file=generate_topup_inputs.export_pe_table,
            **TOPUP_CONFIG,
        )
    )

    return topup.out_field, topup.out_fieldcoef
