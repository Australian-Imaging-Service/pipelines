---
source_file: mri/human/neuro/bidsapps/fmriprep.yaml
title: fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|21.0.2|
|XNAT wrapper version|1.18|
|Base image|`nipreps/fmriprep:21.0.2`|
|Info URL|https://fmriprep.org|

## Commands
### fmriprep
fMRIPrep: a functional fMRI data preprocessing pipeline

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`fMRI`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`fmriprep`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
|fmriprep_flags|string|
|json_edits|string|

