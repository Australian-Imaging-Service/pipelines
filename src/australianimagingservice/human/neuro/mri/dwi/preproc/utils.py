from logging import getLogger
import typing as ty
from pydra.compose import python
from fileformats.vendor.mrtrix3.medimage import ImageIn, ImageFormat as Mif


logger = getLogger(__name__)


@python.define
def CalculateMrgridSpatialPadding(in_image: Mif) -> ty.List[ty.Tuple[int, str]]:
    padding = [(4 - (dim % 4)) % 4 for dim in in_image.dims()[0:3]]
    axis_args = [
        (axis_index, "0:%d" % pad_size)
        for axis_index, pad_size in enumerate(padding)
        if pad_size
    ]
    # TODO Does mrgrid need up to omit from command-line inputs any axes to which padding is not being applied?
    # Believe not
    return axis_args


def extract_pe_scheme(in_image: ImageIn) -> ty.Optional[ty.List[ty.List[float]]]:
    """Extract a phase-encoding scheme from a pre-loaded image header

    Parameters
    ----------
    in_image : ImageIn
        Image object

    Returns
    -------
    pe_scheme : list[list[float]] or None
        List of phase-encoding schemes, or None if the header doesn't specify the
        phase-encoding direction"""
    pe_scheme: ty.List[ty.List[float]]
    try:
        pe_scheme = in_image.metadata["pe_scheme"]
    except KeyError:
        try:
            pe_dir = in_image.metadata["PhaseEncodingDirection"]
        except KeyError:
            return None
        row = [float(value) for value in direction(pe_dir)]
        try:
            total_readout_time = in_image.metadata["TotalReadoutTime"]
        except KeyError:
            pass
        else:
            row.append(float(total_readout_time))
        num_volumes = 1 if len(in_image.dims()) < 4 else in_image.dims()[3]
        logger.debug("%s x %s rows", row, num_volumes)
        pe_scheme = [row] * num_volumes
    return pe_scheme


# From a user-specified string, determine the axis and direction of phase encoding
def direction(string: str) -> ty.List[int]:
    pe_dir: ty.List[int]
    try:
        pe_axis = abs(int(string))
        if pe_axis > 2:
            raise ValueError(
                "When specified as a number, phase encoding axis must be either 0, 1 or 2 (positive or negative)"
            )
        reverse = "-" in string  # Allow -0
        pe_dir = [0, 0, 0]
        if reverse:
            pe_dir[pe_axis] = -1
        else:
            pe_dir[pe_axis] = 1
    except ValueError:
        string = string.lower()
        if string == "lr":
            pe_dir = [1, 0, 0]
        elif string == "rl":
            pe_dir = [-1, 0, 0]
        elif string == "pa":
            pe_dir = [0, 1, 0]
        elif string == "ap":
            pe_dir = [0, -1, 0]
        elif string == "is":
            pe_dir = [0, 0, 1]
        elif string == "si":
            pe_dir = [0, 0, -1]
        elif string == "i":
            pe_dir = [1, 0, 0]
        elif string == "i-":
            pe_dir = [-1, 0, 0]
        elif string == "j":
            pe_dir = [0, 1, 0]
        elif string == "j-":
            pe_dir = [0, -1, 0]
        elif string == "k":
            pe_dir = [0, 0, 1]
        elif string == "k-":
            pe_dir = [0, 0, -1]
        else:
            raise ValueError("Unrecognized phase encode direction specifier: " + string)  # pylint: disable=raise-missing-from
    logger.debug(string + " -> " + str(pe_dir))
    return pe_dir


def axis2dir(string: str) -> ty.List[int]:
    """From a BIDS axis direction identifier, determine the axis and direction of phase
    encoding as a 3-vector"""
    if string == "i":
        direction = [1, 0, 0]
    elif string == "i-":
        direction = [-1, 0, 0]
    elif string == "j":
        direction = [0, 1, 0]
    elif string == "j-":
        direction = [0, -1, 0]
    elif string == "k":
        direction = [0, 0, 1]
    elif string == "k-":
        direction = [0, 0, -1]
    else:
        raise ValueError("Unrecognized NIfTI axis & direction specifier: " + string)
    logger.debug(string + " -> " + str(direction))
    return direction
