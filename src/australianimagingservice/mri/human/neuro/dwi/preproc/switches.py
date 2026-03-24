from pydra.compose import python, workflow
import attrs
import typing as ty
from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from pydra.tasks.mrtrix3.v3_1 import DwiExtract, MrCat


@python.define
def requires_regrid_switch(in_image: Mif, se_epi: Mif) -> bool:
    if se_epi is not attrs.NOTHING:
        dims_match = (
            in_image.dims()[:3] == se_epi.dims()[:3]
            and in_image.vox_sizes()[:3] == se_epi.vox_sizes()[:3]
        )
    else:
        dims_match = False
    return not dims_match


@python.define(outputs=["strategy", "se_epi"])
def CheckContrastAndSelectSeEpi(
    concatenated_se_epi: Mif,
) -> ty.Tuple[str, Mif]:
    """Return the concatenated SE-EPI if it has PE contrast, otherwise
    raise.  The strategy string is determined here too."""
    if "pe_scheme" not in concatenated_se_epi.metadata:
        raise RuntimeError(
            "No phase-encoding contrast present in SE-EPI images, even "
            "after concatenating with b=0 images due to -align_seepi "
            "option; cannot perform inhomogeneity field estimation"
        )
    return "se_epi_concat_all_bzeros", concatenated_se_epi


@python.define(outputs=["strategy", "se_epi"])
def DetermineStrategy(
    se_epi: ty.Optional[Mif],
    pe_design: str,
    align_seepi: bool,
    manual_pe_dir: ty.Optional[str],
    manual_trt: ty.Optional[float],
) -> ty.Tuple[str, ty.Optional[Mif]]:
    """Pure-Python logic for all non-Header-align_seepi cases.

    Returns the strategy string and the (unchanged) SE-EPI image.
    """
    if pe_design == "None":
        return "none", None

    elif pe_design == "All":
        # TODO: Rob to do — implement PE-scheme conflict checking for
        #   the "All" case (se_epi must carry its own PE info)
        if se_epi is None:
            raise RuntimeError(
                "If explicitly including SE EPI images when using "
                "-rpe_all option, they must come with their own "
                "associated phase-encoding information in the image header"
            )
        return "bzeros", se_epi

    elif pe_design == "Pair":
        # TODO: Rob to do — implement PE-scheme conflict checking
        #   (manual_pe_dir / manual_trt vs. header values)
        if se_epi is None:
            raise RuntimeError(
                "SE-EPI image must be provided for pe_design='Pair'"
            )
        if align_seepi:
            return "se_epi_concat_first_bzero", se_epi
        else:
            return "se_epi_standalone", se_epi

    elif pe_design == "Header":
        # align_seepi=True with Header is handled by the workflow branch
        # (DwiExtract + MrCat + CheckContrastAndSelectSeEpi), so this
        # function only sees the non-align_seepi sub-cases.
        if se_epi is None:
            return "bzeros", None
        if "pe_scheme" not in se_epi.metadata:
            raise RuntimeError(
                "No phase-encoding contrast present in SE-EPI images; "
                "cannot perform inhomogeneity field estimation"
            )
        if align_seepi:
            return "se_epi_concat_first_bzero", se_epi
        else:
            return "se_epi_standalone", se_epi

    else:
        raise ValueError(f"Unknown pe_design value: {pe_design!r}")


@workflow.define(outputs=["strategy", "se_epi"])
def field_estimation_data_formation_strategy_switch(
    in_image: Mif,
    se_epi: ty.Optional[Mif],
    pe_design: str,
    align_seepi: bool = False,
    manual_pe_dir: ty.Optional[str] = None,
    manual_trt: ty.Optional[float] = None,
) -> ty.Tuple[str, ty.Optional[Mif]]:
    """Determine the strategy for forming the field estimation input data and
    return a (possibly modified) SE-EPI image.

    In the ``pe_design == "Header"`` case where the SE-EPI lacks phase-encoding
    contrast, and ``align_seepi`` is set, this workflow extracts the DWI b=0
    volumes and concatenates them with the SE-EPI before re-checking for
    contrast.

    Parameters
    ----------
    in_image : Mif
        Input DWI image.
    se_epi : Mif, optional
        Spin-echo EPI image for field estimation.
    pe_design : str
        Phase-encoding acquisition design; one of ``"None"``, ``"Pair"``,
        ``"All"``, ``"Header"``.
    align_seepi : bool
        Whether to align the SE-EPI with the DWI by prepending a DWI b=0
        volume.
    manual_pe_dir : str, optional
        Manually specified phase-encoding direction.
    manual_trt : float, optional
        Manually specified total readout time (seconds).

    Returns
    -------
    strategy : str
        Determined field estimation data formation strategy.
    se_epi : Mif, optional
        SE-EPI image, potentially extended with DWI b=0 volumes.
    """

    if pe_design == "Header" and align_seepi:
        # In this branch the SE-EPI may lack phase-encoding contrast on its
        # own; prepend DWI b=0 volumes and re-check.
        assert se_epi is not None, "se_epi must be provided when pe_design='Header'"

        extract_bzeros = workflow.add(DwiExtract(in_file=in_image, bzero=True))

        cat_bzeros_with_se_epi = workflow.add(
            MrCat(inputs=[extract_bzeros.output, se_epi], axis=3)
        )

        check = workflow.add(
            CheckContrastAndSelectSeEpi(
                concatenated_se_epi=cat_bzeros_with_se_epi.output,
            )
        )
        return check.strategy, check.se_epi

    else:

        determine = workflow.add(
            DetermineStrategy(
                se_epi=se_epi,
                pe_design=pe_design,
                align_seepi=align_seepi,
                manual_pe_dir=manual_pe_dir,
                manual_trt=manual_trt,
            )
        )
        return determine.strategy, determine.se_epi

    # # If there was any relevant padding applied, then we want to provide
    # #   the comprehensive set of files to EddyQC with that padding removed
    # if dwi_post_eddy_crop:
    #     progress = app.ProgressBar(
    #         "Removing image padding prior to running EddyQC",
    #         len(eddy_suppl_files) + 3,
    #     )

    #     for eddy_filename in eddy_suppl_files:
    #         if os.path.isfile("dwi_post_eddy." + eddy_filename):
    #             if slice_padded and eddy_filename in [
    #                 "eddy_outlier_map",
    #                 "eddy_outlier_n_sqr_stdev_map",
    #                 "eddy_outlier_n_stdev_map",
    #             ]:
    #                 with open(
    #                     "dwi_post_eddy." + eddy_filename, "r", encoding="utf-8"
    #                 ) as f_eddyfile:
    #                     eddy_data = f_eddyfile.readlines()
    #                 eddy_data_header = eddy_data[0]
    #                 eddy_data = eddy_data[1:]
    #                 for line in eddy_data:
    #                     line = " ".join(line.strip().split(" ")[:-1])
    #                 with open(
    #                     "dwi_post_eddy_unpad." + eddy_filename,
    #                     "w",
    #                     encoding="utf-8",
    #                 ) as f_eddyfile:
    #                     f_eddyfile.write(eddy_data_header + "\n")
    #                     f_eddyfile.write("\n".join(eddy_data) + "\n")
    #             elif eddy_filename.endswith(".nii.gz"):
    #                 wf.add(
    #                     mrconvert(
    #                         input="dwi_post_eddy." + eddy_filename,
    #                         coord=dwi_post_eddy_crop,
    #                         name="remove_dwi_padding_for_eddyquad",
    #                     )
    #                 )
    #             else:
    #                 run.function(
    #                     os.symlink,
    #                     "dwi_post_eddy." + eddy_filename,
    #                     "dwi_post_eddy_unpad." + eddy_filename,
    #                 )
    #             app.cleanup("dwi_post_eddy." + eddy_filename)
    #         progress.increment()

    #     if eddy_mporder and slice_padded:
    #         logger.debug("Current slice groups: " + str(slice_groups))
    #         logger.debug(
    #             "Slice encoding direction: " + str(slice_encoding_direction)
    #         )
    #         # Remove padded slice from slice_groups, write new slspec
    #         if sum(slice_encoding_direction) < 0:
    #             slice_groups = [
    #                 [index - 1 for index in group if index]
    #                 for group in slice_groups
    #             ]
    #         else:
    #             slice_groups = [
    #                 [index for index in group if index != dwi_num_slices - 1]
    #                 for group in slice_groups
    #             ]
    #         eddyqc_slspec = "slspec_unpad.txt"
    #         logger.debug("Slice groups after removal: " + str(slice_groups))
    #         try:
    #             # After this removal, slspec should now be a square matrix
    #             assert all(
    #                 len(group) == len(slice_groups[0])
    #                 for group in slice_groups[1:]
    #             )
    #             matrix.save_matrix(
    #                 eddyqc_slspec,
    #                 slice_groups,
    #                 add_to_command_history=False,
    #                 fmt="%d",
    #             )
    #         except AssertionError:
    #             matrix.save_numeric(
    #                 eddyqc_slspec,
    #                 slice_groups,
    #                 add_to_command_history=False,
    #                 fmt="%d",
    #             )
    #             raise

    #     wf.add(
    #         mrconvert(
    #             input="eddy_mask.nii",
    #             output="eddy_mask_unpad.nii",
    #             coord=dwi_post_eddy_crop,
    #             name="brainmask_remove_padding_for_eddyquad",
    #         )
    #     )
    #     eddyqc_mask = "eddy_mask_unpad.nii"
    #     progress.increment()
    #     wf.add(
    #         mrconvert(
    #             input=fsl.find_image("field_map"),
    #             output="field_map_unpad.nii",
    #             coord=dwi_post_eddy_crop,
    #             name="fieldmap_remove_padding_for_eddyquad",
    #         )
    #     )
    #     eddyqc_fieldmap = "field_map_unpad.nii"
    #     progress.increment()
    #     wf.add(
    #         mrconvert(
    #             input=eddy_output_image_path,
    #             output="dwi_post_eddy_unpad.nii.gz",
    #             coord=dwi_post_eddy_crop,
    #             name="dwi_remove_padding_for_eddyquad",
    #         )
    #     )
    #     eddyqc_prefix = "dwi_post_eddy_unpad"
    #     progress.done()

    # if len(volume_pairs) != int(dwi_num_volumes / 2):
    #     if execute_topup:
    #         app.cleanup("topup_in.nii")
    #         app.cleanup(fsl.find_image("field_map"))

    #     # Convert the resulting volume to the output image, and re-insert the diffusion encoding
    #     wf.add(
    #         mrconvert(
    #             input=eddy_output_image_path,
    #             output="result.mif",
    #             coord=(3, 1, dwi_permvols_posteddy_slice),
    #             fslgrad=(bvecs_path, "bvals"),
    #             name="post_eddy_conversion",
    #         )
    #     )  # coord=dwi_post_eddy_crop
    #     app.cleanup(eddy_output_image_path)

    # else:
