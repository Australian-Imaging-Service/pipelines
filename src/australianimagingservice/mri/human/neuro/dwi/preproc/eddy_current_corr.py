import pydra.mark
import typing as ty
import logging
import itertools
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from fileformats.medimage import Bvec, Bval
from pydra.tasks.mrtrix3.v3_0 import (
    mrinfo,
    dirstat,
    mrconvert,
    mrcat,
    dwi2mask,
    maskfilter,
    mrgrid,
)
from pydra.tasks.fsl.v6_0 import ApplyTOPUP, Eddy
from fileformats.datascience import TextVector, TextArray
from .utils import calculate_mrgrid_spatial_padding


logger = logging.getLogger(__name__)

EDDY_VERSIONS = ["openmp", "cuda"]


def eddy_current_corr_wf(
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

    wf = pydra.Workflow(
        name="eddy_current_corr_wf",
        input_spec=[
            "input",
            "topup_fieldcoeff",
            "dwi_first_bzero_index",
            "slice_encoding_direction",
            "slice_timings",
            "eddy_use_slm",
        ],
    )

    wf.add(
        mrinfo(
            input=wf.lzin.input,
            export_pe_eddy=True,
            name="generate_applytopup_textfiles",
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

        @pydra.mark.task
        @pydra.mark.annotate(
            {
                "return": {
                    "config_file": TextArray,
                    "indices_file": TextVector,
                    "volumegroups": ty.List[ty.List[int]],
                    "groupindices": ty.List[int],
                }
            }
        )
        def load_topup_pe_info(
            export_pe_eddy: ty.Tuple[TextArray, TextVector]
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

        wf.add(
            load_topup_pe_info(
                topup_config=wf.generate_applytopup_textfiles.lzout.export_pe_eddy,
                name="load_topup_pe_info",
            )
        )

        # We running a sub-workflow for each volume group by splitting over volume group (
        # along with their indices) and then combining them back together
        vg_wf = (
            pydra.Workflow(
                name="volumegroup_wf", input_spec=["input", "groupindex", "volumegroup"]
            )
            .split(
                ("volumegroup", "groupindex"),
                volumegroup=wf.load_topup_pe_info.lzout.volumegroups,
                groupindices=wf.load_topup_pe_info.lzout.groupindices,
            )
            .combine(["volumegroup", "groupindex"])
        )

        @pydra.mark.task
        def coord_arg(group: ty.List[int]) -> ty.Tuple[int, str]:
            return (3, ",".join([str(value) for value in group]))

        vg_wf.add(
            coord_arg(group=vg_wf.lzin.volumegroup, name="coord_arg"),
        )

        vg_wf.add(
            mrconvert(
                input=vg_wf.lzin.input,
                coord=vg_wf.coord_arg.lzout.out,
                strides="-1,+2,+3,+4",
                json_export=True,
                name="extract_volumes_for_applytopup_group",
            )
        )
        vg_wf.add(
            ApplyTOPUP(
                in_files=vg_wf.extract_volumes_for_applytopup_group.lzout.output,
                encoding_file=wf.load_topup_pe_info.lzout.config_file,
                inindex=vg_wf.lzin.groupindex,
                topup="field",
                method="jac",
                name="applytopup_group",
            )
        )
        vg_wf.add(
            mrconvert(
                input=vg_wf.applytopup_group.lzout.output,
                json_import=vg_wf.extract_volumes_for_applytopup_group.lzout.json_export,
                name="post_applytopup_reimport_json",
            )
        )

        vg_wf.set_output(
            [("corrected", vg_wf.post_applytopup_reimport_json.lzout.output)]
        )

        wf.add(vg_wf)

        # TODO Consider allowing mrcat to take as input a single image file
        if dwi_has_pe_contrast:
            wf.add(
                mrcat(
                    inputs=wf.volumegroup_wf.lzout.corrected,
                    name="concatenate_epi_corrected_dwis",
                )
            )
            dwi2mask_input = wf.concatenate_epi_corrected_dwis.lzout.output
        else:

            @pydra.mark.task
            def get_only_item_from_list(input_list: ty.List) -> ty.Any:
                assert len(input_list) == 1
                return input_list[0]

            wf.add(
                get_only_item_from_list(
                    input_list=wf.volumegroup_wf.lzout.corrected,
                    name="get_epi_corrected_dwis",
                )
            )
            dwi2mask_input = wf.get_epi_corrected_dwis.lzout.out

    else:
        dwi2mask_input = wf.lzin.input

    # TODO Obtain dwi2mask algorithm
    wf.add(
        dwi2mask(input=dwi2mask_input, algorithm=dwi2mask_algorithm, name="dwi2mask")
    )

    wf.add(
        maskfilter(
            input=wf.dwi2mask.lzout.output, operation="dilate", name="dilate_brain_mask"
        )
    )

    # If padding was applied to the input data to topup,
    #   we need to perform the same padding here to both the input DWI
    #   and the eddy processing mask
    if have_topup:
        wf.add(
            calculate_mrgrid_spatial_padding(input.lzin.input, name="dwi_padding")
        )

        wf.add(
            mrgrid(
                input=wf.lzin.input,
                operation="pad",
                axis=wf.dwi_padding.lzout.out,
                name="mrgrid_pad_dwis",
            )
        )
        wf.add(
            mrgrid(
                input=wf.dilate_brain_mask.lzout.output,
                operation="pad",
                axis=wf.dwi_padding.lzout.out,
                name="mrgrid_pad_brainmask",
            )
        )

        dwi_mrconvert_in = wf.mrgrid_pad_dwis.lzout.output
        mask_mrconvert_in = wf.mrgrid_pad_brainmask.lzout.output

    else:
        dwi_mrconvert_in = wf.lzin.input
        mask_mrconvert_in = wf.dilate_brain_mask.lzout.output

    @pydra.mark.task
    def permvols_preddy(
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

    wf.add(
        permvols_preddy(
            slice_to_volume=slice_to_volume,
            dwi_first_bzero_index=wf.lzin.dwi_first_bzero_index,
            num_volumes=wf.mrinfo.lzout.num_volumes,
            name="permvols_preddy",
        )
    )

    if slice_to_volume:

        @pydra.mark.task
        def save_eddy_slspec(
            slice_timings: ty.List[float], slice_encoding_direction: ty.List[int],
            dwi_padding: ty.List[ty.Tuple[int, str]]
        ) -> str:
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

        wf.add(
            save_eddy_slspec(
                slice_timings=wf.lzin.slice_timings,
                slice_encoding_direction=wf.lzin.slice_encoding_direction,
                dwi_padding=wf.dwi_padding.lzout.out,
                name="save_eddy_slspec",
            )
        )

    # TODO Find out if it is recommended that we use the second-level model in eddy
    wf.add(mrinfo(image_=wf.lzin.input, shell_bvalues=True, name="mrinfo"))

    wf.add(dirstat(image_=wf.lzin.input, output="asym", name="dirstat"))

    @pydra.mark.task
    def eddy_select_slm(mrinfo_shell_bvalues_out: str, dirstat_asym_out: str) -> str:
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

    wf.add(
        eddy_select_slm(
            mrinfo_shell_bvalues_out=wf.mrinfo_shell_bvalues_out.lzout.stdout,
            dirstat_asym_out=wf.dirstat_asym_out.lzout.stdout,
            name="eddy_requires_slm",
        )
    )

    # TODO Convert image data in preparation for eddy
    wf.add(
        mrconvert(
            input=dwi_mrconvert_in,
            datatype="float32",
            strides="-1,+2,+3,+4",
            coord=wf.dwi_permvols_preeddy.lzout.out,
            export_pe_eddy=True,
            export_grad_fsl=True,
            name="convert_dwi_for_eddy",
        )
    )
    wf.add(
        mrconvert(
            input=mask_mrconvert_in,
            datatype="float32",
            strides="-1,+2,+3",
            name="convert_mask_for_eddy",
        )
    )

    eddy_variable_args = {}
    if have_topup:
        eddy_variable_args["in_topup_fieldcoef"] = wf.lzin.topup_fieldcoeff
    if slice_to_volume:
        eddy_variable_args["slice_order"] = wf.save_eddy_slspec.lzout.output
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

    wf.add(
        Eddy(
            executable=f"eddy_{eddy_version}",
            in_file=wf.convert_dwi_for_eddy.lzout.output,
            in_mask=wf.convert_mask_for_eddy.lzout.output,
            in_acqp=wf.generate_applytopup_textfiles.lzout.export_pe_eddy[0],
            in_index=wf.generate_applytopup_textfiles.lzout.export_pe_eddy[1],
            in_bvec=wf.convert_dwi_for_eddy.export_grad_fsl[0],
            in_bval=wf.convert_dwi_for_eddy.export_grad_fsl[1],
            slm=wf.eddy_requires_slm.lzout.output,
            repol=True,
            method="jac",
            *eddy_variable_args,
            name="eddy",
        )
    )

    @pydra.mark.task
    @pydra.mark.annotate(
        {
            "return": {
                "bvecs": Bvec,
                "bvals": Bval,
            }
        }
    )
    def split_fsl_grads(
        fslgrad: ty.Tuple[Bvec, Bval]
    ) -> ty.Tuple[Bvec, Bval]:
        return fslgrad

    @pydra.mark.task
    def combine_fsl_grads(bvecs: Bvec, bvals: Bval) -> ty.Tuple[Bvec, Bval]:
        return (bvecs, bvals)

    wf.add(
        split_fsl_grads(
            fslgrad=wf.convert_dwi_for_eddy.lzout.export_grad_fsl,
            name="split_fsl_grads",
        )
    )

    wf.add(
        combine_fsl_grads(
            bvecs=wf.eddy.lzout.out_rotated_bvecs,
            bvals=wf.split_fsl_grads.lzout.bvals,
            name="combine_fsl_grads",
        )
    )

    wf.add(
        mrconvert(
            input=wf.eddy.lzout.out_corrected,
            output="output.mif",
            datatype="float32",
            strides="-1,+2,+3,+4",
            coord=wf.dwi_permvols_posteddy.lzout.out,
            fslgrad=wf.combine_fsl_grads.lzout.out,
            name="unpermute_vols_after_eddy",
        )
    )

    out_node = wf.unpermute_vols_after_eddy.lzout.out

    if have_topup:

        wf.add(
            mrgrid(
                input=wf.unpermute_vols_after_eddy.lzout.out_corrected,
                operation="crop",
                axis=wf.dwi_padding.lzout.out,
                name="mrgrid_crop_dwis",
            )
        )
        out_node = wf.mrgrid_crop_dwis.lzout.output

    # Include any requisite reversal of volume permutation

    wf.set_output(
        [("output", out_node)]
    )

    return wf
