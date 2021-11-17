from pathlib import Path
import logging
import tempfile
from importlib import import_module
import click
import docker.errors
from arcana2.data.spaces.clinical import Clinical
from arcana2.data.repositories.xnat.cs import XnatViaCS

DOCKER_REGISTRY = 'docker.io'
AIS_DOCKER_ORG = 'australianimagingservice'


@click.command()
@click.option('module_path',
              help="""The relative path to a module in the 'ais_pipelines' package containing a
        member called `task`, a Pydra task or function that takes a name and
        inputs and returns a workflow, and another called  `metadata`,
        a dictionary withthe following items:

            name : str
                Name of the pipeline
            pydra_task : pydra.task
                The pydra task to be wrapped for the XNAT container service
            inputs : list[XnatViaCS.InputArg or tuple]
                Inputs to be provided to the container
            outputs : list[XnatViaCS.OutputArg or tuple]
                Outputs from the container 
            parameters : list[str]
                Parameters to be exposed in the CS command
            description : str
                User-facing description of the pipeline
            version : str
                Version string for the wrapped pipeline
            requirements : list[tuple[str, str]]
                Name and version of the Neurodocker requirements to add to the image
            packages : list[tuple[str, str]]
                Name and version of the Python PyPI packages to add to the image
            maintainer : str
                The name and email of the developer creating the wrapper (i.e. you)
            info_url : str
                URI explaining in detail what the pipeline does
            frequency : Clinical
                Frequency of the pipeline to generate (can be either 'dataset' or 'session' currently)""")
@click.option('--registry', default=DOCKER_REGISTRY,
              help="The Docker registry to deploy the pipeline to")
@click.option('--loglevel', default='info',
              help="The level to display logs at")
def deploy(module_path, registry, loglevel):
    """Creates a Docker image that wraps a Pydra task so that it can
    be run in XNAT's container service, then pushes it to AIS's Docker Hub
    organisation for deployment
    """

    logging.basicConfig(loglevel)

    full_module_path = 'ais_pipelines.' + module_path
    module = import_module(full_module_path)

    build_dir = Path(tempfile.mkdtemp())

    name = module.metadata['name']
    version = module.metadata['version']

    image_tag = f"{AIS_DOCKER_ORG}/{name}:{version}"

    json_config = XnatViaCS.generate_json_config(
        pipeline_name=name,
        pydra_task=module.task,
        image_tag=image_tag,
        inputs=module.metadata['inputs'],
        outputs=module.metadata['outputs'],
        parameters=module.metadata['parameters'],
        description=module.metadata['description'],
        version=version,
        registry=registry,
        frequency=module.metadata['frequency'],
        info_url=module.metadata['info_url'])

    build_dir = XnatViaCS.generate_dockerfile(
        json_config=json_config,
        maintainer=module.metadata['maintainer'],
        build_dir=build_dir,
        requirements=module.metadata['requirements'],
        packages=module.metadata['packages'])

    logging.info("Generated dockerfile and XNAT command configuration in %s",
                 build_dir)

    dc = docker.from_env()
    try:
        dc.images.build(path=str(build_dir), tag=image_tag)
    except docker.errors.BuildError as e:
        logging.error(f"Error building docker file in {build_dir}")
        logging.error('\n'.join(l.get('stream', '') for l in e.build_log))
        raise

    logging.info("Generated dockerfile and XNAT command configuration for %s "
                 "pipeline in %s", name, build_dir)

    dc.images.push(image_tag)

    logging.info("Pushed %s pipeline to %s Docker Hub organsation",
                 name, DOCKER_REGISTRY)
    
if __name__ == '__main__':
    deploy()
