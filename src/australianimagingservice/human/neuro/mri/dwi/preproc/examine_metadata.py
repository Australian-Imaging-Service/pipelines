import logging
import typing as ty
import attrs
from pydra.compose import workflow, python
from .utils import extract_pe_scheme, axis2dir
from fileformats.vendor.mrtrix3.medimage import (
    ImageFormat as Mif,
    ImageFormatWithDwiEncoding as MifDwi,
)
from pydra.tasks.mrtrix3.v3_1 import MrInfo


logger = logging.getLogger(__name__)


@workflow.define(
    outputs=[
        "num_encodings",
        "slice_timings",
        "se_dims_match",
        "index_of_first_bzero",
        "volume_pairs",
    ]
)
def ExamineMetadata(
    input: Mif, se_epi: Mif, slice_to_volume: bool, bzero_threshold: float = 10.0
) -> tuple[int, ty.List[float], bool, int, ty.List[ty.Tuple[int, int]]]:

    examine_image_dims = workflow.add(ExamineImageDims(in_image=input, se_epi=se_epi))

    if slice_to_volume:
        examine_slice_timing = workflow.add(ExamineSliceEncoding(in_image=input))

    mrinfo_shell_bvalues = workflow.add(MrInfo(image_=input, shell_bvalues=True))
    mrinfo_shell_indices = workflow.add(MrInfo(image_=input, shell_indices=True))
    parse_mrinfo_output = workflow.add(
        ParseMrinfoOutput(
            mrinfo_shell_bvalues_out=mrinfo_shell_bvalues.stdout,
            mrinfo_shell_indices_out=mrinfo_shell_indices.stdout,
        )
    )

    match_rpe_pairs = workflow.add(
        FindFirstBzero(
            in_image=input,
            bzero_threshold=bzero_threshold,
            shell_bvalues=parse_mrinfo_output.shell_bvalues,
            shell_indices=parse_mrinfo_output.shell_indices,
        )
    )
    get_pe_scheme = workflow.add(mrinfo(image_=input, export_pe_table=True))
    determine_volume_pairs = workflow.add(
        DetermineVolumePairs(
            in_image=input,
            pe_scheme=get_pe_scheme.export_pe_table,
            bzero_threshold=bzero_threshold,
        )
    )

    return (
        examine_image_dims.num_encodings,
        examine_slice_encoding.slice_timings,
        num_encodings.se_dims_match,
        examine_diffusion_scheme.index_of_first_bzero,
        determine_volume_pairs.out,
    )


@python.define(outputs=["shell_bvalues", "shell_indices"])
def ParseMrinfoOutput(
    mrinfo_shell_bvalues_out: str, mrinfo_shell_indices_out: str
) -> ty.Tuple[ty.List[float], ty.List[ty.List[int]]]:
    """Extract shell bvalues from mrinfo output"""
    shell_bvalues = [float(value) for value in mrinfo_shell_bvalues_out.split()]
    shell_indices = [
        [int(i) for i in entry.split(",")] for entry in mrinfo_shell_indices_out.split()
    ]
    return shell_bvalues, shell_indices


# Get information on the input images, and check their validity
@python.define(
    outputs=[
        "num_encodings",
        "num_slices",
        "pe_scheme",
        "se_dims_match",
    ]
)
def ExamineImageDims(
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


@python.define(outputs=["axis", "direction", "timings"])
def ExamineSliceEncoding(
    in_image: Mif,
) -> ty.Tuple[int, ty.List[float], ty.List[float]]:
    axis = 2  # default if can't be found in header
    if "SliceEncodingDirection" in in_image.metadata:
        direction = in_image.metadata["SliceEncodingDirection"]
        logger.debug("Slice encoding direction: " + direction)
        if not direction.startswith("k"):
            raise ValueError(
                "DWI header indicates that 3rd spatial axis is not the slice axis; this is not yet compatible with --mporder option in eddy, nor supported in dwifslpreproc"
            )
        direction = axis2dir(direction)
    else:
        logger.info(
            "No slice encoding direction information present; assuming third axis corresponds to slices"
        )
        direction = [0, 0, 1]
    # slice_encoding_axis = slice_encoding_direction.index(1)
    # TODO: This will always be 2, since we're erroring out if it's not, could be changed
    # in future to allow for other directions by permuting the axes pre and post Eddy
    axis = [index for index, value in enumerate(direction) if value][0]
    timings = []
    # Since there's a chance that we may need to pad this info, we can't just copy this file
    #   to the scratch directory...
    if "SliceTiming" not in in_image.metadata:
        raise RuntimeError(
            "Cannot perform slice-to-volume correction in eddy: "
            "-eddy_slspec option not specified, and no slice timing information present in input DWI header"
        )
    timings = in_image.metadata["SliceTiming"]
    logger.debug("Initial slice timing contents from header: " + str(timings))
    if timings in ["invalid", "variable"]:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            'data flagged as "' + timings + '"'
        )
    try:
        timings = [float(entry) for entry in timings.split()]
    except ValueError as exception:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            "data are not numeric"
        ) from exception
    if len(timings) != in_image.dims()[axis]:
        raise RuntimeError(
            "Cannot use slice timing information in image header for slice-to-volume correction: "
            f"number of entries ({len(timings)}) does not match number of slices"
            f"({in_image.dims()[2]})"
        )
    return axis, direction, timings


@python.define(outputs=["index_of_first_bzero"])
def FindFirstBzero(
    in_image: MifDwi,
    bzero_threshold: float,
    shell_bvalues: ty.List[float],  # FIXME: Rob, these aren't being used
    shell_indices: ty.List[ty.List[int]],
) -> int:
    # Find the index of the first DWI volume that is a b=0 volume
    # This needs to occur at the outermost loop as it is pertinent information
    #   not only for the -align_seepi option, but also for when the -se_epi option
    #   is not provided at all, and the input to topup is extracted solely from the DWIs
    index_of_first_bzero = None
    for i, bval in enumerate(in_image.b_vals):
        if bval <= bzero_threshold:
            logger.debug("Index of first b=0 image in DWIs is %s" + i)
            index_of_first_bzero = i
            break
    if index_of_first_bzero is None:
        raise ValueError(
            "No b=0 images found in DWI series; cannot proceed with inhomogeneity field estimation. "
            f"threshold: {bzero_threshold}, bvals: {in_image.encoding.bvals}"
        )
    return index_of_first_bzero


@python.define(outputs=["index_of_first_bzero"])
def DetermineVolumePairs(
    in_image: Mif,
    bzero_threshold: float,
    pe_scheme: ty.List[ty.List[float]],  # FIXME: Rob, transition to use Eddy PE table
    shell_bvalues: ty.List[float],
    shell_indices: ty.List[ty.List[int]],
) -> ty.List[ty.Tuple[int, int]]:

    # For each volume index, store the index of the shell to which it is attributed
    #   (this will make it much faster to determine whether or not two volumes belong to the same shell)
    dwi_num_volumes = in_image.dims()[3]
    grad = in_image.encoding.grad
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
        logger.info(
            "Odd number of DWI volumes for reversed phase-encode combination, not able to pair"
        )
        return []
    else:
        # Determine whether or not volume recombination should be performed
        # This could be either due to use of -rpe_all option, or just due to the data provided with -rpe_header
        # Rather than trying to re-use the code that was used in the case of -rpe_all, run fresh code
        # The phase-encoding scheme needs to be checked also
        volume_matchings = [dwi_num_volumes] * dwi_num_volumes
        volume_pairs = []
        logger.debug(
            "Commencing gradient direction matching; "
            + str(dwi_num_volumes)
            + " volumes"
        )
        for index1 in range(dwi_num_volumes):
            if volume_matchings[index1] == dwi_num_volumes:  # As yet unpaired
                for index2 in range(index1 + 1, dwi_num_volumes):
                    if (
                        volume_matchings[index2] == dwi_num_volumes
                    ):  # Also as yet unpaired
                        # Here, need to check both gradient matching and reversed phase-encode direction
                        if not any(
                            grad[index1][i] + pe_scheme[index2][i] for i in range(0, 3)
                        ) and grads_match(index1, index2):
                            volume_matchings[index1] = index2
                            volume_matchings[index2] = index1
                            volume_pairs.append([index1, index2])
                            logger.debug(
                                "Matched volume %s with %s\nPhase encoding: %s %s\nGradients: %s %s",
                                index1,
                                index2,
                                pe_scheme[index1],
                                pe_scheme[index2],
                                grad[index1],
                                grad[index2],
                            )
                            break

        if not len(volume_pairs) == dwi_num_volumes / 2:
            logger.info(
                "Unable to determine complete matching DWI volume pairs for reversed phase-encode combination, not able to pair"
            )
            return []

    return volume_pairs
