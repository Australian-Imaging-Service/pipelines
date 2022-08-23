---
source_file: specs/mri/human/neuro/bidsapps/fmriprep.yaml
title: fmriprep
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|22.0.0|
|XNAT wrapper version|1|
|Base image|`nipreps/fmriprep:22.0.0`|
|Info URL|https://fmriprep.org|

### Required licenses
|Source file|Mounted at|Info|
|-----------|----------|----|
|`freesurfer.txt`|`/opt/freesurfer/license.txt`||

## Commands
### fmriprep
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


|Key|Value|
|---|-----|
|Short description|fMRIPrep: a functional fMRI data preprocessing pipeline|
|Workflow|`arcana.tasks.bids:bids_app`|
|Version|`1`|
|Executable|`/opt/conda/bin/fmriprep`|
|Operates on|Session|
#### Inputs
|Path|Input format|Stored format|Description|
|----|------------|-------------|-----------|
|`T1w`|`medimage:NiftiGzX`|`medimage:Dicom`|T1-weighted anatomical scan|
|`T2w`|`medimage:NiftiGzX`|`medimage:Dicom`|T2-weighted anatomical scan|
|`fMRI`|`medimage:NiftiGzX`|`medimage:Dicom`|functional MRI|
|`fmap1_phasediff`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 1: phasediff image corresponding to the phase-diff map between echo times|
|`fmap1_shorterEcho_mag`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 1: magnitude of shorter echo|
|`fmap1_longerEcho_mag`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 1: magnitude of longer echo|
|`fmap2_echo1_mag`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 2: magnitude of first echo|
|`fmap2_echo1_phase`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 2: phase of first echo|
|`fmap2_echo2_mag`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 2: magnitude of second echo|
|`fmap2_echo2_phase`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 2: phase of second echo|
|`fmap3_fmap`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 3: directly reconstructed field map|
|`fmap3_mag`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 3: magnitude image used for anatomical reference|
|`fmap4_epi`|`medimage:NiftiGzX`|`medimage:Dicom`|Field map - BIDS Case 4: Spin Echo EPI scans with different phase encoding directions to estimate the distortion map corresponding to the nonuniformities of the B0 field|

#### Outputs
|Name|Output format|Stored format|Description|
|----|-------------|-------------|-----------|
|`fmriprep`|`common:Directory`|`format`||

#### Parameters
|Name|Data type|
|----|---------|
|`fmriprep_flags`|`string`|
|`json_edits`|`string`|

