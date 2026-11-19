---
source_file: /pydra2app-spec.yaml
title: mri.human.neuro.bidsapp.mriqc
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|mri.human.neuro.bidsapp.mriqc|
|Title|Extract quality control metrics from T1w, T2W and fMRI data|
|Version|26.1.1|
|Base image|`nipreps/mriqc:26.1.1`|
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
|`t1w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to" aria-label="medimage/nifti-gz-x+convertible-to">medimage/nifti-gz-x+convertible-to</span>|Y|T1-weighted anatomical MRI|
|`t2w`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|T2-weighted anatomical MRI|
|`bold`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz-x+convertible-to (optional)" aria-label="medimage/nifti-gz-x+convertible-to (optional)">medimage/nifti-gz-x+convertible-to (optional)</span>|N|Resting-state functional MRI|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`t1w_iqms`|<span data-toggle="tooltip" data-placement="bottom" title="application/json" aria-label="application/json">application/json</span>|Y|Image quality metrics of the T1-weighted image|
|`t1w_report`|<span data-toggle="tooltip" data-placement="bottom" title="text/html" aria-label="text/html">text/html</span>|Y|Visual QC report of the T1-weighted image|
|`figures`|<span data-toggle="tooltip" data-placement="bottom" title="generic/directory" aria-label="generic/directory">generic/directory</span>|Y|Figures of the QC reports|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`flags`|<span data-toggle="tooltip" data-placement="bottom" title="field/text+list-of" aria-label="field/text+list-of">field/text+list-of</span>||Additional flags to pass to the app. These are passed as a list of strings and should be formatted as they would be on the command line (e.g. '--flag1 --flag2 value')|

