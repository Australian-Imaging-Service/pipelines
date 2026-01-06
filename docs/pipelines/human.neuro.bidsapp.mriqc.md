---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/mri/human/neuro/bidsapp/mriqc.yaml
title: human.neuro.bidsapp.mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|human.neuro.bidsapp.mriqc|
|Title|Extract quality control metrics from T1w, T2W and fMRI data|
|Version|24.0.2|
|Base image|`nipreps/mriqc:24.0.2`|
|Maintainer|Thomas G. Close (thomas.close@sydney.edu.au)|
|Info URL|https://mriqc.readthedocs.io|

MRIQC extracts no-reference IQMs (image quality metrics) from
structural (T1w and T2w) and functional MRI (magnetic resonance
imaging) data.


## Commands
|Key|Value|
|---|-----|
|Task|mriqc|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`t1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x</span>|Y|T1-weighted anatomical MRI|
|`t2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x</span>|Y|T2-weighted anatomical MRI|
|`bold`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x" aria-label="medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x">medimage/dicom-dir\|medimage/dicom-series\|medimage/nifti-gz-x</span>|Y|Resting-state functional MRI|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`mriqc`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y|Generated QC outputs|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`analysis_level`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`participant`|Level of analysis to run the app at|
|`json_edits`|<span data-toggle="tooltip" data-placement="bottom" title="field/text+tuple-of+list-of (optional)" aria-label="field/text+tuple-of+list-of (optional)">field/text+tuple-of+list-of (optional)</span>|||
|`flags`|<span data-toggle="tooltip" data-placement="bottom" title="field/text (optional)" aria-label="field/text (optional)">field/text (optional)</span>||Additional flags to pass to the app. These are passed as a single string and should be formatted as they would be on the command line (e.g. '--flag1 --flag2 value')|

