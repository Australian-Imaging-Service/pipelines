---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/mri/human/neuro/bidsapp/fmriprep.yaml
title: human.neuro.bidsapp.fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|human.neuro.bidsapp.fmriprep|
|Title|Functional MRI data preprocessing pipeline|
|Version|25.2.5|
|Base image|`nipreps/fmriprep:25.2.5`|
|Maintainer|Thomas G. Close (thomas.close@sydney.edu.au)|
|Info URL|https://fmriprep.org|
|Known issues|See App issues page (https://github.com/nipreps/fmriprep/issues)|

`fMRIPrep` is a functional magnetic resonance imaging (fMRI) data preprocessing
pipeline that is designed to provide an easily accessible, state-of-the-art
interface that is robust to variations in scan acquisition protocols and that
requires minimal user input, while providing easily interpretable and comprehensive
error and output reporting. It performs basic processing steps (coregistration,
normalization, unwarping, noise component extraction, segmentation,
skullstripping etc.) providing outputs that can be easily submitted to a variety
of group level analyses, including task-based or resting-state fMRI, graph
theory measures, surface or volume-based statistics, etc.

Optional flags that can be provided to the `fmriprep_flags` parameter:
```
  [--anat-only] [--boilerplate_only] [--md-only-boilerplate]
  [--error-on-aroma-warnings] [-v]
  [--ignore {fieldmaps,slicetiming,sbref,t2w,flair} [{fieldmaps,slicetiming,sbref,t2w,flair} ...]]
  [--output-spaces [OUTPUT_SPACES [OUTPUT_SPACES ...]]]
  [--me-output-echos] [--bold2t1w-init {register,header}]
  [--bold2t1w-dof {6,9,12}] [--force-bbr] [--force-no-bbr]
  [--medial-surface-nan] [--slice-time-ref SLICE_TIME_REF]
  [--random-seed _RANDOM_SEED]
  [--use-aroma]
  [--aroma-melodic-dimensionality AROMA_MELODIC_DIM]
  [--return-all-components]
  [--fd-spike-threshold REGRESSORS_FD_TH]
  [--dvars-spike-threshold REGRESSORS_DVARS_TH]
  [--skull-strip-template SKULL_STRIP_TEMPLATE]
  [--skull-strip-fixed-seed]
  [--skull-strip-t1w {auto,skip,force}] [--fmap-bspline]
  [--fmap-no-demean] [--topup-max-vols TOPUP_MAX_VOLS]
  [--use-syn-sdc [{warn,error}]] [--force-syn]
  [--no-submm-recon] [--cifti-output [{91k,170k}] | --fs-no-reconall]
  [--resource-monitor]
  [--reports-only] [--config-file FILE] [--write-graph]
  [--stop-on-first-crash] [--notrack]
  [--debug {compcor,fieldmaps,all} [{compcor,fieldmaps,all} ...]]
  [--sloppy]
```


### Required licenses
|Name|URL|Description|
|----|---|-----------|
|freesurfer|`https://surfer.nmr.mgh.harvard.edu/registration.html`|`fMRIPRep` uses FreeSurfer tools, which require a license to run.|

## Commands
|Key|Value|
|---|-----|
|Task|DeferredBidsappTask|
|Operates on|session|
Inputs, outputs and parameters could not be introspected in this environment (the task's package isn't installed here); see the docs generated from within the built image.

