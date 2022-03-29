from arcana.tasks.bids import BidsApp
from arcana.data.formats.common import Directory
from arcana.data.formats.medimage import NiftiXGz


VERSION = '0.16.1'

BIDS_INPUTS = [('T1w', NiftiXGz, 'anat/T1w'),
               ('T2w', NiftiXGz, 'anat/T2w'),
               ('fMRI', NiftiXGz, 'func/bold')]
BIDS_OUTPUTS = [('mriqc', Directory, None)]
BIDS_PARAMETERS = []

docker_image = f"poldracklab/mriqc:{VERSION}"


mriqc = BidsApp(
    app_name="mriqc",
    image=docker_image,
    executable='mriqc',  # Extracted using `docker_image_executable(docker_image)`
    inputs=BIDS_INPUTS,
    outputs=BIDS_OUTPUTS)


spec = {
    'commands': [
        {'pydra_task': __name__ + ':mriqc',
         'inputs': [i[:2] for i in BIDS_INPUTS],
         'outputs': [o[:2] for o in BIDS_OUTPUTS],
         'parameters': [p[0] for p in BIDS_PARAMETERS]}],
         'description': (
             "MRIQC extracts no-reference IQMs (image quality metrics) from "
             "structural (T1w and T2w) and functional MRI (magnetic resonance "
             "imaging) data."),
    'pkg_version': VERSION,
    'wrapper_version': None,    
    'packages': [],
    'python_packages': [],
    'base_image': docker_image,
    'authors': ['thomas.close@sydney.edu.au'],
    'info_url': 'http://mriqc.readthedocs.io',
    'frequency': 'session'}

