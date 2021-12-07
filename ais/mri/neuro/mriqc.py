from arcana2.data.sets.bids import BidsApp
from arcana2.data.spaces.clinical import Clinical
from arcana2.data.types.general import directory
from arcana2.data.types.neuroimaging import nifti_gz


WRAPPER_VERSION = '0.1.1'
MRIQC_VERSION = '0.16.1'

INPUTS = [('T1w', 'anat/T1w', nifti_gz)]
OUTPUTS = [('mriqc', '', directory)]
PARAMETERS = []

docker_image = f"poldracklab/mriqc:{MRIQC_VERSION}"

metadata = {
    'name': "mriqc",
    'description': (
        "MRIQC extracts no-reference IQMs (image quality metrics) from "
        "structural (T1w and T2w) and functional MRI (magnetic resonance "
        "imaging) data."),
    'inputs': INPUTS,
    'outputs': OUTPUTS,
    'parameters': PARAMETERS,
    'version': WRAPPER_VERSION,
    'pkg_version': MRIQC_VERSION,
    'requirements': [],
    'packages': [],
    'base_image': f'poldracklab/mriqc:{MRIQC_VERSION}',
    'maintainer': 'thomas.close@sydney.edu.au',
    'info_url': 'http://mriqc.readthedocs.io',
    'frequency': Clinical.session}


task = BidsApp(
    image=docker_image,
    executable='mriqc',  # Extracted using `docker_image_executable(docker_image)`
    inputs=INPUTS,
    outputs=OUTPUTS)
