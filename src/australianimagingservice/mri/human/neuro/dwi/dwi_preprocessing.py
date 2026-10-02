from pathlib import Path

from pydra.compose import python, shell, workflow
from fileformats.generic import File, Directory
from fileformats.medimage import NiftiXBvec
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
    Dwi2Tensor,
    Tensor2Metric,
)
from australianimagingservice.mri.human.neuro.t1w.preprocess.mri_synthstrip import (
    MriSynthstrip,
)
from fileformats.vendor.mrtrix3.medimage import (  # noqa: F401
    ImageIn,
    ImageOut,
)

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


@python.define(outputs=["fslgrad"])
def SplitBvecBval(dwi: NiftiXBvec) -> tuple[File, File]:
    """Pull the adjacent FSL-style .bvec/.bval sidecar paths out of a
    NiftiXBvec bundle as a single (bvec, bval) tuple output, so they can be
    passed explicitly to MrConvert's fslgrad input, rather than relying on
    tools that only auto-detect them by co-located, same-basename convention.
    Must be a single combined output (not two separate ones) so downstream
    connects to one lazy field whose resolved value is the tuple itself,
    rather than a tuple of two still-unresolved lazy fields."""
    bvec = dwi.encoding
    bval = bvec.b_values_file
    return bvec, bval


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


@python.define(outputs=["out_file"])
def MeanBzero(in_file: File, out_file: str = "meanb0.mif.gz") -> File:
    """Return a single 3D mean-b0 volume from in_file, which may already be
    just one b0 volume (a bare 3D image, e.g. an rpe_pair companion that is
    itself b0-only) or a genuine multi-volume series containing a mix of b0
    and diffusion-weighted volumes. dwiextract -bzero requires >=4 dimensions
    and errors ("Expected input image to contain more than three dimensions")
    on a plain 3D volume, so branch on ndim rather than assuming multi-volume
    input -- confirmed by reproducing the real crash locally against real
    single-volume rpe_pair test data."""
    import subprocess
    import shutil
    from pathlib import Path

    ndim = int(
        subprocess.run(
            ["mrinfo", str(in_file), "-ndim"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    out_path = Path(out_file).absolute()
    if ndim < 4:
        shutil.copy(str(in_file), str(out_path))
    else:
        bzero_path = out_path.with_name(out_path.stem + "_bzero.mif.gz")
        subprocess.run(
            ["dwiextract", str(in_file), str(bzero_path), "-bzero", "-force", "-quiet"],
            check=True,
        )
        subprocess.run(
            ["mrmath", str(bzero_path), "mean", str(out_path), "-axis", "3", "-force", "-quiet"],
            check=True,
        )
    return out_path


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


@python.define(outputs=["out_dir"])
def FinalizeDwiOutputs(
    dwi_preprocessed: File,
    dwimask_preprocessed: File,
    response_wm: File,
    response_gm: File,
    response_csf: File,
    fa: ImageOut | bool | None,
    adc: ImageOut | bool | None,
    execution_log: str,
    cache_root: str = "",
) -> Directory:
    """Collect all DwiPreprocessing outputs into one structured output
    directory, mirroring all_parcs.py's FinalizeOutputs for the T1w pipeline
    (a single namespaced XNAT sink instead of flat, un-namespaced resources).

    execution_log is WritePreprocessingLog's log_file output: already a path
    to a written text file on disk (a plain str, not a File-typed field), so
    it's copied like the other outputs rather than needing write_text()."""
    import shutil
    from pathlib import Path

    out_dir = (
        Path(cache_root) / "dwi_preprocess"
        if cache_root
        else Path("./dwi_preprocess").absolute()
    )
    dwi_dir = out_dir / "DWI"
    response_dir = out_dir / "Response"
    for d in (dwi_dir, response_dir):
        d.mkdir(parents=True, exist_ok=True)

    shutil.copy(str(dwi_preprocessed), dwi_dir / "dwi_preprocessed.mif.gz")
    shutil.copy(str(dwimask_preprocessed), dwi_dir / "dwimask_preprocessed.mif.gz")
    shutil.copy(str(fa), dwi_dir / "FA.mif.gz")
    shutil.copy(str(adc), dwi_dir / "ADC.mif.gz")

    shutil.copy(str(response_wm), response_dir / "response_wm.txt")
    shutil.copy(str(response_gm), response_dir / "response_gm.txt")
    shutil.copy(str(response_csf), response_dir / "response_csf.txt")

    shutil.copy(str(execution_log), out_dir / "execution_log.txt")

    return Directory(out_dir)


# ── Main workflow ──────────────────────────────────────────────────────────────


@workflow.define(
    outputs=[
        "out_dir",
    ]
)
def DwiPreprocessing(
    dwi_raw: NiftiXBvec,
    pe_dir: str = "AP",
    rpe_mode: str = "rpe_none",
    rpe_file: NiftiXBvec | None = None,
    readout_time: float | None = None,
    eddy_options: str = "' --slm=linear'",
    fod_algorithm: str = "msmt_csd",
    start_time: str = "",
    cache_root: str = "",
) -> Directory:

    # ── Import NIfTI+bvec/bval into .mif with an embedded gradient table ────────
    # dwi_raw/rpe_file are DICOM-converted NiftiXBvec bundles (nii+bval+bvec+json),
    # not .mif — none of the mrtrix3 tools below discover gradients automatically
    # unless they're embedded in a .mif header, so import explicitly here rather
    # than relying on co-located-file auto-detection.
    dwi_grad = workflow.add(SplitBvecBval(dwi=dwi_raw), name="SplitBvecBval_dwi")
    dwi_raw_mif = workflow.add(
        MrConvert(
            in_file=dwi_raw,
            fslgrad=dwi_grad.fslgrad,
            out_file="dwi_raw.mif.gz",
            config=[],
        ),
        name="MrConvert_dwi_import",
    ).out_file

    # ── AP/PA preparation ──────────────────────────────────────────────────────
    se_epi_task_out = None

    if rpe_mode == "rpe_all":
        rpe_grad = workflow.add(SplitBvecBval(dwi=rpe_file), name="SplitBvecBval_rpe")
        rpe_file_mif = workflow.add(
            MrConvert(
                in_file=rpe_file,
                fslgrad=rpe_grad.fslgrad,
                out_file="rpe_raw.mif.gz",
                config=[],
            ),
            name="MrConvert_rpe_import",
        ).out_file
        dwicat_task = workflow.add(
            DwiCat(
                in_file1=dwi_raw_mif,
                in_file2=rpe_file_mif,
                out_file="dwi_AP_PA_concat.mif.gz",
            ),
            name="DwiCat_rpe_all",
        )
        dwi_prepared = dwicat_task.out_file

    elif rpe_mode == "rpe_pair":
        rpe_grad = workflow.add(SplitBvecBval(dwi=rpe_file), name="SplitBvecBval_rpe")
        rpe_file_mif = workflow.add(
            MrConvert(
                in_file=rpe_file,
                fslgrad=rpe_grad.fslgrad,
                out_file="rpe_raw.mif.gz",
                config=[],
            ),
            name="MrConvert_rpe_import",
        ).out_file
        fwd_b0_extract = workflow.add(
            DwiExtract(in_file=dwi_raw_mif, out_file="fwd_bzero.mif.gz", bzero=True, config=[]),
            name="DwiExtract_fwd_b0",
        )
        fwd_meanb0 = workflow.add(
            MrMath(
                in_file=fwd_b0_extract.out_file,
                out_file="fwd_meanb0.mif.gz",
                operation="mean",
                axis=3,
                config=[],
            ),
            name="MrMath_fwd_meanb0",
        )
        rpe_meanb0 = workflow.add(
            MeanBzero(in_file=rpe_file_mif, out_file="rpe_meanb0.mif.gz"),
            name="MeanBzero_rpe",
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
            config=[],
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
            config=[],
        ),
        name="MrConvert_grad",
    )

    # ── Step 3: Denoise ────────────────────────────────────────────────────────
    dwi_denoise_task = workflow.add(DwiDenoise(dwi=DWItoMif_task.out_file, config=[]))

    # ── Step 4: Gibbs ringing removal ─────────────────────────────────────────
    dwi_degibbs_task = workflow.add(MrDegibbs(in_=dwi_denoise_task.out, config=[]))

    # ── Step 5: Early b0 brain mask (eddy_mask) ───────────────────────────────
    early_b0_task = workflow.add(
        DwiExtract(
            in_file=dwi_degibbs_task.out,
            out_file="early_bzero.mif.gz",
            bzero=True,
            config=[],
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
            config=[],
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
        "config": [],
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
            config=[],
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
            config=[],
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
            config=[],
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
            config=[],
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
            config=[],
        ),
        name="MrGrid_crop_mask",
    )

    # ── Step 10: Response function estimation (native DWI space) ──────────────
    EstimateResponseFcn_task = workflow.add(
        Dwi2Response_Dhollander(
            in_file=crop_task_dwi.out_file,
            mask=crop_task_mask.out_file,
            voxels="voxels.mif.gz",
            config=[],
        )
    )

    # ── Step 11: Diffusion tensor + FA/ADC maps ────────────────────────────────
    dwi2tensor_task = workflow.add(
        Dwi2Tensor(
            dwi=crop_task_dwi.out_file,
            mask=crop_task_mask.out_file,
            dt="dwi_tensor.mif.gz",
            config=[],
        )
    )
    tensor2metric_task = workflow.add(
        Tensor2Metric(
            tensor=dwi2tensor_task.dt,
            mask=crop_task_mask.out_file,
            fa="FA.mif.gz",
            adc="ADC.mif.gz",
            config=[],
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

    finalize = workflow.add(
        FinalizeDwiOutputs(
            dwi_preprocessed=crop_task_dwi.out_file,
            dwimask_preprocessed=crop_task_mask.out_file,
            response_wm=EstimateResponseFcn_task.out_sfwm,
            response_gm=EstimateResponseFcn_task.out_gm,
            response_csf=EstimateResponseFcn_task.out_csf,
            fa=tensor2metric_task.fa,
            adc=tensor2metric_task.adc,
            execution_log=log_task.log_file,
            cache_root=cache_root,
        )
    )

    return finalize.out_dir
