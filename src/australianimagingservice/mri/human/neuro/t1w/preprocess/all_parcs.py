from pathlib import Path
from fileformats.generic import File, Directory, DirectoryOf
from fileformats.medimage import NiftiGz
from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from pydra.compose import workflow, python
from australianimagingservice.mri.human.neuro.t1w.preprocess.single_parc import (
    SingleParcellation,
)

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

collate_inputs = {p: Mif for p in parcellation_list}
collate_inputs["out_dir"] = Path | None


@python.define(
    inputs=collate_inputs,
    outputs=["out_dir"],
)
def CollateParcellations(out_dir: Path | None = None, **parcs: "Mif") -> "DirectoryOf[Mif]":  # type: ignore[type-arg]
    """Collate multiple parcellations into a single directory."""
    if out_dir is None:
        out_dir = Path("./out_dir").absolute()
    out_dir.mkdir(exist_ok=True)
    for name, parc in parcs.items():
        parc.copy(out_dir, new_stem=name)
    return DirectoryOf[Mif](out_dir)  # type: ignore[no-any-return,type-arg,misc]


@workflow.define(
    outputs=[
        "parcellations",
        "vis_image_fsl",
        "ftt_image_fsl",
        "vis_image_freesurfer",
        "ftt_image_freesurfer",
        "vis_image_hsvs",
        "ftt_image_hsvs",
    ]
)
def AllParcellations(
    t1w: NiftiGz,
    subjects_dir: Path,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
    fs_license: File,
    in_fastsurfer_container: bool = False,
    fastsurfer_python: str = "python3",
) -> tuple[
    DirectoryOf[Mif],
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
]:

    collate_parcs = workflow.add(CollateParcellations(out_dir=None))

    parcs = {}

    for parcellation in parcellation_list:

        parcs[parcellation] = workflow.add(
            SingleParcellation(
                t1w=t1w,
                parcellation=parcellation,
                freesurfer_home=freesurfer_home,
                mrtrix_lut_dir=mrtrix_lut_dir,
                fs_license=fs_license,
                in_fastsurfer_container=in_fastsurfer_container,
                fastsurfer_python=fastsurfer_python,
                subjects_dir=subjects_dir,
            ),  # pyright: ignore[reportArgumentType]
            name=parcellation,
        )

        setattr(
            collate_parcs.inputs,
            parcellation,
            parcs[parcellation].parc_image,
        )

    return (
        collate_parcs.out_dir,
        parcs["desikan"].vis_image_fsl,
        parcs["desikan"].ftt_image_fsl,
        parcs["desikan"].vis_image_freesurfer,
        parcs["desikan"].ftt_image_freesurfer,
        parcs["desikan"].vis_image_hsvs,
        parcs["desikan"].ftt_image_hsvs,
    )


if __name__ == "__main__":
    import sys
    import os

    # Helper: get arg or fallback to env var or default
    def get_arg(idx: int, env: str | None = None, default: str | None = None) -> str:
        if len(sys.argv) > idx:
            return sys.argv[idx]
        if env and env in os.environ:
            return os.environ[env]
        if default is not None:
            return default
        print(f"Missing required argument {idx} (env {env})")
        sys.exit(1)

    if len(sys.argv) < 2:
        print(
            "Usage: python all_parcs.py <t1w.nii.gz> "
            "[subjects_dir] [freesurfer_home] [mrtrix_lut_dir] "
            "[cache_dir] [fs_license] [fastsurfer_executable] [fastsurfer_python]"
        )
        sys.exit(1)

    t1w = Path(sys.argv[1])
    subjects_dir = Path(get_arg(2, "SUBJECTS_DIR"))
    freesurfer_home = Path(get_arg(3, "FREESURFER_HOME"))
    mrtrix_lut_dir = Path(
        get_arg(4, "MRTRIX_LUT_DIR", "/usr/local/mrtrix3/share/mrtrix3/labelconvert")
    )
    cache_dir = Path(
        get_arg(5, None, "/Users/adso8337/Documents/PydraProcessingDirectory/")
    )
    fs_license = Path(get_arg(6, "FS_LICENSE", str(freesurfer_home / "license.txt")))
    fastsurfer_executable = get_arg(7, "FASTSURFER_EXECUTABLE", "fastsurfer")
    fastsurfer_python = get_arg(8, None, "python3")

    wf = AllParcellations(
        t1w=t1w,
        subjects_dir=subjects_dir,
        freesurfer_home=freesurfer_home,
        mrtrix_lut_dir=mrtrix_lut_dir,
        fs_license=fs_license,
        fastsurfer_executable=None,
        fastsurfer_python=fastsurfer_python,
    )

    result = wf(cache_root=cache_dir)
    print("Workflow finished. Outputs:")
    print(result)
