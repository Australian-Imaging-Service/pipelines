---
source_file: specs/mri/human/neuro/bidsapps/smriprep.yaml
title: smriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.9.2|
|XNAT wrapper version|1|
|Base image|`nipreps/smriprep:0.9.2`|
|Info URL|https://www.nipreps.org/smriprep/master/index.html|

### Required licenses
|Source file|Mounted at|Info|
|-----------|----------|----|
|`freesurfer.txt`|`/opt/freesurfer/license.txt`|`sMRIPRep` uses FreeSurfer tools, which require a license to run.<br> See [FreeSurfer Download and Registration](https://surfer.nmr.mgh.harvard.edu/registration.html) for more details.
|

## Commands
### smriprep
"SMRIPrep: a structural MRI data preprocessing pipeline..."


|Key|Value|
|---|-----|
|Short description|SMRIPrep: a structural MRI data preprocessing pipeline|
|Workflow|`arcana.tasks.bids:bids_app`|
|Version|`1a1`|
|Executable|`/opt/conda/bin/smriprep`|
|Operates on|Session|
#### Inputs
|Path|Input format|Stored format|Description|
|----|------------|-------------|-----------|
|`T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|T1-weighted anatomical scan|
|`T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|T2-weighted anatomical scan|

#### Outputs
|Name|Output format|Stored format|Description|
|----|-------------|-------------|-----------|
|`smriprep`|`common:Directory`|`format`||

#### Parameters
|Name|Data type|
|----|---------|
|`smriprep_flags`|`string`|
|`json_edits`|`string`|

