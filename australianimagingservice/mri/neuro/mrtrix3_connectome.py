from arcana2.data.stores.bids import BidsApp
from arcana2.data.spaces.clinical import Clinical
from arcana2.data.types.general import directory
from arcana2.data.types.neuroimaging import niftix_gz


AIS_VERSION = '0.1.4'
VERSION = ''

BIDS_INPUTS = [('T1w', niftix_gz, 'anat/T1w'),
               ('dMRI', niftix_gz, 'dwi/dwi')]
BIDS_OUTPUTS = [('mrtrix_connectome', directory)]
BIDS_PARAMETERS = []

docker_image = f":{VERSION}"


task = BidsApp(
    image=docker_image,
    executable='',  # Extracted using `docker_image_executable(docker_image)`
    inputs=BIDS_INPUTS,
    outputs=BIDS_OUTPUTS)


spec = {
    'package_name': "mrtrix_connectome",
    'description': (
        ""),
    'commands': [
        {'pydra_task': 'task',  # Name of Pydra task preceded by module path, e.g. pydra.tasks.fsl.preprocess.fast:FAST. Module path can be omitted if defined in current module
         'inputs': [i[:2] for i in BIDS_INPUTS],
         'outputs': [o[:2] for o in BIDS_OUTPUTS],
         'parameters': [p[0] for p in BIDS_PARAMETERS]}],
    'version': AIS_VERSION,
    'app_version': VERSION,
    'packages': [],  # [('dcm2niix', '1.0.20201102')],
    'python_packages': [],
    'base_image': docker_image,
    'maintainer': 'thomas.close@sydney.edu.au',
    'info_url': '',
    'frequency': Clinical.session}
