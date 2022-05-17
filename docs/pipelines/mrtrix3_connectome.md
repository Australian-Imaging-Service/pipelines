---
source_file: mri/neuro/bids/mrtrix3_connectome.yaml
title: mrtrix3_connectome
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.5.1|
|XNAT wrapper version|1|
|Base image|`bids/mrtrix3_connectome:0.5.1`|
|Info URL|https://github.com/BIDS-Apps/MRtrix3_connectome|

## Commands
### mrtrix3_connectome
Mrtrix_connectome enables generation and subsequent group analysis of structural connectomes generated from diffusion MRI data. The analysis pipeline relies primarily on the MRtrix3 software package, and includes a number of state-of-the-art methods for image processing, tractography reconstruction, connectome generation and inter-subject connection density normalisation.

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|
|`dwi/dwi`|`medimage:NiftiGzXFslgrad`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`mrtrix_connectome`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
