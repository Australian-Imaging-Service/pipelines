from fileformats.medimage import NiftiGz
from fileformats.generic import File
from pydra.compose import shell


@shell.define
class MriSynthstrip(shell.Task["MriSynthstrip.Outputs"]):
    """Robust, universal skull-stripping for brain images of any type.

    Examples
    --------

    >>> from pydra.tasks.fastsurfer.mri_synthstrip import MriSynthstrip

    References
    ----------

    SynthStrip: Skull-Stripping for Any Brain Image
    A Hoopes, JS Mora, AV Dalca, B Fischl, M Hoffmann
    NeuroImage 206 (2022), 119474
    https://doi.org/10.1016/j.neuroimage.2022.119474
    """

    executable = "mri_synthstrip"

    in_file: File = shell.arg(
        argstr="-i {in_file}",
        help="Input image to skullstrip",
    )
    gpu: bool = shell.arg(
        argstr="-g",
        help="Use the GPU",
        default=False,
    )
    border: int | None = shell.arg(
        argstr="-b {border}",
        help="Mask border threshold in mm (default: 1)",
        default=None,
    )
    threads: int | None = shell.arg(
        argstr="-t {threads}",
        help="PyTorch CPU threads (PyTorch default if unset)",
        default=None,
    )
    no_csf: bool = shell.arg(
        argstr="--no-csf",
        help="Exclude CSF from brain border",
        default=False,
    )
    model: File | None = shell.arg(
        argstr="--model {model}",
        help="Alternative model weights",
        default=None,
    )

    class Outputs(shell.Outputs):
        out_file: NiftiGz | None = shell.outarg(
            argstr="-o {out_file}",
            help="Stripped (brain-only) image",
            path_template="stripped.nii.gz",
            default=None,
        )
        mask_file: NiftiGz = shell.outarg(
            argstr="-m {mask_file}",
            help="Binary brain mask",
            path_template="brain_mask.nii.gz",
        )
        sdt_file: NiftiGz | None = shell.outarg(
            argstr="-d {sdt_file}",
            help="Signed distance transform",
            path_template="sdt.nii.gz",
            default=None,
        )
