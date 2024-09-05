import logging
import pydra.mark
import typing as ty
from .utils import extract_pe_scheme, axis2dir
from fileformats.medimage_mrtrix3 import ImageFormat as Mif

logger = logging.getLogger(__name__)


def strategy_identification_wf(slice_to_volume: bool):
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
        validate_num_encodings(
            in_image=wf.lzin.input, se_epi=wf.lzin.se_epi, name="num_encodings"
        )
    )

    if slice_to_volume:
        wf.add(validate_slice_timing(in_image=wf.lzin.input, name="slice_timing"))

    wf.set_output()

    return wf


# Get information on the input images, and check their validity
@pydra.mark.task
@pydra.mark.annotate(
    {"return": {"num_encodings": int, "num_slices": int, "pe_scheme": ty.List[ty.List[float]]}}
)
def validate_num_encodings(
    in_image: Mif, se_epi: Mif
) -> ty.Tuple[int, int, ty.List[ty.List[float]]]:
    if not len(in_image.dims()) == 4:
        raise RuntimeError(
            f"Input DWI must be a 4D image (found {in_image.dims()} dimensions)"
        )
    num_volumes = in_image.dims()[3]
    logger.debug("Number of DWI volumes: %s", num_volumes)
    num_slices = in_image.dims()[2]
    logger.debug("Number of DWI slices: %s", num_slices)
    if se_epi:
        # This doesn't necessarily apply any more: May be able to combine e.g. a P>>A from -se_epi with an A>>P b=0 image from the DWIs
        #  if not len(se_epi_header.size()) == 4:
        #    raise RuntimeError('File provided using -se_epi option must contain more than one image volume')
        se_epi_pe_scheme = extract_pe_scheme(se_epi)
    num_encodings = len(in_image.encoding.array)
    if not num_encodings == num_volumes:
        raise RuntimeError(
            f"Number of lines in gradient table ({len(num_encodings)}) "
            f") does not match input image ({num_volumes})"
            " volumes); check your input data"
        )
    return num_volumes, num_slices, se_epi_pe_scheme


@pydra.mark.task
@pydra.mark.annotate({"return": {"slice_encoding_axis": int}})
def validate_slice_timing(in_image: Mif) -> int:
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
    logger.debug(
        "Initial slice timing contents from header: " + str(slice_timing)
    )
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
