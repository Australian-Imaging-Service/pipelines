#!/usr/bin/python3

# Copyright (c) 2008-2023 the MRtrix3 contributors.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Covered Software is provided under this License on an "as is"
# basis, without warranty of any kind, either expressed, implied, or
# statutory, including, without limitation, warranties that the
# Covered Software is free of defects, merchantable, fit for a
# particular purpose or non-infringing.
# See the Mozilla Public License v. 2.0 for more details.
#
# For more details, see http://www.mrtrix.org/.

import itertools
import json
import math
from pathlib import Path
import os
import shutil
import sys
from logging import getLogger
import numpy as np
from fileformats.medimage_mrtrix3 import ImageIn, ImageFormat as Mif
import pydra.mark
from pydra import Workflow, ShellCommandTask
from pydra.tasks.mrtrix3.auto import (
    mrconvert,
    mrcalc,
    mrtransform,
    dwi2mask,
    dwiextract,
    mrinfo,
    mrcat,
    mrthreshold,
    maskfilter,
    mrfilter,
)
from pydra.tasks.fsl.auto import TOPUP, Eddy, ApplyTOPUP, EddyQuad
from .strategy_identification import strategy_identification_wf
from .susceptibility_est import susceptibility_estimation_wf
from .eddy_current_corr import eddy_current_corr_wf


logger = getLogger(__name__)


@pydra.mark.task
def requires_regrid_switch(
    in_image: Mif, se_epi: Mif
) -> bool:
    if se_epi is not attrs.NOTHING:
        dims_match = (
            in_image.dims()[:3] == se_epi.dims()[:3]
            and in_image.vox_sizes()[:3] == se_epi.vox_sizes()[:3]
        )
    else:
        dims_match = False
    return not dims_match


@pydra.mark.task
def field_estimation_data_formation_strategy_switch(
    in_image: Mif, se_epi: Mif
) -> str:
    pass


def dwipreproc(
    # How am I estimating my susceptility field?
    # - I'm not ("rpe-none")
    # - I have a pair of b=0 images with reversed phase encoding,
    #   which are going to be provided to the workflow as a separate image
    #   (-se_epi) ("rpe-pair")
    # - I will extract the b=0 violumes from my DWI series, and
    #   use those to estimate the susceptibility field ("rpe-all")
    #
    # Does the set of images provided to topup need to be "tweaked"
    #   in any way to ensure that they align with the DWIs?
    # - Yes, because the "se-epi" image is on a completely different voxel grid
    #   and therefore needs to be first resampled
    # - Yes, because a susceptibility field can't be estimated from the "SE-EPI"
    #   image alone, because it doesn't have any phase encoding contrast
    # - Yes, because it's recommended that the first volume in the topup input
    #   be the same as the first volue in the eddy input
    # - No, because those data are being pulled from the DWIs themselves ("-rpe_all")
    # se_epi_to_dwi_merge: str,
    

    # What is going to form the input to topup for susceptibility field estimation?
    # - I'm not performing susceptibility field estimation ("rpe-none")
    # - I'm providing a separate image series with reversed phase encoding;
    #   these will be used as-is, without any further manipulation
    #   ("rpe-pair" without "-align_seepi")
    #   (Not recommended)
    # - I'm providing a separate image series with reversed phase encoding;
    #   to ensure alignment of these data with the DWIs, the first volume in
    #   this series that has the same phase encoding as the first b=0 volume
    #   in the DWIs will be stripped out and concatenated to becomes the first
    #   volume in that series
    #   ("rpe_pair" with "-align_seepi")
    #   -  If that separate image series contains the same number of volumes in 
    #      each phase encoding direction, then the addition of the first b=0 volume
    #      coincides with removal of one of the volumes in the spin-echo EPI series
    #      in order to keep the data "balanced"
    #   -  If the SE-EPI images do not contain any phase encoding contrast at all, and therefore no susceptibility field estimation can be performed, then concatenate _all_ DWI bzero volumes with the SE-EPI series
    #   -  Otherwise, just do the concatenation without erasure
    #   
    # - I'm providing a separate image series, which has different phase encoding
    #   to the DWI b=0 volumes; the input to topup will be formed by concatenating
    #   the b=0 DWI volumes with this additional series
    #   ("-rpe_header" when SE EPI series does not contain any phase encoding contrast)
    # - b=0 volumes in the DWI series themselves will be extracted and used;
    #   this has the advantage of being intrinsically aligned when the data are
    #   subsequently processed by eddy with no further explicit manipulation
    #   ("-rpe_all" in the absence of "-se_epi")
    #
    # At the point of workflow construction, 3.2 and 4 are in fact identical
    #
    # ['none', 
    #  'se_epi_standalone',
    #  'se_epi_concat_first_bzero_unbalanced',
    #  'se_epi_concat_first_bzero_balanced',
    #  'se_epi_concat_all_bzeros',
    #  'bzeros']
    # -> Note that fir niw, we are not going to discriminate between unbalanced and balanced when concatenating the first DWI b=0 to the SE-EPI. This may be a future augmentation, Therefore the classification for now is going to be:
    # ['none', 
    #  'se_epi_standalone',
    #  'se_epi_concat_first_bzero',
    #  'se_epi_concat_all_bzeros',
    #  'bzeros']
    #
    # Does the SE EPI series need to be resampled onto the voxel grid of the DWIs,
    #   or is it already on the same grid, in which case the requisite concatenation
    #   operations can be performed directly?
    #   ("True" only makes sense for a subset of the options above)
    field_estimation_data_formation_strategy: str,
    requires_regrid: bool,
    eddyqc_all: bool = False,  # whether to include large eddy qc files in outputs    
    slice_to_volume: bool = True,  # whether to include slice-to-volume registration
    bzero_threshold: float = 10.0,    
    #
    # Am I going to perform explicit volume recombination?
    # - Yes, because my data support it ("rpe-all") 
    # - No
):
    """
    Perform diffusion image pre-processing using FSL\'s eddy tool; including inhomogeneity
    distortion correction using FSL\'s topup tool if possible

    This script is intended to provide convenience of use of the FSL software tools
    topup and eddy for performing DWI pre-processing, by encapsulating some of the
    surrounding image data and metadata processing steps. It is intended to simply
    these processing steps for most commonly-used DWI acquisition strategies, whilst
    also providing support for some more exotic acquisitions. The "example usage"
    section demonstrates the ways in which the script can be used based on the
    (compulsory) -rpe_* command-line options.
    More information on use of the dwifslpreproc command can be found at the following
    link:
    https://mrtrix.readthedocs.io/en/' + _version.__tag__ + '/dwi_preprocessing/dwifslpreproc.html
    Note that the MRtrix3 command dwi2mask will automatically be called to derive a
    processing mask for the FSL command "eddy", which determines which voxels contribute
    to the estimation of geometric distortion parameters and possibly also the
    classification of outlier slices. If FSL command "topup" is used to estimate a
    susceptibility field, then dwi2mask will be executed on the resuts of running FSL
    command "applytopup" to the input DWIs; otherwise it will be executed directly on
    the input DWIs. Alternatively, the -eddy_mask option can be specified in order to
    manually provide such a processing mask. More information on mask derivation from
    DWI data can be found at:
    https://mrtrix.readthedocs.io/en/' + _version.__tag__ + '/dwi_preprocessing/masking.html

    The "-topup_options" and "-eddy_options" command-line options allow the user to pass
    desired command-line options directly to the FSL commands topup and eddy. The
    available options for those commands may vary between versions of FSL; users can
    interrogate such by querying the help pages of the installed software, and/or the
    FSL online documentation:

    (topup) https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/topup/TopupUsersGuide ;
    (eddy) https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/eddy/UsersGuide

    The script will attempt to run the CUDA version of eddy; if this does not succeed
    for any reason, or is not present on the system, the CPU version will be attempted
    instead. By default, the CUDA eddy binary found that indicates compilation against
    the most recent version of CUDA will be attempted; this can be over-ridden by
    providing a soft-link "eddy_cuda" within your path that links to the binary you wish
    to be executed.
    Note that this script does not perform any explicit registration between images
    provided to topup via the -se_epi option, and the DWI volumes provided to eddy. In
    some instances (motion between acquisitions) this can result in erroneous application
    of the inhomogeneity field during distortion correction. Use of the -align_seepi
    option is advocated in this scenario, which ensures that the first volume in the
    series provided to topup is also the first volume in the series provided to eddy,
    guaranteeing alignment. But a prerequisite for this approach is that the image
    contrast within the images provided to the -se_epi option must match the b=0 volumes
    present within the input DWI series: this means equivalent TE, TR and flip angle
    (note that differences in multi-band factors between two acquisitions may lead to
    differences in TR).

    Parameters
    ----------
    input:
        The input DWI series to be corrected
    output: str
        The output corrected image series
    json_import: File
        Import image header information from an associated JSON file (may be necessary
        to determine phase encoding information
    pe_dir: PE
        Manually specify the phase encoding direction of the input series; can be a
        signed axis number (e.g. -0, 1, +2), an axis designator (e.g. RL, PA, IS), or
        NIfTI axis codes (e.g. i-, j, k)
    readout_time: float
        type=float,
        Manually specify the total readout time of the input series (in seconds)
    se_epi: image
        Provide an additional image series consisting of spin-echo EPI images, which is
        to be used exclusively by topup for estimating the inhomogeneity field (i.e. it
        will not form part of the output image series)
    align_seepi:
        action="store_true
        Achieve alignment between the SE-EPI images used for inhomogeneity field estimation,
        and the DWIs (more information in Description section)
    topup_options: TopupOptions
        Manually provide additional command-line options to the topup command (provide a
        string within quotation marks that contains at least one space, even if only
        passing a single command-line option to topup)
    topup_files: prefix
        help='Provide files generated by prior execution of the FSL "topup" command to
        be utilised by eddy
    eddy_mask: image
        Provide a processing mask to use for eddy, instead of having dwifslpreproc
        generate one internally using dwi2mask
    eddy_slspec: file
        Provide a file containing slice groupings for eddy's slice-to-volume registration
    eddy_options:
        Manually provide additional command-line options to the eddy command (provide a
        string within quotation marks that contains at least one space, even if only
        passing a single command-line option to eddy)
    eddyqc_text: directory
        Copy the various text-based statistical outputs generated by eddy, and the
        output of eddy_qc (if installed), into an output directory
    eddyqc_all: directory
        Copy ALL outputs generated by eddy (including images), and the output of eddy_qc
        (if installed), into an output directory
    rpe_none: bool
        Specify that no reversed phase-encoding image data is being provided; eddy will
        perform eddy current and motion correction only
    rpe_pair: bool
        Specify that a set of images (typically b=0 volumes) will be provided for use
        in inhomogeneity field estimation only (using the -se_epi option)
    rpe_all: bool
        Specify that ALL DWIs have been acquired with opposing phase-encoding
    rpe_header: bool
        Specify that the phase-encoding information can be found in the image header(s),
        and that this is the information that the script should use


    Examples
    --------
    A basic DWI acquisition, where all image volumes are acquired in a single protocol with fixed phase encoding
        dwifslpreproc DWI_in.mif DWI_out.mif -rpe_none -pe_dir ap -readout_time 0.55
        Due to use of a single fixed phase encoding, no EPI distortion correction can be
        applied in this case
    cmdline.add_example_usage('DWIs all acquired with a single fixed phase encoding; but additionally a pair of b=0 images with reversed phase encoding to estimate the inhomogeneity field
        mrcat b0_ap.mif b0_pa.mif b0_pair.mif -axis 3; dwifslpreproc DWI_in.mif DWI_out.mif -rpe_pair -se_epi b0_pair.mif -pe_dir ap -readout_time 0.72 -align_seepi
        Here the two individual b=0 volumes are concatenated into a single 4D image series, and this is provided to the script via the -se_epi option. Note that with the -rpe_pair option used here, which indicates that the SE-EPI image series contains one or more pairs of b=0 images with reversed phase encoding, the FIRST HALF of the volumes in the SE-EPI series must possess the same phase encoding as the input DWI series, while the second half are assumed to contain the opposite phase encoding direction but identical total readout time. Use of the -align_seepi option is advocated as long as its use is valid (more information in the Description section).')
    cmdline.add_example_usage('All DWI directions & b-values are acquired twice, with the phase encoding direction of the second acquisition protocol being reversed with respect to the first
        mrcat DWI_lr.mif DWI_rl.mif DWI_all.mif -axis 3; dwifslpreproc DWI_all.mif DWI_out.mif -rpe_all -pe_dir lr -readout_time 0.66
        Here the two acquisition protocols are concatenated into a single DWI series containing all acquired volumes. The direction indicated via the -pe_dir option should be the direction of phase encoding used in acquisition of the FIRST HALF of volumes in the input DWI series; ie. the first of the two files that was provided to the mrcat command. In this usage scenario, the output DWI series will contain the same number of image volumes as ONE of the acquired DWI series (ie. half of the number in the concatenated series); this is because the script will identify pairs of volumes that possess the same diffusion sensitisation but reversed phase encoding, and perform explicit recombination of those volume pairs in such a way that image contrast in regions of inhomogeneity is determined from the stretched rather than the compressed image.')
    cmdline.add_example_usage('Any acquisition scheme that does not fall into one of the example usages above
        mrcat DWI_*.mif DWI_all.mif -axis 3; mrcat b0_*.mif b0_all.mif -axis 3; dwifslpreproc DWI_all.mif DWI_out.mif -rpe_header -se_epi b0_all.mif -align_seepi
        With this usage, the relevant phase encoding information is determined entirely based on the contents of the relevant image headers, and dwifslpreproc prepares all metadata for the executed FSL commands accordingly. This can therefore be used if the particular DWI acquisition strategy used does not correspond to one of the simple examples as described in the prior examples. This usage is predicated on the headers of the input files containing appropriately-named key-value fields such that MRtrix3 tools identify them as such. In some cases, conversion from DICOM using MRtrix3 commands will automatically extract and embed this information; however this is not true for all scanner vendors and/or software versions. In the latter case it may be possible to manually provide these metadata; either using the -json_import command-line option of dwifslpreproc, or the -json_import or one of the -import_pe_* command-line options of MRtrix3\'s mrconvert command (and saving in .mif format) prior to running dwifslpreproc.')


    Author
    ------
    Robert E. Smith (robert.smith@florey.edu.au)'

    Citations
    ---------
    Andersson, J. L. & Sotiropoulos, S. N. An integrated approach to correction for off-resonance effects and subject movement in diffusion MR imaging. NeuroImage, 2015, 125, 1063-1078
    Smith, S. M.; Jenkinson, M.; Woolrich, M. W.; Beckmann, C. F.; Behrens, T. E.; Johansen-Berg, H.; Bannister, P. R.; De Luca, M.; Drobnjak, I.; Flitney, D. E.; Niazy, R. K.; Saunders, J.; Vickers, J.; Zhang, Y.; De Stefano, N.; Brady, J. M. & Matthews, P. M. Advances in functional and structural MR image analysis and implementation as FSL. NeuroImage, 2004, 23, S208-S219
    Skare, S. & Bammer, R. Jacobian weighting of distortion corrected EPI data. Proceedings of the International Society for Magnetic Resonance in Medicine, 2010, 5063', if performing recombination of diffusion-weighted volume pairs with opposing phase encoding directions
    Andersson, J. L.; Skare, S. & Ashburner, J. How to correct susceptibility distortions in spin-echo echo-planar images: application to diffusion tensor imaging. NeuroImage, 2003, 20, 870-888', if performing EPI susceptibility distortion correction
    Andersson, J. L. R.; Graham, M. S.; Zsoldos, E. & Sotiropoulos, S. N. Incorporating outlier detection and replacement into a non-parametric framework for movement and distortion correction of diffusion MR images. NeuroImage, 2016, 141, 556-572, if including "--repol" in -eddy_options input
    Andersson, J. L. R.; Graham, M. S.; Drobnjak, I.; Zhang, H.; Filippini, N. & Bastiani, M. Towards a comprehensive framework for movement and distortion correction of diffusion MR images: Within volume movement. NeuroImage, 2017, 152, 450-466, if including "--mporder" in -eddy_options input
    Bastiani, M.; Cottaar, M.; Fitzgibbon, S.P.; Suri, S.; Alfaro-Almagro, F.; Sotiropoulos, S.N.; Jbabdi, S.; Andersson, J.L.R. Automated quality control for within and between studies diffusion MRI data using a non-parametric framework for movement and distortion correction. NeuroImage, 2019, 184, 801-812', if using -eddyqc_text or -eddyqc_all option and eddy_quad is installed
    """
    wf = Workflow(
        name="dwipreproc",
        input_spec={
            "input": Mif,
            "se_epi": Mif,
        },
    )

    # from mrtrix3 import (
    #     CONFIG,
    #     RuntimeError,
    # )  # pylint: disable=no-name-in-module, import-outside-toplevel
    # from mrtrix3 import (
    #     app,
    #     fsl,
    #     image,
    #     matrix,
    #     path,
    #     phaseencoding,
    #     run,
    # )  # pylint: disable=no-name-in-module, import-outside-toplevel

    # @pydra.mark.task
    # def check_image_dims(input: ImageIn) -> None:
    #     if len(input.dims()) < 3:
    #         raise RuntimeError(f"Image '{input}' does not contain 3 spatial dimensions")
    #     if min(input.dims()[:3]) == 1:
    #         raise RuntimeError(
    #             f"Image '{input}' does not contain 3D spatial information (has axis with size 1)"
    #         )
    #     logger.debug(
    #         f"Image '{input}' is >= 3D, and does not contain a unity spatial dimension"
    #     )


    # fsl_path = os.environ.get("FSLDIR", "")
    # if not fsl_path:
    #     raise RuntimeError(
    #         "Environment variable FSLDIR is not set; please run appropriate FSL "
    #         "configuration script"
    #     )

    # if not pe_design == "None":
    #     topup_config_path = os.path.join(fsl_path, "etc", "flirtsch", "b02b0.cnf")
    #     if not os.path.isfile(topup_config_path):
    #         raise RuntimeError(
    #             "Could not find necessary default config file for FSL topup command "
    #             "(expected location: "
    #             + topup_config_path
    #             + ")"
    #         )
    #     topup_cmd = fsl.exe_name("topup")

    # if not fsl.eddy_binary(True) and not fsl.eddy_binary(False):
    #     raise RuntimeError("Could not find any version of FSL eddy command")
    # fsl_suffix = fsl.suffix()

    # Export the gradient table to the path requested by the user if necessary

    # if export_grad_mrtrix:
    #     check_output_path(path.from_user(ARGS.export_grad_mrtrix, False))
    #     grad_export = {"export_grad_mrtrix", path.from_user(ARGS.export_grad_mrtrix)}
    # if ARGS.export_grad_fsl:
    #     check_output_path(path.from_user(ARGS.export_grad_fsl[0], False))
    #     check_output_path(path.from_user(ARGS.export_grad_fsl[1], False))
    #     grad_export = {
    #         "export_grad_fsl": (
    #             path.from_user(ARGS.export_grad_fsl[0]),
    #             path.from_user(ARGS.export_grad_fsl[1]),
    #         )
    #     }

    # eddyqc_path = None
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
    if eddyqc_all:
        eddy_suppl_files.extend(
            [
                "eddy_outlier_free_data.nii.gz",
                "eddy_cnr_maps.nii.gz",
                "eddy_residuals.nii.gz",
            ]
        )
    # if eddyqc_path:
    #     if os.path.exists(eddyqc_path):
    #         if os.path.isdir(eddyqc_path):
    #             if any(
    #                 os.path.exists(os.path.join(eddyqc_path, filename))
    #                 for filename in eddyqc_files
    #             ):
    #                 if app.FORCE_OVERWRITE:
    #                     logger.warning(
    #                         "Output eddy QC directory already contains relevant files; these will be overwritten on completion"
    #                     )
    #                 else:
    #                     raise RuntimeError(
    #                         "Output eddy QC directory already contains relevant files (use -force to override)"
    #                     )
    #         else:
    #             if app.FORCE_OVERWRITE:
    #                 logger.warning(
    #                     "Target for eddy QC output is not a directory; it will be overwritten on completion"
    #                 )
    #             else:
    #                 raise RuntimeError(
    #                     "Target for eddy QC output exists, and is not a directory (use -force to override)"
    #                 )

    # eddy_manual_options = []
    # topup_file_userpath = None
    # if eddy_options:
    #     # Initially process as a list; we'll convert back to a string later
    #     eddy_manual_options = eddy_options.strip().split()
    #     # Check for erroneous usages before we perform any data importing
    #     if any(entry.startswith("--mask=") for entry in eddy_manual_options):
    #         raise RuntimeError(
    #             'Cannot provide eddy processing mask via -eddy_options "--mask=..." as manipulations are required; use -eddy_mask option instead'
    #         )
    #     if any(entry.startswith("--slspec=") for entry in eddy_manual_options):
    #         raise RuntimeError(
    #             'Cannot provide eddy slice specification file via -eddy_options "--slspec=..." as manipulations are required; use -eddy_slspec option instead'
    #         )
    #     if "--resamp=lsr" in eddy_manual_options:
    #         raise RuntimeError(
    #             "dwifslpreproc does not currently support least-squares reconstruction; this cannot be simply passed via -eddy_options"
    #         )
    #     eddy_topup_entry = [
    #         entry for entry in eddy_manual_options if entry.startswith("--topup=")
    #     ]
    #     if len(eddy_topup_entry) > 1:
    #         raise RuntimeError(
    #             'Input to -eddy_options contains multiple "--topup=" entries'
    #         )
    #     if eddy_topup_entry:
    #         # -topup_files and -se_epi are mutually exclusive, but need to check in case
    #         #   pre-calculated topup output files were provided this way instead
    #         if se_epi:
    #             raise RuntimeError(
    #                 'Cannot use both -eddy_options "--topup=" and -se_epi'
    #             )
    #         topup_file_userpath = path.from_user(
    #             eddy_topup_entry[0][len("--topup=") :], False
    #         )
    #         eddy_manual_options = [
    #             entry
    #             for entry in eddy_manual_options
    #             if not entry.startswith("--topup=")
    #         ]

    # # Don't import slspec file directly; just make sure it exists
    # if eddy_slspec and not os.path.isfile(wf.lzin.eddy_slspec, False):
    #     raise RuntimeError(
    #         f'Unable to find file "{eddy_slspec}" provided via -eddy_slspec option'
    #     )

    # # Attempt to find pre-generated topup files before constructing the scratch directory
    # topup_input_movpar = None
    # topup_input_fieldcoef = None
    # if topup_files:
    #     if topup_file_userpath:
    #         raise RuntimeError(
    #             'Cannot use -topup_files option and also specify "... --topup=<prefix> ..." within content of -eddy_options'
    #         )
    #     topup_file_userpath = wf.lzin.topup_files, False

    # execute_applytopup = pe_design != "None" or topup_files
    # if execute_applytopup:
    # applytopup_cmd = fsl.exe_name("applytopup")

    # if topup_file_userpath:
    #     # Find files based on what the user may or may not have specified:
    #     # - Path to the movement parameters text file
    #     # - Path to the field coefficients image
    #     # - Path prefix including the underscore
    #     # - Path prefix omitting the underscore

    #     def check_movpar():
    #         if not os.path.isfile(topup_input_movpar):
    #             raise RuntimeError(
    #                 'No topup movement parameter file found based on path "'
    #                 + topup_file_userpath
    #                 + '" (expected location: '
    #                 + topup_input_movpar
    #                 + ")"
    #             )

    #     def find_fieldcoef(fieldcoef_prefix):
    #         fieldcoef_candidates = glob.glob(fieldcoef_prefix + "_fieldcoef.nii*")
    #         if not fieldcoef_candidates:
    #             raise RuntimeError(
    #                 'No topup field coefficient image found based on path "'
    #                 + topup_file_userpath
    #                 + '"'
    #             )
    #         if len(fieldcoef_candidates) > 1:
    #             raise RuntimeError(
    #                 'Multiple topup field coefficient images found based on path "'
    #                 + topup_file_userpath
    #                 + '": '
    #                 + str(fieldcoef_candidates)
    #             )
    #         return fieldcoef_candidates[0]

    #     if os.path.isfile(topup_file_userpath):
    #         if topup_file_userpath.endswith("_movpar.txt"):
    #             topup_input_movpar = topup_file_userpath
    #             topup_input_fieldcoef = find_fieldcoef(
    #                 topup_file_userpath[: -len("_movpar.txt")]
    #             )
    #         elif topup_file_userpath.endswith(
    #             "_fieldcoef.nii"
    #         ) or topup_file_userpath.endswith("_fieldcoef.nii.gz"):
    #             topup_input_fieldcoef = topup_file_userpath
    #             topup_input_movpar = topup_file_userpath
    #             if topup_input_movpar.endswith(".gz"):
    #                 topup_input_movpar = topup_input_movpar[: -len(".gz")]
    #             topup_input_movpar = (
    #                 topup_input_movpar[: -len("_fieldcoef.nii")] + "_movpar.txt"
    #             )
    #             check_movpar()
    #         else:
    #             raise RuntimeError(
    #                 'Unrecognised file "'
    #                 + topup_file_userpath
    #                 + '" specified as pre-calculated topup susceptibility field'
    #             )
    #     else:
    #         topup_input_movpar = topup_file_userpath
    #         if topup_input_movpar[-1] == "_":
    #             topup_input_movpar = topup_input_movpar[:-1]
    #         topup_input_movpar += "_movpar.txt"
    #         check_movpar()
    #         topup_input_fieldcoef = find_fieldcoef(
    #             topup_input_movpar[: -len("_movpar.txt")]
    #         )

    # TODO: header field manipulation Rob

    # wf.add(
    #     mrconvert(
    #         input=wf.lzin.input,
    #         grad=wf.lzin.grad,
    #         json_import=wf.lzin.json_import,
    #         json_export=wf.lzin.json_export,
    #         name="import_dwi",
    #     )
    # )  # output=path.to_scratch("dwi.mif")
    # if se_epi:
    #     image.check_3d_nonunity(wf.lzin.se_epi, False)
    #     wf.add(
    #         mrconvert(input=wf.lzin.se_epi, name="import_seepi")
    #     )  # output=path.to_scratch("se_epi.mif")

    # # ROB: What is the topup_file_userpath
    # if topup_file_userpath:
    #     run.function(
    #         shutil.copyfile,
    #         topup_input_movpar,
    #         path.to_scratch("field_movpar.txt", False),
    #     )
    #     # Can't run field spline coefficients image through mrconvert:
    #     #   topup encodes voxel sizes within the three NIfTI intent parameters, and
    #     #   applytopup requires that these be set, but mrconvert will wipe them
    #     run.function(
    #         shutil.copyfile,
    #         topup_input_fieldcoef,
    #         path.to_scratch(
    #             "field_fieldcoef.nii"
    #             + (".gz" if topup_input_fieldcoef.endswith(".nii.gz") else ""),
    #             False,
    #         ),
    #     )

    # if eddy_mask:
    #     wf.add(
    #         mrconvert(input=wf.lzin.eddy_mask, datatype="bit", name="import_eddy_mask")
    #     )  # output=path.to_scratch("eddy_mask.mif"),

    # app.goto_scratch_dir()

    # Deal with slice timing information for eddy slice-to-volume correction
    wf.add(
        strategy_identification_wf(
            slice_to_volume=slice_to_volume,
            bzero_threshold=bzero_threshold,
        )(
            input=wf.lzin.input,    
            name="stragy_identification"
        )
    )

    
    wf.add(
        susceptibility_estimation_wf(have_se_epi)(
            input=wf.lzin.input,
            se_epi=wf.import_seepi.lzout.output,
        )
    )

    
    wf.add(
        eddy_current_corr_wf(have_topup, slice_to_volume, dwi_has_pe_contrast)(
            input=wf.lzin.input,
            topup_fieldcoeff=wf.susceptibility_estimation_wf.topup_fieldcoeff,
            slice_timings=wf.stragy_identification.slice_timings,
        )
    )    

    
    # Find the index of the first DWI volume that is a b=0 volume
    # This needs to occur at the outermost loop as it is pertinent information
    #   not only for the -align_seepi option, but also for when the -se_epi option
    #   is not provided at all, and the input to topup is extracted solely from the DWIs
    dwi_first_bzero_index = 0
    for line in grad:
        if line[3] <= bzero_threshold:
            break
        dwi_first_bzero_index += 1
    logger.debug("Index of first b=0 image in DWIs is " + str(dwi_first_bzero_index))



    # Deal with the phase-encoding of the images to be fed to topup (if applicable)
    #execute_topup = (not pe_design == "None") and not topup_file_userpath
    execute_topup = 
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

        if align_seepi:
            for field_name, description in {
                "EchoTime": "echo time",
                "RepetitionTime": "repetition time",
                "FlipAngle": "flip angle",
            }.items():
                dwi_value = dwi_header.keyval().get(field_name)
                se_epi_value = se_epi_header.keyval().get(field_name)
                if dwi_value and se_epi_value and dwi_value != se_epi_value:
                    logger.warning(
                        "It appears that the spin-echo EPI images used for inhomogeneity field estimation have a different "
                        + description
                        + " to the DWIs being corrected. "
                        "This may cause issues in estimation of the field, as the first DWI b=0 volume will be added to the input series to topup "
                        "due to use of the -align_seepi option."
                    )

            # If we are using the -se_epi option, and hence the input images to topup have not come from the DWIs themselves,
            #   we need to insert the first b=0 DWI volume to the start of the topup input image. Otherwise, the field estimated
            #   by topup will not be correctly aligned with the volumes as they are processed by eddy.
            #
            # However, there's also a code path by which we may have already performed this addition.
            # If we have already apliced the b=0 volumes from the DWI input with the SE-EPI image
            #   (due to the absence of phase-encoding contrast in the SE-EPI series), we don't want to
            #   re-attempt such a concatenation; the fact that the DWI b=0 images were inserted ahead of
            #   the SE-EPI images means the alignment issue should be dealt with.

            if dwi_first_bzero_index == len(grad) and not dwi_bzero_added_to_se_epi:
                logger.warning(
                    "Unable to find b=0 volume in input DWIs to provide alignment between topup and eddy; script will proceed as though the -align_seepi option were not provided"
                )

            # If b=0 volumes from the DWIs have already been added to the SE-EPI image due to an
            #   absence of phase-encoding contrast in the latter, we don't need to perform the following
            elif not dwi_bzero_added_to_se_epi:
                wf.add(
                    mrconvert(
                        input=wf.import_dwi.lzout.output,
                        coord=(3, dwi_first_bzero_index),
                        axes="0,1,2",
                        name="dwi_extract_first_bzero",
                    )
                )  # output="dwi_first_bzero.mif"
                dwi_first_bzero_pe = (
                    dwi_manual_pe_scheme[dwi_first_bzero_index]
                    if overwrite_dwi_pe_scheme
                    else dwi_pe_scheme[dwi_first_bzero_index]
                )

                se_epi_pe_sum = [0, 0, 0]
                se_epi_volume_to_remove = len(se_epi_pe_scheme)
                for index, line in enumerate(se_epi_pe_scheme):
                    se_epi_pe_sum = [i + j for i, j in zip(se_epi_pe_sum, line[0:3])]
                    if (
                        se_epi_volume_to_remove == len(se_epi_pe_scheme)
                        and line[0:3] == dwi_first_bzero_pe[0:3]
                    ):
                        se_epi_volume_to_remove = index
                new_se_epi_path = (
                    os.path.splitext(se_epi_path)[0] + "_firstdwibzero.mif"
                )
                if (se_epi_pe_sum == [0, 0, 0]) and (
                    se_epi_volume_to_remove < len(se_epi_pe_scheme)
                ):
                    logger.info(
                        "Balanced phase-encoding scheme detected in SE-EPI series; volume "
                        + str(se_epi_volume_to_remove)
                        + " will be removed and replaced with first b=0 from DWIs"
                    )

                    wf.add(
                        mrconvert(
                            input=se_epi_path,
                            coord=(
                                3
                                + [
                                    index
                                    for index in range(len(se_epi_pe_scheme))
                                    if not index == se_epi_volume_to_remove
                                ]
                            ),
                            name="seepi_remove_one_volume_with_dwi_pe",
                        )
                    )
                    wf.add(
                        mrcat(
                            input=[
                                wf.dwi_extract_first_bzero.lzout.output,
                                wf.seepi_remove_one_volume_with_dwi_pe.lzout.output,
                            ],
                            axis=3,
                            name="balanced_concat_dwibzero_seepi",
                        )
                    )
                    # Also need to update the phase-encoding scheme appropriately if it's being set manually
                    #   (if embedded within the image headers, should be updated through the command calls)
                    if se_epi_manual_pe_scheme:
                        first_line = list(manual_pe_dir)
                        first_line.append(trt)
                        new_se_epi_manual_pe_scheme = []
                        new_se_epi_manual_pe_scheme.append(first_line)
                        for index, entry in enumerate(se_epi_manual_pe_scheme):
                            if not index == se_epi_volume_to_remove:
                                new_se_epi_manual_pe_scheme.append(entry)
                        se_epi_manual_pe_scheme = new_se_epi_manual_pe_scheme
                else:
                    if se_epi_pe_sum == [0, 0, 0] and se_epi_volume_to_remove == len(
                        se_epi_pe_scheme
                    ):
                        logger.info(
                            "Phase-encoding scheme of -se_epi image is balanced, but could not find appropriate volume with which to substitute first b=0 volume from DWIs; first b=0 DWI volume will be inserted to start of series, resulting in an unbalanced scheme"
                        )
                    else:
                        logger.info(
                            "Unbalanced phase-encoding scheme detected in series provided via -se_epi option; first DWI b=0 volume will be inserted to start of series"
                        )
                    wf.add(
                        mrcat(
                            input=(
                                wf.dwi_extract_first_bzero.lzout.output,
                                wf.import_seepi.lzout.output,
                            ),
                            output=new_se_epi_path,
                            axis=3,
                            name="unbalanced_concat_dwibzero_seepi",
                        )
                    )
                    # Also need to update the phase-encoding scheme appropriately
                    if se_epi_manual_pe_scheme:
                        first_line = list(manual_pe_dir)
                        first_line.append(trt)
                        se_epi_manual_pe_scheme = [first_line, se_epi_manual_pe_scheme]

                # Ended branching based on balanced-ness of PE acquisition scheme within SE-EPI volumes
                app.cleanup(se_epi_path)
                app.cleanup("dwi_first_bzero.mif")
                se_epi_path = new_se_epi_path

            # Ended branching based on:
            # - Detection of first b=0 volume in DWIs; or
            # - Prior merge of SE-EPI and DWI b=0 volumes due to no phase-encoding contrast in SE-EPI

        # Completed checking for presence of -se_epi option

    elif (
        not pe_design == "None" and not topup_file_userpath
    ):  # No SE EPI images explicitly provided: In some cases, can extract appropriate b=0 images from DWI
        # If using 'All' or 'Header', and haven't been given any topup images, need to extract the b=0 volumes from the series,
        #   preserving phase-encoding information while doing so
        # Preferably also make sure that there's some phase-encoding contrast in there...
        # With -rpe_all, need to write inferred phase-encoding to file and import before using dwiextract so that the phase-encoding
        #   of the extracted b=0's is propagated to the generated b=0 series
        wf.add(
            mrconvert(
                input=wf.import_dwi.lzout.output,
                import_pe_table=wf.save_dwi_pe_scheme.lzout.output,
                name="dwi_insert_pe_table",
            )
        )
        wf.add(
            dwiextract(
                input=wf.dwi_insert_pe_table.lzout.output,
                output=se_epi_path,
                bzero=True,
                name="extract_dwi_bzero_for_seepi",
            )
        )
        se_epi_header = image.Header(se_epi_path)

        # If there's no contrast remaining in the phase-encoding scheme, it'll be written to
        #   PhaseEncodingDirection and TotalReadoutTime rather than pe_scheme
        # In this scenario, we will be unable to run topup, or volume recombination
        if "pe_scheme" not in se_epi_header.keyval():
            if pe_design == "All":
                raise RuntimeError(
                    "DWI header indicates no phase encoding contrast between b=0 images; cannot proceed with volume recombination-based pre-processing"
                )
            logger.warning(
                "DWI header indicates no phase encoding contrast between b=0 images; proceeding without inhomogeneity field estimation"
            )
            execute_topup = False
            run.function(os.remove, se_epi_path)
            se_epi_path = None
            se_epi_header = None

    # If the first b=0 volume in the DWIs is in fact not the first volume (i.e. index zero), we're going to
    #   manually place it at the start of the DWI volumes when they are input to eddy, so that the
    #   first input volume to topup and the first input volume to eddy are one and the same.
    # Note: If at a later date, the statistical outputs from eddy are considered (e.g. motion, outliers),
    #   then this volume permutation will need to be taken into account
    if not topup_file_userpath:
        if dwi_first_bzero_index == len(grad):
            logger.warning(
                "No image volumes were classified as b=0 by MRtrix3; no permutation of order of DWI volumes can occur "
                + "(do you need to adjust config file entry BZeroThreshold?)"
            )
        elif dwi_first_bzero_index:
            logger.info(
                "First b=0 volume in input DWIs is volume index "
                + str(dwi_first_bzero_index)
                + "; "
                "this will be permuted to be the first volume (index 0) when eddy is run"
            )

            dwi_permvols_preeddy_slice = (
                str(dwi_first_bzero_index)
                + ",0"
                + (
                    ":" + str(dwi_first_bzero_index - 1)
                    if dwi_first_bzero_index > 1
                    else ""
                )
                + (
                    "," + str(dwi_first_bzero_index + 1)
                    if dwi_first_bzero_index < dwi_num_volumes - 1
                    else ""
                )
                + (
                    ":" + str(dwi_num_volumes - 1)
                    if dwi_first_bzero_index < dwi_num_volumes - 2
                    else ""
                )
            )
            # " -coord 3 1"
            dwi_permvols_posteddy_slice = (
                (":" + str(dwi_first_bzero_index) if dwi_first_bzero_index > 1 else "")
                + ",0"
                + (
                    "," + str(dwi_first_bzero_index + 1)
                    if dwi_first_bzero_index < dwi_num_volumes - 1
                    else ""
                )
                + (
                    ":" + str(dwi_num_volumes - 1)
                    if dwi_first_bzero_index < dwi_num_volumes - 2
                    else ""
                )
            )
            # logger.debug("mrconvert options for axis permutation:")
            # logger.debug("Pre: " + str(dwi_permvols_preeddy_option))
            # logger.debug("Post: " + str(dwi_permvols_posteddy_option))



    # se_epi_manual_pe_table_option = {}
    # if se_epi_manual_pe_scheme:
    #     phaseencoding.save("se_epi_manual_pe_scheme.txt", se_epi_manual_pe_scheme)
    #     se_epi_manual_pe_table_option = {"import_pe_table": "se_epi_manual_pe_scheme.txt"}

    # Need gradient table if running dwi2mask after applytopup to derive a brain mask for eddy
    wf.add(
        mrinfo(
            input=wf.import_dwi.lzout.output,
            export_grad_mrtrix="grad.b",
            name="dwi_export_dwscheme",
        )
    )
    dwi2mask_algo = CONFIG["Dwi2maskAlgorithm"]

    eddy_in_topup_option = ""
    dwi_post_eddy_crop = None
    slice_padded = False
    dwi_path = wf.import_dwi.lzout.output
    if execute_topup:
        # Add padding of odd spatial dimensions to the SE-EPI image if required

        # topup will crash if its input image has a spatial dimension with a non-even size;
        #   presumably due to a downsampling by a factor of 2 in a multi-resolution scheme
        # The newest eddy also requires the output from topup and the input DWIs to have the same size;
        #   therefore this restriction applies to the DWIs as well
        # Rather than crop in this case (which would result in a cropped output image),
        #   duplicate the last slice on any problematic axis, and then crop that extra
        #   slice at the output step
        # By this point, if the input SE-EPI images and DWIs are not on the same image grid, the
        #   SE-EPI images have already been re-gridded to DWI image space;
        # odd_axis_count = 0
        # for axis_size in dwi_header.size()[:3]:
        #     if int(axis_size % 2):
        #         odd_axis_count += 1
        # if odd_axis_count:
        #     logger.info(
        #         str(odd_axis_count)
        #         + " spatial "
        #         + ("axes of DWIs have" if odd_axis_count > 1 else "axis of DWIs has")
        #         + " non-even size; "
        #         "this will be automatically padded for compatibility with topup, and the extra slice"
        #         + ("s" if odd_axis_count > 1 else "")
        #         + " erased afterwards"
        #     )
        #     for axis, axis_size in enumerate(dwi_header.size()[:3]):

        #     axis_wf = Workflow(name="axis_processing", input_spec=["axis", "se_epi_path", "dwi_path"])
        #     if int(axis_size % 2):
        #         new_se_epi_path = (
        #             os.path.splitext(se_epi_path)[0] + "_pad" + str(axis) + ".mif"
        #         )
        #         axis_wf.add(mrconvert(input=se_epi_path, output="-", coord=axis_wf.lzin.axis, " " + str(axis_size - 1), name="seepi_extract_slice_for_padding_axis%d" % axis))
        #         axis_wf.add(mrcat(input=(se_epi_path, getattr(wf, "seepi_extract_slice_for_padding_axis%d" % axis).output), output=new_se_epi_path, "-axis " + str(axis), name="seepi_pad_axis%d" % axis))
        #         app.cleanup(se_epi_path)
        #         se_epi_path = new_se_epi_path
        #         new_dwi_path = (
        #             os.path.splitext(dwi_path)[0] + "_pad" + str(axis) + ".mif"
        #         )
        #         axis_wf.add(mrconvert(input=dwi_path, output="-", coord=axis_wf.lzin.axis, + " " + str(axis_size - 1) + clear="dw_scheme", name="dwi_extract_slice_for_padding_axis%d" % axis))
        #         axis_wf.add(mrcat(input=(dwi_path, getattr(wf, "dwi_extract_slice_for_padding_axis%d" % axis).output), output=new_dwi_path, axis=axis_wf.lzin.axis, name="dwi_pad_axis%d" % axis))
        #         app.cleanup(dwi_path)
        #         dwi_path = new_dwi_path
        dwi_post_eddy_crop = (axis, f"0:{axis_size - 1}")
        # if axis == slice_encoding_axis:
        #     slice_padded = True
        #     dwi_num_slices += 1
        #     # If we are padding the slice axis, and performing slice-to-volume correction,
        #     #   then we need to perform the corresponding padding to the slice timing
        #     if eddy_mporder:
        #         # At this point in the script, this information may be encoded either within
        #         #   the slice timing vector (as imported from the image header), or as
        #         #   slice groups (i.e. in the format expected by eddy). How these data are
        #         #   stored affects how the padding is performed.
        #         if slice_timing:
        #             slice_timing.append(slice_timing[-1])
        #         elif slice_groups:
        #             # Can't edit in place when looping through the list
        #             new_slice_groups = []
        #             for group in slice_groups:
        #                 if axis_size - 1 in group:
        #                     group.append(axis_size)
        #                 new_slice_groups.append(group)
        #             slice_groups = new_slice_groups

        # Do the conversion in preparation for topup
        wf.add(
            mrconvert(
                input=se_epi_path,
                output="topup_in.nii",
                import_pe_table=wf.se_epi_manual_table_export.lzout.output,
                strides="-1,+2,+3,+4 ",
                export_pe_table="topup_datain.txt",
                name="seepi_export_for_topup",
            )
        )
        app.cleanup(se_epi_path)

        # Run topup
        topup_manual_options = ""
        if topup_options:
            topup_manual_options = " " + topup_options.strip()
        wf.add(
            TOPUP(
                in_file="topup_in.nii",
                encoding_file="topup_datain.txt",
                out_base="field",
                out_field="field_map" + fsl_suffix,
                config=topup_config_path,
                verbose=topup_manual_options,
                name="topup",
            )
        )
        # with open("topup_output.txt", "wb") as topup_output_file:
        #     topup_output_file.write(
        #         (topup_output.stdout + "\n" + topup_output.stderr + "\n").encode(
        #             "utf-8", errors="replace"
        #         )
        #     )
        if app.VERBOSITY > 1:
            logger.info("Output of topup command:")
            sys.stderr.write(topup_output.stdout + "\n" + topup_output.stderr + "\n")

    if execute_applytopup:
        # Apply the warp field to the input image series to get an initial corrected volume estimate
        # applytopup can't receive the complete DWI input and correct it as a whole, because the phase-encoding
        #   details may vary between volumes
        if dwi_manual_pe_scheme:
            wf.add(
                mrconvert(
                    input=dwi_path,
                    import_pe_table=wf.save_dwi_pe_scheme.lzout.output,
                    name="dwi_import_manual_pe_scheme_for_applytopup",
                )
            )
            wf.add(
                mrinfo(
                    input=wf.dwi_import_manual_pe_scheme_for_applytopup.lzout.output,
                    export_pe_eddy=("applytopup_config.txt", "applytopup_indices.txt"),
                    name="generate_applytopup_textfiles",
                )
            )
        else:
            wf.add(
                mrinfo(
                    input=dwi_path,
                    export_pe_eddy=("applytopup_config.txt", "applytopup_indices.txt"),
                    name="generate_applytopup_textfiles",
                )
            )

        # Call applytopup separately for each unique phase-encoding
        # This should be the most compatible option with more complex phase-encoding acquisition designs,
        #   since we don't need to worry about applytopup performing volume recombination
        # Plus, recombination doesn't need to be optimal; we're only using this to derive a brain mask
        applytopup_image_list = []
        index = 1
        applytopup_config = matrix.load_matrix("applytopup_config.txt")
        applytopup_indices = matrix.load_vector("applytopup_indices.txt", dtype=int)
        applytopup_volumegroups = [
            [index for index, value in enumerate(applytopup_indices) if value == group]
            for group in range(1, len(applytopup_config) + 1)
        ]
        logger.debug("applytopup_config: " + str(applytopup_config))
        logger.debug("applytopup_indices: " + str(applytopup_indices))
        logger.debug("applytopup_volumegroups: " + str(applytopup_volumegroups))
        for index, group in enumerate(applytopup_volumegroups):
            prefix = os.path.splitext(dwi_path)[0] + "_pe_" + str(index)
            nifti_path = prefix + ".nii"
            json_path = prefix + ".json"
            temp_path = prefix + "_applytopup.nii"
            output_path = prefix + "_applytopup.mif"
            wf.add(
                mrconvert(
                    input=dwi_path,
                    output=nifti_path,
                    coord=[3] + group,
                    strides="-1,+2,+3,+4",
                    json_export=json_path,
                    name="extract_volumes_for_applytopup_group%d" % index,
                )
            )
            wf.add(
                ApplyTOPUP(
                    imain=getattr(
                        wf, "extract_volumes_for_applytopup_group%d" % index
                    ).output,
                    datain="applytopup_config.txt",
                    inindex=index + 1,
                    topup="field",
                    out=temp_path,
                    method="jac",
                    name="applytopup_group%d" % index,
                )
            )
            app.cleanup(nifti_path)
            temp_path = fsl.find_image(temp_path)
            wf.add(
                mrconvert(
                    input=temp_path,
                    output=output_path,
                    json_import=json_path,
                    name="post_applytopup_reimport_json",
                )
            )
            app.cleanup(json_path)
            app.cleanup(temp_path)
            applytopup_image_list.append(output_path)
            index += 1

        # Use the initial corrected volumes to derive a brain mask for eddy
        if not eddy_mask:
            dwi2mask_out_path = "dwi2mask_out.mif"
            if len(applytopup_image_list) == 1:
                dwi2mask_in_path = applytopup_image_list[0]
            else:
                dwi2mask_in_path = "dwi2mask_in.mif"
                wf.add(
                    mrcat(
                        input=applytopup_image_list,
                        output=dwi2mask_in_path,
                        axis=3,
                        name="post_applytopup_concat_groups",
                    )
                )
            wf.add(
                dwi2mask(
                    input=dwi2mask_in_path,
                    algorithm=dwi2mask_algo,
                    output=dwi2mask_out_path,
                    name="post_applytopup_dwi2mask_for_eddy",
                )
            )
            wf.add(
                maskfilter(
                    input=dwi2mask_out_path,
                    operation="dilate",
                    output="-",
                    name="dilate_post_applytopup_brainmask",
                )
            )
            wf.add(
                mrconvert(
                    input=wf.dilate_post_applytopup_brainmask.lzout.output,
                    output="eddy_mask.nii",
                    datatype="float32",
                    strides="-1,+2,+3",
                    name="export_brainmask_for_eddy",
                )
            )
            if len(applytopup_image_list) > 1:
                app.cleanup(dwi2mask_in_path)
            app.cleanup(dwi2mask_out_path)

        app.cleanup(applytopup_image_list)

        eddy_in_topup_option = " --topup=field"

    else:
        # Generate a processing mask for eddy based on the uncorrected input DWIs
        if not eddy_mask:
            dwi2mask_out_path = "dwi2mask_out.mif"
            wf.add(
                dwi2mask(
                    input=dwi_path,
                    algorithm=dwi2mask_algo,
                    output=dwi2mask_out_path,
                    name="dwi2mask_pre_eddy",
                )
            )
            wf.add(
                maskfilter(
                    input=dwi2mask_out_path,
                    operation="dilate",
                    output="-",
                    name="dilate_brainmask_for_eddy",
                )
            )
            wf.add(
                mrconvert(
                    input=wf.dilate_brainmask_for_eddy.lzout.output,
                    output="eddy_mask.nii",
                    datatype="float32",
                    strides="-1,+2,+3",
                    name="export_brainmask_for_eddy",
                )
            )
            app.cleanup(dwi2mask_out_path)

    # Use user supplied mask for eddy instead of one derived from the images using dwi2mask
    if eddy_mask:
        if image.match("eddy_mask.mif", dwi_path, up_to_dim=3):
            wf.add(
                mrconvert(
                    input=wf.import_eddy_mask.lzout.output,
                    output="eddy_mask.nii",
                    datatype="float32",
                    stride="-1,+2,+3",
                    name="convert_manual_brainmask_for_eddy",
                )
            )
        else:
            logger.warning(
                "User-provided processing mask for eddy does not match DWI voxel grid; resampling"
            )
            wf.add(
                mrtransform(
                    input=wf.import_eddy_mask.lzout.output,
                    output="-",
                    template=wf.import_dwi.lzout.output,
                    interp="linear",
                    name="resample_manual_brainmask_to_dwi",
                )
            )
            wf.add(
                mrthreshold(
                    input=wf.resample_manual_brainmask_to_dwi.lzout.output,
                    output="-",
                    abs=0.5,
                    name="threshold_resampled_manual_brainmask",
                )
            )
            wf.add(
                mrconvert(
                    input=wf.threshold_resampled_manual_brainmask.lzout.output,
                    output="eddy_mask.nii",
                    datatype="float32",
                    stride="-1,+2,+3",
                    name="convert_resampled_brainmask_for_eddy",
                )
            )
        app.cleanup("eddy_mask.mif")

    # Generate the text file containing slice timing / grouping information if necessary
    if eddy_mporder:
        if slice_timing:
            # This list contains, for each slice, the timing offset between acquisition of the
            #   first slice in the volume, and acquisition of that slice
            # Eddy however requires a text file where each row contains those slices that were
            #   acquired with a single readout, in ordered rows from first slice (group)
            #   acquired to last slice (group) acquired
            if sum(slice_encoding_direction) < 0:
                slice_timing = reversed(slice_timing)
            slice_groups = [
                [x[0] for x in g]
                for _, g in itertools.groupby(
                    sorted(enumerate(slice_timing), key=lambda x: x[1]),
                    key=lambda x: x[1],
                )
            ]  # pylint: disable=unused-variable
            logger.debug("Slice timing: " + str(slice_timing))
            logger.debug("Resulting slice groups: " + str(slice_groups))
        # Variable slice_groups may have already been defined in the correct format.
        #   In that instance, there's nothing to do other than write it to file;
        #   UNLESS the slice encoding direction is known to be reversed, in which case
        #   we need to reverse the timings. Would think that this would however be
        #   rare, given it requires that the slspec text file be provided manually but
        #   SliceEncodingDirection to be present.
        elif slice_groups and sum(slice_encoding_direction) < 0:
            new_slice_groups = []
            for group in new_slice_groups:
                new_slice_groups.append([dwi_num_slices - index for index in group])
            logger.debug("Slice groups reversed due to negative slice encoding direction")
            logger.debug("Original: " + str(slice_groups))
            logger.debug("New: " + str(new_slice_groups))
            slice_groups = new_slice_groups

        matrix.save_numeric(
            "slspec.txt", slice_groups, add_to_command_history=False, fmt="%d"
        )
        eddy_manual_options.append("--slspec=slspec.txt")

    # Revert eddy_manual_options from a list back to a single string
    eddy_manual_options = (
        (" " + " ".join(eddy_manual_options)) if eddy_manual_options else ""
    )

    # Prepare input data for eddy
    wf.add(
        mrconvert(
            input=dwi_path,
            output="eddy_in.nii",
            import_pe_table=wf.save_dwi_pe_scheme.lzout.output,
            coord=(3, dwi_permvols_preeddy_slice),
            strides="-1,+2,+3,+4",
            export_grad_fsl=("bvecs", "bvals"),
            export_pe_eddy=("eddy_config.txt", "eddy_indices.txt"),
            name="convert_inputs_to_eddy",
        )
    )

    # Run eddy
    # If a CUDA version is in PATH, run that first; if it fails, re-try using the non-CUDA version
    eddy_all_options = (
        "--imain=eddy_in.nii --mask=eddy_mask.nii --acqp=eddy_config.txt --index=eddy_indices.txt --bvecs=bvecs --bvals=bvals"
        + eddy_in_topup_option
        + eddy_manual_options
        + " --out=dwi_post_eddy --verbose"
    )
    eddy_cuda_cmd = fsl.eddy_binary(True)
    eddy_openmp_cmd = fsl.eddy_binary(False)
    wf.add(Eddy(eddy_all_options, name="eddy"))
    # if eddy_cuda_cmd:
    #     # If running CUDA version, but OpenMP version is also available, don't stop the script if the CUDA version fails
    #     try:
    #         eddy_output = run.command(eddy_cuda_cmd + " " + eddy_all_options)
    #     except run.MRtrixCmdError as exception_cuda:
    #         if not eddy_openmp_cmd:
    #             raise
    #         with open("eddy_cuda_failure_output.txt", "wb") as eddy_output_file:
    #             eddy_output_file.write(
    #                 str(exception_cuda).encode("utf-8", errors="replace")
    #             )
    #         logger.info(
    #             "CUDA version of 'eddy' was not successful; attempting OpenMP version"
    #         )
    #         try:
    #             eddy_output = run.command(eddy_openmp_cmd + " " + eddy_all_options)
    #         except run.MRtrixCmdError as exception_openmp:
    #             with open("eddy_openmp_failure_output.txt", "wb") as eddy_output_file:
    #                 eddy_output_file.write(
    #                     str(exception_openmp).encode("utf-8", errors="replace")
    #                 )
    #             # Both have failed; want to combine error messages
    #             eddy_cuda_header = (
    #                 ("=" * len(eddy_cuda_cmd))
    #                 + "\n"
    #                 + eddy_cuda_cmd
    #                 + "\n"
    #                 + ("=" * len(eddy_cuda_cmd))
    #                 + "\n"
    #             )
    #             eddy_openmp_header = (
    #                 ("=" * len(eddy_openmp_cmd))
    #                 + "\n"
    #                 + eddy_openmp_cmd
    #                 + "\n"
    #                 + ("=" * len(eddy_openmp_cmd))
    #                 + "\n"
    #             )
    #             exception_stdout = (
    #                 eddy_cuda_header
    #                 + exception_cuda.stdout
    #                 + "\n\n"
    #                 + eddy_openmp_header
    #                 + exception_openmp.stdout
    #                 + "\n\n"
    #             )
    #             exception_stderr = (
    #                 eddy_cuda_header
    #                 + exception_cuda.stderr
    #                 + "\n\n"
    #                 + eddy_openmp_header
    #                 + exception_openmp.stderr
    #                 + "\n\n"
    #             )
    #             raise run.MRtrixCmdError(
    #                 "eddy* " + eddy_all_options, 1, exception_stdout, exception_stderr
    #             )

    # else:
    #     eddy_output = run.command(eddy_openmp_cmd + " " + eddy_all_options)
    # with open("eddy_output.txt", "wb") as eddy_output_file:
    #     eddy_output_file.write(
    #         (eddy_output.stdout + "\n" + eddy_output.stderr + "\n").encode(
    #             "utf-8", errors="replace"
    #         )
    #     )
    if app.VERBOSITY > 1:
        logger.info("Output of eddy command:")
        sys.stderr.write(eddy_output.stdout + "\n" + eddy_output.stderr + "\n")
    app.cleanup("eddy_in.nii")

    eddy_output_image_path = fsl.find_image("dwi_post_eddy")

    # Check to see whether or not eddy has provided a rotated bvecs file;
    #   if it has, import this into the output image
    bvecs_path = "dwi_post_eddy.eddy_rotated_bvecs"
    if not os.path.isfile(bvecs_path):
        logger.warning(
            "eddy has not provided rotated bvecs file; using original gradient table. Recommend updating FSL eddy to version 5.0.9 or later."
        )
        bvecs_path = "bvecs"

    # Run eddy qc tool QUAD if installed and one of -eddyqc_text or -eddyqc_all is specified
    eddyqc_prefix = "dwi_post_eddy"
    if eddyqc_path:
        if shutil.which("eddy_quad"):
            eddyqc_mask = "eddy_mask.nii"
            eddyqc_fieldmap = fsl.find_image("field_map") if execute_topup else None
            eddyqc_slspec = "slspec.txt" if eddy_mporder else None

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

            eddyqc_kwargs = {}
            if os.path.isfile(eddyqc_prefix + ".eddy_residuals.nii.gz"):
                eddyqc_kwargs["bvecs"] = bvecs_path
            if execute_topup:
                eddyqc_kwargs["field"] = eddyqc_fieldmap
            if eddy_mporder:
                eddyqc_kwargs["slice_spec"] = eddyqc_slspec
            if app.VERBOSITY > 2:
                eddyqc_kwargs["verbose"] = True
            try:
                wf.add(
                    EddyQuad(
                        input=eddyqc_prefix,
                        idx_file="eddy_indices.txt",
                        param_file="eddy_config.txt",
                        bvals="bvals",
                        mask="eddyqc_mask",
                        name="eddy_quad",
                        **eddyqc_kwargs,
                    )
                )
            except run.MRtrixCmdError as exception:
                with open(
                    "eddy_quad_failure_output.txt", "wb"
                ) as eddy_quad_output_file:
                    eddy_quad_output_file.write(
                        str(exception).encode("utf-8", errors="replace")
                    )
                logger.debug(str(exception))
                logger.warning(
                    "Error running automated EddyQC tool 'eddy_quad'; QC data written to \""
                    + eddyqc_path
                    + '" will be files from "eddy" only'
                )
                # Delete the directory if the script only made it partway through
                try:
                    shutil.rmtree(eddyqc_prefix + ".qc")
                except OSError:
                    pass
        else:
            logger.info("Command 'eddy_quad' not found in PATH; skipping")

    # Have to retain these images until after eddyQC is run
    # If using -eddyqc_all, also write the mask provided to eddy to the output directory;
    #   therefore don't delete it yet here
    if not eddyqc_all:
        app.cleanup("eddy_mask.nii")
    if execute_topup:
        app.cleanup(fsl.find_image("field_fieldcoef"))

    # Get the axis strides from the input series, so the output image can be modified to match
    stride_option = ",".join([str(i) for i in dwi_header.strides()])

    # Determine whether or not volume recombination should be performed
    # This could be either due to use of -rpe_all option, or just due to the data provided with -rpe_header
    # Rather than trying to re-use the code that was used in the case of -rpe_all, run fresh code
    # The phase-encoding scheme needs to be checked also
    volume_matchings = [dwi_num_volumes] * dwi_num_volumes
    volume_pairs = []
    logger.debug(
        "Commencing gradient direction matching; " + str(dwi_num_volumes) + " volumes"
    )
    for index1 in range(dwi_num_volumes):
        if volume_matchings[index1] == dwi_num_volumes:  # As yet unpaired
            for index2 in range(index1 + 1, dwi_num_volumes):
                if volume_matchings[index2] == dwi_num_volumes:  # Also as yet unpaired
                    # Here, need to check both gradient matching and reversed phase-encode direction
                    if not any(
                        dwi_pe_scheme[index1][i] + dwi_pe_scheme[index2][i]
                        for i in range(0, 3)
                    ) and grads_match(index1, index2):
                        volume_matchings[index1] = index2
                        volume_matchings[index2] = index1
                        volume_pairs.append([index1, index2])
                        logger.debug(
                            "Matched volume "
                            + str(index1)
                            + " with "
                            + str(index2)
                            + "\n"
                            + "Phase encoding: "
                            + str(dwi_pe_scheme[index1])
                            + " "
                            + str(dwi_pe_scheme[index2])
                            + "\n"
                            + "Gradients: "
                            + str(grad[index1])
                            + " "
                            + str(grad[index2])
                        )
                        break

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

    # Grab any relevant files that eddy has created, and copy them to the requested directory
    if eddyqc_path:
        if (
            app.FORCE_OVERWRITE
            and os.path.exists(eddyqc_path)
            and not os.path.isdir(eddyqc_path)
        ):
            run.function(os.remove, eddyqc_path)
        if not os.path.exists(eddyqc_path):
            run.function(os.makedirs, eddyqc_path)
        for filename in eddy_suppl_files:
            if os.path.exists(eddyqc_prefix + "." + filename):
                # If this is an image, and axis padding was applied, want to undo the padding
                if filename.endswith(".nii.gz") and dwi_post_eddy_crop:
                    wf.add(
                        mrconvert(
                            input=eddyqc_prefix + "." + filename,
                            output=os.path.join(eddyqc_path, filename),
                            coord=dwi_post_eddy_crop,
                            force=app.FORCE_OVERWRITE,
                            name="export_eddy_qc_image_%s" % filename,
                        )
                    )
                else:
                    run.function(
                        shutil.copy,
                        eddyqc_prefix + "." + filename,
                        os.path.join(eddyqc_path, filename),
                    )
        # Also grab any files generated by the eddy qc tool QUAD
        if os.path.isdir(eddyqc_prefix + ".qc"):
            if app.FORCE_OVERWRITE and os.path.exists(
                os.path.join(eddyqc_path, "quad")
            ):
                run.function(shutil.rmtree, os.path.join(eddyqc_path, "quad"))
            run.function(
                shutil.copytree,
                eddyqc_prefix + ".qc",
                os.path.join(eddyqc_path, "quad"),
            )
        # Also grab the brain mask that was provided to eddy if -eddyqc_all was specified
        if eddyqc_all:
            if dwi_post_eddy_crop:
                wf.add(
                    mrconvert(
                        input="eddy_mask.nii",
                        output=os.path.join(eddyqc_path, "eddy_mask.nii"),
                        coord=dwi_post_eddy_crop,
                        force=app.FORCE_OVERWRITE,
                        name="export_eddy_mask",
                    )
                )
            else:
                run.function(
                    shutil.copy,
                    "eddy_mask.nii",
                    os.path.join(eddyqc_path, "eddy_mask.nii"),
                )
            app.cleanup("eddy_mask.nii")

    keys_to_remove = [
        "MultibandAccelerationFactor",
        "SliceEncodingDirection",
        "SliceTiming",
    ]
    # These keys are still relevant for the output data if no EPI distortion correction was performed
    if execute_applytopup:
        keys_to_remove.extend(
            ["PhaseEncodingDirection", "TotalReadoutTime", "pe_scheme"]
        )
    # Get the header key-value entries from the input DWI, remove those we don't wish to keep, and
    #   export the result to a new JSON file so that they can be inserted into the output header
    with open("dwi.json", "r", encoding="utf-8") as input_json_file:
        keyval = json.load(input_json_file)
    for key in keys_to_remove:
        keyval.pop(key, None)
    # Make sure to use the revised diffusion gradient table rather than that of the input;
    #  incorporates motion correction, and possibly also the explicit volume recombination
    keyval["dw_scheme"] = image.Header("result.mif").keyval()["dw_scheme"]
    # 'Stash' the phase encoding scheme of the original uncorrected DWIs, since it still
    #   may be useful information at some point in the future but is no longer relevant
    #   for e.g. tracking for different volumes, or performing any geometric corrections
    if execute_applytopup:
        keyval["prior_pe_scheme"] = (
            dwi_manual_pe_scheme if dwi_manual_pe_scheme else dwi_pe_scheme
        )
    with open("output.json", "w", encoding="utf-8") as output_json_file:
        json.dump(keyval, output_json_file)

    # Finish!
    wf.add(
        mrconvert(
            input="result.mif",
            mrconvert_keyval="output.json",
            force=app.FORCE_OVERWRITE,
            name="export_final_dwi",
            **grad_export,
        )
    )
