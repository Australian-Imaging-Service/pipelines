from pathlib import Path

from pydra.compose import python, shell, workflow
from fileformats.generic import File
from pydra.tasks.mrtrix3.v3_1 import (
    DwiGradcheck,
    DwiDenoise,
    MrDegibbs,
    DwiFslpreproc,
    DwiBiascorrect_Ants,
    TransformConvert,
    MrTransform,
    MrConvert,
    MrGrid,
    DwiExtract,
    MrMath,
    Dwi2Response_Dhollander,
    Dwi2Fod,
    MtNormalise,
    TckGen,
    TckSift2,
    Tck2Connectome,
    TckMap,
)
from pydra.tasks.fsl.v6 import EpiReg
from pydra.tasks.fastsurfer.mri_synthstrip import MriSynthstrip
from fileformats.medimage import NiftiGzXBvec, NiftiGz

from fileformats.medimage_mrtrix3 import (
    ImageFormat,
    ImageIn,
    ImageOut,
    Tracks,
)  # noqa: F401

# Define the path and output_path variables
output_path = "<output_path>"  # Set this to your desired output directory


@shell.define
class MrcalcMax(shell.Task):

    executable = "mrcalc"

    in_file: ImageIn = shell.arg(
        help="path to input image 1",
        argstr="{in_file}",
        position=-4,
    )
    number: float = shell.arg(
        help="minimum value",
        argstr="{number}",
        position=-3,
    )
    operand: str = shell.arg(
        help="operand to execute",
        position=-2,
        argstr="-{operand}",
    )
    datatype: str | None = shell.arg(
        help="datatype option",
        argstr="-datatype {datatype}",
        position=-5,
        default=None,
    )

    class Outputs(shell.Outputs):
        output_image: ImageOut = shell.outarg(
            help="path to output image",
            path_template="mrcalc_output_image.nii.gz",
            position=-1,
        )


@shell.define
class Ss3tCsdBeta1(shell.Task):
    """Single-shell 3-tissue CSD from mrtrix3_tissue fork."""

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
class DwiCat(shell.Task):
    """Concatenate two DWI series along the volume axis using dwicat."""

    executable = "dwicat"

    in_file1: ImageIn = shell.arg(
        help="first input DWI image",
        argstr="{in_file1}",
        position=1,
    )
    in_file2: ImageIn = shell.arg(
        help="second input DWI image",
        argstr="{in_file2}",
        position=2,
    )
    force: bool = shell.arg(
        help="force overwrite of output",
        argstr="-force",
        default=True,
    )

    class Outputs(shell.Outputs):
        out_file: ImageOut = shell.outarg(
            help="concatenated output image",
            argstr="{out_file}",
            path_template="dwicat_out.mif.gz",
            position=3,
        )


@shell.define
class MrCat(shell.Task):
    """Concatenate images along a specified axis using mrcat."""

    executable = "mrcat"

    in_file1: ImageIn = shell.arg(
        help="first input image",
        argstr="{in_file1}",
        position=1,
    )
    in_file2: ImageIn = shell.arg(
        help="second input image",
        argstr="{in_file2}",
        position=2,
    )
    axis: int = shell.arg(
        help="concatenation axis",
        argstr="-axis {axis}",
        default=3,
    )
    force: bool = shell.arg(
        help="force overwrite of output",
        argstr="-force",
        default=True,
    )

    class Outputs(shell.Outputs):
        out_file: ImageOut = shell.outarg(
            help="concatenated output image",
            argstr="{out_file}",
            path_template="mrcat_out.mif.gz",
            position=3,
        )


@python.define(outputs=["half_voxel"])
def ComputeHalfVoxelSize(in_file: File) -> list[float]:
    """Run mrinfo -spacing and return spatial voxel dimensions halved,
    as a list of floats suitable for MrGrid voxel parameter."""
    import subprocess

    result = subprocess.run(
        ["mrinfo", str(in_file), "-spacing"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [float(v) / 2 for v in result.stdout.strip().split()[:3]]


@python.define(outputs=["grad_warning"])
def CheckGradientCorrection(in_file: File, corrected_grad_file: File) -> str:
    """Compare original DWI gradients with the DwiGradcheck-corrected export.
    Returns a warning string if corrections were applied."""
    import subprocess
    import numpy as np

    orig = subprocess.run(
        ["mrinfo", str(in_file), "-dwgrad"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    orig_grads = np.array(
        [[float(v) for v in row.split()] for row in orig.splitlines()]
    )

    with open(str(corrected_grad_file)) as fh:
        corr_lines = [
            ln
            for ln in fh.read().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    corr_grads = np.array([[float(v) for v in row.split()] for row in corr_lines])

    if not np.allclose(orig_grads[:, :3], corr_grads[:, :3], atol=1e-4):
        return (
            "WARNING: DwiGradcheck corrected gradient orientations. "
            "Verify tractography outputs carefully."
        )
    return "DwiGradcheck: gradient orientations verified, no correction applied."


@python.define(outputs=["log_file"])
def WriteExecutionLog(
    start_time: str,
    cache_root: str,
    DWI_T1space: File,
    DWImask_T1space: File,
    wm_fod_norm: File,
    gm_fod_norm: File,
    csf_fod_norm: File,
    TDI_file: File,
    DECTDI_file: File,
    connectome: File,
    out_mu: File,
    out_weights: File,
    fod_algorithm: str,
    grad_warning: str,
    dwifslpreproc_options: str = "",
) -> str:
    """Write a plain-text execution log summarising pipeline steps, all outputs,
    timing, resource usage, and any warnings from shell tasks."""
    import datetime
    import os
    import pickle
    import platform
    import resource
    from pathlib import Path

    end_dt = datetime.datetime.now()
    start_dt = datetime.datetime.fromisoformat(start_time)
    elapsed = end_dt - start_dt
    elapsed_str = str(elapsed).split(".")[0]  # drop microseconds

    # Resource usage (children = all shell subprocesses spawned by pydra)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    # macOS: ru_maxrss in bytes; Linux: in KB
    rss_bytes = usage.ru_maxrss
    if platform.system() != "Darwin":
        rss_bytes *= 1024
    peak_ram_gb = rss_bytes / (1024**3)
    cpu_user_s = usage.ru_utime
    cpu_sys_s = usage.ru_stime
    cpu_total_s = cpu_user_s + cpu_sys_s

    # Collect warnings from all shell task result pickles in the cache
    task_warnings = []
    # Always include the gradient correction check
    task_warnings.append(f"DwiGradcheck: {grad_warning}")

    cache_path = Path(cache_root)
    for result_file in sorted(cache_path.glob("shell-*/_result.pklz")):
        try:
            with open(result_file, "rb") as f:
                r = pickle.load(f)
            if r.outputs and hasattr(r.outputs, "stderr"):
                stderr = r.outputs.stderr or ""
                # Extract lines that look like warnings (case-insensitive)
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
        else "Dwi2Fod (msmt_csd) — multi-shell multi-tissue CSD"
    )

    lines = [
        "=" * 60,
        "DWI Analysis Pipeline — Execution Log",
        "=" * 60,
        f"Start time:    {start_dt.isoformat(timespec='seconds')}",
        f"End time:      {end_dt.isoformat(timespec='seconds')}",
        f"Elapsed:       {elapsed_str}",
        "",
        f"Peak RAM:      {peak_ram_gb:.2f} GB",
        f"CPU time:      {cpu_total_s:.1f} s  "
        f"(user {cpu_user_s:.1f} s + sys {cpu_sys_s:.1f} s)",
        "",
        f"FOD algorithm: {fod_algorithm}",
        "",
        "Steps executed:",
        "  1.  DwiGradcheck — verify/correct gradient orientations",
        "  2.  MrConvert — reimport DWI with corrected gradients",
        "  3.  DwiDenoise — MP-PCA denoising",
        "  4.  MrDegibbs — Gibbs ringing removal",
        "  5.  DwiExtract / MrcalcMax / MrMath / MriSynthstrip — early mean b0 brain mask (eddy_mask)",
        "  6.  DwiFslpreproc — motion and distortion correction (eddy/topup)",
        f"       Options: {dwifslpreproc_options}",
        "  7.  DwiExtract / MrcalcMax / MrMath / MriSynthstrip — corrected mean b0 brain mask",
        "  8.  DwiBiascorrect_Ants — ANTs bias field correction",
        "  9.  MrGrid (regrid) — halve voxel size (DWI and mask)",
        " 10.  MrGrid (crop) — crop to brain mask (DWI and mask)",
        " 11.  JoinTask / MrConvert — FreeSurfer path construction and .mgz → NIfTI",
        " 12.  DwiExtract / MrcalcMax / MrMath — mean b0 for registration",
        " 13.  EpiReg — DWI-to-T1 registration",
        " 14.  TransformConvert — convert FLIRT transform to MRtrix3 format",
        " 15.  MrTransform — apply transform to DWI and mask",
        " 16.  Dwi2Response_Dhollander — tissue response function estimation",
        f" 17.  {fod_step}",
        " 18.  MtNormalise — multi-tissue FOD normalisation",
        " 19.  TckGen (iFOD2) — probabilistic tractography",
        " 20.  TckSift2 — streamline weight optimisation",
        " 21.  Tck2Connectome — structural connectivity matrix",
        " 22.  TckMap (TDI) — track density image",
        " 23.  TckMap (DEC-TDI) — directionally-encoded colour TDI",
        "",
        "Outputs:",
        f"  DWI (T1 space):       {DWI_T1space}",
        f"  DWI mask (T1 space):  {DWImask_T1space}",
        f"  WM FOD (normalised):  {wm_fod_norm}",
        f"  GM FOD (normalised):  {gm_fod_norm}",
        f"  CSF FOD (normalised): {csf_fod_norm}",
        f"  TDI map:              {TDI_file}",
        f"  DEC-TDI map:          {DECTDI_file}",
        f"  Connectome:           {connectome}",
        f"  SIFT2 mu:             {out_mu}",
        f"  SIFT2 weights:        {out_weights}",
        "",
        "Warnings / messages:",
    ]
    for w in task_warnings:
        lines.append(f"  {w}")
    if not task_warnings:
        lines.append("  None")

    log_path = os.path.join(cache_root, "pipeline_execution_log.txt")
    with open(log_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    return log_path


def detect_shell_structure(dwi_path: str) -> str:
    """Return 'ss3t' for single-shell data (b=0 + one non-zero shell) or
    'msmt_csd' for multi-shell data, by inspecting the DWI header with mrinfo.

    Call this before constructing DwiPipeline and pass the result as
    fod_algorithm.
    """
    import subprocess

    result = subprocess.run(
        ["mrinfo", str(dwi_path), "-shell_bvalues"],
        capture_output=True,
        text=True,
        check=True,
    )
    bvalues = result.stdout.strip().split()
    non_zero_shells = [b for b in bvalues if float(b) > 50]
    return "ss3t" if len(non_zero_shells) == 1 else "msmt_csd"


@python.define(
    outputs=["t1_FSpath", "t1brain_FSpath", "wmseg_FSpath", "normimg_FSpath"]
)
def JoinTask(FS_dir: str):
    import os

    t1_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")
    t1brain_FSpath = os.path.join(FS_dir, "mri", "brainmask.mgz")
    wmseg_FSpath = os.path.join(FS_dir, "mri", "wm.seg.mgz")
    normimg_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")

    return t1_FSpath, t1brain_FSpath, wmseg_FSpath, normimg_FSpath


def resolve_inputs(subject_dir: str) -> dict:
    """
    Discover all pipeline inputs from a structured subject directory.
    Classifies the DWI acquisition mode by inspecting file headers with mrinfo.
    Image preparation (concatenation, b0 extraction) is handled inside DwiPipeline
    as proper Pydra tasks.

    Expected layout::

        <subject_dir>/
            <id>_dwi_*.mif.gz          (or .nii.gz — AP/PA tagged or untagged)
            <id>_5TT_*.mif.gz
            <id>_5TTvis_*.mif.gz
            <id>_Parcellation_*.mif.gz  (first match used alphabetically)
            FS_outputs/

    AP/PA classification rules (applied in priority order):
      1. Find all DWI candidates (files matching *dwi* or *DWI*).
      2. Group PE-tagged files by acquisition stem (filename with PE tag stripped).
         Untagged files (no PE tag) are collected separately.
      3. If a complete FWD+RPE tagged pair exists AND FWD has non-zero bvals:
           - RPE is b0-only or unequal volumes  →  rpe_pair  (dwi_raw_mif=FWD, rpe_file=RPE)
           - Both non-zero bvals, equal volumes  →  rpe_all   (dwi_raw_mif=FWD, rpe_file=RPE)
         (FWD-tagged b0-only files are skipped as main DWI candidates — treated as scouts)
      4. Else if an untagged DWI exists:
           - With RPE-tagged companion: classify companion as above  →  rpe_pair or rpe_all
             pe_dir is inferred from the header of the untagged file; FWD-tagged
             companion files (AP/LR/SI b0 scouts) are ignored.
           - No companion: pe_dir + rpe_mode from header
             · single PE direction in header  →  rpe_none
             · mixed PE directions in header  →  rpe_header (interleaved AP+PA in one file)
      5. Else fall back to any single PE-tagged file  →  rpe_none

    Returns a dict for DwiPipeline(**resolve_inputs(...)). Image preparation tasks
    (dwicat, dwiextract, mrmath, mrcat) run inside the workflow with full caching.
    """
    import re
    import subprocess

    root = Path(subject_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Subject directory not found: {subject_dir}")

    def _first(patterns, label):
        for pat in patterns:
            matches = sorted(root.glob(pat))
            if matches:
                return str(matches[0])
        raise FileNotFoundError(
            f"Could not find {label} in {subject_dir} "
            f"(tried: {', '.join(patterns)})"
        )

    # ── PE tag helpers ────────────────────────────────────────────────────────
    _FWD = {"AP", "LR", "SI"}
    _RPE = {"PA", "RL", "IS"}
    _PE_PATS = [
        (r"_(AP)(_|\.|$)", "AP"),
        (r"_(PA)(_|\.|$)", "PA"),
        (r"_(LR)(_|\.|$)", "LR"),
        (r"_(RL)(_|\.|$)", "RL"),
        (r"_(SI)(_|\.|$)", "SI"),
        (r"_(IS)(_|\.|$)", "IS"),
    ]

    def _get_pe(name):
        for pat, pe in _PE_PATS:
            if re.search(pat, name, re.IGNORECASE):
                return pe
        return None

    def _strip_pe(name):
        for pat, _ in _PE_PATS:
            name = re.sub(pat, r"_\2", name, flags=re.IGNORECASE)
        return name

    def _has_nonzero_bvals(path):
        try:
            r = subprocess.run(
                ["mrinfo", str(path), "-shell_bvalues"],
                capture_output=True,
                text=True,
                check=True,
            )
            return any(float(s) > 50 for s in r.stdout.strip().split())
        except Exception:
            return True  # assume non-zero if mrinfo unavailable

    def _get_nvols(path):
        try:
            r = subprocess.run(
                ["mrinfo", str(path), "-size"],
                capture_output=True,
                text=True,
                check=True,
            )
            parts = r.stdout.strip().split()
            return int(parts[3]) if len(parts) >= 4 else 1
        except Exception:
            return None

    # ── Find all DWI candidates ───────────────────────────────────────────────
    dwi_candidates = sorted(
        {
            f
            for pat in ["*dwi*.mif.gz", "*DWI*.mif.gz", "*dwi*.nii.gz", "*DWI*.nii.gz"]
            for f in root.glob(pat)
        }
    )
    if not dwi_candidates:
        raise FileNotFoundError(f"No DWI image found in {subject_dir}")

    # ── Group by stem, separate FWD / RPE / untagged ─────────────────────────
    stem_map = {}
    untagged = []
    for f in dwi_candidates:
        pe = _get_pe(f.name)
        if pe:
            stem_map.setdefault(_strip_pe(f.name), {})[pe] = f
        else:
            untagged.append(f)

    # ── Classify ──────────────────────────────────────────────────────────────
    # Priority:
    #  1. Complete FWD+RPE tagged pair where FWD has non-zero bvals  → rpe_pair/rpe_all
    #  2. Untagged DWI + RPE-tagged companion                        → rpe_pair/rpe_all
    #  3. Untagged DWI alone                                         → rpe_none/rpe_header
    #  4. Fallback: any single PE-tagged file                        → rpe_none
    dwi_raw_mif = None
    rpe_file = None
    pe_dir = "AP"
    rpe_mode = "rpe_none"

    def _classify_rpe_companion(fwd_path, rpe_path):
        """Determine rpe_mode from a FWD+RPE pair. Prints a summary. Returns mode string."""
        fwd_name = Path(fwd_path).name
        rpe_name = Path(rpe_path).name
        rpe_has_dwi = _has_nonzero_bvals(str(rpe_path))
        if rpe_has_dwi:
            nvols_fwd = _get_nvols(str(fwd_path))
            nvols_rpe = _get_nvols(str(rpe_path))
            equal_vols = nvols_fwd is not None and nvols_fwd == nvols_rpe
            if equal_vols:
                print(
                    f"  AP/PA pair detected (rpe_all): "
                    f"{fwd_name} + {rpe_name} ({nvols_fwd} vols each)"
                )
                return "rpe_all"
            else:
                print(
                    f"  AP/PA pair detected (rpe_pair — unequal volumes): "
                    f"{fwd_name} ({nvols_fwd} vols) + {rpe_name} ({nvols_rpe} vols)"
                )
                return "rpe_pair"
        else:
            print(
                f"  AP/PA pair detected (rpe_pair): "
                f"{fwd_name} (DWI) + {rpe_name} (b0 SE-EPI)"
            )
            return "rpe_pair"

    # Phase 1: complete FWD+RPE tagged pair where FWD has non-zero bvals
    # (Skips b0-only FWD files — those are scouts, not the main DWI)
    for stem, pe_map in stem_map.items():
        fwds = {pe: p for pe, p in pe_map.items() if pe in _FWD}
        rpes = {pe: p for pe, p in pe_map.items() if pe in _RPE}
        if fwds and rpes:
            fwd_pe, fwd_path = next(iter(fwds.items()))
            _rpe_pe, rpe_path = next(iter(rpes.items()))
            if not _has_nonzero_bvals(str(fwd_path)):
                continue  # FWD is a b0 scout — skip, let Phase 2 handle
            rpe_mode = _classify_rpe_companion(fwd_path, rpe_path)
            dwi_raw_mif = str(fwd_path)
            rpe_file = str(rpe_path)
            pe_dir = fwd_pe
            break

    # Phase 2: untagged DWI (main) + optional RPE-tagged companion
    if dwi_raw_mif is None and untagged:
        main_dwi = (
            max(untagged, key=lambda f: _get_nvols(str(f)) or 0)
            if len(untagged) > 1
            else untagged[0]
        )
        dwi_raw_mif = str(main_dwi)
        # Gather all RPE-tagged (PA/RL/IS) files across all stems
        all_rpe = [
            (pe, p)
            for sm in stem_map.values()
            for pe, p in sm.items()
            if pe in _RPE
        ]
        if all_rpe:
            _rpe_pe, _rpe_path = all_rpe[0]
            rpe_file = str(_rpe_path)
            rpe_mode = _classify_rpe_companion(str(main_dwi), str(_rpe_path))
            pe_dir, _ = detect_dwi_pe_and_mode(dwi_raw_mif)
        else:
            pe_dir, rpe_mode = detect_dwi_pe_and_mode(dwi_raw_mif)
            label = (
                "interleaved AP+PA — rpe_header"
                if rpe_mode == "rpe_header"
                else "single PE direction"
            )
            print(f"  Untagged DWI ({label}): {main_dwi.name}")

    # Phase 3: fallback — single PE-tagged file with no usable pair
    if dwi_raw_mif is None:
        for stem, pe_map in stem_map.items():
            fwds = {pe: p for pe, p in pe_map.items() if pe in _FWD}
            rpes = {pe: p for pe, p in pe_map.items() if pe in _RPE}
            if fwds:
                fwd_pe, fwd_path = next(iter(fwds.items()))
                print(f"  Single FWD DWI (rpe_none): {fwd_path.name}")
                dwi_raw_mif = str(fwd_path)
                pe_dir = fwd_pe
                break
            if rpes:
                rpe_pe, rpe_path = next(iter(rpes.items()))
                print(f"  Single RPE DWI (rpe_none): {rpe_path.name}")
                dwi_raw_mif = str(rpe_path)
                pe_dir = rpe_pe
                break

    if dwi_raw_mif is None:
        raise FileNotFoundError(f"Could not identify a main DWI in {subject_dir}")

    # ── Remaining inputs ──────────────────────────────────────────────────────
    ftt = _first(["*_5TT_*.mif.gz"], "5TT image")
    fttvis = _first(["*_5TTvis_*.mif.gz"], "5TTvis image")
    parcellation = _first(["*_Parcellation_*.mif.gz"], "parcellation image")
    fs_dir = root / "FS_outputs"
    if not fs_dir.is_dir():
        raise FileNotFoundError(f"FS_outputs directory not found in {subject_dir}")

    return {
        "dwi_raw_mif": dwi_raw_mif,
        "rpe_file": rpe_file,
        "FS_dir": str(fs_dir),
        "fTTvis_image_T1space": fttvis,
        "fTT_image_T1space": ftt,
        "parcellation_image_T1space": parcellation,
        "pe_dir": pe_dir,
        "rpe_mode": rpe_mode,
    }


def detect_dwi_pe_and_mode(dwi_path: str) -> tuple[str, str]:
    """
    Infer PE direction and DwiFslpreproc mode from a DWI image.

    Detection order:
      1. Filename patterns (_AP_, _PA_, _LR_, _RL_, _SI_, _IS_)
      2. JSON sidecar PhaseEncodingDirection (for NIfTI inputs)
      3. mrinfo -petable on MIF header

    Returns (pe_dir, rpe_mode) where rpe_mode is one of
    'rpe_none', 'rpe_pair', 'rpe_all', 'rpe_split'.
    For a single-file input the mode is always 'rpe_none'; call
    plan_workflow() from dwi_processing.py for multi-series DICOM inputs.
    """
    import json
    import re
    import subprocess

    name = Path(dwi_path).name

    _pairs = [
        (r"_AP(_|$|\b)", "AP"),
        (r"_A_P(_|$|\b)", "AP"),
        (r"_PA(_|$|\b)", "PA"),
        (r"_P_A(_|$|\b)", "PA"),
        (r"_LR(_|$|\b)", "LR"),
        (r"_L_R(_|$|\b)", "LR"),
        (r"_RL(_|$|\b)", "RL"),
        (r"_R_L(_|$|\b)", "RL"),
        (r"_SI(_|$|\b)", "SI"),
        (r"_S_I(_|$|\b)", "SI"),
        (r"_IS(_|$|\b)", "IS"),
        (r"_I_S(_|$|\b)", "IS"),
    ]
    for pat, pe in _pairs:
        if re.search(pat, name, re.IGNORECASE):
            return pe, "rpe_none"

    # JSON sidecar (NIfTI inputs)
    base = re.sub(r"\.nii(\.gz)?$", "", dwi_path)
    json_path = base + ".json"
    _json_map = {
        "j-": "AP",
        "j": "PA",
        "i": "LR",
        "i-": "RL",
        "k": "SI",
        "k-": "IS",
    }
    if Path(json_path).exists():
        try:
            with open(json_path) as f:
                ped = json.load(f).get("PhaseEncodingDirection", "").strip()
            if ped in _json_map:
                return _json_map[ped], "rpe_none"
        except Exception:
            pass

    # MIF header petable
    try:
        result = subprocess.run(
            ["mrinfo", dwi_path, "-petable"],
            capture_output=True,
            text=True,
            check=True,
        )
        raw = result.stdout.strip()
        if raw:
            _vec_map = {
                (0, -1, 0): "AP",
                (0, 1, 0): "PA",
                (1, 0, 0): "LR",
                (-1, 0, 0): "RL",
                (0, 0, 1): "SI",
                (0, 0, -1): "IS",
            }
            dirs = []
            for line in raw.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    vec = tuple(round(float(v)) for v in parts[:3])
                    if vec in _vec_map:
                        dirs.append(_vec_map[vec])
            if dirs:
                unique = set(dirs)
                if len(unique) == 1:
                    return dirs[0], "rpe_none"
                # Multiple PE directions embedded in header → rpe_header
                counts = {d: dirs.count(d) for d in unique}
                dominant = max(counts, key=lambda d: counts[d])
                return dominant, "rpe_header"
    except Exception:
        pass

    print(
        f"  WARNING: could not determine PE direction for {name}. "
        "Defaulting to AP / rpe_none. Pass pe_dir and rpe_mode explicitly to override."
    )
    return "AP", "rpe_none"


# Define the input_spec for the workflow
@workflow.define(
    outputs=[
        "DWI_T1space",
        "DWImask_T1space",
        "wm_fod_norm",
        "gm_fod_norm",
        "csf_fod_norm",
        "TDI_file",
        "DECTDI_file",
        "connectome_out",
        "out_mu",
        "out_weights",
        "execution_log",
    ]
)
def DwiPipeline(
    dwi_raw_mif: File,
    FS_dir: str,
    fTTvis_image_T1space: File,
    fTT_image_T1space: File,
    parcellation_image_T1space: File,
    pe_dir: str = "AP",
    rpe_mode: str = "rpe_none",
    rpe_file: str | None = None,
    readout_time: float | None = None,
    eddy_options: str = "' --slm=linear'",
    fod_algorithm: str = "msmt_csd",
    start_time: str = "",
    cache_root: str = "",
) -> tuple[File, File, File, File, File, File, File, File, File, File, str]:

    # ── AP/PA preparation (rpe_all and rpe_pair) ──────────────────────────────
    # rpe_all: concatenate FWD + RPE into a single 4D series (FWD first).
    # rpe_pair: build a 1+1 b0 SE-EPI pair (FWD mean b0 first, RPE mean b0 second)
    #           as required by dwifslpreproc -rpe_pair.
    # The prepared dwi input and se_epi path are resolved here before DwiGradcheck.

    se_epi_task_out = None  # will be wired to DwiFslpreproc se_epi if rpe_pair

    if rpe_mode == "rpe_all":
        # Concatenate AP + PA (AP first — pe_dir identifies the first half)
        dwicat_task = workflow.add(
            DwiCat(
                in_file1=dwi_raw_mif,
                in_file2=rpe_file,
                out_file="dwi_AP_PA_concat.mif.gz",
            ),
            name="DwiCat_rpe_all",
        )
        dwi_prepared = dwicat_task.out_file

    elif rpe_mode == "rpe_pair":
        # Extract mean b0 from FWD DWI
        fwd_b0_extract = workflow.add(
            DwiExtract(
                in_file=dwi_raw_mif,
                out_file="fwd_bzero.mif.gz",
                bzero=True,
            ),
            name="DwiExtract_fwd_b0",
        )
        fwd_meanb0 = workflow.add(
            MrMath(
                in_file=fwd_b0_extract.out_file,
                out_file="fwd_meanb0.mif.gz",
                operation="mean",
                axis=3,
            ),
            name="MrMath_fwd_meanb0",
        )
        # Extract mean b0 from RPE series
        rpe_b0_extract = workflow.add(
            DwiExtract(
                in_file=rpe_file,
                out_file="rpe_bzero.mif.gz",
                bzero=True,
            ),
            name="DwiExtract_rpe_b0",
        )
        rpe_meanb0 = workflow.add(
            MrMath(
                in_file=rpe_b0_extract.out_file,
                out_file="rpe_meanb0.mif.gz",
                operation="mean",
                axis=3,
            ),
            name="MrMath_rpe_meanb0",
        )
        # Concatenate: FWD b0 first, RPE b0 second (equal 1+1 pair)
        se_epi_task = workflow.add(
            MrCat(
                in_file1=fwd_meanb0.out_file,
                in_file2=rpe_meanb0.out_file,
                out_file="se_epi_pair.mif.gz",
                axis=3,
            ),
            name="MrCat_se_epi",
        )
        se_epi_task_out = se_epi_task.out_file
        dwi_prepared = dwi_raw_mif

    else:
        dwi_prepared = dwi_raw_mif

    # DWIgradcheck — operates on the prepared (possibly concatenated) DWI
    DWIgradcheck_task = workflow.add(
        DwiGradcheck(
            in_file=dwi_prepared,
            export_grad_mrtrix="DWIgradcheck_grad.txt",
        )
    )

    # Check whether DwiGradcheck applied any corrections
    grad_check_task = workflow.add(
        CheckGradientCorrection(
            in_file=dwi_prepared,
            corrected_grad_file=DWIgradcheck_task.export_grad_mrtrix,
        )
    )

    # create mif with corrected grad
    DWItoMif_task = workflow.add(
        MrConvert(
            in_file=dwi_prepared,
            grad=DWIgradcheck_task.export_grad_mrtrix,
        ),
        name="MrConvert_grad",
    )

    # denoise
    dwi_denoise_task = workflow.add(
        DwiDenoise(
            dwi=DWItoMif_task.out_file,
        )
    )

    # unring
    dwi_degibbs_task = workflow.add(
        MrDegibbs(
            in_=dwi_denoise_task.out,
        )
    )

    # ── Early b0 brain mask — used as eddy_mask in DwiFslpreproc ─────────────
    early_b0_task = workflow.add(
        DwiExtract(
            in_file=dwi_degibbs_task.out,
            out_file="early_bzero.mif.gz",
            bzero=True,
        ),
        name="DwiExtract_early",
    )

    early_b0_nonneg = workflow.add(
        MrcalcMax(
            in_file=early_b0_task.out_file,
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_early_b0",
    )

    early_meanb0_task = workflow.add(
        MrMath(
            in_file=early_b0_nonneg.output_image,
            out_file="early_meanb0.nii.gz",
            operation="mean",
            axis=3,
        ),
        name="MrMath_early_meanb0",
    )

    synthstrip_task = workflow.add(
        MriSynthstrip(
            in_file=early_meanb0_task.out_file,
        ),
        name="MriSynthstrip_early",
    )

    # ── Motion and distortion correction ─────────────────────────────────────
    # Build a human-readable options summary for the execution log.
    _se_epi_label = "yes" if rpe_mode in ("rpe_pair", "rpe_split") else "no"
    _pe_label = "from header" if rpe_mode == "rpe_header" else pe_dir
    _rt_label = (
        "from header"
        if rpe_mode == "rpe_header"
        else (str(readout_time) if readout_time is not None else "from header")
    )
    dwifslpreproc_options = (
        f"mode: -{rpe_mode}  pe_dir: {_pe_label}  "
        f"readout_time: {_rt_label}  "
        f'eddy_options: "{eddy_options}"  '
        f"se_epi: {_se_epi_label}"
    )

    # Only pass the single active rpe flag — pydra's xor constraint rejects
    # multiple rpe_* kwargs even when the extras are False.
    # rpe_header is also mutually exclusive with pe_dir and readout_time.
    if rpe_mode == "rpe_none":
        _rpe_kw = {"rpe_none": True}
    elif rpe_mode == "rpe_pair":
        _rpe_kw = {"rpe_pair": True}
    elif rpe_mode == "rpe_all":
        _rpe_kw = {"rpe_all": True}
    elif rpe_mode == "rpe_header":
        _rpe_kw = {"rpe_header": True}
    else:
        _rpe_kw = {"rpe_split": True}

    _fslpreproc_kw: dict = {
        "in_file": dwi_degibbs_task.out,
        "out_file": "DWI_preproc.mif.gz",
        **_rpe_kw,
        "eddy_mask": synthstrip_task.mask_file,
        "se_epi": se_epi_task_out if rpe_mode in ("rpe_pair", "rpe_split") else None,
        "align_seepi": rpe_mode in ("rpe_pair", "rpe_split"),
        "eddy_options": eddy_options,
    }
    # pe_dir and readout_time are mutually exclusive with rpe_header in dwifslpreproc
    if rpe_mode != "rpe_header":
        _fslpreproc_kw["pe_dir"] = pe_dir
        if readout_time is not None:
            _fslpreproc_kw["readout_time"] = readout_time

    dwifslpreproc_task = workflow.add(DwiFslpreproc(**_fslpreproc_kw))

    # ── Corrected brain mask from DwiFslpreproc output ────────────────────────
    preproc_b0_task = workflow.add(
        DwiExtract(
            in_file=dwifslpreproc_task.out_file,
            out_file="preproc_bzero.mif.gz",
            bzero=True,
        ),
        name="DwiExtract_preproc",
    )

    preproc_b0_nonneg = workflow.add(
        MrcalcMax(
            in_file=preproc_b0_task.out_file,
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_preproc_b0",
    )

    preproc_meanb0_task = workflow.add(
        MrMath(
            in_file=preproc_b0_nonneg.output_image,
            out_file="preproc_meanb0.nii.gz",
            operation="mean",
            axis=3,
        ),
        name="MrMath_preproc_meanb0",
    )

    corrected_synthstrip_task = workflow.add(
        MriSynthstrip(
            in_file=preproc_meanb0_task.out_file,
        ),
        name="MriSynthstrip_corrected",
    )

    # ── Bias field correction (uses DwiFslpreproc output + corrected mask) ───
    dwibiasfieldcorr_task = workflow.add(
        DwiBiascorrect_Ants(
            in_file=dwifslpreproc_task.out_file,
            mask=corrected_synthstrip_task.mask_file,
            bias="biasfield.mif.gz",
        )
    )

    # # Step 7: Regrid to half voxel size, then crop to brain mask

    # Compute half voxel size from bias-corrected DWI header
    half_vox_task = workflow.add(
        ComputeHalfVoxelSize(in_file=dwibiasfieldcorr_task.out_file)
    )

    # Regrid DWI to half voxel size
    regrid_task_dwi = workflow.add(
        MrGrid(
            in_file=dwibiasfieldcorr_task.out_file,
            operation="regrid",
            voxel=half_vox_task.half_voxel,
            out_file="dwi_regrid.mif.gz",
        ),
        name="MrGrid_regrid_dwi",
    )

    # Regrid mask to half voxel size
    regrid_task_mask = workflow.add(
        MrGrid(
            in_file=synthstrip_task.mask_file,
            operation="regrid",
            voxel=half_vox_task.half_voxel,
            interp="nearest",
            out_file="dwimask_regrid.mif.gz",
        ),
        name="MrGrid_regrid_mask",
    )

    # Crop DWI to regridded mask
    crop_task_dwi = workflow.add(
        MrGrid(
            in_file=regrid_task_dwi.out_file,
            operation="crop",
            mask=regrid_task_mask.out_file,
            out_file="dwi_processed.mif.gz",
            uniform=-3,
        ),
        name="MrGrid_crop_dwi",
    )

    # Crop mask
    crop_task_mask = workflow.add(
        MrGrid(
            in_file=regrid_task_mask.out_file,
            operation="crop",
            mask=regrid_task_mask.out_file,
            out_file="dwimask_processed.mif.gz",
            interp="nearest",
            uniform=-3,
        ),
        name="MrGrid_crop_mask",
    )

    # # ########################
    # # # REGISTRATION CONTENT #
    # # ########################

    # Step 8: Generate target images for registration and transformation

    join_task = workflow.add(JoinTask(FS_dir=FS_dir))

    # need to convert .mgz to nifti for registration
    nifti_t1 = workflow.add(
        MrConvert(
            in_file=join_task.t1_FSpath,
            out_file="t1.nii.gz",
        ),
        name="MrConvert_t1",
    )

    nifti_t1brain = workflow.add(
        MrConvert(
            in_file=join_task.t1brain_FSpath,
            out_file="t1brain.nii.gz",
        ),
        name="MrConvert_t1brain",
    )

    nifti_normimg = workflow.add(
        MrConvert(
            in_file=join_task.normimg_FSpath,
            out_file="normimg.nii.gz",
        ),
        name="MrConvert_normimg",
    )

    # extract meanb0 volumes #

    extract_bzeroes_task = workflow.add(
        DwiExtract(
            in_file=crop_task_dwi.out_file,
            out_file="bzero.mif.gz",
            bzero=True,
        )
    )

    # remove negative values from bzero volumes
    mrcalc_max = workflow.add(
        MrcalcMax(
            in_file=extract_bzeroes_task.out_file,
            output_image="b0_nonneg.mif.gz",
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_b0",
    )

    # # create meanb0 image
    meanb0_task = workflow.add(
        MrMath(
            in_file=mrcalc_max.output_image,
            out_file="dwi_meanbzero.nii.gz",
            operation="mean",
            axis=3,
        )
    )

    # make wm mask a binary image
    mrcalc_wmbin = workflow.add(
        MrcalcMax(
            in_file=join_task.wmseg_FSpath,
            number=0.0,
            operand="gt",
        ),
        name="MrcalcMax_wmbin",
    )

    # Step 9: Perform DWI->T1 registration
    epi_reg_task = workflow.add(
        EpiReg(
            epi=meanb0_task.out_file,
            t1_head=nifti_normimg.out_file,
            t1_brain=nifti_t1brain.out_file,
            wmseg=mrcalc_wmbin.output_image,
            out_base="epi2struct",
        )
    )

    # transformconvert task
    transformconvert_task = workflow.add(
        TransformConvert(
            input_matrix=epi_reg_task.epi2str_mat,
            flirt_in=meanb0_task.out_file,
            flirt_ref=nifti_t1brain.out_file,
            operation="flirt_import",
            out_file="epi2struct_mrtrix.txt",
        )
    )

    # #apply transform to DWI image
    transformDWI_task = workflow.add(
        MrTransform(
            in_file=crop_task_dwi.out_file,
            inverse=False,
            out_file="DWI_T1space.mif.gz",
            linear=transformconvert_task.out_file,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_dwi",
    )

    # #apply transform to DWI mask image
    transformDWImask_task = workflow.add(
        MrTransform(
            in_file=crop_task_mask.out_file,
            inverse=False,
            out_file="DWImask_T1space.mif.gz",
            interp="nearest",
            linear=transformconvert_task.out_file,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_mask",
    )

    # # # # ##################################
    # # # # # Tractography preparation steps #
    # # # # ##################################

    # # Estimate Response Function (subject)
    EstimateResponseFcn_task = workflow.add(
        Dwi2Response_Dhollander(
            in_file=transformDWI_task.out_file,
            mask=transformDWImask_task.out_file,
            voxels="voxels.mif.gz",
        )
    )

    ##################
    ## SCRIPT BREAK ##
    ##################

    # Generate FOD — algorithm determined before workflow construction
    if fod_algorithm == "ss3t":
        GenFod_task = workflow.add(
            Ss3tCsdBeta1(
                in_dwi=transformDWI_task.out_file,
                response_wm=EstimateResponseFcn_task.out_sfwm,
                response_gm=EstimateResponseFcn_task.out_gm,
                response_csf=EstimateResponseFcn_task.out_csf,
                mask=transformDWImask_task.out_file,
            )
        )
        wm_fod = GenFod_task.wm_odf
        gm_fod = GenFod_task.gm_odf
        csf_fod = GenFod_task.csf_odf
    else:  # "msmt_csd"
        GenFod_task = workflow.add(
            Dwi2Fod(
                algorithm="msmt_csd",
                dwi=transformDWI_task.out_file,
                mask=transformDWImask_task.out_file,
                response_wm=EstimateResponseFcn_task.out_sfwm,
                response_gm=EstimateResponseFcn_task.out_gm,
                response_csf=EstimateResponseFcn_task.out_csf,
            )
        )
        wm_fod = GenFod_task.fod_wm
        gm_fod = GenFod_task.fod_gm
        csf_fod = GenFod_task.fod_csf

    # Normalise FOD
    NormFod_task = workflow.add(
        MtNormalise(
            fod_wm=wm_fod,
            fod_gm=gm_fod,
            fod_csf=csf_fod,
            mask=transformDWImask_task.out_file,
            fod_wm_norm="wmfod_norm.mif.gz",
            fod_gm_norm="gmfod_norm.mif.gz",
            fod_csf_norm="csffod_norm.mif.gz",
        )
    )

    # Tractography
    tckgen_task = workflow.add(
        TckGen(
            source=NormFod_task.fod_wm_norm,
            # tracks="tractogram.tck",
            algorithm="ifod2",
            select=100,
            minlength=5.0,
            maxlength=350.0,
            seed_dynamic=NormFod_task.fod_wm_norm,
            act=fTT_image_T1space,
            backtrack=True,
            crop_at_gmwmi=True,
            cutoff=0.06,
            seeds=0,
        )
    )

    # SIFT2
    SIFT2_task = workflow.add(
        TckSift2(
            in_tracks=tckgen_task.tracks,
            in_fod=NormFod_task.fod_wm_norm,
            act=fTT_image_T1space,
            out_mu="mu.txt",
        )
    )

    ################
    # CONNECTOMICS #
    ################
    connectomics_task = workflow.add(
        Tck2Connectome(
            tracks_in=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            nodes_in=parcellation_image_T1space,
            symmetric=True,
            zero_diagonal=True,
        )
    )

    # ############
    # # TDI maps #
    # ############

    TDImap_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            vox=1,
            template=fTT_image_T1space,
            out_file="TDI.mif.gz",
        ),
        name="TckMap_TDI",
    )

    DECTDImap_task = workflow.add(
        TckMap(
            tracks=tckgen_task.tracks,
            tck_weights_in=SIFT2_task.out_weights,
            vox=1,
            template=fTT_image_T1space,
            dec=True,
            out_file="DECTDI.mif.gz",
        ),
        name="TckMap_DECTDI",
    )

    # Write execution log
    log_task = workflow.add(
        WriteExecutionLog(
            start_time=start_time,
            cache_root=cache_root,
            DWI_T1space=transformDWI_task.out_file,
            DWImask_T1space=transformDWImask_task.out_file,
            wm_fod_norm=NormFod_task.fod_wm_norm,
            gm_fod_norm=NormFod_task.fod_gm_norm,
            csf_fod_norm=NormFod_task.fod_csf_norm,
            TDI_file=TDImap_task.out_file,
            DECTDI_file=DECTDImap_task.out_file,
            connectome=connectomics_task.connectome_out,
            out_mu=SIFT2_task.out_mu,
            out_weights=SIFT2_task.out_weights,
            fod_algorithm=fod_algorithm,
            grad_warning=grad_check_task.grad_warning,
            dwifslpreproc_options=dwifslpreproc_options,
        )
    )

    # # SET WF OUTPUT

    return (
        transformDWI_task.out_file,
        transformDWImask_task.out_file,
        NormFod_task.fod_wm_norm,
        NormFod_task.fod_gm_norm,
        NormFod_task.fod_csf_norm,
        TDImap_task.out_file,
        DECTDImap_task.out_file,
        connectomics_task.connectome_out,
        SIFT2_task.out_mu,
        SIFT2_task.out_weights,
        log_task.log_file,
    )


# ########################
# # Execute the workflow #
# ########################


if __name__ == "__main__":
    import datetime

    subject_dir = "/Users/adso8337/Desktop/DWIpipeline_testing/Data/100307/"
    output_path = "/Users/adso8337/Desktop/DWIpipeline_testing/output/"

    inputs = resolve_inputs(subject_dir)
    dwi_path = inputs["dwi_raw_mif"]

    wf = DwiPipeline(
        **inputs,
        eddy_options="' --slm=linear'",
        fod_algorithm=detect_shell_structure(dwi_path),
        start_time=datetime.datetime.now().isoformat(timespec="seconds"),
        cache_root=output_path,
    )
    result = wf(cache_root=output_path, rerun=True)
