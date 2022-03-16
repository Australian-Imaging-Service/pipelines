from arcana.data.stores.bids import BidsApp
from arcana.data.spaces.medicalimaging import Clinical
from arcana.data.formats.common import directory
from arcana.data.formats.medicalimaging import niftix_gz


AIS_VERSION = '0.1'
VERSION = ''

BIDS_INPUTS = [('T1w', niftix_gz, 'anat/T1w'),
               ('T2w', niftix_gz, 'anat/T2w')]
BIDS_OUTPUTS = [('freesurfer', directory)]
BIDS_PARAMETERS = []

docker_image = f":{VERSION}"


spec = {
    'package_name': "freesurfer",
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
    'frequency': Clinical.session}


task = BidsApp(
    app_name=spec['package_name'],
    image=docker_image,
    executable='',  # Extracted using `docker_image_executable(docker_image)`
    inputs=BIDS_INPUTS,
    outputs=BIDS_OUTPUTS)
