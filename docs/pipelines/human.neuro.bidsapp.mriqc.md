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
|Task|DeferredBidsappTask|
|Operates on|session|
Inputs, outputs and parameters could not be introspected in this environment (the task's package isn't installed here); see the docs generated from within the built image.

