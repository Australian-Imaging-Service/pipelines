import json
from arcana.cli.deploy import build
from arcana.test.utils import show_cli_trace
from arcana.core.deploy.utils import load_yaml_spec
from arcana.test.stores.medimage.xnat import install_and_launch_xnat_cs_command


SKIP_BUILD = False


def test_bids_app(
    bids_app_blueprint, run_prefix, xnat_connect, license_dir, cli_runner
):

    bp = bids_app_blueprint

    build_dir = bp.spec_path.parent / ".build-test" / bp.spec_path.stem

    build_dir.mkdir(exist_ok=True, parents=True)

    if SKIP_BUILD:
        build_arg = "--generate-only"
    else:
        build_arg = "--build"

    result = cli_runner(
        build,
        [
            str(bp.spec_path),
            "pipelines-core-test",
            "--build_dir",
            str(build_dir),
            build_arg,
            "--use-test-config",
            "--use-local-packages",
            "--raise-errors",
            "--license-dir",
            str(license_dir),
        ],
    )

    assert result.exit_code == 0, show_cli_trace(result)

    spec = load_yaml_spec(bp.spec_path)

    for cmd_spec in spec["commands"]:

        cmd_name = cmd_spec["name"]

        with xnat_connect() as xlogin:

            with open(
                build_dir
                / cmd_spec["name"]
                / "xnat_commands"
                / (cmd_spec["name"] + ".json")
            ) as f:
                xnat_command = json.load(f)
            xnat_command["name"] = xnat_command["label"] = cmd_name + run_prefix

            test_xsession = next(
                iter(xlogin.projects[bp.project_id].experiments.values())
            )

            inputs_json = {}

            for inpt in cmd_spec["inputs"]:
                if (bids_app_blueprint.test_data / inpt["name"]).exists():
                    converter_args_path = (
                        bids_app_blueprint.test_data / inpt["name"] / "converter.json"
                    )
                    converter_args = ""
                    if converter_args_path.exists():
                        with open(converter_args_path) as f:
                            dct = json.load(f)
                        for name, val in dct.items():
                            converter_args += f" converter.{name}={val}"
                    inputs_json[inpt["name"]] = inpt["name"] + converter_args
                else:
                    inputs_json[inpt["name"]] = ""

            for pname, pval in bp.parameters.items():
                inputs_json[pname] = pval

            inputs_json['Arcana_flags'] = (
                "--plugin serial "
                "--work /work "  # NB: work dir moved inside container due to file-locking issue on some mounted volumes (see https://github.com/tox-dev/py-filelock/issues/147)
                "--dataset_name default "
                "--loglevel debug "
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

            # for deriv in blueprint.derivatives:
            #     assert list(test_xsession.resources[deriv.name].files) == deriv.filenames
