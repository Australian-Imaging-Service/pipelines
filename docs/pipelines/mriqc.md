---
source_file: /home/runner/work/pipelines/pipelines/australian-imaging-service/mri/human/neuro/bidsapps/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|mriqc|
|Title|Extract quality control metrics from T1w, T2W and fMRI data|
|Package version|22.0.6|
|Build|3|
|Base image|`nipreps/mriqc:22.0.6`|
|Maintainer|Thomas G. Close (thomas.close@sydney.edu.au)|
|Info URL|https://mriqc.readthedocs.io|

MRIQC extracts no-reference IQMs (image quality metrics) from
structural (T1w and T2w) and functional MRI (magnetic resonance
imaging) data.


## Command
|Key|Value|
|---|-----|
|Task|arcana.bids:bids_app|
|Operates on|session|
#### Inputs
|Name|Required data-type|Default column data-type|Description|
|----|------------------|------------------------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|T1-weighted anatomical scan|
|`T2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|T2-weighted anatomical scan|
|`fMRI`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|functional MRI|

#### Outputs
|Name|Required data-type|Default column data-type|Description|
|----|------------------|------------------------|-----------|
|`mriqc`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Generated QC outputs|

#### Parameters
|Name|Data type|Description|
|----|---------|-----------|

