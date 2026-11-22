---
source_file: /pydra2app-spec.yaml
title: wholeBody_ct_segmentation
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|wholeBody_ct_segmentation|
|Title|MONAI Whole Body CT Segmentation|
|Version|0.2.7|
|Base image|`projectmonai/monai:1.6.1`|
|Maintainer|MONAI Consortium (monai.contact@gmail.com)|
|Info URL|https://monai.io/model-zoo.html|

A SegResNet-based volumetric segmentation model that segments 104 distinct anatomical structures from CT scans. The model processes 96x96x96 pixel patches and provides segmentation masks for major organs, bones, muscles, and vascular structures throughout the body, trained on TotalSegmentator data.

## Commands
|Key|Value|
|---|-----|
|Task|WholeBodyCtSegmentation|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|
|`image`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz+convertible-to" aria-label="medimage/nifti-gz+convertible-to">medimage/nifti-gz+convertible-to</span>|Y|CT image, format: hounsfield, 1 channel(s), patch size: [96, 96, 96]|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|
|`pred`|<span data-toggle="tooltip" data-placement="bottom" title="medimage/nifti-gz" aria-label="medimage/nifti-gz">medimage/nifti-gz</span>|Y|format: segmentation, 105 channel(s), patch size: [96, 96, 96]|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|

