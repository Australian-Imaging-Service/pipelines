---
source_file: mri/neuro/bids/ants_cortical_thickness.yaml
title: ants_cortical_thickness
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|v2.2.0-1|
|XNAT wrapper version|1|
|Base image|`bids/antscorticalthickness:v2.2.0-1`|
|Info URL|https://github.com/ANTsX/ANTs|

## Commands
### ants_cortical_thickness
`ants_cortical_thickness` runs ANTs cortical thickness estimation pipeline on T1w images. Note that only single time-point analyses (i.e. not longtiduninal) are supported at this stage.

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`anat/T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`ants_cortical_thickness`|`common:Directory`|`format`|

#### Parameters
|Name|Data type|
|----|---------|
