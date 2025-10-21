import typing as ty

from pydra.compose import python

from fileformats.medimage import NiftiGzX, DicomDir, DicomSeries
from pydra2app.core.command import ContainerCommand


@python.define(outputs=["out_file"])
def IdentityNiftiGzX(in_file: NiftiGzX) -> NiftiGzX:
    return in_file


def test_command_convertible_source_types() -> None:

    command_spec = ContainerCommand(
        name="identity",
        task=IdentityNiftiGzX,
        operates_on="samples/sample",
    )

    assert (
        command_spec.source("in_file").type == ty.Union[DicomDir, DicomSeries, NiftiGzX]
    )
