from pathlib import Path
from fileformats.generic import File, Directory, DirectoryOf
from fileformats.medimage import NiftiGz
from fileformats.medimage_mrtrix3.image import ImageFormat as Mif, ImageFormatGz
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

collate_inputs = {p: Mif | ImageFormatGz for p in parcellation_list}
collate_inputs["out_dir"] = Path | None


@python.define(
    inputs=collate_inputs,
    outputs=["out_dir"],
)
def CollateParcellations(out_dir: Path | None = None, **parcs: "Mif | ImageFormatGz") -> "Directory":  # type: ignore[type-arg]
    """Collate multiple parcellations into a single directory."""
    if out_dir is None:
        out_dir = Path("./out_dir").absolute()
    out_dir.mkdir(exist_ok=True)
    for name, parc in parcs.items():
        parc.copy(out_dir, new_stem=name)
    return Directory(out_dir)  # type: ignore[no-any-return,misc]


@workflow.define(
    outputs=[
        "parcellations",
        "vis_image_fsl",
        "ftt_image_fsl",
        "vis_image_freesurfer",
        "ftt_image_freesurfer",
        "vis_image_hsvs",
        "ftt_image_hsvs",
        "fastsurfer_output",
    ]
)
def AllParcellations(
    t1w: NiftiGz,
    subjects_dir: Path,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
    fs_license: File,
    resources_dir: Path,
    in_fastsurfer_container: bool = False,
    fastsurfer_python: str = "python3",
    fastsurfer_batch: int = 16,
    labelsgmfirst_executable: str = "labelsgmfix",
    fastsurfer_nthreads: int = 24,
) -> tuple[
    Directory,
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
    Mif,
    Directory,
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
                resources_dir=resources_dir,
                in_fastsurfer_container=in_fastsurfer_container,
                fastsurfer_python=fastsurfer_python,
                fastsurfer_batch=fastsurfer_batch,
                fastsurfer_nthreads=fastsurfer_nthreads,
                subjects_dir=subjects_dir,
                labelsgmfirst_executable=labelsgmfirst_executable,
            ),  # pyright: ignore[reportArgumentType]
            name=parcellation,
        )

        setattr(
            collate_parcs.inputs,
            parcellation,
            parcs[parcellation].parc_image,
        )

    # Most of the outputs will be the same for each parcellation so we just
    # pick the first one
    return (
        collate_parcs.out_dir,
        parcs["desikan"].vis_image_fsl,
        parcs["desikan"].ftt_image_fsl,
        parcs["desikan"].vis_image_freesurfer,
        parcs["desikan"].ftt_image_freesurfer,
        parcs["desikan"].vis_image_hsvs,
        parcs["desikan"].ftt_image_hsvs,
        parcs["desikan"].fastsurfer_output,
    )


if __name__ == "__main__":
    import sys
    import os

    # Helper: get arg or fallback to env var or default
    def get_arg(idx: int, env: str | None = None, default: str | None = None) -> str:
        if len(sys.argv) > idx and sys.argv[idx]:
            return sys.argv[idx]
        if env and os.environ.get(env):
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
    # Derive resources_dir relative to this file (dev install) or from env var
    _default_resources = str(Path(__file__).parents[7] / "resources")
    resources_dir = Path(get_arg(9, "RESOURCES_DIR", _default_resources))

    try:
        n_threads = len(os.sched_getaffinity(0))  # respects cgroup/affinity limits
    except AttributeError:
        n_threads = os.cpu_count() or 1
    os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = str(n_threads)
    print(f"Detected {n_threads} usable CPU threads — ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS set to {n_threads}")

    wf = AllParcellations(
        t1w=t1w,
        subjects_dir=subjects_dir,
        freesurfer_home=freesurfer_home,
        mrtrix_lut_dir=mrtrix_lut_dir,
        fs_license=fs_license,
        resources_dir=resources_dir,
        fastsurfer_python=fastsurfer_python,
    )

    result = wf(cache_root=cache_dir, rerun=False)
    print("Workflow finished. Outputs:")
    print(result)
