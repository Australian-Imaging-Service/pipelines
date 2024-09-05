import os
from logging import getLogger
from fileformats.medimage_mrtrix3 import ImageIn, ImageFormat as Mif
import pydra.mark
from pydra.tasks.mrtrix3.auto import (
    mrconvert,
)

logger = getLogger(__name__)


def volume_recombination_wf():
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    wf = pydra.Workflow(
        name="qc_wf", input_spec=["input"]
    )

    wf.add(
        example_task(
            in_image=wf.lzin.input, name="example"
        )
    )

    wf.set_output(
        [
            ("example", wf.example.lzout.output),
        ],
    )

    return wf





    # If there was any relevant padding applied, then we want to provide
    #   the comprehensive set of files to EddyQC with that padding removed
    if dwi_post_eddy_crop:
        progress = app.ProgressBar(
            "Removing image padding prior to running EddyQC",
            len(eddy_suppl_files) + 3,
        )

        for eddy_filename in eddy_suppl_files:
            if os.path.isfile("dwi_post_eddy." + eddy_filename):
                if slice_padded and eddy_filename in [
                    "eddy_outlier_map",
                    "eddy_outlier_n_sqr_stdev_map",
                    "eddy_outlier_n_stdev_map",
                ]:
                    with open(
                        "dwi_post_eddy." + eddy_filename, "r", encoding="utf-8"
                    ) as f_eddyfile:
                        eddy_data = f_eddyfile.readlines()
                    eddy_data_header = eddy_data[0]
                    eddy_data = eddy_data[1:]
                    for line in eddy_data:
                        line = " ".join(line.strip().split(" ")[:-1])
                    with open(
                        "dwi_post_eddy_unpad." + eddy_filename,
                        "w",
                        encoding="utf-8",
                    ) as f_eddyfile:
                        f_eddyfile.write(eddy_data_header + "\n")
                        f_eddyfile.write("\n".join(eddy_data) + "\n")
                elif eddy_filename.endswith(".nii.gz"):
                    wf.add(
                        mrconvert(
                            input="dwi_post_eddy." + eddy_filename,
                            coord=dwi_post_eddy_crop,
                            name="remove_dwi_padding_for_eddyquad",
                        )
                    )
                else:
                    run.function(
                        os.symlink,
                        "dwi_post_eddy." + eddy_filename,
                        "dwi_post_eddy_unpad." + eddy_filename,
                    )
                app.cleanup("dwi_post_eddy." + eddy_filename)
            progress.increment()

        if eddy_mporder and slice_padded:
            logger.debug("Current slice groups: " + str(slice_groups))
            logger.debug(
                "Slice encoding direction: " + str(slice_encoding_direction)
            )
            # Remove padded slice from slice_groups, write new slspec
            if sum(slice_encoding_direction) < 0:
                slice_groups = [
                    [index - 1 for index in group if index]
                    for group in slice_groups
                ]
            else:
                slice_groups = [
                    [index for index in group if index != dwi_num_slices - 1]
                    for group in slice_groups
                ]
            eddyqc_slspec = "slspec_unpad.txt"
            logger.debug("Slice groups after removal: " + str(slice_groups))
            try:
                # After this removal, slspec should now be a square matrix
                assert all(
                    len(group) == len(slice_groups[0])
                    for group in slice_groups[1:]
                )
                matrix.save_matrix(
                    eddyqc_slspec,
                    slice_groups,
                    add_to_command_history=False,
                    fmt="%d",
                )
            except AssertionError:
                matrix.save_numeric(
                    eddyqc_slspec,
                    slice_groups,
                    add_to_command_history=False,
                    fmt="%d",
                )
                raise

        wf.add(
            mrconvert(
                input="eddy_mask.nii",
                output="eddy_mask_unpad.nii",
                coord=dwi_post_eddy_crop,
                name="brainmask_remove_padding_for_eddyquad",
            )
        )
        eddyqc_mask = "eddy_mask_unpad.nii"
        progress.increment()
        wf.add(
            mrconvert(
                input=fsl.find_image("field_map"),
                output="field_map_unpad.nii",
                coord=dwi_post_eddy_crop,
                name="fieldmap_remove_padding_for_eddyquad",
            )
        )
        eddyqc_fieldmap = "field_map_unpad.nii"
        progress.increment()
        wf.add(
            mrconvert(
                input=eddy_output_image_path,
                output="dwi_post_eddy_unpad.nii.gz",
                coord=dwi_post_eddy_crop,
                name="dwi_remove_padding_for_eddyquad",
            )
        )
        eddyqc_prefix = "dwi_post_eddy_unpad"
        progress.done()

    if len(volume_pairs) != int(dwi_num_volumes / 2):
        if execute_topup:
            app.cleanup("topup_in.nii")
            app.cleanup(fsl.find_image("field_map"))

        # Convert the resulting volume to the output image, and re-insert the diffusion encoding
        wf.add(
            mrconvert(
                input=eddy_output_image_path,
                output="result.mif",
                coord=(3, 1, dwi_permvols_posteddy_slice),
                fslgrad=(bvecs_path, "bvals"),
                name="post_eddy_conversion",
            )
        )  # coord=dwi_post_eddy_crop
        app.cleanup(eddy_output_image_path)

    else:
        logger.info(
            "Detected matching DWI volumes with opposing phase encoding; performing explicit volume recombination"
        )

        # Perform a manual combination of the volumes output by eddy, since LSR is disabled

        # Generate appropriate bvecs / bvals files
        # Particularly if eddy has provided rotated bvecs, since we're combining two volumes into one that
        #   potentially have subject rotation between them (and therefore the sensitisation direction is
        #   not precisely equivalent), the best we can do is take the mean of the two vectors.
        # Manual recombination of volumes needs to take into account the explicit volume matching

        bvecs = matrix.load_matrix(bvecs_path)
        bvecs_combined_transpose = []
        bvals_combined = []

        for pair in volume_pairs:
            bvec_mean = [
                0.5 * (bvecs[0][pair[0]] + bvecs[0][pair[1]]),
                0.5 * (bvecs[1][pair[0]] + bvecs[1][pair[1]]),
                0.5 * (bvecs[2][pair[0]] + bvecs[2][pair[1]]),
            ]
            norm2 = matrix.dot(bvec_mean, bvec_mean)

            # If one diffusion sensitisation gradient direction is reversed with respect to
            #   the other, still want to enable their recombination; but need to explicitly
            #   account for this when averaging the two directions
            if norm2 < 0.5:
                bvec_mean = [
                    0.5 * (bvecs[0][pair[0]] - bvecs[0][pair[1]]),
                    0.5 * (bvecs[1][pair[0]] - bvecs[1][pair[1]]),
                    0.5 * (bvecs[2][pair[0]] - bvecs[2][pair[1]]),
                ]
                norm2 = matrix.dot(bvec_mean, bvec_mean)

            # Occasionally a b=0 volume can have a zero vector
            if norm2:
                factor = 1.0 / math.sqrt(norm2)
                new_vec = [
                    bvec_mean[0] * factor,
                    bvec_mean[1] * factor,
                    bvec_mean[2] * factor,
                ]
            else:
                new_vec = [0.0, 0.0, 0.0]
            bvecs_combined_transpose.append(new_vec)
            bvals_combined.append(0.5 * (grad[pair[0]][3] + grad[pair[1]][3]))

        bvecs_combined = matrix.transpose(bvecs_combined_transpose)
        matrix.save_matrix(
            "bvecs_combined", bvecs_combined, add_to_command_history=False
        )
        matrix.save_vector(
            "bvals_combined", bvals_combined, add_to_command_history=False
        )

        # Prior to 5.0.8, a bug resulted in the output field map image from topup having an identity transform,
        #   regardless of the transform of the input image
        # Detect this, and manually replace the transform if necessary
        #   (even if this doesn't cause an issue with the subsequent mrcalc command, it may in the future, it's better for
        #   visualising the script intermediate files, and it gives the user a warning about an out-of-date FSL)
        field_map_image = fsl.find_image("field_map")
        field_map_header = image.Header(field_map_image)
        if not image.match("topup_in.nii", field_map_header, up_to_dim=3):
            logger.warning(
                "topup output field image has erroneous header; recommend updating FSL to version 5.0.8 or later"
            )
            new_field_map_image = "field_map_fix.mif"
            wf.add(
                mrtransform(
                    input=field_map_image,
                    output=new_field_map_image,
                    replace="topup_in.nii",
                    name="fix_topup_fieldmap_transform",
                )
            )
            app.cleanup(field_map_image)
            field_map_image = new_field_map_image
        # In FSL 6.0.0, field map image is erroneously constructed with the same number of volumes as the input image,
        #   with all but the first volume containing intensity-scaled duplicates of the uncorrected input images
        # The first volume is however the expected field offset image
        elif len(field_map_header.size()) == 4:
            logger.info("Correcting erroneous FSL 6.0.0 field map image output")
            new_field_map_image = "field_map_fix.mif"
            wf.add(
                mrconvert(
                    input=field_map_image,
                    output=new_field_map_image,
                    coord=(3, 0),
                    axes="0,1,2",
                    name="fix_topup_fieldmap_dimensionality",
                )
            )
            app.cleanup(field_map_image)
            field_map_image = new_field_map_image
        app.cleanup("topup_in.nii")

        # Derive the weight images
        # Scaling term for field map is identical to the bandwidth provided in the topup config file
        #   (converts Hz to pixel count; that way a simple image gradient can be used to get the Jacobians)
        # Let mrfilter apply the default 1 voxel size gaussian smoothing filter before calculating the field gradient
        #
        #   The jacobian image may be different for any particular volume pair
        #   The appropriate PE directions and total readout times can be acquired from the eddy-style config/index files
        #   eddy_config.txt and eddy_indices.txt
        eddy_config = matrix.load_matrix("eddy_config.txt")
        eddy_indices = matrix.load_vector("eddy_indices.txt", dtype=int)
        logger.debug("EDDY config: " + str(eddy_config))
        logger.debug("EDDY indices: " + str(eddy_indices))

        # This section derives, for each phase encoding configuration present, the 'weight' to be applied
        #   to the image during volume recombination, which is based on the Jacobian of the field in the
        #   phase encoding direction
        for index, config in enumerate(eddy_config):
            pe_axis = [i for i, e in enumerate(config[0:3]) if e != 0][0]
            total_readout_time = config[3]
            sign_multiplier = " -1.0 -mult" if config[pe_axis] < 0 else ""
            field_derivative_path = "field_deriv_pe_" + str(index + 1) + ".mif"
            wf.add(
                mrcalc(
                    field_map_image,
                    str(total_readout_time),
                    "-mult",
                    sign_multiplier,
                    output="-",
                    name="pegroup%d_scale_fieldmap_trt" % index,
                )
            )
            wf.add(
                mrfilter(
                    input=getattr(wf, "pegroup%d_scale_trt" % index).lzout.output,
                    operation="gradient",
                    output="-",
                    name="pegroup%d_scaled_fieldmap_3dgradient" % index,
                )
            )
            wf.add(
                mrconvert(
                    input=getattr(
                        wf, "pegroup%d_scaled_fieldmap_gradient" % index
                    ).lzout.output,
                    output="field_derivative_path",
                    coord=(3, pe_axis),
                    axes="0,1,2",
                    name="pegroup%d_scaled_fieldmap_pegradient" % index,
                )
            )
            jacobian_path = "jacobian_" + str(index + 1) + ".mif"
            wf.add(
                mrcalc(
                    "1.0",
                    field_derivative_path,
                    "-add",
                    "0.0",
                    "-max",
                    output=jacobian_path,
                    name="pegroup%d_pejacobian" % index,
                )
            )
            app.cleanup(field_derivative_path)
            wf.add(
                mrcalc(
                    jacobian_path,
                    jacobian_path,
                    "-mult",
                    output="weight%d.mif" % index,
                    name="pegroup%d_recombination_weight" % index,
                )
            )
            app.cleanup(jacobian_path)
        app.cleanup(field_map_image)

        # If eddy provides its main image output in a compressed format, the code block below will need to
        #   uncompress that image independently for every volume pair. Instead, if this is the case, let's
        #   convert it to an uncompressed format before we do anything with it.
        if eddy_output_image_path.endswith(".gz"):
            new_eddy_output_image_path = "dwi_post_eddy_uncompressed.mif"
            wf.add(
                mrconvert(
                    input=eddy_output_image_path,
                    output=new_eddy_output_image_path,
                    name="dwi_post_eddy_uncompress_for_recombination",
                )
            )
            app.cleanup(eddy_output_image_path)
            eddy_output_image_path = new_eddy_output_image_path

        # If the DWI volumes were permuted prior to running eddy, then the simplest approach is to permute them
        #   back to their original positions; otherwise, the stored gradient vector directions / phase encode
        #   directions / matched volume pairs are no longer appropriate
        if dwi_permvols_posteddy_slice:
            new_eddy_output_image_path = (
                os.path.splitext(eddy_output_image_path)[0] + "_volpermuteundo.mif"
            )
            wf.add(
                mrconvert(
                    input=eddy_output_image_path,
                    coord=(dwi_permvols_posteddy_slice),
                    name="dwi_post_eddy_unpermute_volumes",
                )
            )  # output=new_eddy_output_image_path,
            app.cleanup(eddy_output_image_path)
            eddy_output_image_path = new_eddy_output_image_path

        # This section extracts the two volumes corresponding to each reversed phase-encoded volume pair, and
        #   derives a single image volume based on the recombination equation
        combined_image_list = []
        progress = app.ProgressBar(
            "Performing explicit volume recombination", len(volume_pairs)
        )
        for index, volumes in enumerate(volume_pairs):
            pe_indices = [eddy_indices[i] for i in volumes]
            wf.add(
                mrconvert(
                    input=eddy_output_image_path,
                    output="volume0.mif",
                    coord=(3, volumes[0]),
                    name="dwi_recombination_pair%d_first" % index,
                )
            )
            wf.add(
                mrconvert(
                    input=eddy_output_image_path,
                    output="volume1.mif",
                    coord=(3, volumes[1]),
                    name="dwi_recombination_pair%d_second" % index,
                )
            )
            # Volume recombination equation described in Skare and Bammer 2010
            combined_image_path = "combined" + str(index) + ".mif"
            wf.add(
                mrcalc(
                    "volume0.mif",
                    "weight" + str(pe_indices[0]) + ".mif",
                    "-mult",
                    "volume1.mif",
                    "weight" + str(pe_indices[1]) + ".mif",
                    "-mult",
                    "-add",
                    "weight" + str(pe_indices[0]) + ".mif",
                    "weight" + str(pe_indices[1]) + ".mif",
                    "-add",
                    "-divide",
                    "0.0",
                    "-max",
                    output=combined_image_path,
                    name="dwi_recombined_pair%d" % index,
                )
            )
            combined_image_list.append(combined_image_path)
            run.function(os.remove, "volume0.mif")
            run.function(os.remove, "volume1.mif")
            progress.increment()
        progress.done()

        app.cleanup(eddy_output_image_path)
        for index in range(0, len(eddy_config)):
            app.cleanup("weight" + str(index + 1) + ".mif")

        # Finally the recombined volumes must be concatenated to produce the resulting image series
        wf.add(
            mrcat(
                input=combined_image_list,
                output="-",
                axis=3,
                name="dwi_recombined_concatenate",
            )
        )
        wf.add(
            mrconvert(
                input=wf.dwi_recombined_concatenate.lzout.output,
                output="result.mif",
                fslgrad=("bvecs_combined", "bvals_combined"),
                coord=dwi_post_eddy_crop,
                strides=stride_option,
                name="generate_final_dwi",
            )
        )
        app.cleanup(combined_image_list)
