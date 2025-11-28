import typing as ty
import logging

from pydra.compose import workflow
from pydra.tasks.fsl.v6 import Reorient2Std, Threshold
from pydra.tasks.freesurfer.v8 import (
    SurfaceTransform,
    Label2Vol,
    Aparc2Aseg,
)
from pydra.tasks.mrtrix3.v3_1 import (
    LabelConvert,
    Fivett2Vis,
    FivettGen_Hsvs,
    FivettGen_Freesurfer,
    FivettGen_Fsl,
    LabelSgmfirst,
)
from fileformats.generic import Directory, File
from fileformats.medimage import NiftiGz
from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from pydra.environments.docker import Docker
from pydra.environments.native import Native
from pydra.tasks.fastsurfer.latest import Fastsurfer
from .helpers import JoinTaskCatalogue, Dependency

# from pydra.engine.task import FunctionTask
# from pydra.engine.specs import BaseSpec
from pathlib import Path
import os

os.environ["SUBJECTS_DIR"] = ""

logger = logging.getLogger(
    "australianimagingservice.mri.human.neuro.t1w.preprocess.single_parc"
)


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
def SingleParcellation(
    t1w: NiftiGz,
    parcellation: str,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
    fs_license: File,
    subjects_dir: Path,
    in_fastsurfer_container: bool = False,
    fastsurfer_python: str = "python3",
    fastsurfer_batch: int = 16,
) -> tuple[Mif, Mif | None, Mif | None, Mif | None, Mif | None, Mif | None, Mif | None]:

    # ###################
    # # FASTSURFER TASK #
    # ###################

    if in_fastsurfer_container:
        fs_environment = Native()
        # executable = "/fastsurfer-run/run-script.sh"
        logger.info(f"Using FastSurfer executable in container")
    else:
        fs_environment = Docker(
            image="deepmi/fastsurfer",
            tag="cpu-v2.4.2",
            xargs=[
                "--user",
                "1000:1000",
                "--entrypoint",
                "/bin/bash",
            ],
        )
        # executable = "/fastsurfer/run_fastsurfer.sh"

        logger.info(f"Using FastSurfer in separate Docker container")

    fastsurfer = workflow.add(
        Fastsurfer(
            # executable=executable,
            T1_files=t1w,
            fs_license=fs_license,
            subject_id="FS_outputs",
            # norm_img="norm.mgz",
            # aparcaseg_img="aparcaseg.mgz",
            fsaparc=True,
            parallel=True,
            batch=fastsurfer_batch,
            threads=24,
            subjects_dir=subjects_dir,
            allow_root=True,
        ),
        environment=fs_environment,
    )

    logger.info("Fastsurfer executable is '%s'", fastsurfer.inputs.executable)

    if in_fastsurfer_container:
        fastsurfer.inputs.py = "/venv/bin/python"
        fastsurfer.inputs.executable = "/fastsurfer/run_fastsurfer.sh"
    # else:
    #     fastsurfer.inputs.py = fastsurfer_python

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
            ),
            name="fTTvis_task_hsvs",
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
            ),
            name="fTTvis_task_freesurfer",
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
            name="fTTvis_task_fsl",
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
        # mri_s2s_tasks = {}
        for hemi in hemispheres:
            mri_s2s_task1_v2atlas = workflow.add(
                SurfaceTransform(
                    source_subject=join_task.fsavg_dir,
                    target_subject=fastsurfer.subjects_dir_output,
                    source_file=getattr(join_task, f"source_annotation_file_{hemi}"),
                    out_file=getattr(join_task, f"{hemi}_annotation"),
                    hemi=hemi,
                ),
                name="mri_s2s_task_lh",
            )

        hemispheres = ["rh"]
        # mri_s2s_tasks2 = {}
        for hemi in hemispheres:
            mri_s2s_task2_v2atlas = workflow.add(
                SurfaceTransform(
                    source_subject=join_task.fsavg_dir,
                    target_subject=fastsurfer.subjects_dir_output,
                    source_file=getattr(join_task, f"source_annotation_file_{hemi}"),
                    out_file=getattr(join_task, f"{hemi}_annotation"),
                    hemi=hemi,
                ),
                name="mri_s2s_task_rh",
            )

        # ###########################################################
        # # dummy task to ensure aparc2aseg occurs after surf2surf  #
        # ###########################################################

        # dependency_task = workflow.add(
        #     Dependency(
        #         subjects_dir=join_task.fsavg_dir,
        #         annot_file_lh=mri_s2s_task1.out_file,
        #         annot_file_rh=mri_s2s_task2.out_file,
        #     )
        # )
        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        mri_a2a_task_v2atlas = workflow.add(
            Aparc2Aseg(
                subject_id=join_task.fsavg_dir,  # create dependency on lh and rh annot files having been created
                volmask=True,  # same as --new-ribbon
                lh_annotation=mri_s2s_task1_v2atlas.out_file,
                rh_annotation=mri_s2s_task2_v2atlas.out_file,
            ),
            name="mri_a2a_task_v2atlasprocessing",
        )

        # ##########################
        # # mri_label2volume task  #
        # ##########################

        mri_l2v_task = workflow.add(
            Label2Vol(
                seg_file=mri_a2a_task_v2atlas.out_file,  # volfile,
                template_file=join_task.l2v_temp,
                reg_header=join_task.l2v_regheader,
            )
        )

        # reorient to standard
        fslreorient2std_task = workflow.add(
            Reorient2Std(
                in_file=mri_l2v_task.vol_label_file,  # l2v_mgz2nii_task.out_file,
            )
        )

        # remove values less than 1000
        threshold_task = workflow.add(
            Threshold(
                # name="threshold_task",
                # executable="fslmaths",
                # input_spec=fslthreshold_input_spec,
                # output_spec=fslthreshold_output_spec,
                # output_image="label2vol_out_std_threshold.nii.gz",  # join_task.output_parcellation_filename,
                in_file=fslreorient2std_task.out_file,
                use_robust_range=False,
                thresh=1000,
            )
        )

        # relabel segmenetation to ascending integers from 1 to N
        LabelConvert_task = workflow.add(
            LabelConvert(
                path_in=threshold_task.out_file,
                lut_in=join_task.parc_lut_file,
                lut_out=join_task.mrtrix_lut_file,
                image_out=join_task.final_parc_image,  # type: ignore[]
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
            mri_s2s_task_originals_lh = workflow.add(
                SurfaceSmooth(
                    source_subject=join_task.fsavg_dir,
                    target_subject=fastsurfer.subjects_dir_output,  # FS_dir,
                    source_annot_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    out_file=getattr(join_task, f"{hemi}_annotation"),
                    hemi=hemi,
                ),
                name="mri_s2s_task_originals_lh",
            )

        hemispheres = ["rh"]
        mri_s2s_task_originals = {}
        for hemi in hemispheres:
            mri_s2s_task_originals_rh = workflow.add(
                SurfaceSmooth(
                    source_subject=join_task.fsavg_dir,
                    target_subject=fastsurfer.subjects_dir_output,  # FS_dir,
                    source_annot_file=getattr(
                        join_task, f"source_annotation_file_{hemi}"
                    ),
                    out_file=getattr(join_task, f"{hemi}_annotation"),
                    hemi=hemi,
                ),
                name="mri_s2s_task_originals_rh",
            )

        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        mri_a2a_task_originals = workflow.add(
            Aparc2Aseg(
                subject_id=mri_s2s_task_originals["rh"].target_subject_id,  # FS_dir,
                old_ribbon=True,
                lh_annotation=mri_s2s_task_originals_lh.out_file,
                rh_annotation=mri_s2s_task_originals_rh.out_file,
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

        sgm_first = workflow.add(
            LabelSgmfirst(
                parc=LabelConvert_task_originals.image_out,
                t1=join_task.normimg_path,
                lut=join_task.mrtrix_lut_file,
                # out_file=join_task.final_parc_image,
                nocleanup=True,
                premasked=True,
                sgm_amyg_hipp=True,
            )
        )

        return_image = sgm_first.out_file
    else:
        return_image = volfile

    return (
        return_image,
        fTTvis_task_fsl_out,
        fTTgen_task_fsl_out,
        fTTvis_task_freesurfer_out,
        fTTgen_task_freesurfer_out,
        fTTvis_task_hsvs_out,
        fTTgen_task_hsvs_out,
    )
