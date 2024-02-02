
# Deal with the phase-encoding of the images to be fed to topup (if applicable)
#execute_topup = (not pe_design == "None") and not topup_file_userpath
overwrite_se_epi_pe_scheme = False
se_epi_path = wf.import_seepi.lzout.output
dwi_permvols_preeddy = None
dwi_permvols_posteddy_slice = None
dwi_bzero_added_to_se_epi = False
se_epi_path = new_se_epi_path
se_epi_header = image.Header(se_epi_path)

# 3 possible sources of PE information: DWI header, topup image header, command-line
# Any pair of these may conflict, and any one could be absent

# Have to switch here based on phase-encoding acquisition design
if pe_design == "Pair":
    # Criteria:
    #   * If present in own header, ignore DWI header entirely -
    #     - If also provided at command-line, look for conflict & report
    #     - If not provided at command-line, nothing to do
    #   * If _not_ present in own header:
    #     - If provided at command-line, infer appropriately
    #     - If not provided at command-line, but the DWI header has that information, infer appropriately
    if se_epi_pe_scheme:
        if manual_pe_dir:
            if not scheme_dirs_match(se_epi_pe_scheme, se_epi_manual_pe_scheme):
                logger.warning(
                    "User-defined phase-encoding direction design does not match what is stored in SE EPI image header; proceeding with user specification"
                )
                overwrite_se_epi_pe_scheme = True
        if manual_trt:
            if not scheme_times_match(
                se_epi_pe_scheme, se_epi_manual_pe_scheme
            ):
                logger.warning(
                    "User-defined total readout time does not match what is stored in SE EPI image header; proceeding with user specification"
                )
                overwrite_se_epi_pe_scheme = True
        if overwrite_se_epi_pe_scheme:
            se_epi_pe_scheme = se_epi_manual_pe_scheme
        else:
            se_epi_manual_pe_scheme = (
                None  # To guarantee that these data are never used
            )
    else:
        overwrite_se_epi_pe_scheme = True
        se_epi_pe_scheme = se_epi_manual_pe_scheme

elif pe_design == "All":
    # Criteria:
    #   * If present in own header:
    #     - Nothing to do
    #   * If _not_ present in own header:
    #     - Don't have enough information to proceed
    #     - Is this too harsh? (e.g. Have rules by which it may be inferred from the DWI header / command-line)
    if not se_epi_pe_scheme:
        raise RuntimeError(
            "If explicitly including SE EPI images when using -rpe_all option, they must come with their own associated phase-encoding information in the image header"
        )

elif pe_design == "Header":
    # Criteria:
    #   * If present in own header:
    #       Nothing to do (-pe_dir option is mutually exclusive)
    #   * If _not_ present in own header:
    #       Cannot proceed
    if not se_epi_pe_scheme:
        raise RuntimeError(
            "No phase-encoding information present in SE-EPI image header"
        )
    # If there is no phase encoding contrast within the SE-EPI series,
    #   try combining it with the DWI b=0 volumes, see if that produces some contrast
    # However, this should probably only be permitted if the -align_seepi option is defined
    se_epi_pe_scheme_has_contrast = "pe_scheme" in se_epi_header.keyval()
    if not se_epi_pe_scheme_has_contrast:
        if align_seepi:
            logger.info(
                "No phase-encoding contrast present in SE-EPI images; will examine again after combining with DWI b=0 images"
            )
            new_se_epi_path = (
                os.path.splitext(se_epi_path)[0] + "_dwibzeros.mif"
            )
            # Don't worry about trying to produce a balanced scheme here
            wf.add(
                dwiextract(
                    input=wf.import_dwi.lzout.output,
                    bzero=True,
                    name="dwi_bzeros_for_align_seepi",
                )
            )
            wf.add(
                mrcat(
                    input=(
                        wf.dwi_bzeros_for_align_seepi.lzout.output,
                        se_epi_path,
                    ),
                    output=new_se_epi_path,
                    axis=3,
                    name="cat_dwi_bzeros_seepi_for_align_seepi",
                )
            )
            se_epi_header = image.Header(new_se_epi_path)
            se_epi_pe_scheme_has_contrast = (
                "pe_scheme" in se_epi_header.keyval()
            )
            if se_epi_pe_scheme_has_contrast:
                app.cleanup(se_epi_path)
                se_epi_path = new_se_epi_path
                se_epi_pe_scheme = phaseencoding.get_scheme(se_epi_header)
                dwi_bzero_added_to_se_epi = True
                # Delay testing appropriateness of the concatenation of these images
                #   (i.e. differences in contrast) to later
            else:
                raise RuntimeError(
                    "No phase-encoding contrast present in SE-EPI images, even after concatenating with b=0 images due to -align_seepi option; "
                    "cannot perform inhomogeneity field estimation"
                )
        else:
            raise RuntimeError(
                "No phase-encoding contrast present in SE-EPI images; cannot perform inhomogeneity field estimation"
            )
