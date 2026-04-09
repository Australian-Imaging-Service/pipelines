import os
from pydra.compose import python, shell, workflow
from fileformats.generic import File
from pydra.tasks.mrtrix3.v3_1 import (
    DwiGradcheck,
    Dwi2Mask_Synthstrip,
    DwiDenoise,
    MrDegibbs,
    DwiFslpreproc,
    DwiBiasnormmask,
    Dwi2Mask_Fslbet,
    DwiBiascorrect_Ants,
    DwiBiascorrect_Fsl,
    TransformConvert,
    MrTransform,
    MrConvert,
    MrGrid,
    DwiExtract,
    MrCalc,
    MrMath,
    DwiBiasnormmask,
    MrThreshold,
    Dwi2Response_Dhollander,
    Dwi2Fod,
    MtNormalise,
    TckGen,
    TckSift2,
    Tck2Connectome,
    TckMap,
)
from pydra.tasks.fsl.v6 import EpiReg
from fileformats.medimage import NiftiGzXBvec, NiftiGz

from fileformats.medimage_mrtrix3 import (
    ImageFormat,
    ImageIn,
    ImageOut,
    Tracks,
)  # noqa: F401

# Define the path and output_path variables
output_path = "/Users/adso8337/Desktop/DWIpreproc_tests/Outputs/"

# @pydra.mark.task
# def run_mri_synthstrip():
#     import subprocess

#     # Define the command to execute
#     command = ["python", "/Users/arkievdsouza/synthstrip-docker"]
#     # Execute the command
#     result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     # Check if the command executed successfully
#     if result.returncode != 0:
#         # Print error message if the command failed
#         print("Error running mri_synthstrip:")
#         print(result.stderr.decode())
#     # Return the stdout output
#     return result.stdout.decode()


# Define the input_spec for the workflow
@workflow.define(
    outputs=[
        "DWI_processed",
        "DWImask_processed",
        "wm_fod_norm",
        "TDI_file",
        "DECTDI_file",
        # "sift_mu",  # SIF2_task.out_mu
        # "sift_weights",  # SIF2_task.out_weights
        # "conenctome_file",  # connectomics_task.connectome_out
    ]
)
def DwiPipeline(
    dwi_preproc_mif: File,
    FS_dir: str,
    fTTvis_image_T1space: File,
    fTT_image_T1space: File,
    parcellation_image_T1space: File,
) -> tuple[File, File, File, File, File]:

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

    # create brainmask and mask DWI image - revisit
    # wf.add(
    #     DwiBiasnormmask(
    #         name="dwibiasnormmask_task",
    #         in_file=dwi_degibbs_task.out, # update to be output of DWIfslpreproc
    #         output_dwi="dwi_biasnorm.mif",
    #         output_mask="dwi_mask.mif",
    #         mask_algo="threshold",
    #         output_bias="bias_field.mif",
    #         output_tissuesum="tissue_sum.mif"
    #     )
    # )

    dwimask_task = workflow.add(
        Dwi2Mask_Fslbet(
            in_file=dwi_degibbs_task.out,  # update to be output of DWIfslpreproc
            out_file="dwi_mask.mif.gz",
        )
    )

    # consider moving to the top
    # wf.add( # mri_synthstrip -i bzero.nii -m synthstrip_mask.nii works but not when used in dwi2mask synthstrip
    #     Dwi2Mask_Synthstrip(
    #         name="dwimask_task",
    #         in_file=dwi_degibbs_task.out,  # update to be output of DWIfslpreproc
    #         out_file="dwi_mask.mif.gz",
    #         gpu=False,
    #         nocleanup=True,
    #     )
    # )

    # wf.add(
    #     DwiBiascorrect_Fsl(  # replace this with ANTs
    #         name="dwibiasfieldcorr_task",
    #         in_file=dwi_degibbs_task.out,
    #         mask=dwimask_task.out_file,
    #         bias="biasfield.mif.gz",
    #     )
    # )

    dwibiasfieldcorr_task = workflow.add(
        DwiBiascorrect_Ants(  # replace this with ANTs
            in_file=dwi_degibbs_task.out,
            mask=dwimask_task.out_file,
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
            mask=dwimask_task.out_file,
            out_file="dwi_processed.mif.gz",
            uniform=-3,
        ),
        name="MrGrid_dwi",
    )

    # grid dwimask
    crop_task_mask = workflow.add(
        MrGrid(
            in_file=dwimask_task.out_file,
            operation="crop",
            mask=dwimask_task.out_file,
            out_file="dwimask_procesesd.mif.gz",
            interp="nearest",
            uniform=-3,
        ),
        name="MrGrid_mask",
    )

    # # REPLACE Step8-10 with epi_reg (and transform DWI to T1 space)

    # # ########################
    # # # REGISTRATION CONTENT #
    # # ########################

    # Step 8: Generate target images for registration and transformation

    @python.define(
        outputs=["t1_FSpath", "t1brain_FSpath", "wmseg_FSpath", "normimg_FSpath"]
    )
    def JoinTask(FS_dir: str):
        t1_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")
        t1brain_FSpath = os.path.join(FS_dir, "mri", "brainmask.mgz")
        wmseg_FSpath = os.path.join(FS_dir, "mri", "wm.seg.mgz")
        normimg_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")

        return t1_FSpath, t1brain_FSpath, wmseg_FSpath, normimg_FSpath

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

    nifti_wmseg = workflow.add(
        MrConvert(
            in_file=join_task.wmseg_FSpath,
            out_file="wmseg.nii.gz",
        ),
        name="MrConvert_wmseg",
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

    # mrcalc spec info
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
            in_file=nifti_wmseg.out_file,
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
        )
    )

    # Tractography
    tckgen_task = workflow.add(
        TckGen(
            source=NormFod_task.fod_wm_norm,
            # tracks="tractogram.tck",
            algorithm="ifod2",
            select=1000,
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
    SIF2_task = workflow.add(
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
            tck_weights_in=SIF2_task.out_weights,
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
            tck_weights_in=SIF2_task.out_weights,
            vox=0.2,
            template=fTT_image_T1space,
            out_file="TDI.mif.gz",
        ),
        name="TckMap_TDI",
    )

    DECTDImap_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=SIF2_task.out_weights,
            vox=0.2,
            template=fTT_image_T1space,
            dec=True,
            out_file="DECTDI.mif.gz",
        ),
        name="TckMap_DECTDI",
    )

    # # SET WF OUTPUT

    return (
        crop_task_dwi.out_file,
        crop_task_mask.out_file,
        NormFod_task.fod_wm_norm,
        TDImap_task.out_file,
        DECTDImap_task.out_file,
    )


# ########################
# # Execute the workflow #
# ########################


if __name__ == "__main__":
    wf = DwiPipeline(
        dwi_preproc_mif="/Users/adso8337/Desktop/DWIpipeline_testing/Data/test001/DWI.mif.gz",
        FS_dir="/Users/adso8337/Desktop/DWIpipeline_testing/Data/test001/FreeSurfer/",
        fTTvis_image_T1space="/Users/adso8337/Desktop/DWIpipeline_testing/Data/test001/5TTvis_msmt.mif.gz",
        fTT_image_T1space="/Users/adso8337/Desktop/DWIpipeline_testing/Data/test001/5TT_msmt.mif.gz",
        parcellation_image_T1space="/Users/adso8337/Desktop/DWIpipeline_testing/Data/test001/FreeSurfer/mri/aparc+aseg.mgz",
    )

    output_path = "/Users/adso8337/Desktop/DWIpipeline_testing/output"
    result = wf(cache_root=output_path)

# # Step 7: Crop images to reduce storage space (but leave some padding on the sides) - pointing to wrong folder, needs fix (nonurgent)
# # grid DWI
# wf.add(
#     mrgrid(
#         input=dwibiasnormmask_task.output_dwi,
#         name="crop_task_dwi",
#         operation="crop",
#         output="dwi_crop.mif",
#         mask=dwibiasnormmask_task.output_mask,
#         uniform=-3,
#     )
# )

# #grid dwimask
# wf.add(
#     mrgrid(
#         input=dwibiasnormmask_task.output_mask,
#         name="crop_task_mask",
#         operation="crop",
#         output="mask_crop.mif",
#         mask=dwibiasnormmask_task.output_mask,
#         uniform=-3,
#     )
# )
