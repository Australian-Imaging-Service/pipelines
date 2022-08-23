---
source_file: specs/mri/human/neuro/bidsapps/deepdicomsort.yaml
title: deepdicomsort
weight: 10

---

## Package Info
|Key|Value|
|---|-----|
|App version|0.1|
|XNAT wrapper version|1|
|Base image|`svordt/dds:0.1`|
|Info URL|https://deepdicomsort.com|

## Commands
### deepdicomsort
Automatically renames MRI DICOMs following BIDS naming convention

|Key|Value|
|---|-----|
|Short description|Automatically renames MRI DICOMs following BIDS naming convention|
|Workflow|`deepdicomsort4xnat:dds4xnat_workflow`|
|Version|`1`|
|Operates on|Session|
#### Inputs
|Path|Input format|Stored format|Description|
|----|------------|-------------|-----------|
|`mr_session`|`arcana.core.data.row:DataRow`|`format`|MR session to be sorted|

#### Outputs
|Name|Output format|Stored format|Description|
|----|-------------|-------------|-----------|
