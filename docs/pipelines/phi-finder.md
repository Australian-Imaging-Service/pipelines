---
source_file: /home/runner/work/pipelines/pipelines/specs/australian-imaging-service/quality-control/phi-finder.yaml
title: phi-finder
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|Name|phi-finder|
|Title|PHI-Finder|
|Version|0.1.8|
|Base image|`debian:bookworm-slim`|
|Maintainer|Pedro Faustini (pedro.faustini@mq.edu.au)|
|Info URL|https://github.com/Australian-Imaging-Service/phi-finder|

PHI-Finder is a tool for de-identifying DICOM files. It uses Tesseract OCR to extract text from images and then applies a set of rules to identify and remove sensitive information. The tool is designed to be easy to use and can be run from the command line or as part of a larger pipeline.

## Commands
|Key|Value|
|---|-----|
|Task|deidentify_dicom_files|
|Operates on|session|
#### Inputs
|Name|Data-type(s)|Required|Description|
|----|------------|--------|-----------|

#### Outputs
|Name|Data-type(s)|Always generated|Description|
|----|------------|----------------|-----------|

#### Parameters
|Name|Data-type(s)|Default|Description|
|----|------------|-------|-----------|
|`score_threshold`|<span data-toggle="tooltip" data-placement="bottom" title="field/decimal" aria-label="field/decimal">field/decimal</span>|`0.5`||
|`spacy_model_name`|<span data-toggle="tooltip" data-placement="bottom" title="field/text" aria-label="field/text">field/text</span>|`en_core_web_md`||
|`destroy_pixels`|<span data-toggle="tooltip" data-placement="bottom" title="field/boolean" aria-label="field/boolean">field/boolean</span>|`True`||
|`use_transformers`|<span data-toggle="tooltip" data-placement="bottom" title="field/boolean" aria-label="field/boolean">field/boolean</span>|||
|`dry_run`|<span data-toggle="tooltip" data-placement="bottom" title="field/boolean" aria-label="field/boolean">field/boolean</span>|||

