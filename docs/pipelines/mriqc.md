---
source_file: specs/mri/human/neuro/bidsapps/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.16.1|
|XNAT wrapper version|1.18|
|Base image|`poldracklab/mriqc:0.16.1`|
|Info URL|https://mriqc.readthedocs.io|

## Commands
### mriqc
MRIQC extracts no-reference IQMs (image quality metrics) from structural (T1w and T2w) and functional MRI (magnetic resonance imaging) data.

|Key|Value|
|---|-----|
|Short description|MRIQC: quality control metrics from T1w, T2W and fMRI data|
|Workflow|`arcana.tasks.bids:bids_app`|
|Version|`1a1`|
|Executable|`/usr/local/miniconda/bin/mriqc`|
|Operates on|Session|
#### Inputs
|Path|Input format|Stored format|Description|
|----|------------|-------------|-----------|
|`T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|T1-weighted anatomical scan|
|`T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|T2-weighted anatomical scan|
|`fMRI`|`medimage:NiftiGzX`|`medimage:Dicom`|functional MRI|

#### Outputs
|Name|Output format|Stored format|Description|
|----|-------------|-------------|-----------|
|`mriqc`|`common:Directory`|`format`||

