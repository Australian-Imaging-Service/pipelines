import typing as ty
import attrs
from pydra import Workflow, mark, ShellCommandTask
from pydra.engine.specs import SpecInfo, ShellSpec, ShellOutSpec, File
from pydra.tasks.mrtrix3.v3_0 import (
    LabelConvert,
    LabelSgmfix,
    Fivett2Vis,
    FivettGen_Hsvs,
    FivettGen_Freesurfer,
    FivettGen_Fsl,
)
from fileformats.generic import Directory, DirectoryOf
from fileformats.medimage import NiftiGz
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.fastsurfer.latest import Fastsurfer
from pydra.engine.task import FunctionTask
from pydra.engine.specs import BaseSpec
from pathlib import Path
import os

os.environ["SUBJECTS_DIR"] = ""


def single_parc(
    parcellation: str,
    freesurfer_home: Path,
    mrtrix_lut_dir: Path,
    cache_dir: Path,
    fs_license: Path,
    fastsurfer_executable: ty.Union[str, ty.List[str], None] = None,
    fastsurfer_python: str = "python3",
    name: str = "t1_preprocessing_pipeline",
    t1w: File = attrs.NOTHING,
) -> Workflow:
    # Define the input values using input_spec
    input_spec = {
        "t1w": File,
    }

    wf = Workflow(
        name=name,
        input_spec=input_spec,
        cache_dir=cache_dir,
        t1w=t1w,
    )

    # ###################
    # # FASTSURFER TASK #
    # ###################

    wf.add(
        Fastsurfer(
            T1_files=wf.lzin.t1w,
            fs_license=fs_license,
            subject_id="FS_outputs",
            name="FastSurfer_task",
            py=fastsurfer_python,
            norm_img="norm.mgz",
            aparcaseg_img="aparcaseg.mgz",
            fsaparc=True,
            parallel=True,
            threads=24,
        )
    )
    if fastsurfer_executable:
        wf.FastSurfer_task.inputs.executable = fastsurfer_executable

    # #################################################
    # # FIVE TISSUE TYPE Generation and visualisation #
    # #################################################
    if (
        parcellation
        == parcellation  # this loop is a placeholder for if/when we decide to iterate through each parcellation image"aparc-a2009s"
    ):  # to avoid repeating this on every iteration of loop, only exectute on one (first) parcellation

        # Five tissue-type task HSVS
        wf.add(
            FivettGen_Hsvs(
                in_file=wf.FastSurfer_task.lzout.subjects_dir_output,
                out_file="5TT_hsvs.mif.gz",
                name="fTTgen_task_hsvs",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
                white_stem=True,
            )
        )

        # Five tissue-type visualisation task HSVS
        wf.add(
            Fivett2Vis(
                in_file=wf.fTTgen_task_hsvs.lzout.out_file,
                out_file="5TTvis_hsvs.mif.gz",
                name="fTTvis_task_hsvs",
            )
        )

        # Five tissue-type task FreeSurfer

        wf.add(
            FivettGen_Freesurfer(
                in_file=wf.FastSurfer_task.lzout.aparcaseg_img,
                out_file="5TT_freesurfer.mif.gz",
                name="fTTgen_task_freesurfer",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
            )
        )

        # Five tissue-type visualisation task FreeSurfer
        wf.add(
            Fivett2Vis(
                in_file=wf.fTTgen_task_freesurfer.lzout.out_file,
                out_file="5TTvis_freesurfer.mif.gz",
                name="fTTvis_task_freesurfer",
            )
        )

        # Five tissue-type task fsl

        wf.add(
            FivettGen_Fsl(
                in_file=wf.FastSurfer_task.lzout.norm_img,
                out_file="5TT_fsl.mif.gz",
                name="fTTgen_task_fsl",
                nocrop=True,
                sgm_amyg_hipp=True,
                nocleanup=True,
                premasked=True,
            )
        )

        # Five tissue-type visualisation task FSL
        wf.add(
            Fivett2Vis(
                in_file=wf.fTTgen_task_fsl.lzout.out_file,
                out_file="5TTvis_fsl.mif.gz",
                name="fTTvis_task_fsl",
            )
        )

    #################################
    # PARCELLATION IMAGE GENERATION #
    #################################

    @mark.task  # type: ignore[misc]
    @mark.annotate(
        {
            "parcellation": str,
            "FS_dir": str,
            "freesurfer_home": str,
            "return": {
                "fsavg_dir": str,
                "parc_lut_file": str,
                "mrtrix_lut_file": str,
                "output_parcellation_filename": str,
                "lh_annotation": str,
                "rh_annotation": str,
                "source_annotation_file_lh": str,
                "source_annotation_file_rh": str,
                "annot_short": str,
                "node_image": str,
                "normimg_path": str,
                "final_parc_image": str,
                "l2v_temp": str,
                "l2v_regheader": str,
            },
        }
    )  # type: ignore[misc]
    def join_task_catalogue(
        parcellation: str,
        FS_dir: str,
        freesurfer_home: str,
        mrtrix_lut_dir: Path,
    ) -> ty.Tuple[str, str, str, str, str, str, str, str, str, str, str, str, str, str]:
        node_image = parcellation + "_nodes.mif"
        final_parc_image = os.path.join(f"Atlas_{parcellation}.mif.gz")
        normimg_path = os.path.join(FS_dir, "mri", "norm.mgz")

        if (
            "schaefer" in parcellation
            or "aparc" in parcellation
            or "vosdewael" in parcellation
            or parcellation == "economo"
            or parcellation == "glasser360"
        ):
            fsavg_dir = os.path.join(freesurfer_home, "subjects", "fsaverage5")
            parc_lut_file = os.path.join(
                freesurfer_home,
                "MICA_MNI_parcellations",
                "lut",
                f"lut_{parcellation}_mics.csv",
            )
            mrtrix_lut_file = os.path.join(
                mrtrix_lut_dir, f"{parcellation}_reordered_LUT.txt"
            )

            output_parcellation_filename = os.path.join(
                FS_dir, "mri", f"{parcellation}.nii.gz"
            )
            lh_annotation = os.path.join(
                FS_dir, "label", f"lh.{parcellation}_mics.annot"
            )
            rh_annotation = os.path.join(
                FS_dir, "label", f"rh.{parcellation}_mics.annot"
            )
            source_annotation_file_lh = os.path.join(
                freesurfer_home,
                "MICA_MNI_parcellations",
                f"lh.{parcellation}_mics.annot",
            )
            source_annotation_file_rh = os.path.join(
                freesurfer_home,
                "MICA_MNI_parcellations",
                f"rh.{parcellation}_mics.annot",
            )
            annot_short = f"{parcellation}_mics"
            l2v_temp = os.path.join(FS_dir, "mri", "T1.mgz")
            l2v_regheader = os.path.join(FS_dir, "mri", "aseg.mgz")

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )

        elif parcellation == "desikan":
            # DESIKAN definitions
            fsavg_dir = ""
            parc_lut_file = os.path.join(freesurfer_home, "FreeSurferColorLUT.txt")
            mrtrix_lut_file = os.path.join(mrtrix_lut_dir, "fs_default.txt")
            output_parcellation_filename = os.path.join(FS_dir, "mri", "aparc+aseg.mgz")
            lh_annotation = ""
            rh_annotation = ""
            source_annotation_file_lh = ""
            source_annotation_file_rh = ""
            annot_short = ""
            l2v_temp = ""
            l2v_regheader = ""

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )

        elif parcellation == "destrieux":
            # DESTRIEUX definitions
            fsavg_dir = ""
            parc_lut_file = os.path.join(freesurfer_home, "FreeSurferColorLUT.txt")
            mrtrix_lut_file = os.path.join(mrtrix_lut_dir, "fs_a2009s.txt")
            output_parcellation_filename = os.path.join(
                FS_dir, "mri", "aparc.a2009s+aseg.mgz"
            )
            lh_annotation = ""
            rh_annotation = ""
            source_annotation_file_lh = ""
            source_annotation_file_rh = ""
            annot_short = ""
            l2v_temp = ""
            l2v_regheader = ""

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )

        elif parcellation == "hcpmmp1":
            # HCPMMP1 definitions
            fsavg_dir = os.path.join(freesurfer_home, "subjects", "fsaverage")
            parc_lut_file = os.path.join(mrtrix_lut_dir, "hcpmmp1_original.txt")
            mrtrix_lut_file = os.path.join(mrtrix_lut_dir, "hcpmmp1_ordered.txt")
            output_parcellation_filename = os.path.join(
                FS_dir, "mri", f"{parcellation}.nii.gz"
            )
            lh_annotation = os.path.join(FS_dir, "label", "lh.HCPMMP1.annot")
            rh_annotation = os.path.join(FS_dir, "label", "rh.HCPMMP1.annot")
            source_annotation_file_lh = os.path.join(
                fsavg_dir, "label", "lh.HCPMMP1.annot"
            )
            source_annotation_file_rh = os.path.join(
                fsavg_dir, "label", "rh.HCPMMP1.annot"
            )
            annot_short = ""
            l2v_temp = ""
            l2v_regheader = ""

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )

        elif parcellation == "Yeo7":
            # yeo7 definitions
            fsavg_dir = os.path.join(freesurfer_home, "subjects", "fsaverage5")
            parc_lut_file = os.path.join(
                freesurfer_home, "Yeo2011", "Yeo2011_7networks_Split_Components_LUT.txt"
            )
            mrtrix_lut_file = os.path.join(mrtrix_lut_dir, "Yeo2011_7N_split.txt")
            output_parcellation_filename = os.path.join(
                FS_dir, "mri", f"{parcellation}.nii.gz"
            )
            lh_annotation = os.path.join(FS_dir, "label", "lh.Yeo7.annot")
            rh_annotation = os.path.join(FS_dir, "label", "rh.Yeo7.annot")
            source_annotation_file_lh = os.path.join(
                fsavg_dir, "label", "lh.Yeo2011_7Networks_N1000.split_components.annot"
            )
            source_annotation_file_rh = os.path.join(
                fsavg_dir, "label", "rh.Yeo2011_7Networks_N1000.split_components.annot"
            )
            annot_short = ""
            l2v_temp = ""
            l2v_regheader = ""

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )

        elif parcellation == "Yeo17":
            # yeo17 definitions
            fsavg_dir = os.path.join(freesurfer_home, "subjects", "fsaverage5")
            parc_lut_file = os.path.join(
                freesurfer_home,
                "Yeo2011",
                "Yeo2011_17networks_Split_Components_LUT.txt",
            )
            mrtrix_lut_file = os.path.join(mrtrix_lut_dir, "Yeo2011_17N_split.txt")
            output_parcellation_filename = os.path.join(
                FS_dir, "mri", f"{parcellation}.nii.gz"
            )
            lh_annotation = os.path.join(FS_dir, "label", "lh.Yeo17.annot")
            rh_annotation = os.path.join(FS_dir, "label", "rh.Yeo17.annot")
            source_annotation_file_lh = os.path.join(
                fsavg_dir, "label", "lh.Yeo2011_17Networks_N1000.split_components.annot"
            )
            source_annotation_file_rh = os.path.join(
                fsavg_dir, "label", "rh.Yeo2011_17Networks_N1000.split_components.annot"
            )
            annot_short = ""
            l2v_temp = ""
            l2v_regheader = ""

            return (
                fsavg_dir,
                parc_lut_file,
                mrtrix_lut_file,
                output_parcellation_filename,
                lh_annotation,
                rh_annotation,
                source_annotation_file_lh,
                source_annotation_file_rh,
                annot_short,
                node_image,
                normimg_path,
                final_parc_image,
                l2v_temp,
                l2v_regheader,
            )
        else:
            raise ValueError(
                f"Parcellation {parcellation} not recognised. Please choose from: "
                "'aparc', 'schaefer', 'vosdewael', 'economo', 'glasser360'"
            )

    wf.add(
        join_task_catalogue(
            FS_dir=wf.FastSurfer_task.lzout.subjects_dir_output,  # wf.lzin.FS_dir,
            parcellation=parcellation,
            freesurfer_home=freesurfer_home,
            mrtrix_lut_dir=mrtrix_lut_dir,
            # output_path=output_path,
            name="join_task",
        )
    )

    ###########################
    # mri_surf2surf spec info #
    ###########################

    mri_s2s_input_spec = SpecInfo(
        name="Input",
        fields=[
            (
                "source_subject_id",
                str,
                {
                    "help_string": "source subject",
                    "argstr": "--srcsubject",
                    "mandatory": True,
                },
            ),
            (
                "target_subject_id",
                str,
                {
                    "help_string": "target subject",
                    "argstr": "--trgsubject",
                    "mandatory": True,
                },
            ),
            (
                "source_annotation_file",
                str,
                {
                    "help_string": "annotfile : map annotation",
                    "argstr": "--sval-annot",
                    "mandatory": True,
                },
            ),
            (
                "target_annotation_file",
                str,
                {
                    "help_string": "path of file in which to store output values",
                    "argstr": "--tval",
                    "mandatory": True,
                },
            ),
            (
                "hemisphere",
                str,
                {
                    "help_string": "hemisphere : (lh or rh) for both source and targ",
                    "argstr": "--hemi",
                    "mandatory": True,
                },
            ),
        ],
        bases=(ShellSpec,),
    )

    mri_s2s_output_spec = SpecInfo(
        name="Output",
        fields=[
            (
                "target_annotation_file",
                File,
                {
                    "help_string": "path of file in which to store output values",
                    "argstr": "--tval",
                    "mandatory": True,
                },
            ),
        ],
        bases=(ShellOutSpec,),
    )

    # ############################
    # # mri_aparc2aseg spec info #
    # ############################

    mri_a2a_input_spec = SpecInfo(
        name="Input",
        fields=[
            (
                "subject",
                Directory,
                {
                    "help_string": "Name of the subject as found in the SUBJECTS_DIR",
                    "argstr": "--s",
                    "mandatory": True,
                },
            ),
            (
                "old_ribbon",
                bool,
                {
                    "help_string": "use mri/hemi.ribbon.mgz as a mask for the cortex",
                    "argstr": "--old-ribbon",
                },
            ),
            (
                "new_ribbon",
                bool,
                {
                    "help_string": "Mask cortical voxels with mri/ribbon.mgz. Same as --volmask",
                    "argstr": "--new-ribbon",
                },
            ),
            (
                "annotname",
                str,
                {
                    "help_string": "Use annotname surface annotation. By default, uses ?h.aparc.annot. With this option, it will load ?h.annotname.annot. The output file will be set to annotname+aseg.mgz, but this can be changed with --o. Note: running --annot aparc.a2009s is NOT the same as running --a2009s. The index numbers will be different.",
                    "argstr": "--annot",
                },
            ),
            (
                "volfile",
                Path,
                {
                    "help_string": "Full path of file to save the output segmentation in. Default is mri/aparc+aseg.mgz",
                    "argstr": "--o",
                    "output_file_template": "volfile.nii.gz",
                },
            ),
        ],
        bases=(ShellSpec,),
    )

    mri_a2a_output_spec = SpecInfo(
        name="Output",
        fields=[
            (
                "volfile",
                NiftiGz,
                {
                    "help_string": "Full path of file to save the output segmentation in. Default is mri/aparc+aseg.mgz",
                    "argstr": "--o",
                },
            ),
        ],
        bases=(ShellOutSpec,),
    )

    # ##############################
    # # mri_label2volume spec info #
    # ##############################

    mri_l2v_input_spec = SpecInfo(
        name="Input",
        fields=[
            (
                "seg",
                Path,
                {
                    "help_string": "segpath : segmentation",
                    "argstr": "--seg",
                    "mandatory": True,
                },
            ),
            (
                "temp",
                File,
                {
                    "help_string": "tempvolid : output template volume",
                    "argstr": "--temp",
                    "mandatory": True,
                },
            ),
            (
                "regheader",
                File,
                {
                    "help_string": "volid : label template volume (needed with --label or --annot)",
                    "argstr": "--regheader",
                    "mandatory": True,
                },
            ),
            (
                "output",
                str,
                {
                    "help_string": "volid : output volume",
                    "argstr": "--o",
                    "output_file_template": "label2vol1_out.nii.gz",
                },
            ),
        ],
        bases=(ShellSpec,),
    )

    mri_l2v_output_spec = SpecInfo(
        name="Output",
        fields=[
            (
                "output",
                File,
                {
                    "help_string": "volid : output volume",
                    "argstr": "--o",
                    "output_file_template": "label2vol_out1.nii.gz",
                },
            ),
        ],
        bases=(ShellOutSpec,),
    )

    # #############################
    # # fslreorient2std spec info #
    # #############################

    fslreorient2std_input_spec = SpecInfo(
        name="Input",
        fields=[
            (
                "input_image",
                File,
                {
                    "help_string": "input image",
                    "argstr": "{input_image}",
                    "position": 0,
                    "mandatory": True,
                },
            ),
            (
                "output_image",
                str,
                {
                    "help_string": "path to output image",
                    "argstr": "{output_image}",
                    "output_file_template": "out_file_reoriented1.nii.gz",
                    "position": 1,
                },
            ),
        ],
        bases=(ShellSpec,),
    )

    fslreorient2std_output_spec = SpecInfo(
        name="Output",
        fields=[
            (
                "output_image",
                NiftiGz,
                {
                    "help_string": "path to output image",
                    "argstr": "{output_image}",
                    "output_file_template": "out_file_reoriented1.nii.gz",
                    "position": 1,
                },
            ),
        ],
        bases=(ShellOutSpec,),
    )

    # ######################
    # # fslmaths spec info #
    # ######################

    fslthreshold_input_spec = SpecInfo(
        name="Input",
        fields=[
            (
                "input_image",
                str,
                {
                    "help_string": "input image",
                    "position": 0,
                    "argstr": "{input_image}",
                    "mandatory": True,
                },
            ),
            (
                "output_image",
                Path,
                {
                    "help_string": "path to output image",
                    "mandatory": True,
                    "argstr": " ",
                    "position": 3,
                },
            ),
            (
                "threshold",
                int,
                {
                    "help_string": "threshold value",
                    "position": 1,
                    "argstr": "-thr",
                },
            ),
        ],
        bases=(ShellSpec,),
    )

    fslthreshold_output_spec = SpecInfo(
        name="Output",
        fields=[
            (
                "output_image",
                NiftiGz,
                {
                    "help_string": "path to output image",
                    "mandatory": True,
                    "argstr": "{output_image}",
                    "output_file_template": "out_file_threshold.nii.gz",
                    "position": 3,
                },
            ),
        ],
        bases=(ShellOutSpec,),
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
        for hemi in hemispheres:
            wf.add(
                ShellCommandTask(
                    name=f"mri_s2s_task_{hemi}",
                    executable="mri_surf2surf",
                    input_spec=mri_s2s_input_spec,
                    output_spec=mri_s2s_output_spec,
                    cache_dir=cache_dir,
                    source_subject_id=wf.join_task.lzout.fsavg_dir,
                    target_subject_id=wf.FastSurfer_task.lzout.subjects_dir_output,
                    source_annotation_file=getattr(
                        wf.join_task.lzout, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(
                        wf.join_task.lzout, f"{hemi}_annotation"
                    ),
                    hemisphere=hemi,
                )
            )

        hemispheres = ["rh"]
        for hemi in hemispheres:
            wf.add(
                ShellCommandTask(
                    name=f"mri_s2s_task_{hemi}",
                    executable="mri_surf2surf",
                    input_spec=mri_s2s_input_spec,
                    output_spec=mri_s2s_output_spec,
                    cache_dir=cache_dir,
                    source_subject_id=wf.join_task.lzout.fsavg_dir,
                    target_subject_id=wf.FastSurfer_task.lzout.subjects_dir_output,
                    source_annotation_file=getattr(
                        wf.join_task.lzout, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(
                        wf.join_task.lzout, f"{hemi}_annotation"
                    ),
                    hemisphere=hemi,
                )
            )

        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        wf.add(
            ShellCommandTask(
                name="mri_a2a_task",
                executable="mri_aparc2aseg",
                input_spec=mri_a2a_input_spec,
                output_spec=mri_a2a_output_spec,
                cache_dir=cache_dir,
                subject=wf.FastSurfer_task.lzout.subjects_dir_output,
                new_ribbon=True,
                annotname=wf.join_task.lzout.annot_short,
            )
        )

        # ##########################
        # # mri_label2volume task  #
        # ##########################

        wf.add(
            ShellCommandTask(
                name="mri_l2v_task",
                executable="mri_label2vol",
                input_spec=mri_l2v_input_spec,
                output_spec=mri_l2v_output_spec,
                cache_dir=cache_dir,
                seg=wf.mri_a2a_task.lzout.volfile,
                temp=wf.join_task.lzout.l2v_temp,
                regheader=wf.join_task.lzout.l2v_regheader,
            )
        )

        # reorient to standard
        wf.add(
            ShellCommandTask(
                name="fslreorient2std_task",
                executable="fslreorient2std",
                input_spec=fslreorient2std_input_spec,
                output_spec=fslreorient2std_output_spec,
                input_image=wf.mri_l2v_task.lzout.output,  # wf.l2v_mgz2nii_task.lzout.out_file,
            )
        )

        # remove values less than 1000
        wf.add(
            ShellCommandTask(
                name="threshold_task",
                executable="fslmaths",
                input_spec=fslthreshold_input_spec,
                output_spec=fslthreshold_output_spec,
                input_image=wf.fslreorient2std_task.lzout.output_image,
                output_image="label2vol_out_std_threshold.nii.gz",  # wf.join_task.lzout.output_parcellation_filename,
                threshold=1000,
            )
        )

        # relabel segmenetation to ascending integers from 1 to N
        wf.add(
            LabelConvert(
                path_in=wf.threshold_task.lzout.output_image,
                lut_in=wf.join_task.lzout.parc_lut_file,
                lut_out=wf.join_task.lzout.mrtrix_lut_file,
                image_out=wf.join_task.lzout.final_parc_image,
                name="LabelConvert_task",
            )
        )

        return_image = wf.LabelConvert_task.lzout.image_out

    # else:
    #     return_image = wf.SGMfix_task.lzout.out_file

    ##########################################################
    # # additional mapping for 'hcpmmp1', 'yeo17', 'yeo7 #
    ##########################################################

    volfile = wf.join_task.lzout.output_parcellation_filename

    if parcellation in ["hcpmmp1", "Yeo17", "Yeo7"]:
        ##################################
        # mri_surf2surf task - lh and rh #
        ##################################
        hemispheres = ["lh"]
        for hemi in hemispheres:
            wf.add(
                ShellCommandTask(
                    name=f"mri_s2s_task_originals_{hemi}",
                    executable="mri_surf2surf",
                    input_spec=mri_s2s_input_spec,
                    output_spec=mri_s2s_output_spec,
                    cache_dir=cache_dir,
                    source_subject_id=wf.join_task.lzout.fsavg_dir,
                    target_subject_id=wf.FastSurfer_task.lzout.subjects_dir_output,  # wf.lzin.FS_dir,
                    source_annotation_file=getattr(
                        wf.join_task.lzout, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(
                        wf.join_task.lzout, f"{hemi}_annotation"
                    ),
                    hemisphere=hemi,
                )
            )

        hemispheres = ["rh"]
        for hemi in hemispheres:
            wf.add(
                ShellCommandTask(
                    name=f"mri_s2s_task_originals_{hemi}",
                    executable="mri_surf2surf",
                    input_spec=mri_s2s_input_spec,
                    output_spec=mri_s2s_output_spec,
                    cache_dir=cache_dir,
                    source_subject_id=wf.join_task.lzout.fsavg_dir,
                    target_subject_id=wf.FastSurfer_task.lzout.subjects_dir_output,  # wf.lzin.FS_dir,
                    source_annotation_file=getattr(
                        wf.join_task.lzout, f"source_annotation_file_{hemi}"
                    ),
                    target_annotation_file=getattr(
                        wf.join_task.lzout, f"{hemi}_annotation"
                    ),
                    hemisphere=hemi,
                )
            )

        # ########################
        # # mri_aparc2aseg task  #
        # ########################

        wf.add(
            ShellCommandTask(
                name="mri_a2a_task_originals",
                executable="mri_aparc2aseg",
                input_spec=mri_a2a_input_spec,
                output_spec=mri_a2a_output_spec,
                cache_dir=cache_dir,
                subject=wf.FastSurfer_task.lzout.subjects_dir_output,  # wf.lzin.FS_dir,
                old_ribbon=True,
            )
        )
        volfile = wf.mri_a2a_task_originals.lzout.volfile

    if parcellation in ["destrieux", "desikan", "hcpmmp1", "Yeo17", "Yeo7"]:
        # relabel segmenetation to integers
        wf.add(
            LabelConvert(
                path_in=volfile,
                lut_in=wf.join_task.lzout.parc_lut_file,
                lut_out=wf.join_task.lzout.mrtrix_lut_file,
                image_out="labelconvert.mif",  # wf.join_task.lzout.node_image,
                name="LabelConvert_task_originals",
            )
        )

        wf.add(
            LabelSgmfix(
                parc=wf.LabelConvert_task_originals.lzout.image_out,
                t1=wf.join_task.lzout.normimg_path,
                lut=wf.join_task.lzout.mrtrix_lut_file,
                out_file=wf.join_task.lzout.final_parc_image,
                name="SGMfix_task",
                nocleanup=True,
                premasked=True,
                sgm_amyg_hipp=True,
            )
        )

        return_image = wf.SGMfix_task.lzout.out_file

    wf.set_output(
        [
            (
                "parc_image",
                return_image,
            ),
            (
                "vis_image_fsl",
                wf.fTTvis_task_fsl.lzout.out_file,
            ),
            (
                "ftt_image_fsl",
                wf.fTTgen_task_fsl.lzout.out_file,
            ),
            (
                "vis_image_freesurfer",
                wf.fTTvis_task_freesurfer.lzout.out_file,
            ),
            (
                "ftt_image_freesurfer",
                wf.fTTgen_task_freesurfer.lzout.out_file,
            ),
            (
                "vis_image_hsvs",
                wf.fTTvis_task_hsvs.lzout.out_file,
            ),
            (
                "ftt_image_hsvs",
                wf.fTTgen_task_hsvs.lzout.out_file,
            ),
        ]
    )

    return wf


# # ########################
# # # Execute the workflow #
# # ########################
parcellation_list = [
    "aparca2009s",
    "aparc",
    "desikan",
    "destrieux",
    "economo",
    "glasser360",
    "hcpmmp1",
    "schaefer100",
    "schaefer1000",
    "schaefer200",
    "schaefer300",
    "schaefer400",
    "schaefer500",
    "schaefer600",
    "schaefer700",
    "schaefer800",
    "schaefer900",
    "vosdewael100",
    "vosdewael200",
    "vosdewael300",
    "vosdewael400",
    "Yeo17",
    "Yeo7",
]  # List of different parcellations


def all_parcs(
    freesurfer_home: Path,
    mrtrix_lut_dir: Path,
    cache_dir: Path,
    fs_license: Path,
    fastsurfer_executable: ty.Union[str, ty.List[str], None] = None,
    fastsurfer_python: str = "python3",
    name: str = "t1_preprocessing_pipeline_all",
) -> Workflow:

    # Define the input values using input_spec
    input_spec = {
        "t1w": File,
        "FS_dir": str,
    }

    wf = Workflow(
        name="t1_processing_pipeline",
        input_spec=input_spec,
        cache_dir=cache_dir,
    )

    def collate_parcs(out_dir: Path, **parcs: Mif) -> DirectoryOf[Mif]:  # type: ignore[type-arg]
        for name, parc in parcs.values():
            parc.copy(out_dir, new_stem=name)
        return DirectoryOf[Mif](out_dir)  # type: ignore[no-any-return,type-arg,misc]

    wf.add(
        FunctionTask(
            collate_parcs,
            name="collate_parcs",
            input_spec=SpecInfo(
                name="CollateParcsInputs",
                bases=(BaseSpec,),
                fields=[(p, Mif) for p in parcellation_list],
            ),
            output_spec=SpecInfo(
                name="CollateParcsOutputs",
                bases=(BaseSpec,),
                fields=[("out_dir", DirectoryOf[Mif])],  # type: ignore[misc]
            ),
        )
    )

    for parcellation in parcellation_list:

        wf.add(
            preprocess(
                t1w=wf.lzin.t1w,
                parcellation=parcellation,
                freesurfer_home=freesurfer_home,
                mrtrix_lut_dir=mrtrix_lut_dir,
                cache_dir=cache_dir,
                fs_license=fs_license,
                fastsurfer_executable=fastsurfer_executable,
                fastsurfer_python=fastsurfer_python,
                name=parcellation,
            )
        )

        setattr(
            wf.collate_parcs.inputs,
            parcellation,
            getattr(wf, parcellation).lzout.parc_image,
        )

    wf.set_output(("parcellations", wf.collate_parcs.lzout.out_dir))
    wf.set_output(("vis_image_fsl", wf.desikan.lzout.vis_image_fsl))
    wf.set_output(("ftt_image_fsl", wf.desikan.lzout.ftt_image_fsl))
    wf.set_output(("vis_image_freesurfer", wf.desikan.lzout.vis_image_freesurfer))
    wf.set_output(("ftt_image_freesurfer", wf.desikan.lzout.ftt_image_freesurfer))
    wf.set_output(("vis_image_hsvs", wf.desikan.lzout.vis_image_hsvs))
    wf.set_output(("ftt_image_hsvs", wf.desikan.lzout.ftt_image_hsvs))

    return wf


if __name__ == "__main__":
    import sys

    args = sys.argv[2:]

    wf = preprocess_all_parcs(*args)  # type: ignore[arg-type]
    wf(t1w=sys.argv[1])
