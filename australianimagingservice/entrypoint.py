from pathlib import Path
import logging
import tempfile
import shutil
from importlib import import_module
import click
import docker.errors
from arcana2.data.repositories.xnat.cs import XnatViaCS
from arcana2.core.utils import get_pkg_name
from .utils import docker_image_executable

DOCKER_REGISTRY = 'docker.io'
AIS_DOCKER_ORG = 'australianimagingservice'


@click.command(help="""The relative path to a module in the 'australianimagingservice'
        package containing a
        member called `task`, a Pydra task or function that takes a name and
        inputs and returns a workflow, and another called  `spec`,
        a dictionary with the following items:

            name : str\n
                Name of the pipeline\n
            pydra_task : pydra.task\n
                The pydra task to be wrapped for the XNAT container service\n
            inputs : list[XnatViaCS.InputArg or tuple]\n
                Inputs to be provided to the container\n
            outputs : list[XnatViaCS.OutputArg or tuple]\n
                Outputs from the container\n
            parameters : list[str]\n
                Parameters to be exposed in the CS command\n
            description : str\n
                User-facing description of the pipeline\n
            version : str\n
                Version string for the wrapped pipeline\n
            packages : list[tuple[str, str]]\n
                Name and version of the Neurodocker requirements to add to the image\n
            python_packages : list[tuple[str, str]]\n
                Name and version of the Python PyPI packages to add to the image\n
            maintainer : str\n
                The name and email of the developer creating the wrapper (i.e. you)\n
            info_url : str\n
                URI explaining in detail what the pipeline does\n
            frequency : Clinical\n
                The frequency of the data nodes on which the pipeline operates
                on (can be either per- 'dataset' or 'session' at the moment)\n""")
@click.argument('module_path')
@click.option('--registry', default=DOCKER_REGISTRY,
              help="The Docker registry to deploy the pipeline to")
@click.option('--loglevel', default='info',
              help="The level to display logs at")
@click.option('--build_dir', default=None, type=str,
              help="Specify the directory to build the Docker image in")
def deploy(module_path, registry, loglevel, build_dir):
    """Creates a Docker image that wraps a Pydra task so that it can
    be run in XNAT's container service, then pushes it to AIS's Docker Hub
    organisation for deployment
    """

    logging.basicConfig(level=getattr(logging, loglevel.upper()))

    full_module_path = 'australianimagingservice.' + module_path
    module = import_module(full_module_path)

    if build_dir is None:
        build_dir = tempfile.mkdtemp()
    build_dir = Path(build_dir)
    build_dir.mkdir(exist_ok=True)

    pkg_name = module.spec['package_name']
    version = module.spec['version']

    image_tag = f"{AIS_DOCKER_ORG}/{pkg_name.lower().replace('-', '_')}:{version}"

    frequency = module.spec['frequency']

    python_packages = module.spec.get('python_packages', [])

    xnat_commands = []
    for cmd_spec in module.spec['commands']:

        cmd_name = cmd_spec.get('name', pkg_name)
        cmd_desc = cmd_spec.get('description', module.spec['description'])

        pydra_task = cmd_spec['pydra_task']
        if ':' not in pydra_task:
            # Default to the module that the spec is defined in
            pydra_task = full_module_path + ':' + pydra_task
            task_module = full_module_path
        else:
            task_module = pydra_task.split(':')[0]

        python_packages.append(get_pkg_name(task_module))

        xnat_commands.append(XnatViaCS.generate_xnat_command(
            pipeline_name=cmd_name,
            task_location=pydra_task,
            image_tag=image_tag,
            inputs=cmd_spec['inputs'],
            outputs=cmd_spec['outputs'],
            parameters=cmd_spec['parameters'],
            description=cmd_desc,
            version=version,
            registry=registry,
            frequency=frequency,
            info_url=module.spec['info_url']))

    build_dir = XnatViaCS.generate_dockerfile(
        xnat_commands=xnat_commands,
        maintainer=module.spec['maintainer'],
        build_dir=build_dir,
        base_image=module.spec.get('base_image'),
        packages=module.spec.get('packages'),
        python_packages=python_packages,
        package_manager=module.spec.get('package_manager'))

    dc = docker.from_env()
    try:
        dc.images.build(path=str(build_dir), tag=image_tag)
    except docker.errors.BuildError as e:
        logging.error(f"Error building docker file in {build_dir}")
        logging.error('\n'.join(l.get('stream', '') for l in e.build_log))
        raise

    logging.info("Built docker image %s", pkg_name)

    dc.images.push(image_tag)

    logging.info("Pushed %s pipeline to %s Docker Hub organsation",
                 pkg_name, DOCKER_REGISTRY)



@click.command(help="""Extract the executable from a Docker image""")
@click.argument('image_tag')
def extract_executable(image_tag):
    """Pulls a given Docker image tag and inspects the image to get its
    entrypoint/cmd

    Parameters
    ----------
    image_tag : str
        Docker image tag

    Returns
    -------
    str
        The entrypoint or default command of the Docker image
    """
    dc = docker.from_env()

    dc.images.pull(image_tag)

    image_attrs = dc.api.inspect_image(image_tag)['Config']

    executable = image_attrs['Entrypoint']
    if executable is None:
        executable = image_attrs['Cmd']

    print(executable)


if __name__ == '__main__':
    deploy()
