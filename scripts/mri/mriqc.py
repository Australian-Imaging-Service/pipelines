import docker
from arcana2.data.repositories.xnat.cs import XnatViaCS

def generate_command():

    image_tag = f'arcana-concatenate{run_prefix}:latest'

    pydra_task = concatenate()

    json_config = XnatViaCS.generate_json_config(
        pipeline_name=PIPELINE_NAME,
        pydra_task=pydra_task,
        image_tag=image_tag,
        inputs=[
            ('in_file1', text, Clinical.session),
            ('in_file2', text, Clinical.session)],
        outputs=[
            ('out_file', text)],
        parameters=['duplicates'],
        description="A pipeline to test Arcana's wrap4xnat function",
        version='0.1',
        registry=xnat_container_registry,
        frequency=Clinical.session,
        info_url=None)


def generate_dockerfile():
    build_dir = XnatViaCS.generate_dockerfile(
        json_config=json_config,
        maintainer='some.one@an.org',
        build_dir=build_dir,
        requirements=[],
        packages=[],
        extra_labels={})



    dc = docker.from_env()
    try:
        dc.images.build(path=str(build_dir), tag=image_tag)
    except docker.errors.BuildError as e:
        logging.error(f"Error building docker file in {build_dir}")
        logging.error('\n'.join(l.get('stream', '') for l in e.build_log))
        raise

    image_path = f'{xnat_container_registry}/{image_tag}'

    dc.images.push(image_path)

    # Login to XNAT and attempt to pull the image and check the command has
    # been detected correctly
    with xnat_repository:

        xlogin = xnat_repository.login

        # Pull image from test registry to XNAT container service
        xlogin.post('/xapi/docker/pull', json={
            'image': image_tag,
            'save-commands': True})

        commands = {c['id']: c for c in xlogin.get(f'/xapi/commands/').json()}