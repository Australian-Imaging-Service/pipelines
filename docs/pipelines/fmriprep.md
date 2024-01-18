---
source_file: /home/runner/work/pipelines/pipelines/australian-imaging-service/mri/human/neuro/bidsapps/fmriprep.yaml
title: fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|fmriprep|
|Title|Functional MRI data preprocessing pipeline|
|Package version|23.1.4|
|Build|0|
|Base image|`nipreps/fmriprep:23.1.4`|
|Maintainer|Thomas G. Close (thomas.close@sydney.edu.au)|
|Info URL|https://fmriprep.org|
|Known issues|https://github.com/nipreps/fmriprep/issues|

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
|`bold`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|functional MRI|
|`fmap_magnitude1`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 1 & 2: magnitude of first echo|
|`fmap_magnitude2`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 1 & 2: magnitude of second echo|
|`fmap_magnitude`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 3: magnitude image used for anatomical reference|
|`fmap_phasediff`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 1: phasediff image corresponding to the phase-diff map between echo times|
|`fmap_phase1`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 2: phase of first echo|
|`fmap_phase2`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 2: phase of second echo|
|`fmap_fieldmap`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 3: directly reconstructed field map|
|`fmap_epi`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x" aria-label="medimage/nifti-gz-x">medimage/nifti-gz-x</span>|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-series" aria-label="medimage/dicom-series">medimage/dicom-series</span>|Field map - BIDS Case 4: Spin Echo EPI scans with different phase encoding directions to estimate the distortion map corresponding to the nonuniformities of the B0 field|

#### Outputs
|Name|Required data-type|Default column data-type|Description|
|----|------------------|------------------------|-----------|
|`fmriprep`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Preprocessed fMRI data|

#### Parameters
|Name|Data type|Description|
|----|---------|-----------|
|`fmriprep_flags`|`str`|Command line flags passed on directly to fMRIPrep|
|`json_edits`|`str`|JQ filters (https://devdocs.io/jq/) to apply to JSON side-cars in order to handle special cases where the dcm2niix fails to produce valid a BIDS|

