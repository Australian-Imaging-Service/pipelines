---
source_file: specs/mri/human/neuro/bidsapps/smriprep.yaml
title: smriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.9.2|
|Base image|`nipreps/smriprep:0.9.2`|
|Info URL|https://www.nipreps.org/smriprep/master/index.html|

### Required licenses
|Source file|Info|
|-----------|----|
|`freesurfer.txt`|`sMRIPRep` uses FreeSurfer tools, which require a license to run.<br> See [FreeSurfer Download and Registration](https://surfer.nmr.mgh.harvard.edu/registration.html) for more details.
|

## Commands
### smriprep
"SMRIPrep: a structural MRI data preprocessing pipeline..."


|Key|Value|
|---|-----|
|Short description|structural MRI data preprocessing pipeline|
|Operates on|Session|
#### Inputs
|Name|Format|Description|
|----|------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage:Dicom" aria-label="medimage:Dicom">Dicom (Directory)</span>|T1-weighted anatomical scan|
|`T2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage:Dicom" aria-label="medimage:Dicom">Dicom (Directory)</span>|T2-weighted anatomical scan|

#### Outputs
|Name|Format|Description|
|----|------|-----------|
|`smriprep`|||

#### Parameters
|Name|Data type|Description|
|----|---------|-----------|
|`smriprep_flags`|`string`|Command line flags passed on directly to sMRIPrep|
|`json_edits`|`string`|JQ filters (https://devdocs.io/jq/) to apply to JSON side-cars in order to handle special cases where the dcm2niix fails to produce valid a BIDS|

