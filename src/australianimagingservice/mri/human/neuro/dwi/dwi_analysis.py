from pydra.compose import python, shell, workflow
from fileformats.generic import File
from pydra.tasks.mrtrix3.v3_1 import (
    DwiGradcheck,
    DwiDenoise,
    MrDegibbs,
    DwiBiascorrect_Ants,
    TransformConvert,
    MrTransform,
    MrConvert,
    MrGrid,
    DwiExtract,
    MrMath,
    Dwi2Response_Dhollander,
    Dwi2Fod,
    MtNormalise,
    TckGen,
    TckSift2,
    Tck2Connectome,
    TckMap,
)
from pydra.tasks.fsl.v6 import EpiReg
from pydra.tasks.fastsurfer.mri_synthstrip import MriSynthstrip
from fileformats.medimage import NiftiGzXBvec, NiftiGz

from fileformats.medimage_mrtrix3 import (
    ImageFormat,
    ImageIn,
    ImageOut,
    Tracks,
)  # noqa: F401

# Define the path and output_path variables
output_path = "<output_path>"


@shell.define
class MrcalcMax(shell.Task):

    executable = "mrcalc"

    in_file: ImageIn = shell.arg(
        help="path to input image 1",
        argstr="{in_file}",
        position=-4,
    )
    number: float = shell.arg(
        help="minimum value",
        argstr="{number}",
        position=-3,
    )
    operand: str = shell.arg(
        help="operand to execute",
        position=-2,
        argstr="-{operand}",
    )
    datatype: str | None = shell.arg(
        help="datatype option",
        argstr="-datatype {datatype}",
        position=-5,
        default=None,
    )

    class Outputs(shell.Outputs):
        output_image: ImageOut = shell.outarg(
            help="path to output image",
            path_template="mrcalc_output_image.nii.gz",
            position=-1,
        )


@python.define(
    outputs=["t1_FSpath", "t1brain_FSpath", "wmseg_FSpath", "normimg_FSpath"]
)
def JoinTask(FS_dir: str):
    import os

    t1_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")
    t1brain_FSpath = os.path.join(FS_dir, "mri", "brainmask.mgz")
    wmseg_FSpath = os.path.join(FS_dir, "mri", "wm.seg.mgz")
    normimg_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")

    return t1_FSpath, t1brain_FSpath, wmseg_FSpath, normimg_FSpath


# Define the input_spec for the workflow
@workflow.define(
    outputs=[
        "DWI_T1space",
        "DWImask_T1space",
        "wm_fod_norm",
        "TDI_file",
        "DECTDI_file",
        "connectome_out",  # connectomics_task.connectome_out
        "out_mu",  # SIF2_task.out_mu
        "out_weights",  # SIF2_task.out_weights
    ]
)
def DwiPipeline(
    dwi_preproc_mif: File,
    FS_dir: str,
    fTTvis_image_T1space: File,
    fTT_image_T1space: File,
    parcellation_image_T1space: File,
) -> tuple[File, File, File, File, File, File, File, File]:

    # DWIgradcheck
    DWIgradcheck_task = workflow.add(
        DwiGradcheck(
            in_file=dwi_preproc_mif,
            export_grad_mrtrix="DWIgradcheck_grad.txt",
            # fslgrad=<bvec bval>,
        )
    )

    # create mif with corrected grad
    DWItoMif_task = workflow.add(
        MrConvert(
            in_file=dwi_preproc_mif,
            grad=DWIgradcheck_task.export_grad_mrtrix,
        ),
        name="MrConvert_grad",
    )

    # denoise
    dwi_denoise_task = workflow.add(
        DwiDenoise(
            dwi=DWItoMif_task.out_file,
        )
    )

    # unring
    dwi_degibbs_task = workflow.add(
        MrDegibbs(
            in_=dwi_denoise_task.out,
        )
    )

    # motion and distortion correction (eddy, topup) - placeholder

    # Extract b0 volumes from degibbs output for mask generation
    early_b0_task = workflow.add(
        DwiExtract(
            in_file=dwi_degibbs_task.out,
            out_file="early_bzero.mif.gz",
            bzero=True,
        ),
        name="DwiExtract_early",
    )

    early_b0_nonneg = workflow.add(
        MrcalcMax(
            in_file=early_b0_task.out_file,
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_early_b0",
    )

    early_meanb0_task = workflow.add(
        MrMath(
            in_file=early_b0_nonneg.output_image,
            out_file="early_meanb0.nii.gz",
            operation="mean",
            axis=3,
        ),
        name="MrMath_early_meanb0",
    )

    # Generate brain mask using mri_synthstrip on mean b0
    synthstrip_task = workflow.add(
        MriSynthstrip(
            in_file=early_meanb0_task.out_file,
        )
    )

    dwibiasfieldcorr_task = workflow.add(
        DwiBiascorrect_Ants(
            in_file=dwi_degibbs_task.out,
            mask=synthstrip_task.mask_file,
            bias="biasfield.mif.gz",
        )
    )

    # # Step 7: Crop images to reduce storage space (but leave some padding on the sides)

    # #CONSIDER ADDING 'REGRID' HERE!

    # grid DWI
    crop_task_dwi = workflow.add(
        MrGrid(
            in_file=dwibiasfieldcorr_task.out_file,
            operation="crop",
            mask=synthstrip_task.mask_file,
            out_file="dwi_processed.mif.gz",
            uniform=-3,
        ),
        name="MrGrid_dwi",
    )

    # grid dwimask
    crop_task_mask = workflow.add(
        MrGrid(
            in_file=synthstrip_task.mask_file,
            operation="crop",
            mask=synthstrip_task.mask_file,
            out_file="dwimask_procesesd.mif.gz",
            interp="nearest",
            uniform=-3,
        ),
        name="MrGrid_mask",
    )

    # # ########################
    # # # REGISTRATION CONTENT #
    # # ########################

    # Step 8: Generate target images for registration and transformation

    join_task = workflow.add(JoinTask(FS_dir=FS_dir))

    # need to convert .mgz to nifti for registration
    nifti_t1 = workflow.add(
        MrConvert(
            in_file=join_task.t1_FSpath,
            out_file="t1.nii.gz",
        ),
        name="MrConvert_t1",
    )

    nifti_t1brain = workflow.add(
        MrConvert(
            in_file=join_task.t1brain_FSpath,
            out_file="t1brain.nii.gz",
        ),
        name="MrConvert_t1brain",
    )

    nifti_normimg = workflow.add(
        MrConvert(
            in_file=join_task.normimg_FSpath,
            out_file="normimg.nii.gz",
        ),
        name="MrConvert_normimg",
    )

    # extract meanb0 volumes #

    extract_bzeroes_task = workflow.add(
        DwiExtract(
            in_file=crop_task_dwi.out_file,
            out_file="bzero.mif.gz",
            bzero=True,
        )
    )

    # remove negative values from bzero volumes
    mrcalc_max = workflow.add(
        MrcalcMax(
            in_file=extract_bzeroes_task.out_file,
            output_image="b0_nonneg.mif.gz",
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_b0",
    )

    # # create meanb0 image
    meanb0_task = workflow.add(
        MrMath(
            in_file=mrcalc_max.output_image,
            out_file="dwi_meanbzero.nii.gz",
            operation="mean",
            axis=3,
        )
    )

    # make wm mask a binary image
    mrcalc_wmbin = workflow.add(
        MrcalcMax(
            in_file=join_task.wmseg_FSpath,
            number=0.0,
            operand="gt",
        ),
        name="MrcalcMax_wmbin",
    )

    # Step 9: Perform DWI->T1 registration
    epi_reg_task = workflow.add(
        EpiReg(
            epi=meanb0_task.out_file,
            t1_head=nifti_normimg.out_file,
            t1_brain=nifti_t1brain.out_file,
            wmseg=mrcalc_wmbin.output_image,
            out_base="epi2struct",
        )
    )

    # transformconvert task
    transformconvert_task = workflow.add(
        TransformConvert(
            input_matrix=epi_reg_task.epi2str_mat,
            flirt_in=meanb0_task.out_file,
            flirt_ref=nifti_t1brain.out_file,
            operation="flirt_import",
            out_file="epi2struct_mrtrix.txt",
        )
    )

    # #apply transform to DWI image
    transformDWI_task = workflow.add(
        MrTransform(
            in_file=crop_task_dwi.out_file,
            inverse=False,
            out_file="DWI_T1space.mif.gz",
            linear=transformconvert_task.out_file,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_dwi",
    )

    # #apply transform to DWI mask image
    transformDWImask_task = workflow.add(
        MrTransform(
            in_file=crop_task_mask.out_file,
            inverse=False,
            out_file="DWImask_T1space.mif.gz",
            interp="nearest",
            linear=transformconvert_task.out_file,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_mask",
    )

    # # # # ##################################
    # # # # # Tractography preparation steps #
    # # # # ##################################

    # # Estimate Response Function (subject)
    EstimateResponseFcn_task = workflow.add(
        Dwi2Response_Dhollander(
            in_file=transformDWI_task.out_file,
            mask=transformDWImask_task.out_file,
            voxels="voxels.mif.gz",
        )
    )

    ##################
    ## SCRIPT BREAK ##
    ##################

    # Generate FOD (Consider switching from subject-response to group-average-response)
    GenFod_task = workflow.add(
        Dwi2Fod(
            algorithm="msmt_csd",
            dwi=transformDWI_task.out_file,
            mask=transformDWImask_task.out_file,
            response_wm=EstimateResponseFcn_task.out_sfwm,
            response_gm=EstimateResponseFcn_task.out_gm,
            response_csf=EstimateResponseFcn_task.out_csf,
        )
    )

    # Normalise FOD
    NormFod_task = workflow.add(
        MtNormalise(
            fod_wm=GenFod_task.fod_wm,
            fod_gm=GenFod_task.fod_gm,
            fod_csf=GenFod_task.fod_csf,
            mask=transformDWImask_task.out_file,
            fod_wm_norm="wmfod_norm.mif.gz",
            fod_gm_norm="gmfod_norm.mif.gz",
            fod_csf_norm="csffod_norm.mif.gz",
        )
    )

    # Tractography
    tckgen_task = workflow.add(
        TckGen(
            source=NormFod_task.fod_wm_norm,
            # tracks="tractogram.tck",
            algorithm="ifod2",
            select=100,
            minlength=5.0,
            maxlength=350.0,
            seed_dynamic=NormFod_task.fod_wm_norm,
            act=fTT_image_T1space,
            backtrack=True,
            crop_at_gmwmi=True,
            cutoff=0.06,
            seeds=0,
        )
    )

    # SIFT2
    SIFT2_task = workflow.add(
        TckSift2(
            in_tracks=tckgen_task.tracks,
            in_fod=NormFod_task.fod_wm_norm,
            act=fTT_image_T1space,
            out_mu="mu.txt",
        )
    )

    ################
    # CONNECTOMICS #
    ################
    connectomics_task = workflow.add(
        Tck2Connectome(
            tracks_in=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            nodes_in=parcellation_image_T1space,
            symmetric=True,
            zero_diagonal=True,
        )
    )

    # ############
    # # TDI maps #
    # ############

    TDImap_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            vox=1,
            template=fTT_image_T1space,
            out_file="TDI.mif.gz",
        ),
        name="TckMap_TDI",
    )

    DECTDImap_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            vox=1,
            template=fTT_image_T1space,
            dec=True,
            out_file="DECTDI.mif.gz",
        ),
        name="TckMap_DECTDI",
    )

    # # SET WF OUTPUT

    return (
        transformDWI_task.out_file,
        transformDWImask_task.out_file,
        NormFod_task.fod_wm_norm,
        TDImap_task.out_file,
        DECTDImap_task.out_file,
        connectomics_task.connectome_out,
        SIFT2_task.out_mu,
        SIFT2_task.out_weights,
    )


# ########################
# # Execute the workflow #
# ########################


if __name__ == "__main__":
    wf = DwiPipeline(
        dwi_preproc_mif="<input dwi>",
        FS_dir="<input freesurfer dir>",
        fTTvis_image_T1space="<input fttvis image in T1 space>",
        fTT_image_T1space="<input ftt image in T1 space>",
        parcellation_image_T1space="<input parcellation image in T1 space>",
    )

    output_path = "<output_path>"
    result = wf(cache_root=output_path)
