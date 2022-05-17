---
source_file: mri/neuro/bids/fibre_density_and_crosssection.yaml
title: fibre_density_and_crosssection
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|v0.0.1|
|XNAT wrapper version|1|
|Base image|`bids/fibredensityandcrosssection:v0.0.1`|
|Info URL|https://github.com/BIDS-Apps/FibreDensityAndCrosssection|

## Commands
### fibre_density_and_crosssection
`fibre_density_and_crosssection` enables group analysis of diffusion MRI data by performing a Fixel-Based Analysis (FBA) of Fibre Density, Fibre Cross-section and a combined measure (Fibre Density & Cross-section).

#### Inputs
|Path|Input format|Stored format|
|----|------------|-------------|
|`dwi/dwi`|`medimage:NiftiGzXFslgrad`|`medimage:Dicom`|

#### Outputs
|Name|Output format|Stored format|
|----|-------------|-------------|
|`fibre_density_and_cross_section`|`common:Directory`|`medimage:Dicom`|

#### Parameters
|Name|Data type|
|----|---------|
