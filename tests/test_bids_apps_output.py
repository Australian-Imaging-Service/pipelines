import json
import typing as ty
from pathlib import Path
from types import SimpleNamespace

from frametree.bids.store import Bids
from pydra.utils import get_fields
from pydra.utils.typing import TypeParser, optional_type
from pydra2app.xnat import XnatApp

SKIP_BUILD = True

PKG_DIR = Path(__file__).parent.parent

FREESURFER_LICENSE_PATH = Path(
    PKG_DIR / "tests" / "data" / "output" / "frmiprepunittest"
)


def test_bids_app_output(
    bids_app_blueprint,
    cli_runner: ty.Any,
):

    bp = bids_app_blueprint

    image_spec = XnatApp.load(bp.spec_path)

    command = image_spec.commands[0]

    task = command.task()
    fields = get_fields(task)

    for src in image_spec.command().sources:
        if (bp.test_data / src.name).exists():
            test_data = bp.test_data / src.name
            fspaths = list(test_data.iterdir())
            input_file = TypeParser(src.type).coerce(fspaths)
            field_type = optional_type(fields[src.field].type)
            converter_json = test_data / "converter.json"
            if converter_json in fspaths:
                with open(converter_json) as f:
                    kwargs = json.load(f)
            else:
                kwargs = {}
            converted = field_type.convert(input_file, **kwargs)
            setattr(task, src.field, converted)

    outputs_dir = (
        PKG_DIR / "tests" / "data" / "output" / "specific-cases" / bp.test_data.name
    )

    # Stand-in for the pickled job, which can only be loaded by the Python version that
    # wrote it, as _from_job only needs its cache directory and frameset
    frameset = Bids().load_frameset(str(outputs_dir / "bids-dataset"), "DEFAULT")
    job = SimpleNamespace(cache_dir=outputs_dir, return_values={"frameset": frameset})

    task.Outputs._from_job(job)
