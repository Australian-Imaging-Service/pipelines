from pydra.compose import shell
from fileformats.generic import File, Directory
from fileformasts.medimage import NiftiGz

###########################
# mri_surf2surf spec info #
###########################


@shell.define
class MRISurf2Surf(shell.Task["MRISurf2Surf.Outputs"]):
    source_subject_id: str = shell.arg(
        help="source subject",
        argstr="--srcsubject",
    )
    target_subject_id: str = shell.arg(
        help="target subject",
        argstr="--trgsubject",
    )
    source_annotation_file: str = shell.arg(
        help="annotfile : map annotation",
        argstr="--sval-annot",
    )
    target_annotation_file: str = shell.arg(
        help="path of file in which to store output values",
        argstr="--tval",
    )
    hemisphere: str = shell.arg(
        help="hemisphere : (lh or rh) for both source and targ",
        argstr="--hemi",
    )

    class Outputs:
        target_annotation_file: File = shell.out(
            help="path of file in which to store output values",
            argstr="--tval",
            mandatory=True,
        )
        target_subject_id: Directory = shell.out(
            help="target subject",
            argstr="--trgsubject",
            mandatory=False,
        )

    # ############################
    # # mri_aparc2aseg spec info #
    # ############################


@shell.define
class MRIAparc2Aseg(shell.Task["MRIAparc2Aseg.Outputs"]):
    subject: Directory = shell.arg(
        help="Name of the subject as found in the SUBJECTS_DIR",
        argstr="--s",
        mandatory=True,
    )
    old_ribbon: bool = shell.arg(
        help="use mri/hemi.ribbon.mgz as a mask for the cortex",
        argstr="--old-ribbon",
        default=False,
    )
    new_ribbon: bool = shell.arg(
        help="Mask cortical voxels with mri/ribbon.mgz. Same as --volmask",
        argstr="--new-ribbon",
        default=False,
    )
    annotname: str = shell.arg(
        help="Use annotname surface annotation. By default, uses ?h.aparc.annot. With this option, it will load ?h.annotname.annot. The output file will be set to annotname+aseg.mgz, but this can be changed with --o. Note: running --annot aparc.a2009s is NOT the same as running --a2009s. The index numbers will be different.",
    )
    volfile: File = shell.arg(
        help="Full path of file to save the output segmentation in. Default is mri/aparc+aseg.mgz",
        argstr="--o",
        path_template="volfile.nii.gz",
        default="mri/aparc+aseg.mgz",
    )

    class Outputs:
        volfile: NiftiGz = shell.out(
            help="Full path of file to save the output segmentation in. Default is mri/aparc+aseg.mgz",
            argstr="--o",
            path_template="volfile.nii.gz",
            default="mri/aparc+aseg.mgz",
        )

    # ##############################
    # # mri_label2volume spec info #
    # ##############################


@shell.define
class MRILabel2Volume(shell.Task["MRILabel2Volume.Outputs"]):
    seg: File = shell.arg(
        help="segpath : segmentation",
        argstr="--seg",
        mandatory=True,
    )
    temp: File = shell.arg(
        help="tempvolid : output template volume",
        argstr="--temp",
        mandatory=True,
    )
    regheader: File = shell.arg(
        help="volid : label template volume (needed with --label or --annot)",
        argstr="--regheader",
        mandatory=True,
    )
    output: str = shell.arg(
        help="volid : output volume",
        argstr="--o",
        path_template="label2vol_out1.nii.gz",
    )

    class Outputs:
        output: NiftiGz = shell.out(
            help="volid : output volume",
            argstr="--o",
            path_template="label2vol_out1.nii.gz",
        )


# ##############################
# # mri_label2vol spec info #
# ##############################
