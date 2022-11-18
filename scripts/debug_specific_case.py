from pathlib import Path
from datetime import datetime
import json
import re
import xnat
import shutil
import shlex
import tempfile
import click
from click.testing import CliRunner
import xnat4tests
from arcana.test.utils import show_cli_trace
from arcana.cli.deploy import run_in_image
from arcana.test.stores.medimage.xnat import (
    install_and_launch_xnat_cs_command,
    XnatViaCS,
)
from arcana.core.deploy.image import ContainerImageSpec
from arcana.deploy.medimage.xnat import (
    build_xnat_cs_image,
    dockerfile_build,
    generate_xnat_cs_command,
)


def xnat_connect(in_docker):
    if in_docker:
        xlogin = xnat.connect(
            server="http://host.docker.internal:8080",
            user=xnat4tests.config["xnat_user"],
            password=xnat4tests.config["xnat_password"],
        )
    else:
        xlogin = xnat4tests.connect()
    return xlogin


def build_image(
    pkg_dir, spec_path, image_tag, build_dir, license_src, pipelines_core_docker_dest
):

    spec = load_yaml_spec(spec_path, base_dir=spec_path)

    spec = {k: v for k, v in spec.items() if not k.startswith("_")}
    python_packages = spec["python_packages"] = spec.get("python_packages", [])
    python_packages.append({"name": "pydra"})
    python_packages.append({"name": "pydra-dcm2niix"})

    dockerfile, _ = build_xnat_cs_image(
        image_tag=image_tag,
        build_dir=build_dir,
        use_local_packages=True,
        test_config=True,
        license_src=license_src,
        arcana_install_extras=["test"],
        generate_only=True,
        **spec,
    )

    pkg_build_path = copy_sdist_into_build_dir(pkg_dir, build_dir)
    dockerfile.copy(
        source=[str(pkg_build_path.relative_to(build_dir))],
        destination=str(pipelines_core_docker_dest),
    )

    dockerfile_build(dockerfile, build_dir, image_tag)


def upload_data(project_id, subject_label, session_label, data_dir, in_docker=False):
    """
    Creates dataset for each entry in dataset_structures
    """

    with xnat_connect(in_docker) as login:
        if project_id in login.projects:
            return
        login.put(f"/data/archive/projects/{project_id}")

    with xnat_connect(in_docker) as login:
        xproject = login.projects[project_id]
        xclasses = login.classes
        xsubject = xclasses.SubjectData(label=subject_label, parent=xproject)
        xsession = xclasses.MrSessionData(label=session_label, parent=xsubject)
        for scan_path in data_dir.iterdir():
            if scan_path.name.startswith("."):
                continue  # skip hidden files
            # Create scan
            xscan = xclasses.MrScanData(
                id=scan_path.stem, type=scan_path.stem, parent=xsession
            )

            for resource_path in scan_path.iterdir():
                # Create the resource
                xresource = xscan.create_resource(resource_path.stem)
                # Create the dummy files
                xresource.upload_dir(resource_path, method="tar_file")
        login.put(f"/data/experiments/{xsession.id}?pullDataFromHeaders=true")
        for xscan in xsession.scans.values():
            xscan.type = xscan.series_description


def run_pipeline_in_container_service(
    build_dir, spec_path, command_index, run_prefix, project_id, inputs_json
):
    spec = load_yaml_spec(spec_path)
    cmd_spec = spec["commands"][command_index]
    cmd_name = cmd_spec["name"]

    with xnat_connect(in_docker=False) as xlogin:

        with open(build_dir / "xnat_commands" / (cmd_spec["name"] + ".json")) as f:
            xnat_command = json.load(f)
        xnat_command["name"] = xnat_command["label"] = cmd_name + run_prefix

        test_xsession = next(iter(xlogin.projects[project_id].experiments.values()))

        workflow_id, status, out_str = install_and_launch_xnat_cs_command(
            command_json=xnat_command,
            project_id=project_id,
            session_id=test_xsession.id,
            inputs=inputs_json,
            xlogin=xlogin,
            timeout=30000,
        )
        assert status == "Complete", f"Workflow {workflow_id} failed.\n{out_str}"


def run_pipeline_directly(
    spec_path,
    command_index,
    image_tag,
    project_id,
    inputs_json,
    subject_label,
    session_label,
    arcana_flags,
    configuration,
    in_docker=False,
):
    spec = load_yaml_spec(spec_path)
    cmd_spec = spec["commands"][command_index]

    if in_docker:
        with open(Path("/xnat_commands") / (cmd_spec["name"] + ".json")) as f:
            xnat_command = json.load(f)
    else:
        cmd_spec["configuration"].update(configuration)
        xnat_command = generate_xnat_cs_command(
            image_tag=image_tag, info_url="http://some.url", **cmd_spec
        )

    cmdline = xnat_command["command-line"].split("run-arcana-pipeline")[-1]

    # Do XNAT replacements
    cmdline = cmdline.replace("[PROJECT_ID]", project_id)
    cmdline = cmdline.replace("#ARCANA_FLAGS#", arcana_flags)
    cmdline = cmdline.replace("[SUBJECT_LABEL]", subject_label)
    cmdline = cmdline.replace("[SESSION_LABEL]", session_label)

    for inpt in cmd_spec["inputs"]:
        inpt_name = inpt["name"]
        cmdline = cmdline.replace(
            f"[{inpt_name.upper()}_INPUT]", f"{inputs_json.get(inpt_name, '')}"
        )

    for param in cmd_spec["parameters"]:
        param_name = param["name"]
        cmdline = cmdline.replace(
            f"[{param['task_field'].upper()}_PARAM]", f"{inputs_json.get(param_name, '')}"
        )

    assert not re.findall(r'\[(\w+)_(?:INPUT|PARAM)\]', cmdline)

    cmd_args = shlex.split(cmdline)

    cmd_args.append("--raise-errors")

    runner = CliRunner()
    result = runner.invoke(run_pipeline, cmd_args, catch_exceptions=False)

    assert result.exit_code == 0, show_cli_trace(result)


@click.command(
    help="""Debug a pipeline run on a specific session

RELATIVE_SPEC PATH is a path to pipeline spec, from main specs dir

TEST_DATA_DIR is name of sub-directory in '<PKG-DIR>/tests/data/specific-cases'
dir containing test scan data. The scan data must be in placed resource
sub-directories under directories named by the scans ID (e.g. '4/DICOM',
'5/DICOM', '7/NIFTI'). A new session will be created in the test XNAT instance
using this label"""
)
@click.argument("relative_spec_path", type=str)
@click.argument("test_data_dir", type=str)
@click.option(
    "--input",
    nargs=2,
    multiple=True,
    metavar="<name> <value>",
    help=("Inputs to be provided to command"),
)
@click.option(
    "--command-index",
    default=0,
    type=int,
    help="The index of the command in the spec to run",
)
@click.option(
    "--run-directly/--run-in-cs",
    type=bool,
    default=False,
    help=(
        "Whether the test is being run via the XNAT container service or not. "
        "If 'run-in-cs', then the pipeline will be launched "
        "via the container service. If 'run-directly', then the "
        "pipeline will be run as-if it was launched by the "
        "container service, but by directly calling the command "
        "so that it can be debugged"
    ),
)
@click.option(
    "--in-docker/--out-of-docker",
    type=bool,
    default=False,
    help=(
        "Whether to access XNAT from host.docker.internal because "
        "this script is being run inside a container"
    ),
)
@click.option(
    "--build",
    default="yes",
    type=click.Choice(["yes", "no", "only"]),
    help="Whether to just build the image instead of build and running",
)
@click.option(
    "--arcana-flags",
    type=str,
    default=None,
    help="Any flags to pass to Arcana run command",
)
@click.option(
    "--configuration",
    type=str,
    multiple=True,
    nargs=2,
    metavar="<name> <val>",
    help=("Configuration arguments to override when running directly " "out of docker"),
)
def run(
    relative_spec_path,
    test_data_dir,
    input,
    command_index,
    run_directly,
    in_docker,
    build,
    configuration,
    arcana_flags,
):

    xnat4tests_config = xnat4tests.Config()

    # Root package dir
    pkg_dir = Path(__file__).parent.parent

    spec_path = pkg_dir / "specs" / relative_spec_path
    data_dir = pkg_dir / "tests" / "data" / "specific-cases" / test_data_dir
    inputs_json = dict(input)

    # Relative directories
    image_tag = "pipelines-core-specific-test/" + spec_path.stem
    license_src = pkg_dir / "licenses"
    build_dir = pkg_dir / "scripts" / ".build" / "specific-test-case"
    build_dir.mkdir(exist_ok=True, parents=True)
    run_prefix = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
    project_id = run_prefix + data_dir.stem  # f'{run_prefix}_{spec_path.stem}_specific'
    pipelines_core_docker_dest = Path("/python-packages/pipelines-core")
    session_label = "testsession"
    subject_label = "testsubj"

    if run_directly and not in_docker:
        output_dir = pkg_dir / "tests" / "output" / "specific-cases" / test_data_dir
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        xnat_cs = XnatViaCS(
            row_id=session_label,
            input_mount=(
                xnat4tests_config.xnat_root_dir,
                / "archive"
                / project_id
                / "arc001"
                / session_label
            ),
            output_mount=output_dir / "xnat-cs-output",
            server=xnat4tests.config["xnat_uri"],
            user=xnat4tests.config["xnat_user"],
            password=xnat4tests.config["xnat_password"],
            cache_dir=output_dir / "cache-dir",
        )
        xnat_cs.save("xnat-cs")

    if not arcana_flags:
        arcana_flags = "--plugin serial --dataset-name default --loglevel debug"
        if run_directly and not in_docker:
            work_dir = str(output_dir / "work")
            export_work_dir = tempfile.mkdtemp()
            arcana_flags += f" --work /{work_dir} --export-work {export_work_dir}"

    if not run_directly:
        if build != "no":
            build_image(
                pkg_dir,
                spec_path,
                image_tag,
                build_dir,
                license_src,
                pipelines_core_docker_dest,
            )
    xnat4tests.launch_xnat()
    upload_data(project_id, subject_label, session_label, data_dir, in_docker=in_docker)
    if build != "only":
        if run_directly:
            run_pipeline_directly(
                spec_path,
                command_index,
                image_tag,
                project_id,
                inputs_json,
                subject_label,
                session_label,
                arcana_flags,
                configuration,
                in_docker=in_docker,
            )
        else:
            run_pipeline_in_container_service(
                build_dir, spec_path, command_index, run_prefix, project_id, inputs_json
            )


if __name__ == "__main__":
    run()

# Example VSCode launch configuration to run the fmriprep BIDS app on the
# 'FTD1684' session (which has to be manually placed in the gitignored directory)
# <PKG-DIR>/tests/data/specific-cases/)
#
# {
#     "name": "Python: specific test case",
#     "type": "python",
#     "request": "launch",
#     "program": "${workspaceFolder}/scripts/debug_specific_case.py",
#     "console": "integratedTerminal",
#     "args": [
#         "mri/human/neuro/bidsapps/fmriprep.yaml",
#         "FTD1684",
#         "--input", "T1w", "Cor 3D T1a",
#         "--input", "T2w", "Ax T2 FLAIR FS",
#         "--input", "fMRI", "Ax fMRI.*",
#         "--input", "fmap2_echo1_mag", "Ax Field map.*4.9.*",
#         "--input", "fmap2_echo1_phase", "\"Ax Field map.*4.9.*\" converter.component=ph",
#         "--input", "fmap2_echo2_mag", "Ax Field map.*7.3.*",
#         "--input", "fmap2_echo2_phase", "\"Ax Field map.*7.3.*\" converter.component=ph",
#         "--input", "fmriprep_flags", "--use-aroma",
#         "--input", "Arcana_flags", "--loglevel debug",
#         "--build", "no",
#         "--run-directly",
#         "--configuration", "dataset", "${workspaceFolder}/tests/data/output/specific-cases/FTD1684/bids-dataset",
#         "--configuration", "app_output_dir", "${workspaceFolder}/tests/data/output/specific-cases/FTD1684/bids-output",
#         "--configuration", "executable", "/opt/fmriprep/bin/fmriprep"
#     ]
# },
