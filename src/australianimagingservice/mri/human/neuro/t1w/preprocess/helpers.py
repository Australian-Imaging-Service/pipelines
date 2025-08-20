import os
import typing as ty
from fileformats.generic import Directory
from pydra.compose import python


@python.define(
    outputs={
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
    }
)  # type: ignore[misc]
def JoinTaskCatalogue(
    parcellation: str,
    FS_dir: Directory,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
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
        lh_annotation = os.path.join(FS_dir, "label", f"lh.{parcellation}_mics.annot")
        rh_annotation = os.path.join(FS_dir, "label", f"rh.{parcellation}_mics.annot")
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
            freesurfer_home, "HCPMMP1", "lh.HCPMMP1.annot"
        )
        source_annotation_file_rh = os.path.join(
            freesurfer_home, "HCPMMP1", "rh.HCPMMP1.annot"
        )
        annot_short = "HCPMMP1"
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
            freesurfer_home,
            "Yeo2011",
            "lh.Yeo2011_7Networks_N1000.split_components.annot",
        )
        source_annotation_file_rh = os.path.join(
            freesurfer_home,
            "Yeo2011",
            "rh.Yeo2011_7Networks_N1000.split_components.annot",
        )
        annot_short = "Yeo7"
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
            freesurfer_home,
            "Yeo2011",
            "lh.Yeo2011_17Networks_N1000.split_components.annot",
        )
        source_annotation_file_rh = os.path.join(
            freesurfer_home,
            "Yeo2011",
            "rh.Yeo2011_17Networks_N1000.split_components.annot",
        )
        annot_short = "Yeo17"
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
