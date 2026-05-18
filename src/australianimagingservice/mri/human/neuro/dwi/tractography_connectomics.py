from pathlib import Path

from pydra.compose import python, shell, workflow
from fileformats.generic import File
from pydra.tasks.mrtrix3.v3_1 import (
    TransformConvert,
    MrTransform,
    MrConvert,
    DwiExtract,
    MrMath,
    Dwi2Fod,
    MtNormalise,
    TckGen,
    TckSift2,
    Tck2Connectome,
    TckMap,
)
from pydra.tasks.fsl.v6 import EpiReg
from fileformats.medimage_mrtrix3 import (
    ImageIn,
    ImageOut,
)  # noqa: F401

from dwi_preprocessing import MrcalcMax


# ── Custom shell task wrappers ─────────────────────────────────────────────────


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


# ── Python task definitions ────────────────────────────────────────────────────


@python.define(
    outputs=["t1_FSpath", "t1brain_FSpath", "wmseg_FSpath", "normimg_FSpath"]
)
def JoinTask(FS_dir: str):
    import os

    t1_FSpath = os.path.join(FS_dir, "mri", "T1.mgz")
    t1brain_FSpath = os.path.join(FS_dir, "mri", "brainmask.mgz")
    wmseg_FSpath = os.path.join(FS_dir, "mri", "wm.seg.mgz")
    normimg_FSpath = os.path.join(FS_dir, "mri", "norm.mgz")

    return t1_FSpath, t1brain_FSpath, wmseg_FSpath, normimg_FSpath


@python.define(outputs=["log_file"])
def WriteTractographyLog(
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
    response_source: str,
    response_wm_path: str,
    response_gm_path: str,
    response_csf_path: str,
    ftt_method: str,
    parcellation_image: str,
) -> str:
    """Write a plain-text execution log summarising tractography steps, all outputs,
    timing, resource usage, response function provenance, and any warnings."""
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

    task_warnings = []
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

    fod_step = (
        "Ss3tCsdBeta1 (ss3t_csd_beta1) — single-shell 3-tissue CSD"
        if fod_algorithm == "ss3t"
        else "Dwi2Fod (msmt_csd) — multi-shell multi-tissue CSD"
    )

    parcellation_name = Path(parcellation_image).name

    lines = [
        "=" * 60,
        "Tractography & Connectomics Pipeline — Execution Log",
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
        f"5TT method:    {ftt_method}",
        f"Parcellation:  {parcellation_name}",
        "",
        "Response functions used for FOD estimation:",
        f"  Source:  {response_source}",
        f"  WM:      {response_wm_path}",
        f"  GM:      {response_gm_path}",
        f"  CSF:     {response_csf_path}",
        "",
        "Steps executed:",
        "  1.  JoinTask / MrConvert — FreeSurfer .mgz → NIfTI",
        "  2.  DwiExtract / MrcalcMax / MrMath — mean b0 for registration",
        "  3.  MrcalcMax — WM binary mask for EpiReg",
        "  4.  EpiReg — DWI-to-T1 registration",
        "  5.  TransformConvert — FLIRT transform → MRtrix3 format",
        "  6.  MrTransform — apply transform + reslice DWI and mask to T1 space",
        f"  7.  {fod_step} — FOD estimation in T1 space",
        "  8.  MtNormalise — multi-tissue FOD normalisation",
        "  9.  TckGen (iFOD2) — probabilistic tractography",
        "  10. TckSift2 — streamline weight optimisation",
        "  11. TckMap (TDI) — track density image",
        "  12. TckMap (DEC-TDI) — directionally-encoded colour TDI",
        "  13. Tck2Connectome — structural connectivity matrix",
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

    pname = Path(parcellation_image).name
    for _ext in (".mif.gz", ".mif", ".nii.gz", ".nii"):
        if pname.endswith(_ext):
            pname = pname[: -len(_ext)]
            break
    log_name = f"pipeline_tractography_log_{pname}.txt"
    log_path = os.path.join(cache_root, log_name)
    with open(log_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return log_path


@python.define(outputs=["connectome_file"])
def CopyConnectome(
    connectome_in: File,
    output_dir: str,
    parcellation_stem: str,
) -> str:
    import shutil
    from pathlib import Path

    dest = Path(output_dir) / f"connectome_{parcellation_stem}.csv"
    shutil.copy2(str(connectome_in), str(dest))
    return str(dest)


# ── Utility functions ──────────────────────────────────────────────────────────


def resolve_tractography_inputs(
    preprocessed_dir: str,
    t1_dir: str,
    response_wm: str | None = None,
    response_gm: str | None = None,
    response_csf: str | None = None,
    ftt_method: str = "hsvs",
) -> dict:
    """
    Discover inputs for Tractography / Connectomics from the preprocessed DWI
    directory and the T1 processing directory.

    Args:
        preprocessed_dir: Output directory from DwiPreprocessing. Must contain
                          ``preprocessing_manifest.json`` written by that script.
        t1_dir: T1 processing directory containing 5TT images, parcellation images,
                and an FS_outputs/ subdirectory.
        response_wm: Optional path to a group-averaged WM response function (text file).
                     If provided together with response_gm and response_csf, these
                     override the subject-specific responses from preprocessed_dir.
                     FODs are always recalculated in T1 space using whichever responses
                     are selected.
        response_gm: Optional path to a group-averaged GM response function.
        response_csf: Optional path to a group-averaged CSF response function.
        ftt_method: 5TT algorithm — ``'hsvs'`` (default), ``'fsl'``, or
                    ``'freesurfer'``. Controls which 5TT/5TTvis images are selected.

    Returns:
        dict suitable for ``Tractography(**...)``.
        The key ``'_parcellations'`` holds a list of all parcellation image paths
        found in t1_dir — pop it and loop over them in ``__main__``.

    Response function selection:
        - All three user-provided  →  group-averaged responses used for FOD estimation
        - None provided            →  subject-specific responses from the manifest
        - 1 or 2 provided          →  ValueError raised

    Expected T1 directory layout::

        <t1_dir>/
            <id>_5TT_hsvs_*.mif.gz     (or fsl / freesurfer variants)
            <id>_5TTvis_*.mif.gz
            <id>_Parcellation_*.mif.gz  (one or more)
            FS_outputs/
    """
    import json

    root_preproc = Path(preprocessed_dir)
    root_t1 = Path(t1_dir)

    # ── Preprocessing manifest ─────────────────────────────────────────────────
    manifest_path = root_preproc / "preprocessing_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"preprocessing_manifest.json not found in {preprocessed_dir}. "
            "Run dwi_preprocessing.py first."
        )
    with open(manifest_path) as f:
        manifest = json.load(f)

    dwi_preprocessed = manifest["dwi_preprocessed"]
    dwimask_preprocessed = manifest["dwimask_preprocessed"]
    fod_algorithm = manifest["fod_algorithm"]

    # ── Response functions ─────────────────────────────────────────────────────
    provided = [response_wm, response_gm, response_csf]
    if all(r is not None for r in provided):
        wm_resp = response_wm
        gm_resp = response_gm
        csf_resp = response_csf
        response_source = "group-averaged (user-provided)"
        print("  Response functions: group-averaged (user-provided)")
        print(f"    WM:  {wm_resp}")
        print(f"    GM:  {gm_resp}")
        print(f"    CSF: {csf_resp}")
    elif any(r is not None for r in provided):
        raise ValueError(
            "Provide all three response functions (response_wm, response_gm, response_csf) "
            "or none. Providing a partial set is not supported."
        )
    else:
        wm_resp = manifest["response_wm"]
        gm_resp = manifest["response_gm"]
        csf_resp = manifest["response_csf"]
        response_source = "subject-specific (estimated by dwi_preprocessing.py)"
        print(f"  Response functions: subject-specific (from {preprocessed_dir})")
        print(f"    WM:  {wm_resp}")
        print(f"    GM:  {gm_resp}")
        print(f"    CSF: {csf_resp}")

    for label, path in [("WM", wm_resp), ("GM", gm_resp), ("CSF", csf_resp)]:
        if not Path(str(path)).exists():
            raise FileNotFoundError(f"{label} response function not found: {path}")

    # ── 5TT and 5TTvis images ──────────────────────────────────────────────────
    _ftt_patterns = {
        "hsvs": ["*5TT*hsvs*", "*hsvs*5TT*", "*_5TT_*.mif.gz"],
        "fsl": ["*5TT*fsl*", "*fsl*5TT*", "*_5TT_*.mif.gz"],
        "freesurfer": [
            "*5TT*freesurfer*",
            "*5TT*FS_*",
            "*freesurfer*5TT*",
            "*_5TT_*.mif.gz",
        ],
    }
    _fttvis_patterns = {
        "hsvs": ["*5TTvis*hsvs*", "*hsvs*5TTvis*", "*_5TTvis_*.mif.gz"],
        "fsl": ["*5TTvis*fsl*", "*fsl*5TTvis*", "*_5TTvis_*.mif.gz"],
        "freesurfer": ["*5TTvis*freesurfer*", "*5TTvis*FS_*", "*_5TTvis_*.mif.gz"],
    }

    def _first_match(root, patterns, label):
        for pat in patterns:
            matches = sorted(root.glob(pat))
            if matches:
                return str(matches[0])
        raise FileNotFoundError(
            f"Could not find {label} in {root} "
            f"(ftt_method={ftt_method!r}, tried: {', '.join(patterns)})"
        )

    ftt_key = ftt_method.lower()
    if ftt_key not in _ftt_patterns:
        raise ValueError(
            f"Unknown ftt_method {ftt_method!r}. Choose from: hsvs, fsl, freesurfer."
        )

    fTT_image = _first_match(
        root_t1, _ftt_patterns[ftt_key], f"5TT image ({ftt_method})"
    )
    fTTvis_image = _first_match(
        root_t1, _fttvis_patterns[ftt_key], f"5TTvis image ({ftt_method})"
    )

    print(f"  5TT method:  {ftt_method}")
    print(f"  5TT image:   {Path(fTT_image).name}")
    print(f"  5TTvis:      {Path(fTTvis_image).name}")

    # ── FreeSurfer outputs ─────────────────────────────────────────────────────
    fs_dir = root_t1 / "FS_outputs"
    if not fs_dir.is_dir():
        raise FileNotFoundError(f"FS_outputs directory not found in {t1_dir}")

    # ── Parcellation images ────────────────────────────────────────────────────
    parcellations = sorted(root_t1.glob("*_Parcellation_*.mif.gz"))
    if not parcellations:
        parcellations = sorted(root_t1.glob("*[Pp]arcellation*.mif.gz"))
    if not parcellations:
        raise FileNotFoundError(f"No parcellation images found in {t1_dir}")

    print(f"  Found {len(parcellations)} parcellation image(s):")
    for p in parcellations:
        print(f"    {p.name}")

    return {
        "dwi_preprocessed": dwi_preprocessed,
        "dwimask_preprocessed": dwimask_preprocessed,
        "FS_dir": str(fs_dir),
        "fTTvis_image_T1space": fTTvis_image,
        "fTT_image_T1space": fTT_image,
        "response_wm": wm_resp,
        "response_gm": gm_resp,
        "response_csf": csf_resp,
        "fod_algorithm": fod_algorithm,
        "response_source": response_source,
        "ftt_method": ftt_method,
        "_parcellations": [str(p) for p in parcellations],
    }


# ── Tractography workflow (runs once per subject) ──────────────────────────────


@workflow.define(
    outputs=[
        "DWI_T1space",
        "DWImask_T1space",
        "wm_fod_norm",
        "gm_fod_norm",
        "csf_fod_norm",
        "tracks",
        "out_mu",
        "out_weights",
        "TDI_file",
        "DECTDI_file",
    ]
)
def Tractography(
    dwi_preprocessed: File,
    dwimask_preprocessed: File,
    FS_dir: str,
    fTTvis_image_T1space: File,
    fTT_image_T1space: File,
    response_wm: File,
    response_gm: File,
    response_csf: File,
    fod_algorithm: str = "msmt_csd",
) -> tuple[File, File, File, File, File, File, File, File, File, File]:

    # ── Step 1: FreeSurfer path construction and .mgz → NIfTI ─────────────────
    join_task = workflow.add(JoinTask(FS_dir=FS_dir))

    nifti_t1brain = workflow.add(
        MrConvert(in_file=join_task.t1brain_FSpath, out_file="t1brain.nii.gz"),
        name="MrConvert_t1brain",
    )
    nifti_normimg = workflow.add(
        MrConvert(in_file=join_task.normimg_FSpath, out_file="normimg.nii.gz"),
        name="MrConvert_normimg",
    )

    # ── Step 2: Mean b0 for registration ──────────────────────────────────────
    extract_bzeroes_task = workflow.add(
        DwiExtract(
            in_file=dwi_preprocessed,
            out_file="bzero.mif.gz",
            bzero=True,
        )
    )
    mrcalc_max = workflow.add(
        MrcalcMax(
            in_file=extract_bzeroes_task.out_file,
            number=0.0,
            operand="max",
        ),
        name="MrcalcMax_b0",
    )
    meanb0_task = workflow.add(
        MrMath(
            in_file=mrcalc_max.output_image,
            out_file="dwi_meanbzero.nii.gz",
            operation="mean",
            axis=3,
        )
    )

    # ── Step 3: WM binary mask for EpiReg ─────────────────────────────────────
    mrcalc_wmbin = workflow.add(
        MrcalcMax(
            in_file=join_task.wmseg_FSpath,
            number=0.0,
            operand="gt",
        ),
        name="MrcalcMax_wmbin",
    )

    # ── Step 4: DWI → T1 registration ─────────────────────────────────────────
    epi_reg_task = workflow.add(
        EpiReg(
            epi=meanb0_task.out_file,
            t1_head=nifti_normimg.out_file,
            t1_brain=nifti_t1brain.out_file,
            wmseg=mrcalc_wmbin.output_image,
            out_base="epi2struct",
        )
    )

    # ── Step 5: Convert FLIRT transform to MRtrix3 format ─────────────────────
    transformconvert_task = workflow.add(
        TransformConvert(
            input_matrix=epi_reg_task.epi2str_mat,
            flirt_in=meanb0_task.out_file,
            flirt_ref=nifti_t1brain.out_file,
            operation="flirt_import",
            out_file="epi2struct_mrtrix.txt",
        )
    )

    # ── Step 6: Apply transform — reslice DWI and mask to T1 space ────────────
    transformDWI_task = workflow.add(
        MrTransform(
            in_file=dwi_preprocessed,
            inverse=False,
            out_file="DWI_T1space.mif.gz",
            linear=transformconvert_task.out_file,
            template=fTTvis_image_T1space,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_dwi",
    )

    transformDWImask_task = workflow.add(
        MrTransform(
            in_file=dwimask_preprocessed,
            inverse=False,
            out_file="DWImask_T1space.mif.gz",
            interp="nearest",
            linear=transformconvert_task.out_file,
            template=fTTvis_image_T1space,
            strides=fTTvis_image_T1space,
            reorient_fod="no",
        ),
        name="MrTransform_mask",
    )

    # ── Step 7: FOD estimation in T1 space ────────────────────────────────────
    if fod_algorithm == "ss3t":
        GenFod_task = workflow.add(
            Ss3tCsdBeta1(
                in_dwi=transformDWI_task.out_file,
                response_wm=response_wm,
                response_gm=response_gm,
                response_csf=response_csf,
                mask=transformDWImask_task.out_file,
            ),
            name="GenFod_T1space",
        )
        wm_fod = GenFod_task.wm_odf
        gm_fod = GenFod_task.gm_odf
        csf_fod = GenFod_task.csf_odf
    else:  # msmt_csd
        GenFod_task = workflow.add(
            Dwi2Fod(
                algorithm="msmt_csd",
                dwi=transformDWI_task.out_file,
                mask=transformDWImask_task.out_file,
                response_wm=response_wm,
                response_gm=response_gm,
                response_csf=response_csf,
            ),
            name="GenFod_T1space",
        )
        wm_fod = GenFod_task.fod_wm
        gm_fod = GenFod_task.fod_gm
        csf_fod = GenFod_task.fod_csf

    # ── Step 8: FOD normalisation ──────────────────────────────────────────────
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

    # ── Step 9: Probabilistic tractography ────────────────────────────────────
    tckgen_task = workflow.add(
        TckGen(
            source=NormFod_task.fod_wm_norm,
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

    # ── Step 10: SIFT2 streamline weight optimisation ─────────────────────────
    SIFT2_task = workflow.add(
        TckSift2(
            in_tracks=tckgen_task.tracks,
            in_fod=NormFod_task.fod_wm_norm,
            act=fTT_image_T1space,
            out_mu="mu.txt",
        )
    )

    # ── Steps 11–12: TDI maps ─────────────────────────────────────────────────
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

    return (
        transformDWI_task.out_file,
        transformDWImask_task.out_file,
        NormFod_task.fod_wm_norm,
        NormFod_task.fod_gm_norm,
        NormFod_task.fod_csf_norm,
        tckgen_task.tracks,
        SIFT2_task.out_mu,
        SIFT2_task.out_weights,
        TDImap_task.out_file,
        DECTDImap_task.out_file,
    )


# ── Connectomics workflow (runs once per parcellation) ─────────────────────────


@workflow.define(outputs=["connectome_out", "execution_log"])
def Connectomics(
    tracks: File,
    out_weights: File,
    out_mu: File,
    parcellation_image_T1space: File,
    parcellation_stem: str,
    DWI_T1space: File,
    DWImask_T1space: File,
    wm_fod_norm: File,
    gm_fod_norm: File,
    csf_fod_norm: File,
    TDI_file: File,
    DECTDI_file: File,
    fod_algorithm: str = "msmt_csd",
    response_source: str = "subject-specific (estimated by dwi_preprocessing.py)",
    response_wm_path: str = "",
    response_gm_path: str = "",
    response_csf_path: str = "",
    ftt_method: str = "hsvs",
    start_time: str = "",
    cache_root: str = "",
) -> tuple[File, str]:

    # ── Step 13: Structural connectivity matrix ────────────────────────────────
    connectomics_task = workflow.add(
        Tck2Connectome(
            tracks_in=tracks,
            tck_weights_in=out_weights,
            nodes_in=parcellation_image_T1space,
            symmetric=True,
            zero_diagonal=True,
        )
    )

    # ── Copy connectome to output directory with parcellation name ─────────────
    copy_task = workflow.add(
        CopyConnectome(
            connectome_in=connectomics_task.connectome_out,
            output_dir=cache_root,
            parcellation_stem=parcellation_stem,
        )
    )

    # ── Execution log ──────────────────────────────────────────────────────────
    log_task = workflow.add(
        WriteTractographyLog(
            start_time=start_time,
            cache_root=cache_root,
            DWI_T1space=DWI_T1space,
            DWImask_T1space=DWImask_T1space,
            wm_fod_norm=wm_fod_norm,
            gm_fod_norm=gm_fod_norm,
            csf_fod_norm=csf_fod_norm,
            TDI_file=TDI_file,
            DECTDI_file=DECTDI_file,
            connectome=copy_task.connectome_file,
            out_mu=out_mu,
            out_weights=out_weights,
            fod_algorithm=fod_algorithm,
            response_source=response_source,
            response_wm_path=response_wm_path,
            response_gm_path=response_gm_path,
            response_csf_path=response_csf_path,
            ftt_method=ftt_method,
            parcellation_image=str(parcellation_image_T1space),
        )
    )

    return (
        copy_task.connectome_file,
        log_task.log_file,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import datetime

    preprocessed_dir = "/Users/adso8337/Desktop/5TTmsmt_testing/outputs/BATMAN_preproc/"
    t1_dir = "/Users/adso8337/Desktop/5TTmsmt_testing/data/BATMAN_T1dir/"
    output_path = "/Users/adso8337/Desktop/5TTmsmt_testing/outputs/BATMAN_tractography/"

    inputs = resolve_tractography_inputs(
        preprocessed_dir=preprocessed_dir,
        t1_dir=t1_dir,
        # Uncomment to use group-averaged response functions instead of subject-specific.
        # All three must be provided together:
        # response_wm="/path/to/group_response_wm.txt",
        # response_gm="/path/to/group_response_gm.txt",
        # response_csf="/path/to/group_response_csf.txt",
        ftt_method="hsvs",  # options: 'hsvs', 'fsl', 'freesurfer'
    )

    parcellations = inputs.pop("_parcellations")
    start_time = datetime.datetime.now().isoformat(timespec="seconds")

    # ── Run tractography once ──────────────────────────────────────────────────
    print("Running tractography (registration · FOD · TckGen · SIFT2 · TDI)...")
    tract_wf = Tractography(
        dwi_preprocessed=inputs["dwi_preprocessed"],
        dwimask_preprocessed=inputs["dwimask_preprocessed"],
        FS_dir=inputs["FS_dir"],
        fTTvis_image_T1space=inputs["fTTvis_image_T1space"],
        fTT_image_T1space=inputs["fTT_image_T1space"],
        response_wm=inputs["response_wm"],
        response_gm=inputs["response_gm"],
        response_csf=inputs["response_csf"],
        fod_algorithm=inputs["fod_algorithm"],
    )
    tract_result = tract_wf(cache_root=output_path, rerun=True)

    # ── Run Tck2Connectome once per parcellation ───────────────────────────────
    for parcellation in parcellations:
        pname = Path(parcellation).name
        for _ext in (".mif.gz", ".mif", ".nii.gz", ".nii"):
            if pname.endswith(_ext):
                pname = pname[: -len(_ext)]
                break
        print(f"\nRunning connectomics: {pname}")
        con_wf = Connectomics(
            tracks=tract_result.tracks,
            out_weights=tract_result.out_weights,
            out_mu=tract_result.out_mu,
            parcellation_image_T1space=parcellation,
            parcellation_stem=pname,
            DWI_T1space=tract_result.DWI_T1space,
            DWImask_T1space=tract_result.DWImask_T1space,
            wm_fod_norm=tract_result.wm_fod_norm,
            gm_fod_norm=tract_result.gm_fod_norm,
            csf_fod_norm=tract_result.csf_fod_norm,
            TDI_file=tract_result.TDI_file,
            DECTDI_file=tract_result.DECTDI_file,
            fod_algorithm=inputs["fod_algorithm"],
            response_source=inputs["response_source"],
            response_wm_path=str(inputs["response_wm"]),
            response_gm_path=str(inputs["response_gm"]),
            response_csf_path=str(inputs["response_csf"]),
            ftt_method=inputs["ftt_method"],
            start_time=start_time,
            cache_root=output_path,
        )
        con_result = con_wf(cache_root=output_path, rerun=True)
