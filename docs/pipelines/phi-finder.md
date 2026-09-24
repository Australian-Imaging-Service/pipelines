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
|Version|0.1.16.post1|
|Base image|`debian:bookworm-slim`|
|Maintainer|Pedro Faustini (pedro.faustini@mq.edu.au)|
|Info URL|https://github.com/Australian-Imaging-Service/phi-finder|

PHI-Finder is a tool for de-identifying DICOM files. It uses Tesseract OCR to extract text from images and then applies a set of rules to identify and remove sensitive information. The tool is designed to be easy to use and can be run from the command line or as part of a larger pipeline.

## Commands
|Key|Value|
|---|-----|
|Task|deidentify_dicom_files|
|Operates on|session|
Inputs, outputs and parameters could not be introspected in this environment (the task's package isn't installed here); see the docs generated from within the built image.

