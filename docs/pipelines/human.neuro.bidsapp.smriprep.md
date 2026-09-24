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
|Task|DeferredBidsappTask|
|Operates on|session|
Inputs, outputs and parameters could not be introspected in this environment (the task's package isn't installed here); see the docs generated from within the built image.

