---
source_file: mri/neuro/bids/fmriprep.yaml
title: fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|21.0.2|
|XNAT wrapper version|1.3|
|Base image|`nipreps/fmriprep:21.0.2`|
|Info URL|https://fmriprep.org|

## Commands
### fmriprep
fMRIPrep: a functional fMRI data preprocessing pipeline

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`anat/T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`func/task-rest_bold`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`fmriprep`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
|json_edits|string|

