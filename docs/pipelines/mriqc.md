---
source_file: mri/neuro/bids/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.16.1|
|XNAT wrapper version|1.3|
|Base image|`poldracklab/mriqc:0.16.1`|
|Info URL|https://mriqc.readthedocs.io|

## Commands
### mriqc
MRIQC: quality control metrics from T1w, T2W and fMRI data

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`anat/T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`func/task-rest_bold`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`mriqc`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
