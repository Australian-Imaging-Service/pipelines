from pathlib import Path
from fileformats.generic import File, Directory, DirectoryOf
from fileformats.medimage import NiftiGz
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.compose import workflow, python
from .single_parc import SingleParcellation

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


def collate_parcellations(out_dir: Path | None = None, **parcs: "Mif") -> "DirectoryOf[Mif]":  # type: ignore[type-arg]
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
    cache_dir: Path,
    fs_license: File,
    fastsurfer_executable: str | list[str] | None = None,
    fastsurfer_python: str = "python3",
) -> tuple[
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
]:

    collate_parcs = workflow.add(
        python.define(
            collate_parcellations,
            inputs={p: Mif for p in parcellation_list},
            outputs={"out_dir": DirectoryOf[Mif]},
        )
    )

    parcs = {}

    for parcellation in parcellation_list:

        parcs[parcellation] = workflow.add(
            SingleParcellation(
                t1w=t1w,
                parcellation=parcellation,
                freesurfer_home=freesurfer_home,
                mrtrix_lut_dir=mrtrix_lut_dir,
                cache_dir=cache_dir,
                fs_license=fs_license,
                fastsurfer_executable=fastsurfer_executable,
                fastsurfer_python=fastsurfer_python,
                subjects_dir=subjects_dir,
            ),  # pyright: ignore[reportArgumentType]
            name=parcellation,
        )

        setattr(
            collate_parcs,
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

    args = sys.argv[2:]

    wf = AllParcellations(*args)  # type: ignore[arg-type]
    wf(t1w=sys.argv[1])  # pyright: ignore[reportCallIssue]

# if __name__ == "__main__":
#     import sys

#     # Expecting the first argument to be the T1-weighted image path
#     t1w_path = sys.argv[1]

#     # Provide sensible default values or pass from command-line arguments
#     # freesurfer_home = "/Applications/freesurfer/"  # Adjust this path as per your setup
#     # mrtrix_lut_dir = "/Users/arkievdsouza/mrtrix3/share/mrtrix3/labelconvert/"  # Adjust this path as per your setup
#     # cache_dir = "/Users/arkievdsouza/git/t1-pipeline/working-dir/"  # Temporary directory for cache
#     # fs_license = (
#     #     "/Applications/freesurfer/license.txt "  # Path to the FreeSurfer license file
#     # )

#     # Pass the arguments explicitly
#     wf = all_parcs(*sys.argv[1])
#     #     freesurfer_home=freesurfer_home,
#     #     mrtrix_lut_dir=mrtrix_lut_dir,
#     #     cache_dir=cache_dir,
#     #     fs_license=fs_license,
#     # )  # type: ignore[arg-type]

#     # # Run the workflow with the T1-weighted image as input
#     wf(t1w=t1w_path)
