import typing as ty
from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from fileformats.generic import File
from pydra.compose import workflow, python
from pydra.tasks.mrtrix3.v3_1 import DwiRecon


@workflow.define(outputs=["output"])
def VolumeRecombination(
    in_file: Mif,
    operation: ty.Optional[str] = None,
    field: ty.Optional[Mif] = None,
    volume_pairs: ty.Optional[ty.List[ty.Tuple[int, int]]] = None,
) -> Mif:
    """Optionally perform explicit DWI volume recombination after eddy correction.

    Parameters
    ----------
    in_file : Mif
        Post-eddy DWI image (volumes already un-permuted and PE info embedded).
    operation : str, optional
        The dwirecon operation to apply; one of ``"combine_pairs"`` or
        ``"combine_predicted"``.  When ``None`` (e.g. ``pe_design`` is
        ``"None"`` or ``"Pair"``), no recombination is performed and the
        input image is returned unchanged.
    field : Mif, optional
        B0 field offset image in Hz from topup.  Required for
        ``"combine_predicted"``; recommended for ``"combine_pairs"``.
    volume_pairs : list of (int, int), optional
        Explicit list of ``(forward_index, reverse_index)`` volume pairs to
        combine.  When provided these are written to a text file and passed to
        ``dwirecon -pairs_in``, overriding automatic pair detection.  Only
        relevant for ``operation="combine_pairs"``.

    Returns
    -------
    output : Mif
        Recombined (or pass-through) DWI image.
    """
    if operation is None:
        # pe_design "None" or "Pair" — eddy correction only, no recombination.
        return in_file

    pairs_in: ty.Optional[File] = None
    if volume_pairs is not None:

        @python.define
        def WritePairsFile(
            volume_pairs: ty.List[ty.Tuple[int, int]],
        ) -> File:
            """Write an explicit volume-pairs list to a two-column text file
            for dwirecon -pairs_in."""
            import tempfile

            f = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            )
            for a, b in volume_pairs:
                f.write(f"{a} {b}\n")
            f.close()
            return File(f.name)

        write_pairs = workflow.add(WritePairsFile(volume_pairs=volume_pairs))
        pairs_in = write_pairs.out

    dwi_recon = workflow.add(
        DwiRecon(
            in_file=in_file,
            operation=operation,
            field=field,
            pairs_in=pairs_in,
        )
    )
    return dwi_recon.out_file
