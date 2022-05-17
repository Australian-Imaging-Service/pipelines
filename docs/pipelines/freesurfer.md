---
source_file: mri/neuro/bids/freesurfer.yaml
title: freesurfer
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|v6.0.1-6.1|
|XNAT wrapper version|1|
|Base image|`bids/freesurfer:v6.0.1-6.1`|
|Info URL|https://github.com/BIDS-Apps/freesurfer|

## Commands
### freesurfer
`Freesurfer` reconstructs the surface for each subject individually and then creates a study specific template. In case there are multiple sessions the Freesurfer longitudinal pipeline is used (creating subject specific templates) unless instructed to combine data across sessions.

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`anat/T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`freesurfer`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
