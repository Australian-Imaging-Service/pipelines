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

from logging import getLogger
import typing as ty
import attrs
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
import pydra.mark
from pydra import Workflow
from .examine_metadata import examine_metadata_wf
from .susceptibility_est import susceptibility_estimation_wf
from .eddy_current_corr import eddy_current_corr_wf
from .qc import qc_wf
from .volume_recombination import volume_recombination_wf


logger = getLogger(__name__)


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
    have_se_epi: bool,
    have_topup: bool,
    dwi_has_pe_contrast: bool,
    eddy_qc_all: bool = False,  # whether to include large eddy qc files in outputs    
    slice_to_volume: bool = True,  # whether to include slice-to-volume registration
    bzero_threshold: float = 10.0,
    volume_pairs: ty.List[ty.Tuple[int, int]] = None,
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
    if volume_pairs is None:
        volume_pairs = []

    wf = Workflow(
        name="dwipreproc",
        input_spec={
            "input": Mif,
            "se_epi": Mif,
        },
    )

    # Deal with slice timing information for eddy slice-to-volume correction
    wf.add(
        examine_metadata_wf(
            slice_to_volume=slice_to_volume,
            bzero_threshold=bzero_threshold,
        )(
            input=wf.lzin.input,    
            name="stragy_identification"
        )
    )

    wf.add(
        susceptibility_estimation_wf(
            have_se_epi=have_se_epi
        )(
            input=wf.lzin.input,
            se_epi=wf.import_seepi.lzout.output,
            dwi_first_bzero_index=wf.examine_metadata_wf.lzout.dwi_first_bzero_index,
            name="susceptibility_estimation_wf"
        )
    )

    wf.add(
        eddy_current_corr_wf(
            have_topup=have_topup,
            slice_to_volume=slice_to_volume, dwi_has_pe_contrast=dwi_has_pe_contrast,
            eddy_qc_all=eddy_qc_all
        )(
            input=wf.lzin.input,
            topup_fieldcoeff=wf.susceptibility_estimation_wf.lzout.topup_fieldcoeff,
            slice_timings=wf.stragy_identification.lzout.slice_timings,
            name="eddy_current_corr_wf",
        )
    )

    wf.add(
        qc_wf(
            eddy_qc_all=eddy_qc_all
        )(
            input=wf.lzin.input,
            name="qc_wf",
        )
    )

    wf.add(
        volume_recombination_wf(
            volume_pairs=volume_pairs,
        )(
            input=wf.eddy_current_corr_wf.lzout.output,
            name="volume_recombination_wf",
        )
    )

    wf.set_output([
        ("output", wf.volume_recombination_wf.lzout.output),
        ("qc_dir", wf.qc_wf.lzout.qc_dir)
    ])
