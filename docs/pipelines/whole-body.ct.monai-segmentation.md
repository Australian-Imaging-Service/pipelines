---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/human/whole-body/ct/monai-segmentation.yaml
title: whole-body.ct.monai-segmentation
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|whole-body.ct.monai-segmentation|
|Title|MONAI Whole Body CT Segmentation|
|Version|0.2.7|
|Base image|`projectmonai/monai:1.6.1`|
|Maintainer|MONAI Consortium (monai.contact@gmail.com)|
|Info URL|https://monai.io/model-zoo.html|

A SegResNet-based volumetric segmentation model that segments 104 distinct anatomical structures from CT scans. The model processes 96x96x96 pixel patches and provides segmentation masks for major organs, bones, muscles, and vascular structures throughout the body, trained on TotalSegmentator data.

MONAI Model Zoo bundle `wholeBody_ct_segmentation`, version 0.2.7.

## Commands
|Key|Value|
|---|-----|
|Task|DeferredMonaiTask|
|Operates on|session|
Inputs, outputs and parameters could not be introspected in this environment (the task's package isn't installed here); see the docs generated from within the built image.

