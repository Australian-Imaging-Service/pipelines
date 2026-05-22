"""PhantomKit pydra task wrapper for XNAT deployment.

Wraps ``phantomkit pipeline`` as a pydra Python task so that pydra2app +
frametree-xnat can drive it from an XNAT Container Service job.

The ``run_pipeline`` function is referenced by the spec at
``specs/australian-imaging-service/mri/quality-control/phantomkit.yaml``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pydra.compose import python


@python.define(outputs=["out_dir"])
def run_pipeline(
    input_dir: Path,
    phantom: str,
    out_dir: Path,
    denoise_degibbs: bool = False,
    gradcheck: bool = False,
    readout_time: float | None = None,
    eddy_options: str | None = None,
) -> Path:
    """Run the PhantomKit end-to-end phantom QA pipeline.

    Parameters
    ----------
    input_dir:
        Root directory containing DICOM acquisition subdirectories.
        Provided by frametree-xnat from the ``DicomData`` source defined
        in the pydra2app spec (``operates_on: medimage/session``).
    phantom:
        Phantom name matching a key in ``template_data/``
        (e.g. ``"SPIRIT"`` or ``"120E"``).
    out_dir:
        Output directory for QA reports and metric files. Managed by pydra.
    denoise_degibbs:
        Apply MRtrix3 dwidenoise + mrdegibbs before DWI preprocessing.
    gradcheck:
        Run MRtrix3 ``dwigradcheck`` to verify gradient table orientations.
    readout_time:
        Override the TotalReadoutTime (seconds) used by FSL topup/eddy.
    eddy_options:
        Override the FSL eddy options string passed to ``dwifslpreproc``.

    Returns
    -------
    Path
        The output directory containing all QA HTML reports and NIfTI files.
    """
    cmd: list[str] = [
        "phantomkit", "pipeline",
        "--input-dir", str(input_dir),
        "--output-dir", str(out_dir),
        "--phantom", phantom,
    ]
    if denoise_degibbs:
        cmd.append("--denoise-degibbs")
    if gradcheck:
        cmd.append("--gradcheck")
    if readout_time is not None:
        cmd.extend(["--readout-time", str(readout_time)])
    if eddy_options is not None:
        cmd.extend(["--eddy-options", eddy_options])

    subprocess.run(cmd, check=True)
    return out_dir
