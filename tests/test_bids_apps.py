import json
import typing as ty

from fileformats.medimage import DicomDir
from frametree.core.utils import show_cli_trace
from frametree.xnat import Xnat
from pydra.utils.typing import TypeParser
from frametree.core.cli import install_license, define
from pydra2app.core.cli import make
from pydra2app.xnat import XnatApp
from pydra2app.xnat.deploy import install_and_launch_xnat_cs_command

from conftest import BidsAppTestBlueprint


SKIP_BUILD = False

QUALIFIERS_FNAME = "qualifiers.json"


def test_bids_app(
    bids_app_blueprint: BidsAppTestBlueprint,
    run_prefix: str,
    xnat_connect: ty.Any,
    xnat_repository: Xnat,
    cli_runner: ty.Any,
):

    bp = bids_app_blueprint

    build_dir = bp.spec_path.parent / ".build-test" / bp.spec_path.stem

    build_dir.mkdir(exist_ok=True, parents=True)

    if SKIP_BUILD:
        build_arg = "--generate-only"
    else:
        build_arg = "--build"

    frameset_id = f"{xnat_repository.name}//{bp.project_id}"

    result = cli_runner(
        define,
        [
            frameset_id,
        ],
    )
    assert result.exit_code == 0, show_cli_trace(result)

    for lic_name, lic_path in bp.licenses.items():
        result = cli_runner(
            install_license,
            [
                lic_name,
                str(lic_path),
                frameset_id,
            ],
        )
        assert result.exit_code == 0, show_cli_trace(result)

    result = cli_runner(
        make,
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

        command = image_spec.command()
        for src in command.sources:
            if (bids_app_blueprint.test_data / src.name).exists():
                test_data = bids_app_blueprint.test_data / src.name
                # Optional qualifiers for the input, e.g.
                # {"converter": {...}, "criteria": {"required_metadata": {...}}},
                # which are needed to tell apart scans that share a series
                # description, e.g. the magnitude and phase-difference fieldmaps
                qualifiers: dict[str, dict[str, ty.Any]] = {}
                qualifiers_path = test_data / QUALIFIERS_FNAME
                if qualifiers_path.exists():
                    with open(qualifiers_path) as f:
                        qualifiers = json.load(f)
                input_file = TypeParser(src.type).coerce(
                    [p for p in test_data.iterdir() if p.name != QUALIFIERS_FNAME]
                )
                if isinstance(input_file, DicomDir):
                    inpt = input_file.metadata["SeriesDescription"]
                else:
                    inpt = src.name
                inputs_json[src.name] = command.format_qualifiers(inpt, qualifiers)
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
