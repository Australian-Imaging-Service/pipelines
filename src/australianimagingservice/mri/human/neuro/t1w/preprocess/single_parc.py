import typing as ty
from pydra.compose import workflow
from pydra.tasks.fsl.v6 import Reorient2Std, Threshold
from pydra.tasks.freesurfer.v8 import (
    SurfaceSmooth,
    SurfaceTransform,
    Label2Vol,
    Aparc2Aseg,
)
from pydra.tasks.mrtrix3.v3_0 import (
    LabelConvert,
    LabelSgmfix,
    Fivett2Vis,
    FivettGen_Hsvs,
    FivettGen_Freesurfer,
    FivettGen_Fsl,
)
from fileformats.generic import Directory, File
from fileformats.medimage import NiftiGz
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.fastsurfer.latest import Fastsurfer
from .helpers import JoinTaskCatalogue

# from pydra.engine.task import FunctionTask
# from pydra.engine.specs import BaseSpec
from pathlib import Path
import os

os.environ["SUBJECTS_DIR"] = ""


@workflow.define(
    outputs=[
        "parc_image",
        "vis_image_fsl",
        "ftt_image_fsl",
        "vis_image_freesurfer",
        "ftt_image_freesurfer",
        "vis_image_hsvs",
        "ftt_image_hsvs",
    ]
)
def single_parc(
    t1w: NiftiGz,
    parcellation: str,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
    cache_dir: Directory,
    fs_license: File,
    subjects_dir: Directory,
    fastsurfer_executable: ty.Union[str, ty.List[str], None] = None,
    fastsurfer_python: str = "python3",
) -> tuple[Mif, Mif | None, Mif | None, Mif | None, Mif | None, Mif | None, Mif | None]:

    # ###################
    # # FASTSURFER TASK #
    # ###################

    fastsurfer = workflow.add(
        Fastsurfer(
            T1_files=t1w,
            fs_license=fs_license,
            subject_id="FS_outputs",
            py=fastsurfer_python,
            # norm_img="norm.mgz",
            # aparcaseg_img="aparcaseg.mgz",
            fsaparc=True,
            parallel=True,
            threads=24,
            subjects_dir=subjects_dir,
        )
    )
    if fastsurfer_executable:
        fastsurfer.inputs.executable = fastsurfer_executable

    # #################################################
    # # FIVE TISSUE TYPE Generation and visualisation #
    # #################################################
    if (
        parcellation
        == parcellation  # this loop is a placeholder for if/when we decide to iterate through each parcellation image"aparc-a2009s"
    ):  # to avoid repeating this on every iteration of loop, only exectute on one (first) parcellation

        # Five tissue-type task HSVS
        fTTgen_task_hsvs = workflow.add(
            FivettGen_Hsvs(
                in_file=fastsurfer.subjects_dir_output,
                # out_file="5TT_hsvs.mif.gz",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
                white_stem=True,
            )
        )

        # Five tissue-type visualisation task HSVS
        fTTvis_task_hsvs = workflow.add(
            Fivett2Vis(
                in_file=fTTgen_task_hsvs.out_file,
                # out_file="5TTvis_hsvs.mif.gz",
            )
        )

        # Five tissue-type task FreeSurfer

        fTTgen_task_freesurfer = workflow.add(
            FivettGen_Freesurfer(
                in_file=fastsurfer.aparcaseg_img,
                # out_file="5TT_freesurfer.mif.gz",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
            )
        )

        # Five tissue-type visualisation task FreeSurfer
        fTTvis_task_freesurfer = workflow.add(
            Fivett2Vis(
                in_file=fTTgen_task_freesurfer.out_file,
                # out_file="5TTvis_freesurfer.mif.gz",
            )
        )

        # Five tissue-type task fsl

        fTTgen_task_fsl = workflow.add(
            FivettGen_Fsl(
                in_file=fastsurfer.norm_img,
                # out_file="5TT_fsl.mif.gz",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
                premasked=True,
            )
        )

        # Five tissue-type visualisation task FSL
        fTTvis_task_fsl = workflow.add(
            Fivett2Vis(
                in_file=fTTgen_task_fsl.out_file,
                #    out_file="5TTvis_fsl.mif.gz",
            ),
        )
        fTTgen_task_hsvs_out = fTTgen_task_hsvs.out_file
        fTTvis_task_hsvs_out = fTTvis_task_hsvs.out_file
        fTTgen_task_freesurfer_out = fTTgen_task_freesurfer.out_file
        fTTvis_task_freesurfer_out = fTTvis_task_freesurfer.out_file
        fTTgen_task_fsl_out = fTTgen_task_fsl.out_file
        fTTvis_task_fsl_out = fTTvis_task_fsl.out_file
    else:
        fTTgen_task_hsvs_out = None
        fTTvis_task_hsvs_out = None
        fTTgen_task_freesurfer_out = None
        fTTvis_task_freesurfer_out = None
        fTTgen_task_fsl_out = None
        fTTvis_task_fsl_out = None

    #################################
    # PARCELLATION IMAGE GENERATION #
    #################################

    join_task = workflow.add(
        JoinTaskCatalogue(
            FS_dir=fastsurfer.subjects_dir_output,  # FS_dir,
            parcellation=parcellation,
            freesurfer_home=freesurfer_home,
            mrtrix_lut_dir=mrtrix_lut_dir,
            # output_path=output_path,
        )  # pyright: ignore[reportArgumentType]
    )

    #########################
    # # v2 atlas processing #
    #########################

    if (
        "schaefer" in parcellation
        or "aparc" in parcellation
        or "vosdewael" in parcellation
        or parcellation == "economo"
        or parcellation == "glasser360"
    ):

        ##################################
        # mri_surf2surf task - lh and rh #
        ##################################
        hemispheres = ["lh"]
        mri_s2s_tasks = {}
        for hemi in hemispheres:
            mri_s2s_tasks[hemi] = workflow.add(
                SurfaceSmooth(
                    cache_dir=cache_dir,
                    source_subject_id=join_task.fsavg_dir,
                    target_subject_id=fastsurfer.subjects_dir_output,
                    source_annotation_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                    hemisphere=hemi,
                )
                # ShellCommandTask(
                #     executable="mri_surf2surf",
                #     input_spec=mri_s2s_input_spec,
                #     output_spec=mri_s2s_output_spec,
                #     cache_dir=cache_dir,
                #     source_subject_id=join_task.fsavg_dir,
                #     target_subject_id=fastsurfer.subjects_dir_output,
                #     source_annotation_file=getattr(
                #         join_task, f"source_annotation_file_{hemi}"
                #     ),
                #     target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                #     hemisphere=hemi,
                # )
            )

        hemispheres = ["rh"]
        mri_s2s_tasks2 = {}
        for hemi in hemispheres:
            mri_s2s_tasks2[hemi] = workflow.add(
                SurfaceSmooth(
                    cache_dir=cache_dir,
                    source_subject_id=join_task.fsavg_dir,
                    target_subject_id=mri_s2s_tasks[
                        "rh"
                    ].target_subject_id,  # create dependency on lh being executed first
                    source_annotation_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                    hemisphere=hemi,
                )
                # ShellCommandTask(
                #     name=f"mri_s2s_task_{hemi}",
                #     executable="mri_surf2surf",
                #     input_spec=mri_s2s_input_spec,
                #     output_spec=mri_s2s_output_spec,
                #     cache_dir=cache_dir,
                #     source_subject_id=join_task.fsavg_dir,
                #     target_subject_id=mri_s2s_task_lh.target_subject_id,  # create dependency on lh being executed first
                #     source_annotation_file=getattr(
                #         join_task, f"source_annotation_file_{hemi}"
                #     ),
                #     target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                #     hemisphere=hemi,
                # )
            )

        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        mri_a2a_task = workflow.add(
            Aparc2Aseg(
                cache_dir=cache_dir,
                subject=mri_s2s_tasks[
                    "rh"
                ].target_subject_id,  # create dependency on lh and rh annot files having been created
                new_ribbon=True,
                annotname=join_task.annot_short,
            )
            # ShellCommandTask(
            #     name="mri_a2a_task",
            #     executable="mri_aparc2aseg",
            #     input_spec=mri_a2a_input_spec,
            #     output_spec=mri_a2a_output_spec,
            #     cache_dir=cache_dir,
            #     subject=mri_s2s_task_rh.target_subject_id,  # create dependency on lh and rh annot files having been created
            #     new_ribbon=True,
            #     annotname=join_task.annot_short,
            # )
        )

        # ##########################
        # # mri_label2volume task  #
        # ##########################

        mri_l2v_task = workflow.add(
            Label2Vol(
                cache_dir=cache_dir,
                seg=mri_a2a_task.volfile,
                temp=join_task.l2v_temp,
                regheader=join_task.l2v_regheader,
            )
            # ShellCommandTask(
            #     name="mri_l2v_task",
            #     executable="mri_label2vol",
            #     input_spec=mri_l2v_input_spec,
            #     output_spec=mri_l2v_output_spec,
            #     cache_dir=cache_dir,
            #     seg=mri_a2a_task.volfile,
            #     temp=join_task.l2v_temp,
            #     regheader=join_task.l2v_regheader,
            # )
        )

        # reorient to standard
        fslreorient2std_task = workflow.add(
            Reorient2Std(
                in_file=mri_l2v_task.output,  # l2v_mgz2nii_task.out_file,
            )
        )

        # remove values less than 1000
        threshold_task = workflow.add(
            Threshold(
                # name="threshold_task",
                # executable="fslmaths",
                # input_spec=fslthreshold_input_spec,
                # output_spec=fslthreshold_output_spec,
                in_file=fslreorient2std_task.output_image,
                use_robust_range=False,
                # output_image="label2vol_out_std_threshold.nii.gz",  # join_task.output_parcellation_filename,
                thresh=1000,
            )
        )

        # relabel segmenetation to ascending integers from 1 to N
        LabelConvert_task = workflow.add(
            LabelConvert(
                path_in=threshold_task.output_image,
                lut_in=join_task.parc_lut_file,
                lut_out=join_task.mrtrix_lut_file,
                image_out=join_task.final_parc_image,
                # name="LabelConvert_task",
            )
        )

        return_image = LabelConvert_task.image_out

    # else:
    #     return_image = SGMfix_task.out_file

    ##########################################################
    # # additional mapping for 'hcpmmp1', 'yeo17', 'yeo7 #
    ##########################################################

    volfile = join_task.output_parcellation_filename

    mri_s2s_task_originals = {}

    if parcellation in ["hcpmmp1", "Yeo17", "Yeo7"]:
        ##################################
        # mri_surf2surf task - lh and rh #
        ##################################
        hemispheres = ["lh"]
        for hemi in hemispheres:
            mri_s2s_task_originals[hemi] = workflow.add(
                SurfaceSmooth(
                    cache_dir=cache_dir,
                    source_subject_id=join_task.fsavg_dir,
                    target_subject_id=fastsurfer.subjects_dir_output,  # FS_dir,
                    source_annotation_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                    hemi=hemi,
                ),
                name=f"mri_s2s_task_originals_{hemi}",
                # ShellCommandTask(
                #     name=f"mri_s2s_task_originals_{hemi}",
                #     executable="mri_surf2surf",
                #     input_spec=mri_s2s_input_spec,
                #     output_spec=mri_s2s_output_spec,
                #     cache_dir=cache_dir,
                #     source_subject_id=join_task.fsavg_dir,
                #     target_subject_id=fastsurfer.subjects_dir_output,  # FS_dir,
                #     source_annotation_file=getattr(
                #         join_task, f"source_annotation_file_{hemi}"
                #     ),
                #     target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                #     hemisphere=hemi,
                # )
            )

        hemispheres = ["rh"]
        mri_s2s_task_originals = {}
        for hemi in hemispheres:
            mri_s2s_task_originals[hemi] = workflow.add(
                SurfaceSmooth(
                    cache_dir=cache_dir,
                    source_subject_id=join_task.fsavg_dir,
                    target_subject_id=mri_s2s_task_originals[
                        "rh"
                    ].target_subject_id,  # create dependency on rh being executed first
                    source_annotation_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                    hemisphere=hemi,
                ),
                name=f"mri_s2s_task_originals_{hemi}",
                # ShellCommandTask(
                #     name=f"mri_s2s_task_originals_{hemi}",
                #     executable="mri_surf2surf",
                #     input_spec=mri_s2s_input_spec,
                #     output_spec=mri_s2s_output_spec,
                #     cache_dir=cache_dir,
                #     source_subject_id=join_task.fsavg_dir,
                #     target_subject_id=mri_s2s_task_originals_lh.target_subject_id,  # create dependency on lh being executed first
                #     source_annotation_file=getattr(
                #         join_task, f"source_annotation_file_{hemi}"
                #     ),
                #     target_annotation_file=getattr(join_task, f"{hemi}_annotation"),
                #     hemisphere=hemi,
                # )
            )

        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        mri_a2a_task_originals = workflow.add(
            Aparc2Aseg(
                cache_dir=cache_dir,
                subject=mri_s2s_task_originals["rh"].target_subject_id,  # FS_dir,
                old_ribbon=True,
                annotname=join_task.annot_short,
            )
        )
        volfile = mri_a2a_task_originals.volfile

    if parcellation in ["destrieux", "desikan", "hcpmmp1", "Yeo17", "Yeo7"]:
        # relabel segmenetation to integers
        LabelConvert_task_originals = workflow.add(
            LabelConvert(
                path_in=volfile,
                lut_in=join_task.parc_lut_file,
                lut_out=join_task.mrtrix_lut_file,
                # image_out="labelconvert.mif",  # join_task.node_image,
            )
        )

        SGMfix_task = workflow.add(
            LabelSgmfix(
                parc=LabelConvert_task_originals.image_out,
                t1=join_task.normimg_path,
                lut=join_task.mrtrix_lut_file,
                out_file=join_task.final_parc_image,
                nocleanup=True,
                premasked=True,
                sgm_amyg_hipp=True,
            )
        )

        return_image = SGMfix_task.out_file

    return (
        return_image,
        fTTvis_task_fsl_out,
        fTTgen_task_fsl_out,
        fTTvis_task_freesurfer_out,
        fTTgen_task_freesurfer_out,
        fTTvis_task_hsvs_out,
        fTTgen_task_hsvs_out,
    )
