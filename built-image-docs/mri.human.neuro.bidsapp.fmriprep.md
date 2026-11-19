---
source_file: /pydra2app-spec.yaml
title: mri.human.neuro.bidsapp.fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|mri.human.neuro.bidsapp.fmriprep|
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
|Task|fmriprep|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`t1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to" aria-label="medimage/nifti-gz-x+convertible-to">medimage/nifti-gz-x+convertible-to</span>|Y|T1-weighted anatomical scan|
|`t2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|T2-weighted anatomical scan|
|`bold`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to" aria-label="medimage/nifti-gz-x+convertible-to">medimage/nifti-gz-x+convertible-to</span>|Y|functional MRI|
|`fmap_magnitude1`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 1 & 2: magnitude of first echo|
|`fmap_magnitude2`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 1 & 2: magnitude of second echo|
|`fmap_magnitude`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 3: magnitude image used for anatomical reference|
|`fmap_phasediff`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 1: phasediff image corresponding to the phase-diff map between echo times|
|`fmap_phase1`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 2: phase of first echo|
|`fmap_phase2`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 2: phase of second echo|
|`fmap_fieldmap`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 3: directly reconstructed field map|
|`fmap_epi`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Field map - BIDS Case 4: Spin Echo EPI scans with different phase encoding directions to estimate the distortion map corresponding to the nonuniformities of the B0 field|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`t1w_preproc`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|Y|Preprocessed T1-weighted image in native space|
|`t1w_preproc_mni`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|Y|Preprocessed T1-weighted image in MNI152NLin2009cAsym space|
|`t1w_brain_mask`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|Y|Brain mask of the T1-weighted image in native space|
|`t1w_dseg`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz" aria-label="medimage/nifti-gz">medimage/nifti-gz</span>|Y|Tissue segmentation (CSF, GM, WM) of the T1-weighted image in native space|
|`bold_preproc_mni`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|Y|Preprocessed BOLD series in MNI152NLin2009cAsym space|
|`bold_brain_mask_mni`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|Y|Brain mask of the BOLD series in MNI152NLin2009cAsym space|
|`bold_confounds`|<span data-toggle="tooltip" data-placement="bottom" title="text/tsv" aria-label="text/tsv">text/tsv</span>|Y|Confound regressors of the BOLD series (motion, CompCor, DVARS, FD etc.)|
|`figures`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y|Figures referenced by the HTML report|
|`log`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y|Logs and the citation boilerplate of the run|
|`report`|<span data-toggle="tooltip" data-placement="bottom" title="text/html" aria-label="text/html">text/html</span>|Y|HTML report summarising the preprocessing|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`flags`|<span data-toggle="tooltip" data-placement="bottom" title="field/text+list-of" aria-label="field/text+list-of">field/text+list-of</span>||Additional flags to pass to the app. These are passed as a list of strings and should be formatted as they would be on the command line (e.g. '--flag1 --flag2 value')|

