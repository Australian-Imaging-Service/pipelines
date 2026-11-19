import typing as ty
import os
import shutil
from logging import getLogger
from fileformats.medimage import Nifti1
from fileformats.generic import File
from fileformats.text import TextFile
from pydra.compose import workflow, python
from pydra.tasks.mrtrix3.v3_1 import MrConvert
from pydra.tasks.fsl.v6 import EddyQuad


logger = getLogger(__name__)


@python.define(outputs=["bvecs"])
def SelectBvecs(eddy_rotated_bvecs: ty.Optional[File]) -> File:
    """Use eddy's rotated bvecs if available, otherwise fall back to the
    original bvecs file and emit a warning."""
    if eddy_rotated_bvecs is not None:
        return eddy_rotated_bvecs
    logger.warning(
        "eddy has not provided rotated bvecs file; using original gradient "
        "table. Recommend updating FSL eddy to version 5.0.9 or later."
    )
    return File("bvecs")


@python.define(outputs=["qc_dir"])
def GatherEddyQcAllOutputs(
    qc_json: ty.Optional[File],
    outlier_free_data: ty.Optional[Nifti1],
    cnr_maps: ty.Optional[Nifti1],
    residuals: ty.Optional[Nifti1],
    eddy_mask: File,
) -> str:
    """Copy additional eddy image outputs into the eddy_quad QC directory."""
    if qc_json is None:
        raise RuntimeError("EddyQuad did not produce the expected qc.json output")
    qc_dir = os.path.dirname(str(qc_json))
    for src, name in [
        (outlier_free_data, "eddy_outlier_free_data.nii.gz"),
        (cnr_maps, "eddy_cnr_maps.nii.gz"),
        (residuals, "eddy_residuals.nii.gz"),
    ]:
        if src is not None:
            shutil.copy(str(src), os.path.join(qc_dir, name))
    shutil.copy(str(eddy_mask), os.path.join(qc_dir, "eddy_mask.nii"))
    return qc_dir


@python.define(outputs=["qc_dir"])
def GetEddyQuadOutputDir(qc_json: ty.Optional[File]) -> str:
    """Return the eddy_quad output directory from the qc.json path."""
    if qc_json is None:
        raise RuntimeError("EddyQuad did not produce the expected qc.json output")
    return os.path.dirname(str(qc_json))


@workflow.define(outputs=["qc_dir"])
def Qc(
    eddy_base_name: str,
    eddy_idx_file: File,
    eddy_param_file: TextFile,
    bvals: File,
    eddy_mask: Nifti1,
    have_topup: bool,
    eddy_qc_all: bool = False,
    eddy_mporder: ty.Optional[int] = None,
    eddy_rotated_bvecs: ty.Optional[File] = None,
    eddy_outlier_free_data: ty.Optional[Nifti1] = None,
    eddy_cnr_maps: ty.Optional[Nifti1] = None,
    eddy_residuals: ty.Optional[Nifti1] = None,
    topup_field: ty.Optional[File] = None,
    slspec: ty.Optional[File] = None,
    dwi_post_eddy_crop: ty.Optional[ty.Tuple[int, str]] = None,
) -> str:
    """Run eddy QC using FSL's eddy_quad and gather outputs into a QC directory.

    Parameters
    ----------
    eddy_base_name : str
        Basename (including path) for EDDY output files.
    eddy_idx_file : File
        File containing indices for all volumes into acquisition parameters.
    eddy_param_file : File
        File containing acquisition parameters (acqp).
    bvals : File
        b-values file.
    eddy_mask : File
        Brain mask used in eddy.
    have_topup : bool
        Whether topup field estimation was performed; if True, axis padding was
        applied before eddy and image outputs need to be cropped back to their
        original dimensions using ``dwi_post_eddy_crop``.
    eddy_qc_all : bool
        Whether to include all eddy image outputs (outlier-free data, CNR maps,
        residuals, brain mask) in the QC directory.
    eddy_mporder : int, optional
        Slice-to-volume correction order used in eddy; if set, ``slspec`` is
        passed to eddy_quad.
    eddy_rotated_bvecs : File, optional
        b-vectors rotated by eddy to account for subject motion.  When absent
        the original b-vectors file is used and a warning is emitted.
    eddy_outlier_free_data : Nifti1, optional
        Eddy outlier-free image; required when ``eddy_qc_all`` is True.
    eddy_cnr_maps : Nifti1, optional
        Eddy CNR maps image; required when ``eddy_qc_all`` is True.
    eddy_residuals : Nifti1, optional
        Eddy squared-residuals image; required when ``eddy_qc_all`` is True.
    topup_field : File, optional
        Topup-estimated field in Hz; required when ``have_topup`` is True.
    slspec : File, optional
        Slice/group acquisition specification; required when ``eddy_mporder``
        is set.
    dwi_post_eddy_crop : tuple[int, str], optional
        Crop parameters (axis, range string) to undo the axis padding applied
        prior to eddy; required when ``have_topup`` is True and
        ``eddy_qc_all`` is True.

    Returns
    -------
    qc_dir : str
        Path to the QC output directory produced by eddy_quad.
    """

    select_bvecs = workflow.add(SelectBvecs(eddy_rotated_bvecs=eddy_rotated_bvecs))

    eddy_quad_kwargs: ty.Dict[str, ty.Any] = {}
    if have_topup:
        eddy_quad_kwargs["field"] = topup_field
    if eddy_mporder:
        eddy_quad_kwargs["slice_spec"] = slspec

    eddy_quad = workflow.add(
        EddyQuad(
            base_name=eddy_base_name,
            idx_file=eddy_idx_file,
            param_file=eddy_param_file,
            bval_file=bvals,
            mask_file=eddy_mask,
            bvec_file=select_bvecs.bvecs,
            **eddy_quad_kwargs,
        )
    )

    if eddy_qc_all:
        if have_topup:
            # Undo the axis padding that was applied before eddy so that image
            # outputs match the original image dimensions.
            export_outlier_free = workflow.add(
                MrConvert(
                    in_file=eddy_outlier_free_data,
                    coord=dwi_post_eddy_crop,
                )
            )
            export_cnr_maps = workflow.add(
                MrConvert(
                    in_file=eddy_cnr_maps,
                    coord=dwi_post_eddy_crop,
                )
            )
            export_residuals = workflow.add(
                MrConvert(
                    in_file=eddy_residuals,
                    coord=dwi_post_eddy_crop,
                )
            )
            export_eddy_mask = workflow.add(
                MrConvert(
                    in_file=eddy_mask,
                    coord=dwi_post_eddy_crop,
                )
            )
            outlier_free_qc = export_outlier_free.output
            cnr_maps_qc = export_cnr_maps.output
            residuals_qc = export_residuals.output
            eddy_mask_qc = export_eddy_mask.output
        else:
            outlier_free_qc = eddy_outlier_free_data
            cnr_maps_qc = eddy_cnr_maps
            residuals_qc = eddy_residuals
            eddy_mask_qc = eddy_mask

        gather_qc = workflow.add(
            GatherEddyQcAllOutputs(
                qc_json=eddy_quad.qc_json,
                outlier_free_data=outlier_free_qc,
                cnr_maps=cnr_maps_qc,
                residuals=residuals_qc,
                eddy_mask=eddy_mask_qc,
            )
        )
        qc_dir = gather_qc.qc_dir

    else:
        get_qc_dir = workflow.add(GetEddyQuadOutputDir(qc_json=eddy_quad.qc_json))
        qc_dir = get_qc_dir.qc_dir

    return qc_dir
