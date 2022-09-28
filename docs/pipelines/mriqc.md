---
source_file: specs/mri/human/neuro/bidsapps/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|22.0.6|
|Base image|`nipreps/mriqc:22.0.6`|
|Info URL|https://mriqc.readthedocs.io|

## Commands
### mriqc
MRIQC extracts no-reference IQMs (image quality metrics) from
structural (T1w and T2w) and functional MRI (magnetic resonance
imaging) data.


|Key|Value|
|---|-----|
|Short description|MRIQC: quality control metrics from T1w, T2W and fMRI data|
|Operates on|Session|
#### Inputs
|Name|Format|Description|
|----|------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage:Dicom" aria-label="medimage:Dicom">Dicom (Directory)</span>|T1-weighted anatomical scan|
|`T2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage:Dicom" aria-label="medimage:Dicom">Dicom (Directory)</span>|T2-weighted anatomical scan|
|`fMRI`|<span data-toggle="tooltip" data-placement="bottom" title="medimage:Dicom" aria-label="medimage:Dicom">Dicom (Directory)</span>|functional MRI|

#### Outputs
|Name|Format|Description|
|----|------|-----------|
|`mriqc`|||

