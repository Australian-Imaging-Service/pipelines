from arcana.data.formats.common import Directory
from arcana.data.formats.medimage import NiftiGzX
from arcana.data.stores.bids import BidsApp

VERSION = "0.16.1"

mriqc = BidsApp(
    app_name="mriqc",
    image=f"poldracklab/mriqc:{VERSION}",
    executable="mriqc",  # Extracted using `docker_image_executable(docker_image)`
    inputs=[
        ("T1w", NiftiGzX, "anat/T1w"),
        ("T2w", NiftiGzX, "anat/T2w"),
        ("fMRI", NiftiGzX, "func/bold"),
    ],
    outputs=[
        ("mriqc", Directory, None),
    ],
)
