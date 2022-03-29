from arcana.tasks.bids import BidsApp
from arcana.data.formats.common import Directory
from arcana.data.formats.medimage import NiftiXGz


AIS_VERSION = '0.1'
VERSION = ''

BIDS_INPUTS = [('T1w', NiftiXGz, 'anat/T1w'),
               ('T2w', NiftiXGz, 'anat/T2w'),
               ('fMRI', NiftiXGz, 'func/bold'),
               ('dMRI', NiftiXGz, 'dwi/dwi')]
BIDS_OUTPUTS = [('fmriprep', Directory)]
BIDS_PARAMETERS = []

docker_image = f":{VERSION}"


spec = {
    'package_name': "fmriprep",
    'description': (
        ""),
    'commands': [
        {'pydra_task': 'task',  # Name of Pydra task preceded by module path, e.g. pydra.tasks.fsl.preprocess.fast:FAST. Module path can be omitted if defined in current module
         'inputs': [i[:2] for i in BIDS_INPUTS],
         'outputs': [o[:2] for o in BIDS_OUTPUTS],
         'parameters': [p[0] for p in BIDS_PARAMETERS]}],
    'version': AIS_VERSION,
    'pkg_version': VERSION,
    'packages': [],  # [('dcm2niix', '1.0.20201102')],
    'python_packages': [],
    'base_image': docker_image,
    'maintainer': 'thomas.close@sydney.edu.au',
    'info_url': '',
    'frequency': 'session'}


task = BidsApp(
    app_name=spec['package_name'],
    image=docker_image,
    executable='',  # Extracted using `docker_image_executable(docker_image)`
    inputs=BIDS_INPUTS,
    outputs=BIDS_OUTPUTS)
