---
source_file: mri/neuro/bids/mriqc.yaml
title: mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.16.1|
|XNAT wrapper version|1|
|Base image|`poldracklab/mriqc:0.16.1`|
|Info URL|https://mriqc.readthedocs.io|

## Commands
### mriqc
MRIQC extracts no-reference IQMs (image quality metrics) from structural (T1w and T2w) and functional MRI (magnetic resonance imaging) data.

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`anat/T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`func/bold`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`mriqc`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
