from arcana.data.formats.common import Directory
from arcana.data.formats.medimage import NiftiGzX
from arcana.data.stores.bids import BidsApp

VERSION = ""

task = BidsApp(
    app_name="freesurfer",
    image=f":{VERSION}",
    executable="",  # Extracted using `docker_image_executable(docker_image)`
    inputs=[
        ("T1w", NiftiGzX, "anat/T1w"),
        ("T2w", NiftiGzX, "anat/T2w"),
    ],
    outputs=[
        ("freesurfer", Directory),
    ],
)
