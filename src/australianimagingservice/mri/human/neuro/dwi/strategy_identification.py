import logging
import typing as ty
import attrs
import pydra.mark
from .utils import extract_pe_scheme, axis2dir
from fileformats.medimage_mrtrix3 import ImageFormat as Mif
from pydra.tasks.mrtrix3 import mrinfo


logger = logging.getLogger(__name__)


def strategy_identification_wf(slice_to_volume: bool, bzero_threshold: float = 10.0):
    """Identify the strategy for DWI processing

    Parameters
    ----------

    Returns
    -------
    wf : pydra.Workflow
        Workflow object
    """

    wf = pydra.Workflow(
        name="strategy_identification_wf", input_spec=["input", "se_epi"]
    )

    wf.add(
        examine_image_dims(
            in_image=wf.lzin.input, se_epi=wf.lzin.se_epi, name="examine_image_dims"
        )
    )

    if slice_to_volume:
        wf.add(examine_slice_timing(in_image=wf.lzin.input, name="examine_slice_timing"))

    wf.add(
        mrinfo(image_=wf.lzin.input, shell_bvalues=True, name="mrinfo_shell_bvalues")
    )
    wf.add(
        mrinfo(image_=wf.lzin.input, shell_indices=True, name="mrinfo_shell_indices")
    )
    wf.add(
        parse_mrinfo_output(
            mrinfo_shell_bvalues_out=wf.mrinfo_shell_bvalues_out.lzout.stdout,
            mrinfo_shell_indices_out=wf.mrinfo_shell_indices_out.lzout.stdout,
            name="parse_mrinfo_output",
        )
    )

    wf.add(
        match_rpe_pairs(
            in_image=wf.lzin.input,
            bzero_threshold=bzero_threshold,
            shell_bvalues=wf.parse_mrinfo_output.lzout.shell_bvalues,
            shell_indices=wf.parse_mrinfo_output.lzout.shell_indices,
            name="match_rpe_pairs",
        )
    )

    wf.set_output(
        [("num_encodings", wf.examine_image_dims.lzout.num_encodings),
         ("se_dims_match", wf.num_encodings.lzout.se_dims_match)],
    )

    return wf


@pydra.mark.task
@pydra.mark.annotate(
    {
        "return": {
            "shell_bvalues": ty.List[float],
            "shell_indices": ty.List[ty.List[int]],
        }
    }
)
def parse_mrinfo_output(
    mrinfo_shell_bvalues_out: str, mrinfo_shell_indices_out
) -> ty.Tuple[ty.List[float], ty.List[ty.List[int]]]:
    """Extract shell bvalues from mrinfo output"""
    shell_bvalues = [float(value) for value in mrinfo_shell_bvalues_out.split()]
    shell_indices = [
        [int(i) for i in entry.split(",")] for entry in mrinfo_shell_indices_out.split()
    ]
    return shell_bvalues, shell_indices


# Get information on the input images, and check their validity
@pydra.mark.task
@pydra.mark.annotate(
    {
        "return": {
            "num_encodings": int,
            "num_slices": int,
            "pe_scheme": ty.List[ty.List[float]],
            "se_dims_match": bool,
        }
    }
)
def examine_image_dims(
    in_image: Mif, se_epi: Mif
) -> ty.Tuple[int, int, bool, ty.List[ty.List[float]]]:
    if not len(in_image.dims()) == 4:
        raise RuntimeError(
            f"Input DWI must be a 4D image (found {in_image.dims()} dimensions)"
        )
    num_volumes = in_image.dims()[3]
    logger.debug("Number of DWI volumes: %s", num_volumes)
    num_slices = in_image.dims()[2]
    logger.debug("Number of DWI slices: %s", num_slices)
    if se_epi is not attrs.NOTHING:
        # This doesn't necessarily apply any more: May be able to combine e.g. a P>>A from -se_epi with an A>>P b=0 image from the DWIs
        #  if not len(se_epi_header.size()) == 4:
        #    raise RuntimeError('File provided using -se_epi option must contain more than one image volume')
        se_epi_pe_scheme = extract_pe_scheme(se_epi)
        dims_match = (
            in_image.dims()[:3] == se_epi.dims()[:3]
            and in_image.vox_sizes()[:3] == se_epi.vox_sizes()[:3]
        )
    else:
        dims_match = False
        se_epi_pe_scheme = None
    num_encodings = len(in_image.encoding.array)
    if not num_encodings == num_volumes:
        raise RuntimeError(
            f"Number of lines in gradient table ({len(num_encodings)}) "
            f") does not match input image ({num_volumes})"
            " volumes); check your input data"
        )
    return num_volumes, num_slices, dims_match, se_epi_pe_scheme


@pydra.mark.task
@pydra.mark.annotate({"return": {"slice_encoding_axis": int}})
def examine_slice_timing(in_image: Mif) -> int:
    slice_encoding_axis = 2  # default if can't be found in header
    if "SliceEncodingDirection" in in_image.metadata:
        slice_encoding_direction = in_image.metadata["SliceEncodingDirection"]
        logger.debug("Slice encoding direction: " + slice_encoding_direction)
        if not slice_encoding_direction.startswith("k"):
            raise ValueError(
                "DWI header indicates that 3rd spatial axis is not the slice axis; this is not yet compatible with --mporder option in eddy, nor supported in dwifslpreproc"
            )
        slice_encoding_direction = axis2dir(slice_encoding_direction)
    else:
        logger.info(
            "No slice encoding direction information present; assuming third axis corresponds to slices"
        )
        slice_encoding_direction = [0, 0, 1]
    # slice_encoding_axis = slice_encoding_direction.index(1)
    # TODO: This will always be 2, since we're erroring out if it's not, could be changed
    # in future to allow for other directions by permuting the axes pre and post Eddy
    slice_encoding_axis = [
        index for index, value in enumerate(slice_encoding_direction) if value
    ][0]
    slice_timing = []
    # Since there's a chance that we may need to pad this info, we can't just copy this file
    #   to the scratch directory...
    if "SliceTiming" not in in_image.metadata:
        raise RuntimeError(
            "Cannot perform slice-to-volume correction in eddy: "
            "-eddy_slspec option not specified, and no slice timing information present in input DWI header"
        )
    slice_timing = in_image.metadata["SliceTiming"]
    logger.debug("Initial slice timing contents from header: " + str(slice_timing))
    if slice_timing in ["invalid", "variable"]:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            'data flagged as "' + slice_timing + '"'
        )
    try:
        slice_timing = [float(entry) for entry in slice_timing.split()]
    except ValueError as exception:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            "data are not numeric"
        ) from exception
    if len(slice_timing) != in_image.dims()[slice_encoding_axis]:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            f"number of entries ({len(slice_timing)}) does not match number of slices"
            f"({in_image.dims()[2]})"
        )
    return slice_encoding_axis


@pydra.mark.task
def match_rpe_pairs(
    in_image: Mif,
    bzero_threshold: float,
    shell_bvalues: ty.List[float],
    shell_indices: ty.List[ty.List[int]],
) -> ty.List[ty.Tuple[int, int]]:
    # For each volume index, store the index of the shell to which it is attributed
    #   (this will make it much faster to determine whether or not two volumes belong to the same shell)
    dwi_num_volumes = in_image.dims()[3]
    grad = in_image.encoding.array
    vol2shell = [-1] * dwi_num_volumes
    for index, volumes in enumerate(shell_indices):
        for volume in volumes:
            vol2shell[volume] = index
    assert all(index >= 0 for index in vol2shell)

    def grads_match(one, two):
        # Are the two volumes assigned to different b-value shells?
        if vol2shell[one] != vol2shell[two]:
            return False
        # Does this shell correspond to b=0?
        if shell_bvalues[vol2shell[one]] <= bzero_threshold:
            return True
        # Dot product between gradient directions
        # First, need to check for zero-norm vectors:
        # - If both are zero, skip this check
        # - If one is zero and the other is not, volumes don't match
        # - If neither is zero, test the dot product
        if any(grad[one][0:3]):
            if not any(grad[two][0:3]):
                return False
            dot_product = (
                grad[one][0] * grad[two][0]
                + grad[one][1] * grad[two][1]
                + grad[one][2] * grad[two][2]
            )
            if abs(dot_product) < 0.999:
                return False
        elif any(grad[two][0:3]):
            return False
        return True

        if dwi_num_volumes % 2:
            raise RuntimeError(
                "Input DWI contains odd number of volumes; "
                "cannot possibly pair up volumes for reversed phase-encode direction combination"
            )
        grads_matched = [dwi_num_volumes] * dwi_num_volumes
        grad_pairs = []
        logger.debug(
            "Commencing gradient direction matching; "
            + str(dwi_num_volumes)
            + " volumes"
        )
        for index1 in range(int(dwi_num_volumes / 2)):
            if grads_matched[index1] == dwi_num_volumes:  # As yet unpaired
                for index2 in range(int(dwi_num_volumes / 2), dwi_num_volumes):
                    if grads_matched[index2] == dwi_num_volumes:  # Also as yet unpaired
                        if grads_match(index1, index2):
                            grads_matched[index1] = index2
                            grads_matched[index2] = index1
                            grad_pairs.append((index1, index2))
                            logger.debug(
                                f"Matched volume {index1} with {index2} : {grad[index1]} {grad[index2]}"
                            )
                            break
                else:
                    raise RuntimeError(
                        "Unable to determine matching reversed phase-encode direction volume for DWI volume "
                        + str(index1)
                    )
        if not len(grad_pairs) == dwi_num_volumes / 2:
            raise RuntimeError(
                "Unable to determine complete matching DWI volume pairs for reversed phase-encode combination"
            )

        return grad_pairs
