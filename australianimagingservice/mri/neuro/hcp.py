from arcana2.data.stores.bids import BidsApp
from arcana2.data.spaces.clinical import Clinical
from arcana2.data.types.general import directory
from arcana2.data.types.neuroimaging import niftix_gz


AIS_VERSION = '0.1.4'
VERSION = 'v4.3.0-3'

BIDS_INPUTS = [('T1w', niftix_gz, 'anat/T1w'),
               ('T2w', niftix_gz, 'anat/T2w'),
               ('fMRI', niftix_gz, 'func/bold')]
BIDS_OUTPUTS = [('hcp', directory)]
BIDS_PARAMETERS = []

docker_image = f"bids/hcppipelines:{VERSION}"


task = BidsApp(
    image=docker_image,
    executable='/run.py',  # Extracted using 'extract_executable' CL tool
    inputs=BIDS_INPUTS,
    outputs=BIDS_OUTPUTS)


spec = {
    'package_name': "hcp_pipelines",
    'description': (
        "This a BIDS App wrapper for HCP Pipelines v4.3.0. Like every BIDS App "
        "it consists of a container that includes all of the dependencies and "
        "run script that parses a BIDS dataset. BIDS Apps run on Windows, "
        "Linux, Mac as well as HPCs/clusters."),
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
    'info_url': 'https://github.com/BIDS-Apps/HCPPipelines/blob/master/README.md',
    'frequency': Clinical.session}
