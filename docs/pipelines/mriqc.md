---
source_file: mri/human/neuro/bidsapps/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.16.1|
|XNAT wrapper version|1.16|
|Base image|`poldracklab/mriqc:0.16.1`|
|Info URL|https://mriqc.readthedocs.io|

## Commands
### mriqc
MRIQC: quality control metrics from T1w, T2W and fMRI data

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`fMRI`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`mriqc`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
