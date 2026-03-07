import typing as ty
import logging
import itertools
from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from fileformats.medimage import Bvec, Bval

from pydra.compose import python, workflow
from pydra.tasks.mrtrix3.v3_1 import (
    MrInfo,
    DirStat,
    MrConvert,
    MrCat,
    Dwi2Mask_Ants,
    MaskFilter,
    MrGrid,
)
from pydra.tasks.fsl.v6 import ApplyTOPUP, Eddy
from fileformats.datascience import TextVector, TextArray
from .utils import CalculateMrgridSpatialPadding


logger = logging.getLogger(__name__)

EDDY_VERSIONS = ["openmp", "cuda"]


@workflow.define
def EddyCurrentCorrection(
    in_file: Mif,
    topup_fieldcoeff: TextVector,
    dwi_first_bzero_index: int,
    slice_encoding_direction: TextVector,
    slice_timings: TextArray,
    eddy_use_slm: bool,
    have_topup: bool,
    slice_to_volume: bool,
    dwi_has_pe_contrast: bool,
    dwi2mask_algorithm: str,
    eddy_version: str = "openmp",
    eddy_qc_all: bool = False,
):
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    if eddy_version not in EDDY_VERSIONS:
        raise ValueError(
            f"eddy version, '{eddy_version}', not recognised; must be one of {EDDY_VERSIONS}"
        )

    eddy_suppl_files = [
        "eddy_parameters",
        "eddy_movement_rms",
        "eddy_restricted_movement_rms",
        "eddy_post_eddy_shell_alignment_parameters",
        "eddy_post_eddy_shell_PE_translation_parameters",
        "eddy_outlier_report",
        "eddy_outlier_map",
        "eddy_outlier_n_stdev_map",
        "eddy_outlier_n_sqr_stdev_map",
        "eddy_movement_over_time",
    ]
    if eddy_qc_all:
        eddy_suppl_files.extend(
            [
                "eddy_outlier_free_data.nii.gz",
                "eddy_cnr_maps.nii.gz",
                "eddy_residuals.nii.gz",
            ]
        )

    generate_applytopup_textfiles = workflow.add(
        MrInfo(
            input=in_file,
            export_pe_eddy=True,
        )
    )

    if have_topup:
        # Create brain mask for use in eddy
        # Eddy would ideallyh have a brain mask coinciding with the fully pre-processed
        #   data; but obviously this is not available prior to pre-processing.
        # Instead, we generate our best estimate of this by:
        # - Using applytopup to perform exclusively susceptibility distortion correction
        #   to the input DWIs
        # - Run an appropriate algorithm to estimate a brain mask from those
        #   partially corrected DWIs
        #
        # Imagine we have a DWI with 8 volumes, where the phase encoding was:
        # 1: A>>P
        # 2: A>>P
        # 3: A>>P
        # 4: A>>P
        # 5: P>>A
        # 6: P>>A
        # 7: P>>A
        # 8: P>>A
        #
        # The phase encoding table for these data would look something like:
        # 0 -1 0 0.1
        # 0 -1 0 0.1
        # 0 -1 0 0.1
        # 0 -1 0 0.1
        # 0 1 0 0.1
        # 0 1 0 0.1
        # 0 1 0 0.1
        # 0 1 0 0.1
        #
        # The "eddy config" files for these data would be:
        #
        # "config":
        # 0 -1 0 0.1
        # 0 1 0 0.1
        #
        # "indices":
        # 1 1 1 1 2 2 2 2
        #
        # What we want to do is run applytopup just once, for each of the unique phase encoding
        # lines. Therefore we have to extract all volumes corresponding to that specific
        # phase encoding as we convert to nifti inorder to run applytopup.
        # This is done by loading the "indices" file, and generating the "volume groups":
        # [[1,2,3,4],[5,6,7,8]]
        # For each element in this list, we run mrconvert, providing the "coord" option
        # to extract the relevant volumes, and then run applytopup on the resulting data.

        @python.define(
            outputs=[
                "config_file",  #: TextArray,
                "indices_file",  #: TextVector,
                "volumegroups",  #: ty.List[ty.List[int]],
                "groupindices",  #: ty.List[int],
            ]
        )
        def LoadTopupPeInfo(
            export_pe_eddy: ty.Tuple[TextArray, TextVector],
        ) -> ty.Tuple[
            ty.List[ty.List[float]], ty.List[int], ty.List[ty.List[int]], ty.List[int]
        ]:
            """Load the topup field coefficients"""
            config = export_pe_eddy[0].load()  # TODO: need to write this function
            indices = export_pe_eddy[1].load()
            volumegroups = [
                [index for index, value in enumerate(indices) if value == group]
                for group in range(1, len(config) + 1)
            ]
            return (
                export_pe_eddy[0],
                export_pe_eddy[1],
                volumegroups,
                list(range(len(volumegroups))),
            )

        load_topup_pe_info = workflow.add(
            LoadTopupPeInfo(
                topup_config=generate_applytopup_textfiles.export_pe_eddy,
            )
        )

        volume_group = workflow.add(
            VolumeGroup(
                in_file=in_file, topup_config_file=load_topup_pe_info.config_file
            )
            .split(
                ("volumegroup", "groupindex"),
                volumegroup=load_topup_pe_info.volumegroups,
                groupindices=load_topup_pe_info.groupindices,
            )
            .combine(["volumegroup", "groupindex"])
        )

        # TODO Consider allowing mrcat to take as input a single image file
        if dwi_has_pe_contrast:
            concatenate_epi_corrected_dwis = workflow.add(
                MrCat(
                    inputs=volume_group.corrected,
                )
            )
            dwi2mask_input = concatenate_epi_corrected_dwis.output
        else:

            @python.define(outputs=["corrected_dwis"])
            def GetOnlyItemFromList(input_list: ty.List) -> ty.Any:
                assert len(input_list) == 1
                return input_list[0]

            get_epi_corrected_dwis = workflow.add(
                GetOnlyItemFromList(
                    input_list=volume_group.corrected,
                )
            )
            dwi2mask_input = get_epi_corrected_dwis.out

    else:
        dwi2mask_input = in_file

    # TODO Obtain dwi2mask algorithm
    dwi2mask = workflow.add(
        Dwi2Mask(input=dwi2mask_input, algorithm=dwi2mask_algorithm, name="")
    )

    dilate_brain_mask = workflow.add(
        MaskFilter(input=dwi2mask.output, operation="dilate", name="")
    )

    # If padding was applied to the input data to topup,
    #   we need to perform the same padding here to both the input DWI
    #   and the eddy processing mask
    if have_topup:
        dwi_padding = workflow.add(CalculateMrgridSpatialPadding(in_file, name=""))

        mrgrid_pad_dwis = workflow.add(
            MrGrid(
                input=in_file,
                operation="pad",
                axis=dwi_padding.out,
            )
        )
        mrgrid_pad_brainmask = workflow.add(
            MrGrid(
                input=dilate_brain_mask.output,
                operation="pad",
                axis=dwi_padding.out,
            )
        )

        dwi_mrconvert_in = mrgrid_pad_dwis.output
        mask_mrconvert_in = mrgrid_pad_brainmask.output

    else:
        dwi_mrconvert_in = in_file
        mask_mrconvert_in = dilate_brain_mask.output

    @python.define(outputs=["slice_dim", "slice_str"])
    def PermvolsPreddy(
        slice_to_volume: bool, dwi_first_bzero_index: int, num_volumes: int
    ) -> ty.Tuple[int, str]:
        slice_str = f"{dwi_first_bzero_index},0"
        if dwi_first_bzero_index > 1:
            slice_str += f":{dwi_first_bzero_index - 1}"
        if dwi_first_bzero_index < num_volumes - 1:
            slice_str += f",{dwi_first_bzero_index + 1}"
        if dwi_first_bzero_index < num_volumes - 2:
            slice_str += f":{num_volumes - 1}"
        return (3, slice_str)

    permvols_preddy = workflow.add(
        PermvolsPreddy(
            slice_to_volume=slice_to_volume,
            dwi_first_bzero_index=dwi_first_bzero_index,
            num_volumes=mrinfo.num_volumes,
        )
    )

    if slice_to_volume:

        @python.define(outputs=["slice_timings"])
        def SaveEddySlspec(
            slice_timings: ty.List[float],
            slice_encoding_direction: ty.List[int],
            dwi_padding: ty.List[ty.Tuple[int, str]],
        ) -> TextArray:
            # Slice timing vector must be of same length as number of slices
            # For padded slices, pretend they were acquired at time 0
            slice_timings.extend([0.0] * dwi_padding[2])

            # TODO Not sure if the need for this was ever tested using real data?
            if sum(slice_encoding_direction) < 0:
                slice_timings = reversed(slice_timings)

            slice_groups = [
                [x[0] for x in g]
                for _, g in itertools.groupby(
                    sorted(enumerate(slice_timings), key=lambda x: x[1]),
                    key=lambda x: x[1],
                )
            ]

            slice_groups_file = TextArray("slice_groups.txt")
            slice_groups_file.save(slice_groups)
            return slice_groups_file

        save_eddy_slspec = workflow.add(
            SaveEddySlspec(
                slice_timings=slice_timings,
                slice_encoding_direction=slice_encoding_direction,
                dwi_padding=dwi_padding.out,
            )
        )

    # TODO Find out if it is recommended that we use the second-level model in eddy
    mrinfo = workflow.add(MrInfo(image_=in_file, shell_bvalues=True, name=""))

    dirstat = workflow.add(DirStat(image_=in_file, output="asym", name=""))

    @python.define(outputs=["slm"])
    def EddySelectSlm(mrinfo_shell_bvalues_out: str, dirstat_asym_out: str) -> str:
        """Check whether eddy distortion correction requires use of --slm=linear"""
        shell_bvalues = [
            int(round(float(value))) for value in mrinfo_shell_bvalues_out.split()
        ]
        shell_asymmetries = [float(value) for value in dirstat_asym_out.splitlines()]
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
        slm = "none"
        for bvalue, asymmetry in zip(shell_bvalues, shell_asymmetries):
            if asymmetry >= 0.1:
                slm = "linear"
                logger.warning(
                    "sampling of b="
                    + str(bvalue)
                    + " shell is "
                    + ("strongly" if asymmetry >= 0.4 else "moderately")
                    + " asymmetric; linear second level model in eddy will be activated"
                )
        return slm

    eddy_requires_slm = workflow.add(
        EddySelectSlm(
            mrinfo_shell_bvalues_out=mrinfo_shell_bvalues_out.stdout,
            dirstat_asym_out=dirstat_asym_out.stdout,
        )
    )

    # TODO Convert image data in preparation for eddy
    convert_dwi_for_eddy = workflow.add(
        MrConvert(
            input=dwi_mrconvert_in,
            datatype="float32",
            strides="-1,+2,+3,+4",
            coord=dwi_permvols_preeddy.out,
            export_pe_eddy=True,
            export_grad_fsl=True,
        )
    )
    convert_mask_for_eddy = workflow.add(
        MrConvert(
            input=mask_mrconvert_in,
            datatype="float32",
            strides="-1,+2,+3",
        )
    )

    eddy_variable_args = {}
    if have_topup:
        eddy_variable_args["in_topup_fieldcoef"] = topup_fieldcoeff
    if slice_to_volume:
        eddy_variable_args["slice_order"] = save_eddy_slspec.output
    # TODO if using slice-to-volume motion correction,
    #   need to calculate the appropriate factor, and add that to the invocation
    # TODO Want to incorporate MRtrix3_connectome's loop?
    # - What if eddy complains about data not being shelled, even if we think they are?
    #   Can't process non-shelled data due to dwibiasnormmask performing MSMT CSD
    #   Could add very early check of data shelled-ness using mrinfo, and if that succeeds,
    #   just always include the --data-is-shelled option
    # - What if eddy fails due to not being able to find any individual slice that does
    #   not contain any outliers? One potential solution to at least succeeed with processing
    #   is to increase the stringency of the thresholding by which outlier slices are detected,
    #   making it more likely for there to be at least one volume with precisely zero outliers.

    eddy = workflow.add(
        Eddy(
            executable=f"eddy_{eddy_version}",
            in_file=convert_dwi_for_eddy.output,
            in_mask=convert_mask_for_eddy.output,
            in_acqp=generate_applytopup_textfiles.export_pe_eddy[0],
            in_index=generate_applytopup_textfiles.export_pe_eddy[1],
            in_bvec=convert_dwi_for_eddy.export_grad_fsl[0],
            in_bval=convert_dwi_for_eddy.export_grad_fsl[1],
            slm=eddy_requires_slm.output,
            repol=True,
            method="jac",
            *eddy_variable_args,
        )
    )

    @python.define(outputs=["bvecs", "bvals"])
    def SplitFslGrads(fslgrad: ty.Tuple[Bvec, Bval]) -> ty.Tuple[Bvec, Bval]:
        return fslgrad

    @python.define(outputs=["bvecs", "bvals"])
    def CombineFslGrads(bvecs: Bvec, bvals: Bval) -> ty.Tuple[Bvec, Bval]:
        return (bvecs, bvals)

    split_fsl_grads = workflow.add(
        SplitFslGrads(
            fslgrad=convert_dwi_for_eddy.export_grad_fsl,
        )
    )

    combine_fsl_grads = workflow.add(
        CombineFslGrads(
            bvecs=eddy.out_rotated_bvecs,
            bvals=split_fsl_grads.bvals,
        )
    )

    unpermute_vols_after_eddy = workflow.add(
        MrConvert(
            input=eddy.out_corrected,
            output="output.mif",
            datatype="float32",
            strides="-1,+2,+3,+4",
            coord=dwi_permvols_posteddy.out,
            fslgrad=combine_fsl_grads.out,
        )
    )

    out_node = unpermute_vols_after_eddy.out

    if have_topup:

        mrgrid_crop_dwis = workflow.add(
            MrGrid(
                input=unpermute_vols_after_eddy.out_corrected,
                operation="crop",
                axis=dwi_padding.out,
            )
        )
        out_node = mrgrid_crop_dwis.output

    # Include any requisite reversal of volume permutation

    return out_node


@workflow.define(outputs=["corrected"])
def VolumeGroup(
    in_file: Mif, groupindex: int, volumegroup: int, topup_config_file: File
) -> Mif:

    @python.define
    def CoordArg(group: ty.List[int]) -> ty.Tuple[int, str]:
        return (3, ",".join([str(value) for value in group]))

    coord_arg = workflow.add(
        CoordArg(group=volumegroup, name=""),
    )

    extract_volumes_for_applytopup_group = workflow.add(
        MrConvert(
            input=in_file,
            coord=coord_arg.out,
            strides="-1,+2,+3,+4",
            json_export=True,
        )
    )
    applytopup_group = workflow.add(
        ApplyTOPUP(
            in_files=extract_volumes_for_applytopup_group.output,
            encoding_file=topup_config_file.config_file,
            inindex=groupindex,
            topup="field",
            method="jac",
        )
    )
    post_applytopup_reimport_json = workflow.add(
        MrConvert(
            input=applytopup_group.output,
            json_import=extract_volumes_for_applytopup_group.json_export,
        )
    )

    return post_applytopup_reimport_json.output
