from arcana.data.formats.common import Directory
from arcana.data.formats.medimage import NiftiGzX
from arcana.data.stores.bids import BidsApp

VERSION = ""

task = BidsApp(
    app_name="mrtrix_connectome",
    image=f":{VERSION}",
    executable="",  # Extracted using `docker_image_executable(docker_image)`
    inputs=[
        ("T1w", NiftiGzX, "anat/T1w"),
        ("dMRI", NiftiGzX, "dwi/dwi"),
    ],
    outputs=[
        ("mrtrix_connectome", Directory),
    ],
)
