import shutil
import subprocess
from pathlib import Path
from fileformats.generic import File, Directory
from fileformats.medimage import NiftiGz
from fileformats.vendor.mrtrix3.medimage.image import ImageFormat as Mif, ImageFormatGz
from pydra.compose import workflow, python
from australianimagingservice.mri.human.neuro.t1w.preprocess.single_parc import (
    SingleParcellation,
)

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
]

# ---------------------------------- #
#  FinalizeOutputs input type map    #
# ---------------------------------- #
_finalize_inputs: dict = {p: Mif | ImageFormatGz for p in parcellation_list}
_finalize_inputs.update(
    {
        "out_dir": Path | None,
        "ftt_fsl": Mif | None,
        "vis_fsl": Mif | None,
        "ftt_freesurfer": Mif | None,
        "vis_freesurfer": Mif | None,
        "ftt_hsvs": Mif | None,
        "vis_hsvs": Mif | None,
        "fastsurfer_dir": Directory | None,
        "resources_dir": Path,
        "mrtrix_lut_dir": Directory | None,
    }
)


def _lut_src(
    parcellation: str, resources_dir: Path, mrtrix_lut_dir: Path
) -> Path | None:
    """Return the MRtrix3 LUT file path for a given parcellation."""
    neuro = resources_dir / "neuro-parcellations"
    if (
        "schaefer" in parcellation
        or "aparc" in parcellation
        or "vosdewael" in parcellation
        or parcellation in ("economo", "glasser360")
    ):
        return neuro / f"{parcellation}_reordered_LUT.txt"
    elif parcellation == "desikan":
        return mrtrix_lut_dir / "fs_default.txt"
    elif parcellation == "destrieux":
        return mrtrix_lut_dir / "fs_a2009s.txt"
    elif parcellation == "hcpmmp1":
        return neuro / "hcpmmp1_ordered.txt"
    elif parcellation == "Yeo7":
        return neuro / "Yeo2011_7N_split.txt"
    elif parcellation == "Yeo17":
        return neuro / "Yeo2011_17N_split.txt"
    return None


@python.define(inputs=_finalize_inputs, outputs=["out_dir"])
def FinalizeOutputs(
    out_dir: Path | None = None,
    ftt_fsl: "Mif | None" = None,
    vis_fsl: "Mif | None" = None,
    ftt_freesurfer: "Mif | None" = None,
    vis_freesurfer: "Mif | None" = None,
    ftt_hsvs: "Mif | None" = None,
    vis_hsvs: "Mif | None" = None,
    fastsurfer_dir: "Directory | None" = None,
    resources_dir: Path = Path("."),
    mrtrix_lut_dir: "Directory | None" = None,
    **parcs: "Mif | ImageFormatGz",
) -> "Directory":
    """Collect all pipeline outputs into a structured output directory."""
    if out_dir is None:
        out_dir = Path("./final_outputs").absolute()
    out_dir = Path(out_dir)

    atlases_dir = out_dir / "Atlases"
    ftt_dir = out_dir / "5TTimages"
    lut_dir = out_dir / "LUT"
    fs_dest = out_dir / "FS_outputs"

    for d in (atlases_dir, ftt_dir, lut_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Parcellations → Atlases/Atlas_{name}.mif.gz
    for name, parc in parcs.items():
        dest = atlases_dir / f"Atlas_{name}.mif.gz"
        subprocess.run(
            ["mrconvert", str(parc), str(dest), "-quiet", "-force"],
            check=True,
        )

    # 5TT and visualisation images → 5TTimages/
    ftt_images = {
        "5TT_fsl": ftt_fsl,
        "5TTvis_fsl": vis_fsl,
        "5TT_freesurfer": ftt_freesurfer,
        "5TTvis_freesurfer": vis_freesurfer,
        "5TT_hsvs": ftt_hsvs,
        "5TTvis_hsvs": vis_hsvs,
    }
    for name, img in ftt_images.items():
        if img is not None:
            dest = ftt_dir / f"{name}.mif.gz"
            subprocess.run(
                ["mrconvert", str(img), str(dest), "-quiet", "-force"],
                check=True,
            )

    # LUT files → LUT/{parcellation}_LUT.txt
    resources_path = Path(str(resources_dir))
    mrtrix_lut_path = (
        Path(str(mrtrix_lut_dir))
        if mrtrix_lut_dir is not None
        else Path("/usr/local/mrtrix3/share/mrtrix3/labelconvert")
    )
    for name in parcs:
        src = _lut_src(name, resources_path, mrtrix_lut_path)
        if src is not None and src.exists():
            shutil.copy(src, lut_dir / f"{name}_LUT.txt")

    # FreeSurfer outputs → FS_outputs/
    if fastsurfer_dir is not None:
        if fs_dest.exists():
            shutil.rmtree(fs_dest)
        shutil.copytree(str(fastsurfer_dir), str(fs_dest))

    return Directory(out_dir)


@workflow.define(outputs=["out_dir"])
def AllParcellations(
    t1w: NiftiGz,
    subjects_dir: Path,
    freesurfer_home: Directory,
    mrtrix_lut_dir: Directory,
    fs_license: File,
    resources_dir: Path,
    output_dir: Path | None = None,
    in_fastsurfer_container: bool = False,
    fastsurfer_python: str = "python3",
    fastsurfer_batch: int = 16,
    labelsgmfirst_executable: str = "labelsgmfix",
    fastsurfer_nthreads: int = 24,
) -> Directory:

    finalize = workflow.add(
        FinalizeOutputs(
            out_dir=output_dir,
            resources_dir=resources_dir,
            mrtrix_lut_dir=mrtrix_lut_dir,
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
        setattr(finalize.inputs, parcellation, parcs[parcellation].parc_image)

    # Wire 5TT and FreeSurfer outputs into finalize (all parcellations share the same
    # FastSurfer run, so any parcellation's outputs would give the same values here)
    finalize.inputs.ftt_fsl = parcs["desikan"].ftt_image_fsl
    finalize.inputs.vis_fsl = parcs["desikan"].vis_image_fsl
    finalize.inputs.ftt_freesurfer = parcs["desikan"].ftt_image_freesurfer
    finalize.inputs.vis_freesurfer = parcs["desikan"].vis_image_freesurfer
    finalize.inputs.ftt_hsvs = parcs["desikan"].ftt_image_hsvs
    finalize.inputs.vis_hsvs = parcs["desikan"].vis_image_hsvs
    finalize.inputs.fastsurfer_dir = parcs["desikan"].fastsurfer_output

    return finalize.out_dir


if __name__ == "__main__":
    import glob
    import sys
    import os

    # Separate flags (--flag) from positional arguments
    _flags = {a for a in sys.argv[1:] if a.startswith("-")}
    _pos = [sys.argv[0]] + [a for a in sys.argv[1:] if not a.startswith("-")]
    no_cleanup = "--no_cleanup" in _flags or "-no_cleanup" in _flags

    def get_arg(idx: int, env: str | None = None, default: str | None = None) -> str:
        if len(_pos) > idx and _pos[idx]:
            return _pos[idx]
        if env and os.environ.get(env):
            return os.environ[env]
        if default is not None:
            return default
        print(f"Missing required argument {idx} (env {env})")
        sys.exit(1)

    if len(_pos) < 2:
        print(
            "Usage: python all_parcs.py <t1w.nii.gz> "
            "[subjects_dir] [freesurfer_home] [mrtrix_lut_dir] "
            "[cache_dir] [fs_license] [fastsurfer_python] "
            "[resources_dir] [output_dir] [--no_cleanup]"
        )
        sys.exit(1)

    t1w = Path(_pos[1])
    subjects_dir = Path(get_arg(2, "SUBJECTS_DIR"))
    freesurfer_home = Path(get_arg(3, "FREESURFER_HOME"))
    mrtrix_lut_dir = Path(
        get_arg(4, "MRTRIX_LUT_DIR", "/usr/local/mrtrix3/share/mrtrix3/labelconvert")
    )
    cache_dir = Path(
        get_arg(5, None, "/Users/adso8337/Documents/PydraProcessingDirectory/")
    )
    fs_license = Path(get_arg(6, "FS_LICENSE", str(freesurfer_home / "license.txt")))
    fastsurfer_python = get_arg(7, None, "python3")
    _default_resources = str(Path(__file__).parents[7] / "resources")
    resources_dir = Path(get_arg(8, "RESOURCES_DIR", _default_resources))
    output_dir = Path(get_arg(9, "OUTPUT_DIR", str(cache_dir / "final_outputs")))

    try:
        n_threads = len(os.sched_getaffinity(0))
    except AttributeError:
        n_threads = os.cpu_count() or 1
    os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = str(n_threads)
    print(
        f"Detected {n_threads} usable CPU threads — "
        f"ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS set to {n_threads}"
    )

    wf = AllParcellations(
        t1w=t1w,
        subjects_dir=subjects_dir,
        freesurfer_home=freesurfer_home,
        mrtrix_lut_dir=mrtrix_lut_dir,
        fs_license=fs_license,
        resources_dir=resources_dir,
        fastsurfer_python=fastsurfer_python,
        output_dir=output_dir,
    )

    result = wf(cache_root=cache_dir, rerun=False)
    final_dir = Path(str(result.out_dir))
    print(f"Workflow finished. Final outputs at: {final_dir}")

    if not no_cleanup:
        print("Cleaning up intermediate pydra cache directories...")
        for pattern in ["shell-*", "python-*", "workflow-*"]:
            for d in glob.glob(str(cache_dir / pattern)):
                d_path = Path(d)
                # Never delete the final output directory or anything inside it
                if not (d_path == final_dir or final_dir.is_relative_to(d_path)):
                    shutil.rmtree(d_path, ignore_errors=True)
        # Remove subjects_dir if it lives inside cache_dir (FS outputs already copied)
        subjects_path = Path(subjects_dir)
        if subjects_path.is_relative_to(cache_dir):
            shutil.rmtree(subjects_path, ignore_errors=True)
        print("Cleanup complete.")
    else:
        print("Skipping cleanup (--no_cleanup flag set).")
