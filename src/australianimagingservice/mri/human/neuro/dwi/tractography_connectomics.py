from pathlib import Path

from pydra.compose import python, shell, workflow
from fileformats.generic import File, Directory
from fileformats.medimage import MghGz
from pydra.tasks.mrtrix3.v3_1 import (
    MrTransform,
    MrConvert,
    DwiExtract,
    MrMath,
    TckSift2,
    Tck2Connectome,
    TckMap,
)
from fileformats.vendor.mrtrix3.medimage import (  # noqa: F401
    ImageFormatGz,
    ImageIn,
    ImageOut,
    Tracks,
)

from australianimagingservice.mri.human.neuro.dwi.dwi_preprocessing import MrcalcMax

# ── Custom shell task wrappers ─────────────────────────────────────────────────
#
# pydra-tasks-mrtrix3 3.1.0a9's auto-generated TckGen, Dwi2Fod, MtNormalise and
# TransformConvert interfaces can't express this pipeline's calls: TckGen
# declares its output `tracks` as an input (so there's no `tracks` output to
# wire downstream), Dwi2Fod/MtNormalise collapse their interleaved
# input/output pairs into one list with a single output template (so three
# tissue outputs can't be produced), and TransformConvert takes its three
# flirt_import inputs as one list. pydra-tasks-fsl's EpiReg types its `.mat`
# transform output as NIfTI, which fails output validation. These thin
# wrappers expose only the arguments used here.
#
# FLAG: these are interface bugs that other users of those packages will hit
# too, so they should be fixed upstream (pending discussion with tclose) and
# these wrappers replaced with the upstream tasks once they are.


@shell.define
class TckGenAct(shell.Task):
    """Anatomically-constrained probabilistic tractography (tckgen)."""

    executable = "tckgen"

    source: ImageIn = shell.arg(
        help="FOD image to track on", argstr="{source}", position=1
    )
    act: ImageIn = shell.arg(help="5TT image for ACT", argstr="-act {act}")
    seed_dynamic: ImageIn = shell.arg(
        help="FOD image for dynamic seeding", argstr="-seed_dynamic {seed_dynamic}"
    )
    algorithm: str = shell.arg(
        help="tracking algorithm", argstr="-algorithm {algorithm}", default="ifod2"
    )
    select: int = shell.arg(
        help="number of streamlines to select", argstr="-select {select}"
    )
    seeds: int = shell.arg(
        help="number of seeds to attempt (0 = unlimited)",
        argstr="-seeds {seeds}",
        default=0,
    )
    minlength: float = shell.arg(
        help="minimum streamline length (mm)", argstr="-minlength {minlength}"
    )
    maxlength: float = shell.arg(
        help="maximum streamline length (mm)", argstr="-maxlength {maxlength}"
    )
    cutoff: float = shell.arg(
        help="FOD amplitude cutoff for termination", argstr="-cutoff {cutoff}"
    )
    backtrack: bool = shell.arg(
        help="allow tracks to be truncated and re-tracked",
        argstr="-backtrack",
        default=False,
    )
    crop_at_gmwmi: bool = shell.arg(
        help="crop streamline endpoints at the GM-WM interface",
        argstr="-crop_at_gmwmi",
        default=False,
    )

    class Outputs(shell.Outputs):
        tracks: Tracks = shell.outarg(
            help="output tracks file",
            argstr="{tracks}",
            path_template="tracks.tck",
            position=2,
        )


@shell.define
class Dwi2FodMsmt(shell.Task):
    """Multi-shell multi-tissue CSD (dwi2fod msmt_csd) for WM/GM/CSF."""

    executable = "dwi2fod"

    algorithm: str = shell.arg(
        help="FOD algorithm", argstr="{algorithm}", position=1, default="msmt_csd"
    )
    dwi: ImageIn = shell.arg(help="input DWI image", argstr="{dwi}", position=2)
    response_wm: File = shell.arg(
        help="WM response function", argstr="{response_wm}", position=3
    )
    response_gm: File = shell.arg(
        help="GM response function", argstr="{response_gm}", position=5
    )
    response_csf: File = shell.arg(
        help="CSF response function", argstr="{response_csf}", position=7
    )
    mask: ImageIn = shell.arg(help="brain mask", argstr="-mask {mask}")

    class Outputs(shell.Outputs):
        wm_fod: ImageOut = shell.outarg(
            help="output WM FOD image",
            argstr="{wm_fod}",
            path_template="wm_fod.mif.gz",
            position=4,
        )
        gm_fod: ImageOut = shell.outarg(
            help="output GM FOD image",
            argstr="{gm_fod}",
            path_template="gm_fod.mif.gz",
            position=6,
        )
        csf_fod: ImageOut = shell.outarg(
            help="output CSF FOD image",
            argstr="{csf_fod}",
            path_template="csf_fod.mif.gz",
            position=8,
        )


@shell.define
class Ss3tCsdBeta1(shell.Task):
    """Single-shell 3-tissue CSD from the MRtrix3Tissue fork. Note that
    ss3t_csd_beta1 is not part of MRtrix3 itself, so it is not available in
    the image built from specs/.../dwi/tractography.yaml."""

    executable = "ss3t_csd_beta1"

    in_dwi: ImageIn = shell.arg(
        help="input DWI image",
        argstr="{in_dwi}",
        position=1,
    )
    response_wm: File = shell.arg(
        help="WM response function text file",
        argstr="{response_wm}",
        position=2,
    )
    response_gm: File = shell.arg(
        help="GM response function text file",
        argstr="{response_gm}",
        position=4,
    )
    response_csf: File = shell.arg(
        help="CSF response function text file",
        argstr="{response_csf}",
        position=6,
    )
    mask: ImageIn | None = shell.arg(
        help="brain mask",
        argstr="-mask {mask}",
        default=None,
    )

    class Outputs(shell.Outputs):
        wm_odf: ImageOut = shell.outarg(
            help="output WM FOD image",
            argstr="{wm_odf}",
            path_template="wm_fod.mif.gz",
            position=3,
        )
        gm_odf: ImageOut = shell.outarg(
            help="output GM FOD image",
            argstr="{gm_odf}",
            path_template="gm_fod.mif.gz",
            position=5,
        )
        csf_odf: ImageOut = shell.outarg(
            help="output CSF FOD image",
            argstr="{csf_odf}",
            path_template="csf_fod.mif.gz",
            position=7,
        )


@shell.define
class MtNormalise3Tissue(shell.Task):
    """Multi-tissue FOD intensity normalisation (mtnormalise) for WM/GM/CSF."""

    executable = "mtnormalise"

    fod_wm: ImageIn = shell.arg(help="input WM FOD", argstr="{fod_wm}", position=1)
    fod_gm: ImageIn = shell.arg(help="input GM FOD", argstr="{fod_gm}", position=3)
    fod_csf: ImageIn = shell.arg(
        help="input CSF FOD", argstr="{fod_csf}", position=5
    )
    mask: ImageIn = shell.arg(help="brain mask", argstr="-mask {mask}")

    class Outputs(shell.Outputs):
        fod_wm_norm: ImageOut = shell.outarg(
            help="normalised WM FOD",
            argstr="{fod_wm_norm}",
            path_template="wmfod_norm.mif.gz",
            position=2,
        )
        fod_gm_norm: ImageOut = shell.outarg(
            help="normalised GM FOD",
            argstr="{fod_gm_norm}",
            path_template="gmfod_norm.mif.gz",
            position=4,
        )
        fod_csf_norm: ImageOut = shell.outarg(
            help="normalised CSF FOD",
            argstr="{fod_csf_norm}",
            path_template="csffod_norm.mif.gz",
            position=6,
        )


@shell.define
class TransformConvertFlirt(shell.Task):
    """Convert a FLIRT matrix to MRtrix3 format (transformconvert flirt_import)."""

    executable = "transformconvert"

    input_matrix: File = shell.arg(
        help="FLIRT transformation matrix", argstr="{input_matrix}", position=1
    )
    flirt_in: ImageIn = shell.arg(
        help="the image FLIRT registered (moving)", argstr="{flirt_in}", position=2
    )
    flirt_ref: ImageIn = shell.arg(
        help="the FLIRT reference image", argstr="{flirt_ref}", position=3
    )
    operation: str = shell.arg(
        help="conversion operation",
        argstr="{operation}",
        position=4,
        default="flirt_import",
    )

    class Outputs(shell.Outputs):
        out_file: File = shell.outarg(
            help="output MRtrix3 transform",
            argstr="{out_file}",
            path_template="epi2struct_mrtrix.txt",
            position=5,
        )


def _epi2str_mat(cache_dir, out_base) -> Path:
    return Path(cache_dir) / f"{out_base}.mat"


@shell.define
class EpiRegMat(shell.Task):
    """Boundary-based EPI-to-T1 registration (FSL epi_reg) with an explicit
    white-matter segmentation, exposing only the rigid transform output."""

    executable = "epi_reg"

    epi: ImageIn = shell.arg(help="EPI image (mean b0)", argstr="--epi={epi}")
    t1_head: ImageIn = shell.arg(help="whole-head T1", argstr="--t1={t1_head}")
    t1_brain: ImageIn = shell.arg(
        help="brain-extracted T1", argstr="--t1brain={t1_brain}"
    )
    wmseg: ImageIn = shell.arg(
        help="binary white matter segmentation", argstr="--wmseg={wmseg}"
    )
    out_base: str = shell.arg(
        help="output basename", argstr="--out={out_base}", default="epi2struct"
    )

    class Outputs(shell.Outputs):
        epi2str_mat: File = shell.out(
            help="rigid EPI-to-structural FLIRT matrix", callable=_epi2str_mat
        )


# ── Python task definitions ────────────────────────────────────────────────────


@python.define(
    outputs=[
        "dwi_preprocessed",
        "dwimask_preprocessed",
        "response_wm",
        "response_gm",
        "response_csf",
        "ftt_image",
        "fttvis_image",
        "t1brain_mgz",
        "norm_mgz",
        "wmseg_mgz",
        "parcellations",
        "parcellation_stems",
    ]
)
def ResolveTractographyInputs(
    dwi_preproc_dir: Directory,
    t1_preproc_dir: Directory,
    ftt_method: str = "hsvs",
) -> tuple[
    ImageFormatGz,
    ImageFormatGz,
    File,
    File,
    File,
    ImageFormatGz,
    ImageFormatGz,
    MghGz,
    MghGz,
    MghGz,
    list[ImageFormatGz],
    list[str],
]:
    """Locate tractography inputs within the bundled output directories of the
    DWI preprocessing (dwi_preprocess) and T1w preprocessing (t1w_preprocess)
    pipelines. Files are found by name anywhere below each directory, so it
    doesn't matter whether the sourced resource keeps the bundle's top-level
    folder or not.

    Expected (relative) layouts::

        dwi_preprocess/
            DWI/dwi_preprocessed.mif.gz
            DWI/dwimask_preprocessed.mif.gz
            Response/response_{wm,gm,csf}.txt

        t1w_preprocess/
            5TTimages/5TT_<ftt_method>.mif.gz
            5TTimages/5TTvis_<ftt_method>.mif.gz
            Atlases/Atlas_<name>.mif.gz      (one per parcellation)
            FS_outputs/.../mri/{brainmask,norm,wm.seg}.mgz
    """
    from pathlib import Path
    from fileformats.generic import File
    from fileformats.medimage import MghGz
    from fileformats.vendor.mrtrix3.medimage import ImageFormatGz

    def find_one(root: Path, *names: str) -> Path:
        for name in names:
            matches = sorted(p for p in root.rglob(name) if p.is_file())
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    f"Found multiple '{name}' files in {root}: "
                    + ", ".join(str(m) for m in matches)
                )
        raise FileNotFoundError(
            f"None of {list(names)} found anywhere in {root}. Contents:\n  "
            + "\n  ".join(str(p.relative_to(root)) for p in sorted(root.rglob("*")))
        )

    ftt_key = ftt_method.lower()
    if ftt_key not in ("hsvs", "fsl", "freesurfer"):
        raise ValueError(
            f"Unknown ftt_method {ftt_method!r}. Choose from: hsvs, fsl, freesurfer."
        )

    dwi_root = Path(dwi_preproc_dir)
    t1_root = Path(t1_preproc_dir)

    parcellation_paths = sorted(
        p for p in t1_root.rglob("Atlas_*.mif.gz") if p.parent.name == "Atlases"
    )
    if not parcellation_paths:
        raise FileNotFoundError(f"No Atlases/Atlas_*.mif.gz images found in {t1_root}")
    parcellation_stems = [p.name[: -len(".mif.gz")] for p in parcellation_paths]

    return (
        ImageFormatGz(find_one(dwi_root, "dwi_preprocessed.mif.gz")),
        ImageFormatGz(find_one(dwi_root, "dwimask_preprocessed.mif.gz")),
        File(find_one(dwi_root, "response_wm.txt")),
        File(find_one(dwi_root, "response_gm.txt")),
        File(find_one(dwi_root, "response_csf.txt")),
        ImageFormatGz(find_one(t1_root, f"5TT_{ftt_key}.mif.gz")),
        ImageFormatGz(find_one(t1_root, f"5TTvis_{ftt_key}.mif.gz")),
        MghGz(find_one(t1_root, "brainmask.mgz")),
        MghGz(find_one(t1_root, "norm.mgz")),
        # FreeSurfer's recon-all writes wm.seg.mgz; fall back to wm.mgz, which
        # is likewise non-zero exactly inside white matter
        MghGz(find_one(t1_root, "wm.seg.mgz", "wm.mgz")),
        [ImageFormatGz(p) for p in parcellation_paths],
        parcellation_stems,
    )


@python.define(outputs=["log_file"])
def WriteTractographyLog(
    start_time: str,
    cache_root: str,
    connectomes: list[File],
    parcellation_stems: list[str],
    fod_algorithm: str,
    response_source: str,
    ftt_method: str,
    num_streamlines: int,
) -> str:
    """Write a plain-text execution log summarising the tractography steps,
    timing, resource usage, response function provenance and any warnings."""
    import datetime
    import os
    import pickle
    import platform
    import resource
    from pathlib import Path

    end_dt = datetime.datetime.now()
    if start_time:
        start_dt = datetime.datetime.fromisoformat(start_time)
        start_str = start_dt.isoformat(timespec="seconds")
        elapsed_str = str(end_dt - start_dt).split(".")[0]
    else:
        start_str = elapsed_str = "unknown (no start_time provided)"

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_bytes = usage.ru_maxrss
    if platform.system() != "Darwin":
        rss_bytes *= 1024
    peak_ram_gb = rss_bytes / (1024**3)
    cpu_user_s = usage.ru_utime
    cpu_sys_s = usage.ru_stime

    task_warnings = []
    cache_path = Path(cache_root) if cache_root else Path(".")
    for result_file in sorted(cache_path.glob("shell-*/_result.pklz")):
        try:
            with open(result_file, "rb") as f:
                r = pickle.load(f)
            if r.outputs and hasattr(r.outputs, "stderr"):
                stderr = r.outputs.stderr or ""
                warn_lines = [
                    ln.strip()
                    for ln in stderr.splitlines()
                    if any(
                        kw in ln.lower()
                        for kw in ("warn", "error", "caution", "note:", "failed")
                    )
                ]
                if warn_lines:
                    task_name = type(r.outputs).__name__.replace("Outputs", "")
                    task_warnings.append(f"{task_name}: " + " | ".join(warn_lines))
        except Exception:
            pass

    fod_step = (
        "Ss3tCsdBeta1 (ss3t_csd_beta1) — single-shell 3-tissue CSD"
        if fod_algorithm == "ss3t"
        else "Dwi2FodMsmt (dwi2fod msmt_csd) — multi-shell multi-tissue CSD"
    )

    lines = [
        "=" * 60,
        "Tractography & Connectomics Pipeline — Execution Log",
        "=" * 60,
        f"Start time:    {start_str}",
        f"End time:      {end_dt.isoformat(timespec='seconds')}",
        f"Elapsed:       {elapsed_str}",
        "",
        f"Peak RAM:      {peak_ram_gb:.2f} GB",
        f"CPU time:      {cpu_user_s + cpu_sys_s:.1f} s  "
        f"(user {cpu_user_s:.1f} s + sys {cpu_sys_s:.1f} s)",
        "",
        f"FOD algorithm: {fod_algorithm}",
        f"5TT method:    {ftt_method}",
        f"Streamlines:   {num_streamlines}",
        f"Responses:     {response_source}",
        "",
        "Steps executed:",
        "  1.  MrConvert — FreeSurfer brainmask/norm .mgz → NIfTI",
        "  2.  DwiExtract / MrcalcMax / MrMath — mean b0 for registration",
        "  3.  MrcalcMax — WM binary mask for epi_reg",
        "  4.  EpiRegMat (epi_reg) — DWI-to-T1 registration",
        "  5.  TransformConvertFlirt — FLIRT transform → MRtrix3 format",
        "  6.  MrTransform — apply transform + reslice DWI and mask to T1 space",
        f"  7.  {fod_step} — FOD estimation in T1 space",
        "  8.  MtNormalise3Tissue — multi-tissue FOD normalisation",
        "  9.  TckGenAct (iFOD2, ACT) — probabilistic tractography",
        "  10. TckSift2 — streamline weight optimisation",
        "  11. TckMap (TDI) — track density image",
        "  12. TckMap (DEC-TDI) — directionally-encoded colour TDI",
        "  13. Tck2Connectome — structural connectivity matrix per parcellation",
        "",
        "Connectomes:",
    ]
    for stem, connectome in zip(parcellation_stems, connectomes):
        lines.append(f"  {stem}: {connectome}")
    lines += ["", "Warnings / messages:"]
    lines += [f"  {w}" for w in task_warnings] or ["  None"]

    log_path = os.path.join(str(cache_path), "pipeline_tractography_log.txt")
    with open(log_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return log_path


@python.define(outputs=["out_dir"])
def FinalizeTractographyOutputs(
    transform: File,
    dwi_t1space: File,
    dwimask_t1space: File,
    wm_fod_norm: File,
    gm_fod_norm: File,
    csf_fod_norm: File,
    tracks: File,
    sift2_weights: File,
    sift2_mu: File,
    tdi: File,
    dec_tdi: File,
    connectomes: list[File],
    parcellation_stems: list[str],
    execution_log: str,
    cache_root: str = "",
) -> Directory:
    """Collect all outputs into one structured directory for a single
    namespaced XNAT sink, mirroring FinalizeDwiOutputs in dwi_preprocessing.py."""
    import shutil
    from pathlib import Path

    out_dir = (
        Path(cache_root) / "tractography"
        if cache_root
        else Path("./tractography").absolute()
    )
    reg_dir = out_dir / "Registration"
    fod_dir = out_dir / "FOD"
    tract_dir = out_dir / "Tractography"
    conn_dir = out_dir / "Connectomes"
    for d in (reg_dir, fod_dir, tract_dir, conn_dir):
        d.mkdir(parents=True, exist_ok=True)

    shutil.copy(str(transform), reg_dir / "epi2struct_mrtrix.txt")
    shutil.copy(str(dwi_t1space), reg_dir / "DWI_T1space.mif.gz")
    shutil.copy(str(dwimask_t1space), reg_dir / "DWImask_T1space.mif.gz")

    shutil.copy(str(wm_fod_norm), fod_dir / "wmfod_norm.mif.gz")
    shutil.copy(str(gm_fod_norm), fod_dir / "gmfod_norm.mif.gz")
    shutil.copy(str(csf_fod_norm), fod_dir / "csffod_norm.mif.gz")

    shutil.copy(str(tracks), tract_dir / "tracks.tck")
    shutil.copy(str(sift2_weights), tract_dir / "sift2_weights.txt")
    shutil.copy(str(sift2_mu), tract_dir / "sift2_mu.txt")
    shutil.copy(str(tdi), tract_dir / "TDI.mif.gz")
    shutil.copy(str(dec_tdi), tract_dir / "DECTDI.mif.gz")

    for stem, connectome in zip(parcellation_stems, connectomes):
        shutil.copy(str(connectome), conn_dir / f"connectome_{stem}.csv")

    shutil.copy(str(execution_log), out_dir / "execution_log.txt")

    return Directory(out_dir)


# ── Main workflow ──────────────────────────────────────────────────────────────


@workflow.define(outputs=["out_dir"])
def TractographyConnectomics(
    dwi_preproc_dir: Directory,
    t1_preproc_dir: Directory,
    fod_algorithm: str = "msmt_csd",
    ftt_method: str = "hsvs",
    num_streamlines: int = 10_000_000,
    response_wm: File | None = None,
    response_gm: File | None = None,
    response_csf: File | None = None,
    start_time: str = "",
    cache_root: str = "",
) -> Directory:
    """Register preprocessed DWI to T1 space, estimate and normalise FODs,
    run ACT/iFOD2 tractography with SIFT2 weighting, produce TDI/DEC-TDI maps,
    and build one structural connectome per parcellation found in the T1w
    preprocessing outputs.

    response_wm/gm/csf optionally override the subject-specific response
    functions from dwi_preproc_dir (e.g. with group-averaged ones); either all
    three or none must be given."""

    resolved = workflow.add(
        ResolveTractographyInputs(
            dwi_preproc_dir=dwi_preproc_dir,
            t1_preproc_dir=t1_preproc_dir,
            ftt_method=ftt_method,
        ),
        name="ResolveTractographyInputs",
    )

    overrides = [response_wm, response_gm, response_csf]
    if all(r is not None for r in overrides):
        resp_wm, resp_gm, resp_csf = overrides
        response_source = "group-averaged (user-provided)"
    elif any(r is not None for r in overrides):
        raise ValueError(
            "Provide all three response functions (response_wm, response_gm, "
            "response_csf) or none."
        )
    else:
        resp_wm = resolved.response_wm
        resp_gm = resolved.response_gm
        resp_csf = resolved.response_csf
        response_source = "subject-specific (from dwi_preprocess)"

    # ── Step 1: FreeSurfer .mgz → NIfTI for epi_reg ───────────────────────────
    t1brain_nii = workflow.add(
        MrConvert(in_file=resolved.t1brain_mgz, out_file="t1brain.nii.gz", config=[]),
        name="MrConvert_t1brain",
    )
    norm_nii = workflow.add(
        MrConvert(in_file=resolved.norm_mgz, out_file="normimg.nii.gz", config=[]),
        name="MrConvert_normimg",
    )

    # ── Step 2: Mean b0 for registration ──────────────────────────────────────
    b0_task = workflow.add(
        DwiExtract(
            in_file=resolved.dwi_preprocessed,
            out_file="bzero.mif.gz",
            bzero=True,
            config=[],
        ),
        name="DwiExtract_b0",
    )
    b0_clamped = workflow.add(
        MrcalcMax(in_file=b0_task.out_file, number=0.0, operand="max"),
        name="MrcalcMax_b0",
    )
    meanb0_task = workflow.add(
        MrMath(
            in_file=b0_clamped.output_image,
            out_file="dwi_meanbzero.nii.gz",
            operation="mean",
            axis=3,
            config=[],
        ),
        name="MrMath_meanb0",
    )

    # ── Step 3: WM binary mask for epi_reg ────────────────────────────────────
    wmbin_task = workflow.add(
        MrcalcMax(in_file=resolved.wmseg_mgz, number=0.0, operand="gt"),
        name="MrcalcMax_wmbin",
    )

    # ── Step 4: DWI → T1 registration ─────────────────────────────────────────
    epi_reg_task = workflow.add(
        EpiRegMat(
            epi=meanb0_task.out_file,
            t1_head=norm_nii.out_file,
            t1_brain=t1brain_nii.out_file,
            wmseg=wmbin_task.output_image,
        ),
        name="EpiReg",
    )

    # ── Step 5: Convert FLIRT transform to MRtrix3 format ─────────────────────
    transformconvert_task = workflow.add(
        TransformConvertFlirt(
            input_matrix=epi_reg_task.epi2str_mat,
            flirt_in=meanb0_task.out_file,
            flirt_ref=t1brain_nii.out_file,
        ),
        name="TransformConvert",
    )

    # ── Step 6: Apply transform — reslice DWI and mask to T1 space ────────────
    # mrtransform treats any 4D image with an SH-compatible volume count (6, 15,
    # 28, 45, 66, ...) as an FOD and reorients it unless told otherwise, so
    # "-reorient_fod no" is required for DWI. MrTransform's reorient_fod field
    # is a bare bool flag that can't render the "no" value, hence append_args.
    dwi_t1_task = workflow.add(
        MrTransform(
            in_file=resolved.dwi_preprocessed,
            out_file="DWI_T1space.mif.gz",
            linear=transformconvert_task.out_file,
            template=resolved.fttvis_image,
            strides=resolved.fttvis_image,
            append_args=["-reorient_fod", "no"],
            config=[],
        ),
        name="MrTransform_dwi",
    )
    mask_t1_task = workflow.add(
        MrTransform(
            in_file=resolved.dwimask_preprocessed,
            out_file="DWImask_T1space.mif.gz",
            interp="nearest",
            linear=transformconvert_task.out_file,
            template=resolved.fttvis_image,
            strides=resolved.fttvis_image,
            append_args=["-reorient_fod", "no"],
            config=[],
        ),
        name="MrTransform_mask",
    )

    # ── Step 7: FOD estimation in T1 space ────────────────────────────────────
    if fod_algorithm == "ss3t":
        fod_task = workflow.add(
            Ss3tCsdBeta1(
                in_dwi=dwi_t1_task.out_file,
                response_wm=resp_wm,
                response_gm=resp_gm,
                response_csf=resp_csf,
                mask=mask_t1_task.out_file,
            ),
            name="GenFod_T1space",
        )
        wm_fod, gm_fod, csf_fod = fod_task.wm_odf, fod_task.gm_odf, fod_task.csf_odf
    elif fod_algorithm == "msmt_csd":
        fod_task = workflow.add(
            Dwi2FodMsmt(
                dwi=dwi_t1_task.out_file,
                mask=mask_t1_task.out_file,
                response_wm=resp_wm,
                response_gm=resp_gm,
                response_csf=resp_csf,
            ),
            name="GenFod_T1space",
        )
        wm_fod, gm_fod, csf_fod = fod_task.wm_fod, fod_task.gm_fod, fod_task.csf_fod
    else:
        raise ValueError(
            f"Unknown fod_algorithm {fod_algorithm!r}. Choose from: msmt_csd, ss3t."
        )

    # ── Step 8: FOD normalisation ──────────────────────────────────────────────
    norm_fod_task = workflow.add(
        MtNormalise3Tissue(
            fod_wm=wm_fod,
            fod_gm=gm_fod,
            fod_csf=csf_fod,
            mask=mask_t1_task.out_file,
        ),
        name="MtNormalise",
    )

    # ── Step 9: Probabilistic tractography ────────────────────────────────────
    tckgen_task = workflow.add(
        TckGenAct(
            source=norm_fod_task.fod_wm_norm,
            seed_dynamic=norm_fod_task.fod_wm_norm,
            act=resolved.ftt_image,
            algorithm="ifod2",
            select=num_streamlines,
            seeds=0,
            minlength=5.0,
            maxlength=350.0,
            cutoff=0.06,
            backtrack=True,
            crop_at_gmwmi=True,
        ),
        name="TckGen",
    )

    # ── Step 10: SIFT2 streamline weight optimisation ─────────────────────────
    sift2_task = workflow.add(
        TckSift2(
            in_tracks=tckgen_task.tracks,
            in_fod=norm_fod_task.fod_wm_norm,
            act=resolved.ftt_image,
            out_weights="sift2_weights.txt",
            out_mu="sift2_mu.txt",
            config=[],
        ),
        name="TckSift2",
    )

    # ── Steps 11–12: TDI maps ─────────────────────────────────────────────────
    tdi_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=sift2_task.out_weights,
            vox=[1.0],
            template=resolved.ftt_image,
            out_file="TDI.mif.gz",
            config=[],
        ),
        name="TckMap_TDI",
    )
    dectdi_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=sift2_task.out_weights,
            vox=[1.0],
            template=resolved.ftt_image,
            dec=True,
            out_file="DECTDI.mif.gz",
            config=[],
        ),
        name="TckMap_DECTDI",
    )

    # ── Step 13: Structural connectivity matrix, once per parcellation ────────
    connectome_task = workflow.add(
        Tck2Connectome(
            tracks_in=tckgen_task.tracks,
            tck_weights_in=sift2_task.out_weights,
            symmetric=True,
            zero_diagonal=True,
            config=[],
        )
        .split("nodes_in", nodes_in=resolved.parcellations)
        .combine("nodes_in"),
        name="Tck2Connectome",
    )

    # ── Execution log and bundled output directory ─────────────────────────────
    log_task = workflow.add(
        WriteTractographyLog(
            start_time=start_time,
            cache_root=cache_root,
            connectomes=connectome_task.connectome_out,
            parcellation_stems=resolved.parcellation_stems,
            fod_algorithm=fod_algorithm,
            response_source=response_source,
            ftt_method=ftt_method,
            num_streamlines=num_streamlines,
        ),
        name="WriteTractographyLog",
    )

    finalize_task = workflow.add(
        FinalizeTractographyOutputs(
            transform=transformconvert_task.out_file,
            dwi_t1space=dwi_t1_task.out_file,
            dwimask_t1space=mask_t1_task.out_file,
            wm_fod_norm=norm_fod_task.fod_wm_norm,
            gm_fod_norm=norm_fod_task.fod_gm_norm,
            csf_fod_norm=norm_fod_task.fod_csf_norm,
            tracks=tckgen_task.tracks,
            sift2_weights=sift2_task.out_weights,
            sift2_mu=sift2_task.out_mu,
            tdi=tdi_task.out_file,
            dec_tdi=dectdi_task.out_file,
            connectomes=connectome_task.connectome_out,
            parcellation_stems=resolved.parcellation_stems,
            execution_log=log_task.log_file,
            cache_root=cache_root,
        ),
        name="FinalizeTractographyOutputs",
    )

    return finalize_task.out_dir
