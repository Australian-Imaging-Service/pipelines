from pathlib import Path

from pydra.compose import python, shell, workflow
from fileformats.generic import File
from pydra.tasks.mrtrix3.v3_1 import (
    DwiGradcheck,
    DwiDenoise,
    MrDegibbs,
    DwiFslpreproc,
    DwiBiascorrect_Ants,
    MrConvert,
    MrGrid,
    DwiExtract,
    MrMath,
    Dwi2Response_Dhollander,
)
from pydra.tasks.fastsurfer.mri_synthstrip import MriSynthstrip
from fileformats.medimage_mrtrix3 import (
    ImageIn,
    ImageOut,
)  # noqa: F401


# ── Custom shell task wrappers ─────────────────────────────────────────────────


@shell.define
class MrcalcMax(shell.Task):

    executable = "mrcalc"

    in_file: ImageIn = shell.arg(
        help="path to input image",
        argstr="{in_file}",
        position=-4,
    )
    number: float = shell.arg(
        help="threshold value",
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


# ── Python task definitions ────────────────────────────────────────────────────


@python.define(outputs=["grad_warning"])
def CheckGradientCorrection(in_file: File, corrected_grad_file: File) -> str:
    """Compare original DWI gradients with DwiGradcheck-corrected export.
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


@python.define(outputs=["manifest_file"])
def WritePreprocessingManifest(
    output_dir: str,
    dwi_preprocessed: File,
    dwimask_preprocessed: File,
    response_wm: File,
    response_gm: File,
    response_csf: File,
    fod_algorithm: str,
) -> str:
    """Write a JSON manifest to output_dir recording all preprocessing output paths.
    tractography_connectomics.py reads this manifest to locate script-1 outputs."""
    import json
    from pathlib import Path

    manifest = {
        "dwi_preprocessed": str(dwi_preprocessed),
        "dwimask_preprocessed": str(dwimask_preprocessed),
        "response_wm": str(response_wm),
        "response_gm": str(response_gm),
        "response_csf": str(response_csf),
        "fod_algorithm": fod_algorithm,
    }
    path = Path(output_dir) / "preprocessing_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return str(path)


@python.define(outputs=["log_file"])
def WritePreprocessingLog(
    start_time: str,
    cache_root: str,
    dwi_preprocessed: File,
    dwimask_preprocessed: File,
    response_wm: File,
    response_gm: File,
    response_csf: File,
    grad_warning: str,
    pe_dir: str,
    rpe_mode: str,
    eddy_options: str,
    fod_algorithm: str,
    dwifslpreproc_options: str = "",
) -> str:
    """Write a plain-text execution log summarising preprocessing steps, all outputs,
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
    elapsed_str = str(elapsed).split(".")[0]

    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    rss_bytes = usage.ru_maxrss
    if platform.system() != "Darwin":
        rss_bytes *= 1024
    peak_ram_gb = rss_bytes / (1024**3)
    cpu_user_s = usage.ru_utime
    cpu_sys_s = usage.ru_stime
    cpu_total_s = cpu_user_s + cpu_sys_s

    task_warnings = [f"DwiGradcheck: {grad_warning}"]

    cache_path = Path(cache_root)
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

    shell_label = (
        "single-shell (ss3t)" if fod_algorithm == "ss3t" else "multi-shell (msmt_csd)"
    )

    lines = [
        "=" * 60,
        "DWI Preprocessing Pipeline — Execution Log",
        "=" * 60,
        f"Start time:    {start_dt.isoformat(timespec='seconds')}",
        f"End time:      {end_dt.isoformat(timespec='seconds')}",
        f"Elapsed:       {elapsed_str}",
        "",
        f"Peak RAM:      {peak_ram_gb:.2f} GB",
        f"CPU time:      {cpu_total_s:.1f} s  "
        f"(user {cpu_user_s:.1f} s + sys {cpu_sys_s:.1f} s)",
        "",
        f"Shell structure:  {shell_label}",
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
        "  9.  MrGrid (crop) — crop DWI and mask to brain extent (native DWI resolution)",
        "  10. Dwi2Response_Dhollander — tissue response function estimation (native DWI space)",
        "",
        "Outputs:",
        f"  Preprocessed DWI:   {dwi_preprocessed}",
        f"  Preprocessed mask:  {dwimask_preprocessed}",
        f"  WM response:        {response_wm}",
        f"  GM response:        {response_gm}",
        f"  CSF response:       {response_csf}",
        "",
        "Warnings / messages:",
    ]
    for w in task_warnings:
        lines.append(f"  {w}")
    if not task_warnings:
        lines.append("  None")

    log_path = os.path.join(cache_root, "pipeline_preprocessing_log.txt")
    with open(log_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return log_path


# ── Utility functions ──────────────────────────────────────────────────────────


def detect_shell_structure(dwi_path: str) -> str:
    """Return 'ss3t' for single-shell data (b=0 + one non-zero shell) or
    'msmt_csd' for multi-shell data, by inspecting the DWI header with mrinfo."""
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


def detect_dwi_pe_and_mode(dwi_path: str) -> tuple[str, str]:
    """
    Infer PE direction and DwiFslpreproc mode from a DWI image.

    Detection order:
      1. Filename patterns (_AP_, _PA_, _LR_, _RL_, _SI_, _IS_)
      2. JSON sidecar PhaseEncodingDirection (for NIfTI inputs)
      3. mrinfo -petable on MIF header

    Returns (pe_dir, rpe_mode) where rpe_mode is one of
    'rpe_none', 'rpe_pair', 'rpe_all', 'rpe_header'.
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


def resolve_dwi_inputs(subject_dir: str) -> dict:
    """
    Discover DWI inputs from a subject directory.
    Returns a dict suitable for DwiPreprocessing(**resolve_dwi_inputs(...)).

    Only discovers DWI-related inputs (DWI image, RPE companion, PE direction).
    T1/FreeSurfer inputs are handled by resolve_tractography_inputs in
    tractography_connectomics.py.

    Expected layout::

        <subject_dir>/
            <id>_dwi_*.mif.gz          (or .nii.gz — AP/PA tagged or untagged)

    AP/PA classification rules (applied in priority order):
      1. Find all DWI candidates (files matching *dwi* or *DWI*).
      2. Group PE-tagged files by acquisition stem. Untagged files collected separately.
      3. If a complete FWD+RPE tagged pair exists AND FWD has non-zero bvals:
           - RPE is b0-only or unequal volumes  →  rpe_pair
           - Both non-zero bvals, equal volumes  →  rpe_all
      4. Else if an untagged DWI exists:
           - With RPE-tagged companion: classify as rpe_pair or rpe_all
           - No companion: pe_dir + rpe_mode from header
      5. Else fallback to any single PE-tagged file  →  rpe_none
    """
    import re
    import subprocess

    root = Path(subject_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Subject directory not found: {subject_dir}")

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
            return True

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

    dwi_candidates = sorted(
        {
            f
            for pat in ["*dwi*.mif.gz", "*DWI*.mif.gz", "*dwi*.nii.gz", "*DWI*.nii.gz"]
            for f in root.glob(pat)
        }
    )
    if not dwi_candidates:
        raise FileNotFoundError(f"No DWI image found in {subject_dir}")

    stem_map = {}
    untagged = []
    for f in dwi_candidates:
        pe = _get_pe(f.name)
        if pe:
            stem_map.setdefault(_strip_pe(f.name), {})[pe] = f
        else:
            untagged.append(f)

    dwi_raw_mif = None
    rpe_file = None
    pe_dir = "AP"
    rpe_mode = "rpe_none"

    def _classify_rpe_companion(fwd_path, rpe_path):
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
    for stem, pe_map in stem_map.items():
        fwds = {pe: p for pe, p in pe_map.items() if pe in _FWD}
        rpes = {pe: p for pe, p in pe_map.items() if pe in _RPE}
        if fwds and rpes:
            fwd_pe, fwd_path = next(iter(fwds.items()))
            _rpe_pe, rpe_path = next(iter(rpes.items()))
            if not _has_nonzero_bvals(str(fwd_path)):
                continue
            rpe_mode = _classify_rpe_companion(fwd_path, rpe_path)
            dwi_raw_mif = str(fwd_path)
            rpe_file = str(rpe_path)
            pe_dir = fwd_pe
            break

    # Phase 2: untagged DWI + optional RPE-tagged companion
    if dwi_raw_mif is None and untagged:
        main_dwi = (
            max(untagged, key=lambda f: _get_nvols(str(f)) or 0)
            if len(untagged) > 1
            else untagged[0]
        )
        dwi_raw_mif = str(main_dwi)
        all_rpe = [
            (pe, p) for sm in stem_map.values() for pe, p in sm.items() if pe in _RPE
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

    # Phase 3: fallback — single PE-tagged file
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

    return {
        "dwi_raw_mif": dwi_raw_mif,
        "rpe_file": rpe_file,
        "pe_dir": pe_dir,
        "rpe_mode": rpe_mode,
    }


# ── Main workflow ──────────────────────────────────────────────────────────────


@workflow.define(
    outputs=[
        "dwi_preprocessed",
        "dwimask_preprocessed",
        "response_wm",
        "response_gm",
        "response_csf",
        "execution_log",
    ]
)
def DwiPreprocessing(
    dwi_raw_mif: File,
    pe_dir: str = "AP",
    rpe_mode: str = "rpe_none",
    rpe_file: str | None = None,
    readout_time: float | None = None,
    eddy_options: str = "' --slm=linear'",
    fod_algorithm: str = "msmt_csd",
    start_time: str = "",
    cache_root: str = "",
) -> tuple[File, File, File, File, File, str]:

    # ── AP/PA preparation ──────────────────────────────────────────────────────
    se_epi_task_out = None

    if rpe_mode == "rpe_all":
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
        fwd_b0_extract = workflow.add(
            DwiExtract(in_file=dwi_raw_mif, out_file="fwd_bzero.mif.gz", bzero=True),
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
        rpe_b0_extract = workflow.add(
            DwiExtract(in_file=rpe_file, out_file="rpe_bzero.mif.gz", bzero=True),
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

    # ── Step 1: Gradient check ─────────────────────────────────────────────────
    DWIgradcheck_task = workflow.add(
        DwiGradcheck(
            in_file=dwi_prepared,
            export_grad_mrtrix="DWIgradcheck_grad.txt",
        )
    )

    grad_check_task = workflow.add(
        CheckGradientCorrection(
            in_file=dwi_prepared,
            corrected_grad_file=DWIgradcheck_task.export_grad_mrtrix,
        )
    )

    # ── Step 2: Reimport with corrected gradients ──────────────────────────────
    DWItoMif_task = workflow.add(
        MrConvert(
            in_file=dwi_prepared,
            grad=DWIgradcheck_task.export_grad_mrtrix,
        ),
        name="MrConvert_grad",
    )

    # ── Step 3: Denoise ────────────────────────────────────────────────────────
    dwi_denoise_task = workflow.add(DwiDenoise(dwi=DWItoMif_task.out_file))

    # ── Step 4: Gibbs ringing removal ─────────────────────────────────────────
    dwi_degibbs_task = workflow.add(MrDegibbs(in_=dwi_denoise_task.out))

    # ── Step 5: Early b0 brain mask (eddy_mask) ───────────────────────────────
    early_b0_task = workflow.add(
        DwiExtract(
            in_file=dwi_degibbs_task.out,
            out_file="early_bzero.mif.gz",
            bzero=True,
        ),
        name="DwiExtract_early",
    )
    early_b0_nonneg = workflow.add(
        MrcalcMax(in_file=early_b0_task.out_file, number=0.0, operand="max"),
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
        MriSynthstrip(in_file=early_meanb0_task.out_file),
        name="MriSynthstrip_early",
    )

    # ── Step 6: Motion and distortion correction ───────────────────────────────
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
    if rpe_mode != "rpe_header":
        _fslpreproc_kw["pe_dir"] = pe_dir
        if readout_time is not None:
            _fslpreproc_kw["readout_time"] = readout_time

    dwifslpreproc_task = workflow.add(DwiFslpreproc(**_fslpreproc_kw))

    # ── Step 7: Corrected b0 brain mask ───────────────────────────────────────
    preproc_b0_task = workflow.add(
        DwiExtract(
            in_file=dwifslpreproc_task.out_file,
            out_file="preproc_bzero.mif.gz",
            bzero=True,
        ),
        name="DwiExtract_preproc",
    )
    preproc_b0_nonneg = workflow.add(
        MrcalcMax(in_file=preproc_b0_task.out_file, number=0.0, operand="max"),
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
        MriSynthstrip(in_file=preproc_meanb0_task.out_file),
        name="MriSynthstrip_corrected",
    )

    # ── Step 8: Bias field correction ─────────────────────────────────────────
    dwibiasfieldcorr_task = workflow.add(
        DwiBiascorrect_Ants(
            in_file=dwifslpreproc_task.out_file,
            mask=corrected_synthstrip_task.mask_file,
            bias="biasfield.mif.gz",
        )
    )

    # ── Step 9: Crop DWI and mask to brain extent ──────────────────────────────
    crop_task_dwi = workflow.add(
        MrGrid(
            in_file=dwibiasfieldcorr_task.out_file,
            operation="crop",
            mask=corrected_synthstrip_task.mask_file,
            out_file="dwi_processed.mif.gz",
            uniform=-3,
        ),
        name="MrGrid_crop_dwi",
    )
    crop_task_mask = workflow.add(
        MrGrid(
            in_file=corrected_synthstrip_task.mask_file,
            operation="crop",
            mask=corrected_synthstrip_task.mask_file,
            out_file="dwimask_processed.mif.gz",
            interp="nearest",
            uniform=-3,
        ),
        name="MrGrid_crop_mask",
    )

    # ── Step 10: Response function estimation (native DWI space) ──────────────
    EstimateResponseFcn_task = workflow.add(
        Dwi2Response_Dhollander(
            in_file=crop_task_dwi.out_file,
            mask=crop_task_mask.out_file,
            voxels="voxels.mif.gz",
        )
    )

    # ── Write manifest (paths consumed by tractography_connectomics.py) ───────
    workflow.add(
        WritePreprocessingManifest(
            output_dir=cache_root,
            dwi_preprocessed=crop_task_dwi.out_file,
            dwimask_preprocessed=crop_task_mask.out_file,
            response_wm=EstimateResponseFcn_task.out_sfwm,
            response_gm=EstimateResponseFcn_task.out_gm,
            response_csf=EstimateResponseFcn_task.out_csf,
            fod_algorithm=fod_algorithm,
        )
    )

    # ── Execution log ──────────────────────────────────────────────────────────
    log_task = workflow.add(
        WritePreprocessingLog(
            start_time=start_time,
            cache_root=cache_root,
            dwi_preprocessed=crop_task_dwi.out_file,
            dwimask_preprocessed=crop_task_mask.out_file,
            response_wm=EstimateResponseFcn_task.out_sfwm,
            response_gm=EstimateResponseFcn_task.out_gm,
            response_csf=EstimateResponseFcn_task.out_csf,
            grad_warning=grad_check_task.grad_warning,
            pe_dir=pe_dir,
            rpe_mode=rpe_mode,
            eddy_options=eddy_options,
            fod_algorithm=fod_algorithm,
            dwifslpreproc_options=dwifslpreproc_options,
        )
    )

    return (
        crop_task_dwi.out_file,
        crop_task_mask.out_file,
        EstimateResponseFcn_task.out_sfwm,
        EstimateResponseFcn_task.out_gm,
        EstimateResponseFcn_task.out_csf,
        log_task.log_file,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import datetime

    subject_dir = "/Users/adso8337/Desktop/5TTmsmt_testing/data/BATMAN/"
    output_path = "/Users/adso8337/Desktop/5TTmsmt_testing/outputs/BATMAN_preproc/"

    inputs = resolve_dwi_inputs(subject_dir)
    dwi_path = inputs["dwi_raw_mif"]

    wf = DwiPreprocessing(
        **inputs,
        eddy_options="' --slm=linear'",
        fod_algorithm=detect_shell_structure(dwi_path),
        start_time=datetime.datetime.now().isoformat(timespec="seconds"),
        cache_root=output_path,
    )
    result = wf(cache_root=output_path, rerun=True)
