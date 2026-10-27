---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/mri/human/neuro/dwi/preprocess.yaml
title: human.neuro.dwi.preprocess
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|human.neuro.dwi.preprocess|
|Title|Preprocess diffusion-weighted MRI|
|Version|0.1.1|
|Base image|`debian:bookworm-slim`|
|Maintainer|Arkiev D'Souza (arkiev.dsouza@sydney.edu.au)|
|Info URL|https://placeholder.org|

Preprocess a diffusion-weighted MRI series: gradient-check, denoise,
Gibbs-ringing removal, motion/distortion correction (eddy/topup via
dwifslpreproc), bias-field correction, brain-extraction/cropping, and
tissue response function estimation (Dhollander). The reverse
phase-encode (RPE) image is optional — if not provided, only eddy
correction is applied (no topup).


### Required licenses
|Name|URL|Description|
|----|---|-----------|
|freesurfer|`https://surfer.nmr.mgh.harvard.edu/registration.html`|DwiPreprocessing uses mri_synthstrip (a FreeSurfer-distributed tool) for brain masking, which requires a FreeSurfer license to run.|

## Commands
|Key|Value|
|---|-----|
|Task|australianimagingservice.mri.human.neuro.dwi.dwi_preprocessing:DwiPreprocessing|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`DWI`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-x-bvec+convertible-to" aria-label="medimage/nifti-x-bvec+convertible-to">medimage/nifti-x-bvec+convertible-to</span>|Y|The diffusion-weighted MRI series to preprocess|
|`RPE`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-x-bvec+convertible-to (optional)" aria-label="medimage/nifti-x-bvec+convertible-to (optional)">medimage/nifti-x-bvec+convertible-to (optional)</span>|N|Optional reverse phase-encode (or b0-only) companion image, used for topup distortion correction. If not provided, only eddy motion correction is performed.|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`dwi_preprocess`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y||

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`PeDir`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`AP`|Phase-encode direction of the DWI series (e.g. AP, PA, LR, RL, SI, IS)|
|`RpeMode`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`rpe_none`|Reverse phase-encode mode passed to dwifslpreproc: rpe_none (no RPE image), rpe_pair (RPE is b0-only or unequal volumes to DWI), rpe_all (RPE is a full DWI series with equal volumes), or rpe_header (PE info embedded in the image header)|
|`ReadoutTime`|<span data-toggle="tooltip" data-placement="bottom" title="field/decimal (optional)" aria-label="field/decimal (optional)">field/decimal (optional)</span>||Total readout time (s) of the DWI acquisition, if known|
|`FodAlgorithm`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`msmt_csd`|FOD estimation algorithm downstream steps should use: msmt_csd (multi-shell) or ss3t (single-shell)|

