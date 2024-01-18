---
source_file: /home/runner/work/pipelines/pipelines/australian-imaging-service/mri/human/neuro/bidsapps/smriprep.yaml
title: smriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|smriprep|
|Title|Structural MRI data preprocessing pipeline|
|Package version|0.9.2|
|Build|3|
|Base image|`nipreps/smriprep:0.9.2`|
|Maintainer|Mahdieh Dashtbani-Moghari (mahdieh.dashtbanimoghari@sydney.edu.au)|
|Info URL|https://www.nipreps.org/smriprep/master/index.html|

SMRIPrep: a structural MRI data preprocessing pipeline including Freesurfer


### Required licenses
|Name|URL|Description|
|----|---|-----------|
|freesurfer|`https://surfer.nmr.mgh.harvard.edu/registration.html`|`sMRIPRep` uses FreeSurfer tools, which require a license to run.|

## Command
|Key|Value|
|---|-----|
|Task|arcana.bids:bids_app|
|Operates on|session|
#### Inputs
|Name|Required data-type|Default column data-type|Description|
|----|------------------|------------------------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|T1-weighted anatomical scan|
|`T2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|T2-weighted anatomical scan|

#### Outputs
|Name|Required data-type|Default column data-type|Description|
|----|------------------|------------------------|-----------|
|`smriprep`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Preprocessed sMRI data|

#### Parameters
|Name|Data type|Description|
|----|---------|-----------|
|`smriprep_flags`|`str`|Command line flags passed on directly to sMRIPrep|
|`json_edits`|`str`|JQ filters (https://devdocs.io/jq/) to apply to JSON side-cars in order to handle special cases where the dcm2niix fails to produce valid a BIDS|

