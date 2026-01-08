import json
import itertools
import typing as ty
from anyio import Path
from fileformats.medimage import DicomDir
from pydra.utils.typing import TypeParser
from pydra2app.core.cli import make
from pydra2app.xnat import XnatApp
from frametree.core.utils import show_cli_trace
from pydra2app.xnat.deploy import install_and_launch_xnat_cs_command


SKIP_BUILD = True


def test_bids_app(
    bids_app_blueprint,
    run_prefix,
    xnat_connect: ty.Any,
    license_src: Path,
    cli_runner: ty.Any,
):

    bp = bids_app_blueprint

    build_dir = bp.spec_path.parent / ".build-test" / bp.spec_path.stem

    build_dir.mkdir(exist_ok=True, parents=True)

    if SKIP_BUILD:
        build_arg = "--generate-only"
    else:
        build_arg = "--build"

    licenses = [["--license", name, str(path)] for name, path in bp.licenses.items()]

    result = cli_runner(
        make,
        list(
            itertools.chain(
                [
                    "xnat",
                    str(bp.spec_path),
                    "--registry",
                    "pipelines-core-test",
                    "--build-dir",
                    str(build_dir),
                    build_arg,
                    "--for-localhost",
                    "--use-local-packages",
                    "--raise-errors",
                ],
                *licenses,
            )
        ),
    )

    assert result.exit_code == 0, show_cli_trace(result)

    image_spec = XnatApp.load(bp.spec_path)

    with xnat_connect() as xlogin:

        build_name = image_spec.name.split(".")[-1]

        with open(build_dir / "xnat_commands" / (build_name + ".json")) as f:
            xnat_command = json.load(f)
        xnat_command["name"] = xnat_command["label"] = image_spec.name + run_prefix

        test_xsession = next(iter(xlogin.projects[bp.project_id].experiments.values()))

        inputs_json = {}

        for src in image_spec.command().sources:
            if (bids_app_blueprint.test_data / src.name).exists():
                test_data = bids_app_blueprint.test_data / src.name
                converter_args_path = test_data / "converter.json"
                converter_args = ""
                if converter_args_path.exists():
                    with open(converter_args_path) as f:
                        dct = json.load(f)
                    for name, val in dct.items():
                        converter_args += f" converter.{name}={val}"
                input_file = TypeParser(src.type).coerce(list(test_data.iterdir()))
                if isinstance(input_file, DicomDir):
                    inpt = input_file.metadata["SeriesDescription"]
                else:
                    inpt = src.name
                inputs_json[src.name] = inpt + converter_args
            else:
                inputs_json[src.name] = ""

        for pname, pval in bp.parameters.items():
            inputs_json[pname] = pval

        inputs_json["pydra2app_flags"] = (
            "--worker debug "
            "--work /work "  # NB: work dir moved inside container due to file-locking issue on some mounted volumes (see https://github.com/tox-dev/py-filelock/issues/147)
            "--dataset-name default "
            "--logger frametree debug "
            "--logger pydra2app debug "
        )

        workflow_id, status, out_str = install_and_launch_xnat_cs_command(
            command_json=xnat_command,
            project_id=bp.project_id,
            session_id=test_xsession.id,
            inputs=inputs_json,
            xlogin=xlogin,
            timeout=30000,
        )
        assert status == "Complete", f"Workflow {workflow_id} failed.\n{out_str}"
