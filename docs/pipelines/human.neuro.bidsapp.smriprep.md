---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/mri/human/neuro/bidsapp/smriprep.yaml
title: human.neuro.bidsapp.smriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|human.neuro.bidsapp.smriprep|
|Title|Structural MRI data preprocessing pipeline|
|Version|0.19.1|
|Base image|`nipreps/smriprep:0.19.1`|
|Maintainer|Mahdieh Dashtbani-Moghari (mahdieh.dashtbanimoghari@sydney.edu.au)|
|Info URL|https://www.nipreps.org/smriprep/master/index.html|

SMRIPrep: a structural MRI data preprocessing pipeline including Freesurfer


### Required licenses
|Name|URL|Description|
|----|---|-----------|
|freesurfer|`https://surfer.nmr.mgh.harvard.edu/registration.html`|`sMRIPRep` uses FreeSurfer tools, which require a license to run.|

## Commands
|Key|Value|
|---|-----|
|Task|smriprep|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`t1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x</span>|Y|T1-weighted anatomical scan|
|`T2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x</span>|Y|T2-weighted anatomical scan|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`smriprep`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y|Preprocessed sMRI data|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`flags`|<span data-toggle="tooltip" data-placement="bottom" title="field/text (optional)" aria-label="field/text (optional)">field/text (optional)</span>||Additional flags to pass to the app. These are passed as a single string and should be formatted as they would be on the command line (e.g. '--flag1 --flag2 value')|
|`json_edits`|<span data-toggle="tooltip" data-placement="bottom" title="field/text+tuple-of+list-of (optional)" aria-label="field/text+tuple-of+list-of (optional)">field/text+tuple-of+list-of (optional)</span>|||

