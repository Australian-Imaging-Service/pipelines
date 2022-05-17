---
source_file: mri/neuro/bids/fmriprep.yaml
title: fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|21.0.2|
|XNAT wrapper version|1|
|Base image|`nipreps/fmriprep:21.0.2`|
|Info URL|https://fmriprep.org|

## Commands
### fmriprep
`fMRIPrep` is a functional magnetic resonance imaging (fMRI) data preprocessing pipeline that is designed to provide an easily accessible, state-of-the-art interface that is robust to variations in scan acquisition protocols and that requires minimal user input, while providing easily interpretable and comprehensive error and output reporting. It performs basic processing steps (coregistration, normalization, unwarping, noise component extraction, segmentation, skullstripping etc.) providing outputs that can be easily submitted to a variety of group level analyses, including task-based or resting-state fMRI, graph theory measures, surface or volume-based statistics, etc.

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`anat/T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`func/bold`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`fmriprep`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
