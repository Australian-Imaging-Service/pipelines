import docker


def docker_image_executable(image_tag):
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

    return executable
    