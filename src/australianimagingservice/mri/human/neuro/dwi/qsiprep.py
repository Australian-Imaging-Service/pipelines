import pydra
from pathlib import Path
import typing as ty
from fileformats.generic import File


@pydra.mark.task
def fix_multi_source_name(in_files: ty.List[File], dwi_only: bool, anatomical_contrast: str = "T1w") -> Path:
    """
    Make up a generic source name when there are multiple T1s

    >>> fix_multi_T1w_source_name([
    ...     '/path/to/sub-045_ses-test_T1w.nii.gz',
    ...     '/path/to/sub-045_ses-retest_T1w.nii.gz'])
    '/path/to/sub-045_T1w.nii.gz'

    """
    import os
    from nipype.utils.filemanip import filename_to_list
    base, in_file = os.path.split(filename_to_list(in_files)[0])
    subject_label = in_file.split("_", 1)[0].split("-")[1]
    if dwi_only:
        anatomical_contrast = "dwi"
        base = base.replace("/dwi", "/anat")
    return os.path.join(base, "sub-%s_%s.nii.gz" % (subject_label, anatomical_contrast))


@pydra.mark.task
def _seg2msks(in_file: File, newpath: ty.Optional[str] = None) -> ty.List[File]:
    """Converts labels to masks"""
    import nibabel as nb
    import numpy as np
    from nipype.utils.filemanip import fname_presuffix

    nii = nb.load(in_file)
    labels = nii.get_fdata()

    out_files = []
    for i in range(1, 4):
        ldata = np.zeros_like(labels)
        ldata[labels == i] = 1
        out_files.append(fname_presuffix(
            in_file, suffix='_label%03d' % i, newpath=newpath))
        nii.__class__(ldata, nii.affine, nii.header).to_filename(out_files[-1])

    return out_files


def qsiprep():

    wf = pydra.Workflow(name="qsiprep")

    wf.add(
        nipype.interfaces.mrtrix3.connectivity.LabelConvert(
            name="acpc_aseg_to_dseg",
            in_lut="/Users/tclose/git/workflows/qsiprep/qsiprep/data/FreeSurferColorLUT.txt",
            in_config="/Users/tclose/git/workflows/qsiprep/qsiprep/data/FreeSurfer2dseg.txt",
            out_file="acpc_dseg.nii.gz",
            environ={},
            in_file=wf.rigid_acpc_resample_aseg.lzout.output_image
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_aseg",
            base_directory=".",
            space="",
            desc="aseg",
            bundle="",
            suffix="dseg",
            keep_dtype=False,
            in_file=wf.lzin.t1_aseg,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_mask",
            base_directory=".",
            space="",
            desc="brain",
            bundle="",
            suffix="mask",
            keep_dtype=False,
            in_file=wf.lzin.t1_mask,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_mni_inv_warp",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="from-MNI152NLin2009cAsym_to-T1w_mode-image_xfm",
            keep_dtype=False,
            in_file=wf.lzin.t1_2_mni_reverse_transform,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_mni_warp",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm",
            keep_dtype=False,
            in_file=wf.lzin.t1_2_mni_forward_transform,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_preproc",
            base_directory=".",
            space="",
            desc="preproc",
            bundle="",
            suffix="",
            keep_dtype=True,
            in_file=wf.lzin.t1_preproc,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_seg",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="dseg",
            keep_dtype=False,
            in_file=wf.lzin.t1_seg,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_template_acpc_inv_transforms",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="from-T1wACPC_to-T1wNative_mode-image_xfm",
            keep_dtype=False,
            in_file=wf.lzin.t1_acpc_inv_transform,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_template_acpc_transforms",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="from-T1wNative_to-T1wACPC_mode-image_xfm",
            keep_dtype=False,
            in_file=wf.lzin.t1_acpc_transform,
            source_file=wf.t1_name.lzout.out
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_template_transforms",
            base_directory=".",
            bundle="",
            desc="",
            keep_dtype=False,
            space="",
            suffix="from-orig_to-T1w_mode-image_xfm",
            source_file=wf.lzin.source_files,
            in_file=wf.lzin.t1_template_transforms
        )
    )

    wf.add(
        fix_multi_source_name(
            name="t1_name",
            dwi_only=False,
            anatomical_contrast="T1w",
            in_files=wf.lzin.source_files
        )
    )
    wf.add(
        qsiprep.niworkflows.interfaces.registration.RobustMNINormalizationRPT(
            name="acpc_reg",
            out_report="report.svg",
            compress_report="auto",
            num_threads=1,
            flavor="precise",
            orientation="LPS",
            reference="T1w",
            moving="T1w",
            template="MNI152NLin2009cAsym",
            settings=["/Users/tclose/git/workflows/qsiprep/qsiprep/data/intramodal_ACPC.json"],
            template_resolution=1,
            explicit_masking=True,
            float=True,
            reference_image=wf.lzin.template_image,
            reference_mask=wf.lzin.template_mask,
            moving_image=wf.lzin.anatomical_reference,
            lesion_mask=wf.lzin.roi,
            moving_mask=wf.lzin.brain_mask
        )
    )
    wf.add(
        qsiprep.niworkflows.interfaces.registration.RobustMNINormalizationRPT(
            name="anat_nlin_normalization",
            out_report="report.svg",
            compress_report="auto",
            num_threads=1,
            flavor="precise",
            orientation="LPS",
            reference="T1w",
            moving="T1w",
            template="MNI152NLin2009cAsym",
            template_resolution=1,
            explicit_masking=True,
            float=True,
            reference_image=wf.lzin.template_image,
            reference_mask=wf.lzin.template_mask,
            moving_mask=wf.rigid_acpc_resample_mask.lzout.output_image,
            moving_image=wf.rigid_acpc_resample_anat.lzout.output_image
        )
    )
    wf.add(
        qsiprep.interfaces.itk.DisassembleTransform(
            name="disassemble_transform",
            in_file=wf.acpc_reg.lzout.composite_transform
        )
    )
    wf.add(
        qsiprep.interfaces.itk.AffineToRigid(
            name="extract_rigid_transform"
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            to_template_rigid_transform=wf.extract_rigid_transform.lzout.rigid_transform,
            from_template_rigid_transform=wf.extract_rigid_transform.lzout.rigid_transform_inverse,
            to_template_nonlinear_transform=wf.anat_nlin_normalization.lzout.composite_transform,
            from_template_nonlinear_transform=wf.anat_nlin_normalization.lzout.inverse_composite_transform,
            out_report=wf.anat_nlin_normalization.lzout.out_report
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_anat",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="LanczosWindowedSinc",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.lzin.template_image,
            input_image=wf.lzin.anatomical_reference,
            transforms=wf.extract_rigid_transform.lzout.rigid_transform
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_mask",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="MultiLabel",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.lzin.template_image,
            input_image=wf.lzin.brain_mask,
            transforms=wf.extract_rigid_transform.lzout.rigid_transform
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_2_mni_report",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="t1_2_mni",
            keep_dtype=False,
            source_file=wf.lzin.source_file,
            in_file=wf.lzin.t1_2_mni_report
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_conform_report",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="conform",
            keep_dtype=False,
            source_file=wf.lzin.source_file,
            in_file=wf.lzin.t1_conform_report
        )
    )
    wf.add(
        qsiprep.workflows.anatomical.volume.DerivativesDataSink(
            name="ds_t1_seg_mask_report",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="seg_brainmask",
            keep_dtype=False,
            source_file=wf.lzin.source_file,
            in_file=wf.lzin.seg_report
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        qsiprep.interfaces.images.Conform(
            name="anat_conform",
            deoblique_header=True,
            in_file=wf.template_dimensions.lzout.t1w_valid_list,
            target_zooms=wf.template_dimensions.lzout.target_zooms,
            target_shape=wf.template_dimensions.lzout.target_shape
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.ants.segmentation.N4BiasFieldCorrection(
            name="n4_correct",
            dimension=3,
            bspline_fitting_distance=200.0,
            shrink_factor=4,
            n_iterations=[50, 50, 50, 50],
            convergence_threshold=1e-07,
            save_bias=False,
            copy_header=True,
            rescale_intensities=False,
            num_threads=1,
            environ={"NSLOTS": "1"}
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            template_transforms=["/Users/tclose/git/workflows/qsiprep/qsiprep/data/itkIdentityTransform.txt"],
            out_report=wf.template_dimensions.lzout.out_report,
            valid_list=wf.template_dimensions.lzout.t1w_valid_list,
            bias_corrected=wf.n4_correct.lzout.output_image
        )
    )
    wf.add(
        qsiprep.niworkflows.interfaces.images.TemplateDimensions(
            name="template_dimensions",
            max_scale=3.0,
            t1w_list=wf.lzin.images
        )
    )
    wf.add(
        qsiprep.interfaces.anatomical.GetTemplate(
            name="get_template_image",
            template_name="MNI152NLin2009cAsym",
            infant_mode=False,
            anatomical_contrast="T1w"
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.afni.utils.Autobox(
            name="autobox_template",
            padding=8,
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.lzin.template_image
        )
    )
    wf.add(
        nipype.interfaces.afni.preprocess.Warp(
            name="deoblique_autobox",
            deoblique=True,
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.autobox_template.lzout.out_file
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            grid_image=wf.resample_to_voxel_size.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Resample(
            name="resample_to_voxel_size",
            voxel_size=[1.25, 1.25, 1.25],
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.deoblique_autobox.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            dwi_sampling_grid=wf.output_grid_wf.lzout.outputnode.grid_image,
            anat_template_transforms=wf.anat_template_wf.lzout.outputnode.template_transforms,
            segmentation_qc=wf.synthseg_anat_wf.lzout.outputnode.qc_file,
            acpc_transform=wf.anat_normalization_wf.lzout.outputnode.to_template_rigid_transform,
            acpc_inv_transform=wf.anat_normalization_wf.lzout.outputnode.from_template_rigid_transform,
            t1_2_mni_forward_transform=wf.anat_normalization_wf.lzout.outputnode.to_template_nonlinear_transform,
            t1_2_mni_reverse_transform=wf.anat_normalization_wf.lzout.outputnode.from_template_nonlinear_transform,
            t1_brain=wf.rigid_acpc_resample_brain.lzout.output_image,
            t1_mask=wf.rigid_acpc_resample_mask.lzout.output_image,
            t1_preproc=wf.rigid_acpc_resample_head.lzout.output_image,
            t1_aseg=wf.rigid_acpc_resample_aseg.lzout.output_image,
            t1_seg=wf.acpc_aseg_to_dseg.lzout.out_file
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            padded_image=wf.resample_skulled_to_reference.lzout.output_image
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.PrepareSynthStripGrid(
            name="prepare_synthstrip_reference",
            input_image=wf.skulled_autobox.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="resample_skulled_to_reference",
            dimension=3,
            out_postfix="_trans",
            interpolation="BSpline",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.image,
            reference_image=wf.prepare_synthstrip_reference.lzout.prepared_image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Resample(
            name="skulled_1mm_resample",
            voxel_size=[1.0, 1.0, 1.0],
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.lzin.image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Autobox(
            name="skulled_autobox",
            padding=3,
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.skulled_1mm_resample.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_aseg",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="MultiLabel",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.get_template_image.lzout.template_file,
            input_image=wf.synthseg_anat_wf.lzout.outputnode.aparc_image,
            transforms=wf.anat_normalization_wf.lzout.outputnode.to_template_rigid_transform
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_brain",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="LanczosWindowedSinc",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.get_template_image.lzout.template_file,
            input_image=wf.synthstrip_anat_wf.lzout.outputnode.brain_image,
            transforms=wf.anat_normalization_wf.lzout.outputnode.to_template_rigid_transform
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_head",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="LanczosWindowedSinc",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.get_template_image.lzout.template_file,
            input_image=wf.anat_template_wf.lzout.outputnode.bias_corrected,
            transforms=wf.anat_normalization_wf.lzout.outputnode.to_template_rigid_transform
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="rigid_acpc_resample_mask",
            input_image_type=0,
            out_postfix="_trans",
            interpolation="MultiLabel",
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.get_template_image.lzout.template_file,
            input_image=wf.synthstrip_anat_wf.lzout.outputnode.brain_mask,
            transforms=wf.anat_normalization_wf.lzout.outputnode.to_template_rigid_transform
        )
    )
    wf.add(
        _seg2msks(
            name="seg2msks",
            in_file=wf.outputnode.lzout.t1_seg
        )
    )
    wf.add(
        qsiprep.niworkflows.interfaces.masks.ROIsPlot(
            name="seg_rpt",
            masked=False,
            colors=["r", "magenta", "b", "g"],
            levels=None,
            mask_color="r",
            out_report="report.svg",
            compress_report="auto",
            in_mask=wf.outputnode.lzout.t1_mask,
            in_file=wf.outputnode.lzout.t1_preproc,
            in_rois=wf.seg2msks.lzout.out
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            aparc_image=wf.synthseg.lzout.out_seg,
            posterior_image=wf.synthseg.lzout.out_post,
            qc_file=wf.synthseg.lzout.out_qc
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.SynthSeg(
            name="synthseg",
            num_threads=1,
            fast=False,
            environ={"OMP_NUM_THREADS": "1"},
            input_image=wf.lzin.padded_image
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.ants.utils.MultiplyImages(
            name="mask_brain",
            dimension=3,
            output_product_image="masked_brain.nii",
            num_threads=1,
            environ={"NSLOTS": "1"},
            first_input=wf.lzin.original_image,
            second_input=wf.mask_to_original_grid.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="mask_to_original_grid",
            dimension=3,
            out_postfix="_trans",
            interpolation="NearestNeighbor",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.lzin.original_image,
            input_image=wf.synthstrip.lzout.out_brain_mask
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            brain_mask=wf.mask_to_original_grid.lzout.output_image,
            brain_image=wf.mask_brain.lzout.output_product_image
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.FixHeaderSynthStrip(
            name="synthstrip",
            num_threads=1,
            environ={"OMP_NUM_THREADS": "1"},
            input_image=wf.lzin.padded_image
        )
    )
    wf.add(
        qsiprep.interfaces.bids.BIDSInfo(
            name="bids_info"
        )
    )
    wf.add(
        qsiprep.interfaces.bids.BIDSDataGrabber(
            name="bidssrc",
            subject_data={"t1w": ["/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/anat/sub-01_ses-test_T1w.nii.gz"], "dwi": ["/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz"], "t2w": ["/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/anat/sub-01_ses-test_T1w.nii.gz"], "roi": []}
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_about",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="about",
            keep_dtype=False,
            in_file=wf.about.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_summary",
            base_directory=".",
            space="",
            desc="",
            bundle="",
            suffix="summary",
            keep_dtype=False,
            in_file=wf.summary.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioBTable(
            name="btab_t1",
            bvec_convention="DIPY",
            bval_file=wf.transform_dwis_t1.lzout.outputnode.bvals,
            bvec_file=wf.transform_dwis_t1.lzout.outputnode.rotated_bvecs
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_carpetplot",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="SliceQC",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            in_file=wf.lzin.carpetplot_data
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_interactive_report",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="dwiqc",
            keep_dtype=False,
            in_file=wf.interactive_report_wf.lzout.outputnode.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_gradients",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="sampling_scheme",
            keep_dtype=False,
            in_file=wf.gradient_plot.lzout.plot_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_series_qc",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="ImageQC",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            in_file=wf.series_qc.lzout.series_qc_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_btable_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="preproc",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            extension=".b_table.txt",
            in_file=wf.lzin.btable_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_bvals_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="preproc",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            extension=".bval",
            in_file=wf.lzin.bvals_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_bvecs_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="preproc",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            extension=".bvec",
            in_file=wf.lzin.bvecs_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_cnr_map_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="3dSHORE",
            bundle="",
            suffix="cnr",
            keep_dtype=False,
            compress=True,
            extension=".nii.gz",
            in_file=wf.lzin.cnr_map_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_dwi_mask_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="brain",
            bundle="",
            suffix="mask",
            keep_dtype=False,
            compress=True,
            extension=".nii.gz",
            in_file=wf.lzin.dwi_mask_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_dwi_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="preproc",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            compress=True,
            extension=".nii.gz",
            in_file=wf.lzin.dwi_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_gradient_table_t1",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="preproc",
            bundle="",
            suffix="dwi",
            keep_dtype=False,
            extension=".b",
            in_file=wf.lzin.gradient_table_t1
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_optimization",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="hmcOptimization",
            keep_dtype=False,
            in_file=wf.lzin.hmc_optimization_data
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_t1_b0_ref",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="T1w",
            desc="",
            bundle="",
            suffix="dwiref",
            keep_dtype=False,
            compress=True,
            extension=".nii.gz",
            in_file=wf.lzin.t1_b0_ref
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            confounds=wf.lzin.confounds,
            dwi_t1=wf.lzin.dwi_t1,
            t1_b0_series=wf.lzin.t1_b0_series,
            t1_b0_ref=wf.lzin.t1_b0_ref,
            dwi_mask_t1=wf.lzin.dwi_mask_t1
        )
    )
    wf.add(
        qsiprep.interfaces.reports.GradientPlot(
            name="gradient_plot",
            orig_bvec_files=wf.lzin.bvec_files,
            orig_bval_files=wf.lzin.bval_files,
            source_files=wf.lzin.original_files,
            final_bvec_file=wf.outputnode.lzout.bvecs_t1
        )
    )
    wf.add(
        qsiprep.interfaces.mrtrix.MRTrixGradientTable(
            name="gtab_t1",
            bval_file=wf.transform_dwis_t1.lzout.outputnode.bvals,
            bvec_file=wf.transform_dwis_t1.lzout.outputnode.rotated_bvecs
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        qsiprep.interfaces.reports.InteractiveReport(
            name="interactive_report",
            series_qc_file=wf.lzin.series_qc_file,
            carpetplot_data=wf.lzin.carpetplot_data,
            raw_dwi_file=wf.lzin.raw_dwi_file,
            processed_dwi_file=wf.lzin.processed_dwi_file,
            confounds_file=wf.lzin.confounds_file,
            mask_file=wf.lzin.mask_file,
            color_fa=wf.tensor_fit.lzout.color_fa_image
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            out_report=wf.interactive_report.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.dipy.TensorReconstruction(
            name="tensor_fit",
            big_delta=None,
            little_delta=None,
            b0_threshold=50,
            dwi_file=wf.lzin.processed_dwi_file,
            bval_file=wf.lzin.bval_file,
            bvec_file=wf.lzin.bvec_file,
            mask_file=wf.lzin.mask_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            hmc_optimization_data=wf.lzin.hmc_optimization_data,
            bvals_t1=wf.transform_dwis_t1.lzout.outputnode.bvals,
            bvecs_t1=wf.transform_dwis_t1.lzout.outputnode.rotated_bvecs,
            cnr_map_t1=wf.transform_dwis_t1.lzout.outputnode.cnr_map_resampled,
            local_bvecs_t1=wf.transform_dwis_t1.lzout.outputnode.local_bvecs,
            confounds=wf.final_denoise_wf.lzout.outputnode.confounds,
            dwi_t1=wf.final_denoise_wf.lzout.outputnode.dwi_t1,
            t1_b0_ref=wf.final_denoise_wf.lzout.outputnode.t1_b0_ref,
            dwi_mask_t1=wf.final_denoise_wf.lzout.outputnode.dwi_mask_t1,
            interactive_report=wf.interactive_report_wf.lzout.outputnode.out_report,
            gradient_table_t1=wf.gtab_t1.lzout.gradient_file,
            btable_t1=wf.btab_t1.lzout.btable_file
        )
    )
    wf.add(
        qsiprep.interfaces.reports.SeriesQC(
            name="series_qc",
            output_file_name="sub-1",
            pre_qc=wf.lzin.raw_qc_file,
            confounds_file=wf.lzin.confounds,
            t1_cnr_file=wf.transform_dwis_t1.lzout.outputnode.cnr_map_resampled,
            t1_qc=wf.transform_dwis_t1.lzout.outputnode.resampled_qc,
            t1_qc_postproc=wf.final_denoise_wf.lzout.outputnode.series_qc_postproc,
            t1_mask_file=wf.final_denoise_wf.lzout.outputnode.dwi_mask_t1,
            t1_b0_series=wf.final_denoise_wf.lzout.outputnode.t1_b0_series,
            t1_dice_score=wf.t1_dice_calc.lzout.outputnode.dice_score
        )
    )
    wf.add(
        qsiprep.interfaces.anatomical.DiceOverlap(
            name="calculate_dice",
            dwi_mask=wf.lzin.dwi_mask,
            anatomical_mask=wf.downsample_t1_mask.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Resample(
            name="downsample_t1_mask",
            resample_mode="NN",
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.lzin.anatomical_mask,
            master=wf.lzin.dwi_mask
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            dice_score=wf.calculate_dice.lzout.dice_score
        )
    )
    # wf.add(
    #     nipype.interfaces.utility.base.IdentityInterface(
    #         name="inputnode"
    #     )
    # )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioMergeQC(
            name="merged_qc",
            src_qc=wf.raw_src_qc.lzout.qc_txt,
            fib_qc=wf.raw_fib_qc.lzout.qc_txt
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            qc_summary=wf.merged_qc.lzout.qc_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioFibQC(
            name="raw_fib_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_gqi.lzout.output_fib
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioGQIReconstruction(
            name="raw_gqi",
            ratio_of_mean_diffusion_distance=1.25,
            thread_count=1,
            dti_no_high_b=True,
            r2_weighted=False,
            output_odf=True,
            odf_order=8,
            other_output="all",
            align_acpc=False,
            check_btable=0,
            num_fibers=3,
            num_threads=1,
            environ={},
            input_src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioCreateSrc(
            name="raw_src",
            bvec_convention="DIPY",
            num_threads=1,
            environ={},
            input_nifti_file=wf.lzin.dwi_file,
            input_bvals_file=wf.lzin.bval_file,
            input_bvecs_file=wf.lzin.bvec_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioSrcQC(
            name="raw_src_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        qsiprep.interfaces.ants.GetImageType(
            name="cnr_image_type",
            image=wf.lzin.cnr_map
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="cnr_tfm",
            out_postfix="_trans",
            interpolation="LanczosWindowedSinc",
            default_value=0.0,
            float=True,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.cnr_map,
            reference_image=wf.lzin.output_grid,
            input_image_type=wf.cnr_image_type.lzout.image_type
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.ComposeTransforms(
            name="compose_transforms",
            save_cmd=True,
            copy_dtype=False,
            num_threads=1,
            out_postfix="_trans",
            interpolation="Linear",
            default_value=0.0,
            float=False,
            environ={},
            reference_image=wf.lzin.output_grid,
            dwi_files=wf.lzin.dwi_files,
            hmc_affines=wf.lzin.hmc_xforms,
            hmcsdc_dwi_ref_to_t1w_affine=wf.lzin.itk_b0_to_t1,
            fieldwarps=wf.lzin.fieldwarps,
            b0_to_intramodal_template_transforms=wf.lzin.b0_to_intramodal_template_transforms,
            intramodal_template_to_t1_warp=wf.lzin.intramodal_template_to_t1_warp
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="dwi_transform",
            default_value=0.0,
            environ={"NSLOTS": "1"},
            float=True,
            interpolation="Linear",
            num_threads=1,
            out_postfix="_trans",
            input_image=wf.lzin.dwi_files,
            reference_image=wf.lzin.output_grid,
            transforms=wf.compose_transforms.lzout.out_warps,
            interpolation=wf.get_interpolation.lzout.interpolation_method
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.ExtractB0s(
            name="extract_b0_series",
            b0_threshold=50,
            b0_indices=wf.lzin.b0_indices,
            dwi_series=wf.merge.lzout.out_file
        )
    )
    wf.add(
        qsiprep.niworkflows.interfaces.registration.SimpleBeforeAfterRPT(
            name="b0ref_reportlet",
            out_report="report.svg",
            compress_report="auto",
            before=wf.lzin.b0_template,
            after=wf.synthstrip_wf.lzout.outputnode.brain_image,
            wm_seg=wf.synthstrip_wf.lzout.outputnode.brain_mask
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_b0_mask",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="resampled",
            bundle="",
            suffix="b0ref",
            keep_dtype=False,
            in_file=wf.b0ref_reportlet.lzout.out_report
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            raw_ref_image=wf.lzin.b0_template,
            ref_image=wf.lzin.b0_template,
            ref_image_brain=wf.synthstrip_wf.lzout.outputnode.brain_image,
            dwi_mask=wf.synthstrip_wf.lzout.outputnode.brain_mask,
            validation_report=wf.b0ref_reportlet.lzout.out_report
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.ants.utils.MultiplyImages(
            name="mask_brain",
            dimension=3,
            output_product_image="masked_brain.nii",
            num_threads=1,
            environ={"NSLOTS": "1"},
            first_input=wf.lzin.original_image,
            second_input=wf.mask_to_original_grid.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="mask_to_original_grid",
            dimension=3,
            out_postfix="_trans",
            interpolation="NearestNeighbor",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.lzin.original_image,
            input_image=wf.synthstrip.lzout.out_brain_mask
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            brain_mask=wf.mask_to_original_grid.lzout.output_image,
            brain_image=wf.mask_brain.lzout.output_product_image
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            padded_image=wf.resample_skulled_to_reference.lzout.output_image
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.PrepareSynthStripGrid(
            name="prepare_synthstrip_reference",
            input_image=wf.skulled_autobox.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="resample_skulled_to_reference",
            dimension=3,
            out_postfix="_trans",
            interpolation="BSpline",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.image,
            reference_image=wf.prepare_synthstrip_reference.lzout.prepared_image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Resample(
            name="skulled_1mm_resample",
            voxel_size=[1.0, 1.0, 1.0],
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.lzin.image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Autobox(
            name="skulled_autobox",
            padding=3,
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.skulled_1mm_resample.lzout.out_file
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.FixHeaderSynthStrip(
            name="synthstrip",
            num_threads=1,
            environ={"OMP_NUM_THREADS": "1"},
            input_image=wf.pad_before_synthstrip_wf.lzout.outputnode.padded_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="t1_mask_to_b0",
            out_postfix="_trans",
            interpolation="Linear",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.t1_mask,
            reference_image=wf.lzin.b0_template
        )
    )
    wf.add(
        qsiprep.interfaces.images.ChooseInterpolator(
            name="get_interpolation",
            output_resolution=1.25,
            dwi_files=wf.lzin.dwi_files
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        qsiprep.interfaces.nilearn.Merge(
            name="merge",
            dtype="f4",
            compress=False,
            is_dwi=True,
            header_source=wf.lzin.name_source,
            in_files=wf.scale_dwis.lzout.scaled_images
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            cnr_map_resampled=wf.cnr_tfm.lzout.output_image,
            bvals=wf.rotate_gradients.lzout.bvals,
            rotated_bvecs=wf.rotate_gradients.lzout.bvecs,
            dwi_resampled=wf.merge.lzout.out_file,
            dwi_ref_resampled=wf.final_b0_ref.lzout.outputnode.ref_image,
            resampled_dwi_mask=wf.final_b0_ref.lzout.outputnode.dwi_mask,
            resampled_qc=wf.calculate_qc.lzout.outputnode.qc_summary
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.GradientRotation(
            name="rotate_gradients",
            bvec_files=wf.lzin.bvec_files,
            bval_files=wf.lzin.bval_files,
            original_images=wf.lzin.dwi_files,
            affine_transforms=wf.compose_transforms.lzout.out_affines
        )
    )
    wf.add(
        qsiprep.interfaces.fmap.ApplyScalingImages(
            name="scale_dwis",
            save_cmd=True,
            copy_dtype=False,
            num_threads=1,
            out_postfix="_trans",
            interpolation="Linear",
            default_value=0.0,
            float=False,
            environ={},
            scaling_image_files=wf.lzin.sdc_scaling_images,
            reference_image=wf.lzin.output_grid,
            hmcsdc_dwi_ref_to_t1w_affine=wf.lzin.itk_b0_to_t1,
            b0_to_intramodal_template_transforms=wf.lzin.b0_to_intramodal_template_transforms,
            intramodal_template_to_t1_warp=wf.lzin.intramodal_template_to_t1_warp,
            dwi_files=wf.dwi_transform.lzout.output_image
        )
    )
    wf.add(
        qsiprep.interfaces.niworkflows.ANTSRegistrationRPT(
            name="b0_to_anat",
            out_report="report.svg",
            compress_report="auto",
            dimension=3,
            initial_moving_transform_com=0,
            metric=["Mattes"],
            metric_weight_item_trait=1.0,
            metric_weight=[1.0],
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[32],
            sampling_strategy=["Random"],
            sampling_percentage=[0.25],
            use_histogram_matching=True,
            interpolation="HammingWindowedSinc",
            write_composite_transform=False,
            collapse_output_transforms=True,
            initialize_transforms_per_stage=False,
            transforms=["Rigid"],
            transform_parameters=[[0.2]],
            number_of_iterations=[[10000, 1000, 10000, 10000]],
            smoothing_sigmas=[[7.0, 3.0, 1.0, 0.0]],
            sigma_units=["vox"],
            shrink_factors=[[8, 4, 2, 1]],
            convergence_threshold=[1e-06],
            convergence_window_size=[10],
            output_transform_prefix="transform",
            output_warped_image=True,
            winsorize_upper_quantile=0.975,
            winsorize_lower_quantile=0.025,
            verbose=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            fixed_image=wf.lzin.t1_brain,
            moving_image=wf.lzin.ref_b0_brain
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            itk_b0_to_t1=wf.b0_to_anat.lzout.forward_transforms,
            itk_t1_to_b0=wf.b0_to_anat.lzout.reverse_transforms,
            coreg_metric=wf.b0_to_anat.lzout.metric_value,
            report=wf.b0_to_anat.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.confounds.DMRISummary(
            name="conf_plot",
            sliceqc_file=wf.hmc_sdc_wf.lzout.outputnode.slice_quality,
            sliceqc_mask=wf.hmc_sdc_wf.lzout.outputnode.b0_template_mask,
            confounds_file=wf.confounds_wf.lzout.outputnode.confounds_file
        )
    )
    wf.add(
        qsiprep.interfaces.utils.AddTSVHeader(
            name="add_motion_headers",
            columns=["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"],
            in_file=wf.lzin.motion_params
        )
    )
    wf.add(
        qsiprep.interfaces.confounds.GatherConfounds(
            name="concat",
            sliceqc_file=wf.lzin.sliceqc_file,
            original_bvals=wf.lzin.bval_file,
            original_bvecs=wf.lzin.bvec_file,
            original_files=wf.lzin.original_files,
            denoising_confounds=wf.lzin.denoising_confounds,
            fd=wf.fdisp.lzout.out_file,
            motion=wf.add_motion_headers.lzout.out_file
        )
    )
    wf.add(
        nipype.algorithms.confounds.FramewiseDisplacement(
            name="fdisp",
            parameter_source="SPM",
            radius=50,
            out_file="fd_power_2012.txt",
            out_figure="fd_power_2012.pdf",
            save_plot=False,
            normalize=False,
            figdpi=100,
            figsize=[11.7, 2.3],
            in_file=wf.lzin.motion_params
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            confounds_file=wf.concat.lzout.confounds_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_confounds",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="confounds",
            keep_dtype=False,
            in_file=wf.confounds_wf.lzout.outputnode.confounds_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_coreg",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="coreg",
            keep_dtype=False,
            in_file=wf.b0_anat_coreg.lzout.outputnode.report
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_dwi_conf",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="carpetplot",
            keep_dtype=False,
            in_file=wf.conf_plot.lzout.out_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_summary",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="summary",
            keep_dtype=False,
            in_file=wf.summary.lzout.out_report
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageImages(
            name="initial_template",
            dimension=3,
            output_average_image="average.nii",
            normalize=True,
            num_threads=1,
            environ={"NSLOTS": "1"},
            images=wf.lzin.b0_images
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="iteration_templates",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.initial_template.lzout.output_average_image,
            in2=wf.iterative_alignment_001.lzout.outputnode.updated_template,
            in3=wf.iterative_alignment_002.lzout.outputnode.updated_template
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageImages(
            name="averaged_images",
            dimension=3,
            output_average_image="average.nii",
            normalize=True,
            num_threads=1,
            environ={"NSLOTS": "1"},
            images=wf.reg_000.lzout.warped_image
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageAffineTransform(
            name="avg_affine",
            dimension=3,
            output_affine_transform="AveragedAffines.mat",
            num_threads=1,
            environ={"NSLOTS": "1"},
            transforms=wf.transforms_to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="inputnode",
            iteration_num=0
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="invert_average",
            out_postfix="_trans",
            interpolation="HammingWindowedSinc",
            invert_transform_flags=[True],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.averaged_images.lzout.output_average_image,
            reference_image=wf.averaged_images.lzout.output_average_image,
            transforms=wf.to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            affine_transforms=wf.reg_000.lzout.forward_transforms,
            registered_image_paths=wf.reg_000.lzout.warped_image,
            updated_template=wf.invert_average.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="reg_000",
            collapse_output_transforms=True,
            convergence_threshold=[1e-06, 1e-06],
            convergence_window_size=[20, 20],
            dimension=3,
            environ={"NSLOTS": "1"},
            float=True,
            initialize_transforms_per_stage=False,
            interpolation="BSpline",
            metric=["Mattes", "Mattes"],
            metric_weight=[1.0, 1.0],
            metric_weight_item_trait=1.0,
            num_threads=1,
            number_of_iterations=[[100, 100], [100]],
            output_transform_prefix="transform",
            output_warped_image=True,
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[48, 48],
            sampling_percentage=[0.15, 0.2],
            sampling_strategy=["Random", "Random"],
            shrink_factors=[[2, 1], [1]],
            sigma_units=["mm", "mm"],
            smoothing_sigmas=[[8.0, 2.0], [2.0]],
            transform_parameters=[[0.2], [0.15]],
            transforms=["Rigid", "Affine"],
            use_histogram_matching=[False, False],
            verbose=False,
            winsorize_lower_quantile=0.002,
            winsorize_upper_quantile=0.998,
            write_composite_transform=False,
            moving_image=wf.lzin.image_paths,
            fixed_image=wf.lzin.template_image
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.avg_affine.lzout.affine_transform
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="transforms_to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=True,
            in1=wf.reg_000.lzout.forward_transforms
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageImages(
            name="averaged_images",
            dimension=3,
            output_average_image="average.nii",
            normalize=True,
            num_threads=1,
            environ={"NSLOTS": "1"},
            images=wf.reg_001.lzout.warped_image
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageAffineTransform(
            name="avg_affine",
            dimension=3,
            output_affine_transform="AveragedAffines.mat",
            num_threads=1,
            environ={"NSLOTS": "1"},
            transforms=wf.transforms_to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="inputnode",
            iteration_num=1
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="invert_average",
            out_postfix="_trans",
            interpolation="HammingWindowedSinc",
            invert_transform_flags=[True],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.averaged_images.lzout.output_average_image,
            reference_image=wf.averaged_images.lzout.output_average_image,
            transforms=wf.to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            affine_transforms=wf.reg_001.lzout.forward_transforms,
            registered_image_paths=wf.reg_001.lzout.warped_image,
            updated_template=wf.invert_average.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="reg_001",
            collapse_output_transforms=True,
            convergence_threshold=[1e-08, 1e-08],
            convergence_window_size=[20, 20],
            dimension=3,
            environ={"NSLOTS": "1"},
            float=True,
            initialize_transforms_per_stage=False,
            interpolation="BSpline",
            metric=["Mattes", "Mattes"],
            metric_weight=[1.0, 1.0],
            metric_weight_item_trait=1.0,
            num_threads=1,
            number_of_iterations=[[1000, 1000], [1000]],
            output_transform_prefix="transform",
            output_warped_image=True,
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[48, 48],
            sampling_percentage=[0.15, 0.2],
            sampling_strategy=["Random", "Random"],
            shrink_factors=[[2, 1], [1]],
            sigma_units=["mm", "mm"],
            smoothing_sigmas=[[8.0, 2.0], [2.0]],
            transform_parameters=[[0.2], [0.15]],
            transforms=["Rigid", "Affine"],
            use_histogram_matching=[False, False],
            verbose=False,
            winsorize_lower_quantile=0.002,
            winsorize_upper_quantile=0.998,
            write_composite_transform=False,
            moving_image=wf.lzin.image_paths,
            fixed_image=wf.lzin.template_image
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.avg_affine.lzout.affine_transform
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="transforms_to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=True,
            in1=wf.reg_001.lzout.forward_transforms
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageImages(
            name="averaged_images",
            dimension=3,
            output_average_image="average.nii",
            normalize=True,
            num_threads=1,
            environ={"NSLOTS": "1"},
            images=wf.reg_002.lzout.warped_image
        )
    )
    wf.add(
        nipype.interfaces.ants.utils.AverageAffineTransform(
            name="avg_affine",
            dimension=3,
            output_affine_transform="AveragedAffines.mat",
            num_threads=1,
            environ={"NSLOTS": "1"},
            transforms=wf.transforms_to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="inputnode",
            iteration_num=2
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="invert_average",
            out_postfix="_trans",
            interpolation="HammingWindowedSinc",
            invert_transform_flags=[True],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.averaged_images.lzout.output_average_image,
            reference_image=wf.averaged_images.lzout.output_average_image,
            transforms=wf.to_list.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            affine_transforms=wf.reg_002.lzout.forward_transforms,
            registered_image_paths=wf.reg_002.lzout.warped_image,
            updated_template=wf.invert_average.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="reg_002",
            collapse_output_transforms=True,
            convergence_threshold=[1e-08, 1e-08],
            convergence_window_size=[20, 20],
            dimension=3,
            environ={"NSLOTS": "1"},
            float=True,
            initialize_transforms_per_stage=False,
            interpolation="BSpline",
            metric=["Mattes", "Mattes"],
            metric_weight=[1.0, 1.0],
            metric_weight_item_trait=1.0,
            num_threads=1,
            number_of_iterations=[[1000, 1000], [1000]],
            output_transform_prefix="transform",
            output_warped_image=True,
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[48, 48],
            sampling_percentage=[0.15, 0.2],
            sampling_strategy=["Random", "Random"],
            shrink_factors=[[2, 1], [1]],
            sigma_units=["mm", "mm"],
            smoothing_sigmas=[[8.0, 2.0], [2.0]],
            transform_parameters=[[0.2], [0.15]],
            transforms=["Rigid", "Affine"],
            use_histogram_matching=[False, False],
            verbose=False,
            winsorize_lower_quantile=0.002,
            winsorize_upper_quantile=0.998,
            write_composite_transform=False,
            moving_image=wf.lzin.image_paths,
            fixed_image=wf.lzin.template_image
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.avg_affine.lzout.affine_transform
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="transforms_to_list",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=True,
            in1=wf.reg_002.lzout.forward_transforms
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            iteration_templates=wf.iteration_templates.lzout.out,
            final_template=wf.iterative_alignment_001.lzout.outputnode.updated_template,
            forward_transforms=wf.iterative_alignment_002.lzout.outputnode.affine_transforms,
            aligned_images=wf.iterative_alignment_002.lzout.outputnode.registered_image_paths
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            raw_ref_image=wf.lzin.b0_template,
            ref_image=wf.lzin.b0_template,
            ref_image_brain=wf.synthstrip_wf.lzout.outputnode.brain_image,
            dwi_mask=wf.synthstrip_wf.lzout.outputnode.brain_mask
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="register_t1_to_raw",
            dimension=3,
            initial_moving_transform_com=1,
            metric=["MI", "MI"],
            metric_weight_item_trait=1.0,
            metric_weight=[1.0, 1.0],
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[32, 32],
            sampling_strategy=["Regular", "Regular"],
            sampling_percentage=[0.25, 0.25],
            use_histogram_matching=[False, False],
            interpolation="Linear",
            write_composite_transform=False,
            collapse_output_transforms=True,
            initialize_transforms_per_stage=False,
            float=False,
            transforms=["Rigid", "Affine"],
            transform_parameters=[[0.1], [0.1]],
            number_of_iterations=[[1000, 500, 250, 100], [1000, 500, 250, 100]],
            smoothing_sigmas=[[3.0, 2.0, 1.0, 0.0], [3.0, 2.0, 1.0, 0.0]],
            sigma_units=["vox", "vox"],
            shrink_factors=[[8, 4, 2, 1], [8, 4, 2, 1]],
            convergence_threshold=[1e-06, 1e-06],
            convergence_window_size=[10, 10],
            output_transform_prefix="transform",
            winsorize_upper_quantile=0.995,
            winsorize_lower_quantile=0.005,
            verbose=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            fixed_image=wf.lzin.t1_brain,
            fixed_image_masks=wf.lzin.t1_mask,
            moving_image=wf.lzin.b0_template
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.ants.utils.MultiplyImages(
            name="mask_brain",
            dimension=3,
            output_product_image="masked_brain.nii",
            num_threads=1,
            environ={"NSLOTS": "1"},
            first_input=wf.lzin.original_image,
            second_input=wf.mask_to_original_grid.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="mask_to_original_grid",
            dimension=3,
            out_postfix="_trans",
            interpolation="NearestNeighbor",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            reference_image=wf.lzin.original_image,
            input_image=wf.synthstrip.lzout.out_brain_mask
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            brain_mask=wf.mask_to_original_grid.lzout.output_image,
            brain_image=wf.mask_brain.lzout.output_product_image
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            padded_image=wf.resample_skulled_to_reference.lzout.output_image
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.PrepareSynthStripGrid(
            name="prepare_synthstrip_reference",
            input_image=wf.skulled_autobox.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="resample_skulled_to_reference",
            dimension=3,
            out_postfix="_trans",
            interpolation="BSpline",
            transforms=["identity"],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.image,
            reference_image=wf.prepare_synthstrip_reference.lzout.prepared_image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Resample(
            name="skulled_1mm_resample",
            voxel_size=[1.0, 1.0, 1.0],
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.lzin.image
        )
    )
    wf.add(
        nipype.interfaces.afni.utils.Autobox(
            name="skulled_autobox",
            padding=3,
            num_threads=1,
            outputtype="NIFTI_GZ",
            environ={},
            in_file=wf.skulled_1mm_resample.lzout.out_file
        )
    )
    wf.add(
        qsiprep.interfaces.freesurfer.FixHeaderSynthStrip(
            name="synthstrip",
            num_threads=1,
            environ={"OMP_NUM_THREADS": "1"},
            input_image=wf.pad_before_synthstrip_wf.lzout.outputnode.padded_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="t1_mask_to_b0",
            out_postfix="_trans",
            interpolation="MultiLabel",
            invert_transform_flags=[True],
            default_value=0.0,
            float=False,
            num_threads=1,
            environ={"NSLOTS": "1"},
            input_image=wf.lzin.t1_mask,
            reference_image=wf.lzin.b0_template,
            transforms=wf.register_t1_to_raw.lzout.forward_transforms
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.GradientRotation(
            name="b0_based_bvec_transforms",
            bvec_files=wf.extract_dwis.lzout.model_bvecs,
            bval_files=wf.extract_dwis.lzout.model_bvals,
            affine_transforms=wf.extract_dwis.lzout.transforms
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="b0_based_image_transforms",
            default_value=0.0,
            environ={"NSLOTS": "1"},
            float=False,
            interpolation="BSpline",
            num_threads=1,
            out_postfix="_trans",
            input_image=wf.extract_dwis.lzout.model_dwi_files,
            transforms=wf.extract_dwis.lzout.transforms,
            reference_image=wf.b0_mean.lzout.average_image
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.B0Mean(
            name="b0_mean",
            b0_images=wf.lzin.warped_b0_images
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.CalculateCNR(
            name="calculate_cnr",
            mask_image=wf.lzin.warped_b0_mask,
            hmc_warped_images=wf.reorder_dwi_xforms.lzout.hmc_warped_images,
            predicted_images=wf.reorder_dwi_xforms.lzout.full_predicted_dwi_series
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="collect_motion_params",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.initial_model_iteration.lzout.outputnode.motion_params,
            in2=wf.shoreline_iteration001.lzout.outputnode.motion_params
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_iteration_plot",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="shoreline_iterdata",
            keep_dtype=False,
            in_file=wf.summarize_iterations.lzout.plot_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_shoreline_gif",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-1_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="shoreline_animation",
            keep_dtype=False,
            in_file=wf.shoreline_report.lzout.plot_file
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.ExtractDWIsForModel(
            name="extract_dwis",
            dwi_files=wf.lzin.dwi_files,
            bval_files=wf.lzin.bval_files,
            bvec_files=wf.lzin.bvec_files,
            transforms=wf.lzin.initial_transforms,
            b0_indices=wf.lzin.b0_indices
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.CombineMotions(
            name="calculate_motion",
            source_files=wf.lzin.original_dwi_files,
            ref_file=wf.lzin.b0_mean
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            predicted_dwis=wf.predict_dwis.lzout.predicted_image,
            aligned_dwis=wf.register_to_predicted.lzout.warped_image,
            hmc_transforms=wf.register_to_predicted.lzout.forward_transforms,
            motion_params=wf.calculate_motion.lzout.motion_file,
            aligned_bvecs=wf.post_bvec_transforms.lzout.bvecs
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.GradientRotation(
            name="post_bvec_transforms",
            bvec_files=wf.lzin.original_bvecs,
            bval_files=wf.lzin.bvals
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.SignalPrediction(
            name="predict_dwis",
            minimal_q_distance=2.0,
            model="3dSHORE",
            aligned_dwis=wf.lzin.approx_aligned_dwi_files,
            aligned_bvecs=wf.lzin.approx_aligned_bvecs,
            bvals=wf.lzin.bvals,
            aligned_b0_mean=wf.lzin.b0_mean,
            aligned_mask=wf.lzin.b0_mask
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="register_to_predicted",
            collapse_output_transforms=True,
            convergence_threshold=[1e-06, 1e-06],
            convergence_window_size=[20, 20],
            dimension=3,
            environ={"NSLOTS": "1"},
            float=True,
            initialize_transforms_per_stage=False,
            interpolation="BSpline",
            metric=["Mattes", "Mattes"],
            metric_weight=[1.0, 1.0],
            metric_weight_item_trait=1.0,
            num_threads=1,
            number_of_iterations=[[100, 100], [100]],
            output_transform_prefix="transform",
            output_warped_image=True,
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[48, 48],
            sampling_percentage=[0.15, 0.2],
            sampling_strategy=["Random", "Random"],
            shrink_factors=[[2, 1], [1]],
            sigma_units=["mm", "mm"],
            smoothing_sigmas=[[8.0, 2.0], [2.0]],
            transform_parameters=[[0.2], [0.15]],
            transforms=["Rigid", "Affine"],
            use_histogram_matching=[False, False],
            verbose=False,
            winsorize_lower_quantile=0.002,
            winsorize_upper_quantile=0.998,
            write_composite_transform=False,
            moving_image=wf.lzin.original_dwi_files,
            fixed_image_masks=wf.lzin.b0_mask,
            fixed_image=wf.predict_dwis.lzout.predicted_image
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            optimization_data=wf.summarize_iterations.lzout.iteration_summary_file,
            aligned_dwis=wf.reorder_dwi_xforms.lzout.hmc_warped_images,
            hmc_transforms=wf.reorder_dwi_xforms.lzout.full_transforms,
            model_predicted_images=wf.reorder_dwi_xforms.lzout.full_predicted_dwi_series,
            cnr_image=wf.calculate_cnr.lzout.cnr_image
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.ReorderOutputs(
            name="reorder_dwi_xforms",
            warped_b0_images=wf.lzin.warped_b0_images,
            b0_indices=wf.lzin.b0_indices,
            initial_transforms=wf.lzin.initial_transforms,
            b0_mean=wf.b0_mean.lzout.average_image,
            model_based_transforms=wf.shoreline_iteration001.lzout.outputnode.hmc_transforms,
            model_predicted_images=wf.shoreline_iteration001.lzout.outputnode.predicted_dwis,
            warped_dwi_images=wf.shoreline_iteration001.lzout.outputnode.aligned_dwis
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.CombineMotions(
            name="calculate_motion",
            source_files=wf.lzin.original_dwi_files,
            ref_file=wf.lzin.b0_mean
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            predicted_dwis=wf.predict_dwis.lzout.predicted_image,
            aligned_dwis=wf.register_to_predicted.lzout.warped_image,
            hmc_transforms=wf.register_to_predicted.lzout.forward_transforms,
            motion_params=wf.calculate_motion.lzout.motion_file,
            aligned_bvecs=wf.post_bvec_transforms.lzout.bvecs
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.GradientRotation(
            name="post_bvec_transforms",
            bvec_files=wf.lzin.original_bvecs,
            bval_files=wf.lzin.bvals
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.SignalPrediction(
            name="predict_dwis",
            minimal_q_distance=2.0,
            model="3dSHORE",
            aligned_dwis=wf.lzin.approx_aligned_dwi_files,
            aligned_bvecs=wf.lzin.approx_aligned_bvecs,
            bvals=wf.lzin.bvals,
            aligned_b0_mean=wf.lzin.b0_mean,
            aligned_mask=wf.lzin.b0_mask
        )
    )
    wf.add(
        nipype.interfaces.ants.registration.Registration(
            name="register_to_predicted",
            collapse_output_transforms=True,
            convergence_threshold=[1e-08, 1e-08],
            convergence_window_size=[20, 20],
            dimension=3,
            environ={"NSLOTS": "1"},
            float=True,
            initialize_transforms_per_stage=False,
            interpolation="BSpline",
            metric=["Mattes", "Mattes"],
            metric_weight=[1.0, 1.0],
            metric_weight_item_trait=1.0,
            num_threads=1,
            number_of_iterations=[[1000, 1000], [1000]],
            output_transform_prefix="transform",
            output_warped_image=True,
            radius_bins_item_trait=5,
            radius_or_number_of_bins=[48, 48],
            sampling_percentage=[0.15, 0.2],
            sampling_strategy=["Random", "Random"],
            shrink_factors=[[2, 1], [1]],
            sigma_units=["mm", "mm"],
            smoothing_sigmas=[[8.0, 2.0], [2.0]],
            transform_parameters=[[0.2], [0.15]],
            transforms=["Rigid", "Affine"],
            use_histogram_matching=[False, False],
            verbose=False,
            winsorize_lower_quantile=0.002,
            winsorize_upper_quantile=0.998,
            write_composite_transform=False,
            moving_image=wf.lzin.original_dwi_files,
            fixed_image_masks=wf.lzin.b0_mask,
            fixed_image=wf.predict_dwis.lzout.predicted_image
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.SHORELineReport(
            name="shoreline_report",
            original_images=wf.lzin.dwi_files,
            iteration_summary=wf.summarize_iterations.lzout.iteration_summary_file,
            model_predicted_images=wf.reorder_dwi_xforms.lzout.full_predicted_dwi_series,
            registered_images=wf.reorder_dwi_xforms.lzout.hmc_warped_images
        )
    )
    wf.add(
        qsiprep.interfaces.shoreline.IterationSummary(
            name="summarize_iterations",
            collected_motion_files=wf.collect_motion_params.lzout.out
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        qsiprep.interfaces.gradients.MatchTransforms(
            name="match_transforms",
            dwi_files=wf.lzin.dwi_files,
            b0_indices=wf.lzin.b0_indices
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            final_template=wf.b0_hmc_wf.lzout.outputnode.final_template,
            final_template_brain=wf.b0_template_mask.lzout.outputnode.ref_image_brain,
            final_template_mask=wf.b0_template_mask.lzout.outputnode.dwi_mask,
            forward_transforms=wf.dwi_model_hmc_wf.lzout.outputnode.hmc_transforms,
            optimization_data=wf.dwi_model_hmc_wf.lzout.outputnode.optimization_data,
            cnr_image=wf.dwi_model_hmc_wf.lzout.outputnode.cnr_image,
            noise_free_dwis=wf.uncorrect_model_images.lzout.output_image
        )
    )
    wf.add(
        nipype.interfaces.ants.resampling.ApplyTransforms(
            name="uncorrect_model_images",
            default_value=0.0,
            environ={"NSLOTS": "1"},
            float=False,
            interpolation="LanczosWindowedSinc",
            invert_transform_flags=[True],
            num_threads=1,
            out_postfix="_trans",
            reference_image=wf.lzin.dwi_files,
            input_image=wf.dwi_model_hmc_wf.lzout.outputnode.model_predicted_images,
            transforms=wf.dwi_model_hmc_wf.lzout.outputnode.hmc_transforms
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            bvec_files_to_transform=wf.split_bvals.lzout.bvec_files,
            bval_files=wf.split_bvals.lzout.bval_files,
            b0_indices=wf.split_bvals.lzout.b0_indices,
            pre_sdc_template=wf.dwi_hmc_wf.lzout.outputnode.final_template,
            hmc_optimization_data=wf.dwi_hmc_wf.lzout.outputnode.optimization_data,
            cnr_map=wf.dwi_hmc_wf.lzout.outputnode.cnr_image,
            b0_template_mask=wf.dwi_hmc_wf.lzout.outputnode.final_template_mask,
            slice_quality=wf.slice_qc.lzout.slice_stats,
            dwi_files_to_transform=wf.slice_qc.lzout.imputed_images,
            motion_params=wf.summarize_motion.lzout.spm_motion_file,
            sdc_method=wf.sdc_bypass_wf.lzout.outputnode.method,
            b0_template=wf.sdc_bypass_wf.lzout.outputnode.b0_ref,
            to_dwi_ref_warps=wf.sdc_bypass_wf.lzout.outputnode.out_warp
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="inputnode",
            template="MNI152NLin2009cAsym"
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            method="None",
            b0_ref=wf.lzin.b0_ref,
            b0_mask=wf.lzin.b0_mask
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.SliceQC(
            name="slice_qc",
            impute_slice_threshold=0.0,
            min_slice_size_percentile=10.0,
            uncorrected_dwi_files=wf.split_dwis.lzout.out_files,
            ideal_image_files=wf.dwi_hmc_wf.lzout.outputnode.noise_free_dwis,
            mask_image=wf.dwi_hmc_wf.lzout.outputnode.final_template_mask
        )
    )
    wf.add(
        qsiprep.interfaces.images.SplitDWIsBvals(
            name="split_bvals",
            deoblique_bvecs=True,
            b0_threshold=100,
            bval_file=wf.lzin.bval_file,
            bvec_file=wf.lzin.bvec_file,
            split_files=wf.split_dwis.lzout.out_files
        )
    )
    wf.add(
        qsiprep.interfaces.images.TSplit(
            name="split_dwis",
            out_name="vol",
            digits=4,
            num_threads=1,
            outputtype="AFNI",
            environ={},
            in_file=wf.lzin.dwi_file
        )
    )
    wf.add(
        qsiprep.interfaces.gradients.CombineMotions(
            name="summarize_motion",
            ref_file=wf.dwi_hmc_wf.lzout.outputnode.final_template,
            source_files=wf.dwi_hmc_wf.lzout.outputnode.final_template
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            raw_qc_file=wf.pre_hmc_wf.lzout.outputnode.qc_file,
            original_files=wf.pre_hmc_wf.lzout.outputnode.original_files,
            original_bvecs=wf.pre_hmc_wf.lzout.outputnode.bvec_file,
            bias_images=wf.pre_hmc_wf.lzout.outputnode.bias_images,
            noise_images=wf.pre_hmc_wf.lzout.outputnode.noise_images,
            raw_concatenated=wf.pre_hmc_wf.lzout.outputnode.raw_concatenated,
            hmc_optimization_data=wf.hmc_sdc_wf.lzout.outputnode.hmc_optimization_data,
            b0_indices=wf.hmc_sdc_wf.lzout.outputnode.b0_indices,
            bval_files=wf.hmc_sdc_wf.lzout.outputnode.bval_files,
            bvec_files=wf.hmc_sdc_wf.lzout.outputnode.bvec_files_to_transform,
            b0_ref_image=wf.hmc_sdc_wf.lzout.outputnode.b0_template,
            cnr_map=wf.hmc_sdc_wf.lzout.outputnode.cnr_map,
            dwi_mask=wf.hmc_sdc_wf.lzout.outputnode.b0_template_mask,
            hmc_xforms=wf.hmc_sdc_wf.lzout.outputnode.to_dwi_ref_affines,
            fieldwarps=wf.hmc_sdc_wf.lzout.outputnode.to_dwi_ref_warps,
            dwi_files=wf.hmc_sdc_wf.lzout.outputnode.dwi_files_to_transform,
            coreg_score=wf.b0_anat_coreg.lzout.outputnode.coreg_metric,
            confounds=wf.confounds_wf.lzout.outputnode.confounds_file,
            carpetplot_data=wf.conf_plot.lzout.carpetplot_json
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioMergeQC(
            name="merged_qc",
            src_qc=wf.raw_src_qc.lzout.qc_txt,
            fib_qc=wf.raw_fib_qc.lzout.qc_txt
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            qc_summary=wf.merged_qc.lzout.qc_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioFibQC(
            name="raw_fib_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_gqi.lzout.output_fib
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioGQIReconstruction(
            name="raw_gqi",
            ratio_of_mean_diffusion_distance=1.25,
            thread_count=1,
            dti_no_high_b=True,
            r2_weighted=False,
            output_odf=True,
            odf_order=8,
            other_output="all",
            align_acpc=False,
            check_btable=0,
            num_fibers=3,
            num_threads=1,
            environ={},
            input_src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioCreateSrc(
            name="raw_src",
            bvec_convention="DIPY",
            num_threads=1,
            environ={},
            input_nifti_file=wf.lzin.dwi_file,
            input_bvals_file=wf.lzin.bval_file,
            input_bvecs_file=wf.lzin.bvec_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioSrcQC(
            name="raw_src_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="bias_images",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.bias_image
        )
    )
    wf.add(
        qsiprep.interfaces.images.ConformDwi(
            name="conform_dwis01",
            dwi_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz",
            orientation="LPS"
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="conformation_reports",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.conform_dwis01.lzout.out_report
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="conformed_bvals",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.bval_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="conformed_bvecs",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.bvec_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="conformed_images",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.dwi_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="conformed_raw_images",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.conform_dwis01.lzout.dwi_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="denoising_confounds",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.confounds
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="buffer00",
            dwi_file=wf.lzin.dwi_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="buffer01",
            dwi_file=wf.denoiser.lzout.out_file
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="buffer02",
            dwi_file=wf.degibbser.lzout.out_file
        )
    )
    wf.add(
        qsiprep.interfaces.mrtrix.MRDeGibbs(
            name="degibbser",
            out_report="degibbs_report.svg",
            nthreads=1,
            environ={},
            in_file=wf.buffer01.lzout.dwi_file
        )
    )
    wf.add(
        qsiprep.interfaces.dipy.Patch2Self(
            name="denoiser",
            patch_radius=7,
            model="ols",
            alpha=1.0,
            b0_threshold=50.0,
            b0_denoising=True,
            clip_negative_vals=False,
            shift_intensity=True,
            out_report="patch2self_report.svg",
            bval_file=wf.lzin.bval_file,
            in_file=wf.buffer00.lzout.dwi_file
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_dwi_denoise_ses_test_dwi_wf_denoising",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="dwi_denoise_ses_test_dwi_wf_denoising",
            keep_dtype=False,
            in_file=wf.denoiser.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.bids.DerivativesDataSink(
            name="ds_report_dwi_denoise_ses_test_dwi_wf_unringing",
            base_directory=".",
            source_file="/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz",
            space="",
            desc="",
            bundle="",
            suffix="dwi_denoise_ses_test_dwi_wf_unringing",
            keep_dtype=False,
            in_file=wf.degibbser.lzout.out_report
        )
    )
    wf.add(
        qsiprep.interfaces.dwi_merge.StackConfounds(
            name="hstack_confounds",
            axis=1,
            in_files=wf.merge_confounds.lzout.out
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="merge_confounds",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.denoiser.lzout.nmse_text,
            in2=wf.degibbser.lzout.nmse_text
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            bval_file=wf.lzin.bval_file,
            bvec_file=wf.lzin.bvec_file,
            dwi_file=wf.buffer02.lzout.dwi_file,
            confounds=wf.hstack_confounds.lzout.confounds_file
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioMergeQC(
            name="merged_qc",
            src_qc=wf.raw_src_qc.lzout.qc_txt,
            fib_qc=wf.raw_fib_qc.lzout.qc_txt
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            qc_summary=wf.merged_qc.lzout.qc_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioFibQC(
            name="raw_fib_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_gqi.lzout.output_fib
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioGQIReconstruction(
            name="raw_gqi",
            ratio_of_mean_diffusion_distance=1.25,
            thread_count=1,
            dti_no_high_b=True,
            r2_weighted=False,
            output_odf=True,
            odf_order=8,
            other_output="all",
            align_acpc=False,
            check_btable=0,
            num_fibers=3,
            num_threads=1,
            environ={},
            input_src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioCreateSrc(
            name="raw_src",
            bvec_convention="DIPY",
            num_threads=1,
            environ={},
            input_nifti_file=wf.lzin.dwi_file,
            input_bvals_file=wf.lzin.bval_file,
            input_bvecs_file=wf.lzin.bvec_file
        )
    )
    wf.add(
        qsiprep.interfaces.dsi_studio.DSIStudioSrcQC(
            name="raw_src_qc",
            num_threads=1,
            environ={},
            src_file=wf.raw_src.lzout.output_src
        )
    )
    wf.add(
        qsiprep.interfaces.dwi_merge.MergeDWIs(
            name="merge_dwis",
            bids_dwi_files=["/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz"],
            b0_threshold=100,
            harmonize_b0_intensities=True,
            denoising_confounds=wf.denoising_confounds.lzout.out,
            dwi_files=wf.conformed_images.lzout.out,
            bval_files=wf.conformed_bvals.lzout.out,
            bvec_files=wf.conformed_bvecs.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.Merge(
            name="noise_images",
            axis="vstack",
            no_flatten=False,
            ravel_inputs=False,
            in1=wf.dwi_denoise_ses_test_dwi_wf.lzout.outputnode.noise_image
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            noise_images=wf.noise_images.lzout.out,
            bias_images=wf.bias_images.lzout.out,
            validation_reports=wf.conformation_reports.lzout.out,
            original_files=wf.merge_dwis.lzout.original_images,
            merged_bval=wf.merge_dwis.lzout.out_bval,
            merged_bvec=wf.merge_dwis.lzout.out_bvec,
            merged_image=wf.merge_dwis.lzout.out_dwi,
            denoising_confounds=wf.merge_dwis.lzout.merged_denoising_confounds,
            merged_raw_image=wf.raw_merge.lzout.out_file,
            qc_summary=wf.dwi_qc_wf.lzout.outputnode.qc_summary
        )
    )
    wf.add(
        qsiprep.interfaces.nilearn.Merge(
            name="raw_merge",
            dtype="f4",
            compress=True,
            is_dwi=True,
            in_files=wf.conformed_raw_images.lzout.out
        )
    )
    wf.add(
        nipype.interfaces.utility.base.IdentityInterface(
            name="outputnode",
            dwi_file=wf.merge_and_denoise_wf.lzout.outputnode.merged_image,
            bval_file=wf.merge_and_denoise_wf.lzout.outputnode.merged_bval,
            bvec_file=wf.merge_and_denoise_wf.lzout.outputnode.merged_bvec,
            bias_images=wf.merge_and_denoise_wf.lzout.outputnode.bias_images,
            noise_images=wf.merge_and_denoise_wf.lzout.outputnode.noise_images,
            validation_reports=wf.merge_and_denoise_wf.lzout.outputnode.validation_reports,
            denoising_confounds=wf.merge_and_denoise_wf.lzout.outputnode.denoising_confounds,
            original_files=wf.merge_and_denoise_wf.lzout.outputnode.original_files,
            raw_concatenated=wf.merge_and_denoise_wf.lzout.outputnode.merged_raw_image,
            qc_file=wf.dwi_qc_wf.lzout.outputnode.qc_summary
        )
    )
    wf.add(
        qsiprep.interfaces.reports.DiffusionSummary(
            name="summary",
            pe_direction="j",
            impute_slice_threshold=0.0,
            hmc_transform="Affine",
            hmc_model="3dSHORE",
            b0_to_t1w_transform="Rigid",
            denoise_method="patch2self",
            dwi_denoise_window=7,
            validation_reports=wf.pre_hmc_wf.lzout.outputnode.validation_reports,
            distortion_correction=wf.hmc_sdc_wf.lzout.outputnode.sdc_method
        )
    )
    wf.add(
        qsiprep.interfaces.utils.TestInput(
            name="test_pre_hmc_connect",
            test1=wf.pre_hmc_wf.lzout.outputnode.raw_concatenated
        )
    )
#    wf.add(
#        nipype.interfaces.utility.base.IdentityInterface(
#            name="inputnode"
#        )
#    )
    wf.add(
        qsiprep.interfaces.reports.SubjectSummary(
            name="summary",
            dwi_groupings={"sub-1": {"dwi_series": ["/Users/tclose/Data/openneuro/ds000114/sub-01/ses-test/dwi/sub-01_ses-test_dwi.nii.gz"], "fieldmap_info": {"suffix": None}, "dwi_series_pedir": "j", "concatenated_bids_name": "sub-1"}},
            template="MNI152NLin2009cAsym",
            subjects_dir=wf.lzin.subjects_dir,
            t1w=wf.bidssrc.lzout.t1w,
            t2w=wf.bidssrc.lzout.t2w,
            subject_id=wf.bids_info.lzout.subject_id
        )
    )