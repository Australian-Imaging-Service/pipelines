# Dynamic assessor documentation outline

Points to cover for pipeline results stored as XNAT assessors. The implementation
is currently on a pydra2app-xnat feature branch, not main.

## ICT support staff

- **Purpose and requirements:** Explain that assessor-enabled pipelines register result types and forms in XNAT; they do not require a separate service. Cover XNAT 1.10+, Container Service, and a compatible reconciler and pipeline image. **Location:** [pydra2app-xnat assessor documentation](https://github.com/ArcanaFramework/pydra2app-xnat/blob/issue72-dynamic-assessors/README.md#pipeline-assessor-outputs-xnat-110), linked from the [pipelines release guide](releasing-pipelines.md).

- **Installation and permissions:** `deploy-pipelines` or `install-command` registers types and forms, requiring an XNAT site administrator. Explain how this differs from ordinary reconciler permissions, and that image-label discovery alone does not register them. **Location:** pydra2app-xnat assessor documentation; site-specific credentials and deployment in [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io) (page to be decided).

- **Operations:** Cover existing-type and form checks, schema or permission failures, form revisions and preserving existing results. Explain the fallback to existing output storage on older XNAT versions and how to identify registration or result-upload failures. **Location:** pydra2app-xnat assessor documentation; local monitoring and contacts in AIS documentation (page to be decided).

## Pipeline developers

- **Opt-in:** Show `assessor_outputs: true` on a command, rebuilding and releasing the image, and installing it through the reconciler or `install-command`. Commands without opt-in retain their existing behavior. **Location:** pydra2app-xnat assessor documentation; link from the [pipelines release guide](releasing-pipelines.md).

- **Result scope:** Explain `medimage/session`, `medimage/subject` and `medimage/dataset`, where their results are attached, and the supported run scope. For Container Service REST launches, document the required wrapper input names. **Location:** pydra2app-xnat assessor documentation.

- **Outputs and constraints:** Document file outputs, explicitly declared scalar sinks and supported scalar types. Cover staging until success, `internal_upload` incompatibility, and that reading assessors as FrameTree derivatives is separate work. **Location:** pydra2app-xnat assessor documentation; individual pipeline specs for their outputs.

- **Changes and testing:** Explain stable assessor types, new form revisions when fields change, reruns and output reconciliation. Cover testing on XNAT 1.10+, including command registration, file and scalar outputs, provenance and failed runs. **Location:** pydra2app-xnat developer documentation or tests (page to be decided); pipeline-specific checks in the pipelines repository.

## Pipeline users

- **Finding results:** Explain where session and subject results appear, where file outputs and scalar values are stored, and how to search form fields. Note the XNAT 1.10 limitation for browsing project-level results. **Location:** [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io), pipeline user guide (page to be decided).

- **Understanding results:** Explain how to find pipeline version, image, inputs, parameters and workflow information, and when a rerun reuses an existing result. Describe the `PROVENANCE/provenance.json` file. **Location:** AIS pipeline user guide, linked from individual pipeline pages (locations to be decided).

- **Access and support:** Results use the launching user's project permissions. Explain whom to contact for missing results, access problems or failed runs. **Location:** AIS pipeline user guide and site support documentation (pages to be decided).

## Existing technical references

- [pydra2app-xnat assessor documentation on the feature branch](https://github.com/ArcanaFramework/pydra2app-xnat/blob/issue72-dynamic-assessors/README.md#pipeline-assessor-outputs-xnat-110).
- [Releasing pipelines](releasing-pipelines.md) — image publication and reconciliation.
