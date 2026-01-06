---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/mri/human/neuro/t1w/preprocess.yaml
title: human.neuro.t1w.preprocess
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|human.neuro.t1w.preprocess|
|Title|Preprocess T1-weighted MRI|
|Version|1.1.4|
|Base image|`deepmi/fastsurfer:gpu-v2.2.0`|
|Maintainer|Arkiev D'Souza (arkiev.dsouza@sydney.edu.au)|
|Info URL|https://placeholder.org|

Generate a 5TT image (HSVS) and parcellation image (Desikan, Destrieux, HCPMMP1,
Yeo7 and Yeo17) from a single input anatomical image. Input image should satisfy
the input requirements for FastSurfer


### Required licenses
|Name|URL|Description|
|----|---|-----------|
|freesurfer|`https://surfer.nmr.mgh.harvard.edu/registration.html`|FastSurfer, which is used to perform segmentation and surface recon, requires a FreeSurfer license to run.|

## Commands
|Key|Value|
|---|-----|
|Task|australianimagingservice.mri.human.neuro.t1w.preprocess.single_parc:SingleParcellation|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz</span>|Y|The T1-weighted MRI dataset to preprocess|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`parc_image`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`vis_image_fsl`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||
|`ftt_image_fsl`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||
|`vis_image_freesurfer`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||
|`ftt_image_freesurfer`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||
|`vis_image_hsvs`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||
|`ftt_image_hsvs`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|N||

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`Parcellation`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`-`|The parcellation to parcelate the cortex with|
|`FastSurferBatchSize`|<span data-toggle="tooltip" data-placement="bottom" title="field/integer" aria-label="field/integer">field/integer</span>|`16`|Batch size to use for FastSurfer inference|
|`FastSurferNThreads`|<span data-toggle="tooltip" data-placement="bottom" title="field/integer" aria-label="field/integer">field/integer</span>|`24`|Number of threads to use for FastSurfer inference|

|Key|Value|
|---|-----|
|Task|australianimagingservice.mri.human.neuro.t1w.preprocess.all_parcs:AllParcellations|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`T1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz</span>|Y|The T1-weighted MRI dataset to preprocess|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`parcellations`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format+directory-of" aria-label="medimage/vnd.mrtrix3.image-format+directory-of">medimage/vnd.mrtrix3.image-format+directory-of</span>|Y||
|`vis_image_fsl`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`ftt_image_fsl`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`vis_image_freesurfer`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`ftt_image_freesurfer`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`vis_image_hsvs`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||
|`ftt_image_hsvs`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/vnd.mrtrix3.image-format" aria-label="medimage/vnd.mrtrix3.image-format">medimage/vnd.mrtrix3.image-format</span>|Y||

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`FastSurferBatchSize`|<span data-toggle="tooltip" data-placement="bottom" title="field/integer" aria-label="field/integer">field/integer</span>|`16`|Batch size to use for FastSurfer inference|
|`FastSurferNThreads`|<span data-toggle="tooltip" data-placement="bottom" title="field/integer" aria-label="field/integer">field/integer</span>|`24`|Number of threads to use for FastSurfer inference|

