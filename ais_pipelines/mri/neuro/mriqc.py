from arcana2.data.sets.bids import BidsFormat
from arcana2.data.types.general import directory
from arcana2.data.types.neuroimaging import nifti_gz

MRIQC_VERSION = '0.16.1'

INPUTS = [('anat/t1w', nifti_gz)]
OUTPUTS = [('mriqc', directory)]

docker_image = f"poldracklab/mriqc:{MRIQC_VERSION}"

metadata = {
    'name': "MRI-QC",
    'description': (
        "MRIQC extracts no-reference IQMs (image quality metrics) from "
        "structural (T1w and T2w) and functional MRI (magnetic resonance "
        "imaging) data."),
    'inputs': INPUTS,
    'outputs': OUTPUTS,
    'parameters': [],
    'version': '0.1',
    'pkg_version': MRIQC_VERSION,
    'requirements': [],
    'packages': [],
    'maintainer': 'thomas.close@sydney.edu.au',
    'info_url': 'http://mriqc.readthedocs.io'}


task = BidsFormat.wrap_app(
    docker_image,
    input_paths=[i[0] for i in INPUTS])


if __name__ == '__main__':
    from ais_pipelines.utils import deploy_pipeline
    deploy_pipeline(task, **metadata)
