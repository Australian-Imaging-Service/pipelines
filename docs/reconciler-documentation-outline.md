# Reconciler documentation outline

Points to cover when writing documentation for each audience.
Locations below are suggestions; they do not imply the documentation is complete.

## ICT support staff

- **Purpose:** Each AIS node runs the reconciler against its own XNAT. It reads the published pipeline catalogue and installs or updates XNAT Container Service commands. It does not run the pipelines itself. **Location:** [Pipelines release guide](releasing-pipelines.md#reconciler-image).

- **Prerequisites:** XNAT with Container Service, an XNAT administrator or Container Service manager account, access to the reconciler image, catalogue and command assets, and access to pipeline images when they are run. **Location:** [Pipelines release guide](releasing-pipelines.md#reconciler-image); link to [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines) for command requirements.

- **Deployment:** Reconciler image and release tag; `XNAT_HOST`, `XNAT_USER`, `XNAT_PASS`; secure credential storage; non-root execution. Each invocation runs once and exits, so the site must schedule repeated runs. Document the
  site's Kubernetes scheduling, configuration and monitoring once decided. **Location:** [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io) for site-specific deployment (page to be decided); link from the [pipelines release guide](releasing-pipelines.md#reconciler-image).

- **Catalogue:** The image defaults to the latest published catalogue; `PIPELINE_CATALOGUE_URL` can select another catalogue. Explain that the reconciler image version and the catalogue release are separate choices. **Location:** [Pipelines release guide](releasing-pipelines.md#reconciler-image).

- **Selection:** Optional `PIPELINE_RECONCILER_CONFIG` YAML file; `include` and `exclude` patterns match pipeline IDs, are case-sensitive, and `exclude` wins. Without a config, all pipelines are selected. **Location:** [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#selecting-and-enabling-pipelines) for config behavior; link from the [pipeline naming guide](pipeline-naming.md) for AIS patterns.

- **Approval:** `approval` is the default: new commands are installed disabled. `auto` enables selected commands site-wide on every run, including commands an administrator disabled. Project owners still enable commands for their own
  projects. To block an auto-enabled command, exclude its pipeline and disable it in XNAT. **Location:** [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#selecting-and-enabling-pipelines); link from the [pipelines release guide](releasing-pipelines.md#reconciler-image).

- **Updates and removal:** Updates preserve existing site and project enablement. Excluded or removed catalogue entries are left untouched; the reconciler does not delete commands. Explain how staff should handle renamed
  pipelines and old commands. **Location:** [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines) for general behavior and the [pipeline naming guide](pipeline-naming.md) for AIS renames.

- **Operations:** Interpret `installed`, `updated`, `unchanged`, `failed` and enablement counts; monitor nonzero exits and retry failures. Cover invalid configuration, unmatched patterns, authentication, catalogue or image access,
  checksum errors and duplicate XNAT command names. **Location:** [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines) for command errors; [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io) for site monitoring and contacts (page to be decided).

## Pipeline developers

- **Release path:** A reviewed spec and version increment lead to a pipeline image, XNAT command assets and a complete release catalogue. The reconciler consumes the catalogue; node schedules determine when sites pick up changes. **Location:** [Pipelines release guide](releasing-pipelines.md).

- **Identity:** The spec path determines the stable pipeline ID used by catalogue entries and site filters. Explain naming, command names, and the impact of renaming: sites can retain the old command and install the new one separately. **Location:** [Pipeline naming guide](pipeline-naming.md).

- **Versioning:** Changed published specs require a version bump. The catalogue records digest-pinned images and checksummed command assets; explain why a successful image build alone is not a published catalogue. **Location:** [Pipelines release guide](releasing-pipelines.md); link to [pydra2app spec documentation](https://github.com/ArcanaFramework/pydra2app/blob/main/docs/source/building.rst) for versioning.

- **Compatibility:** Document pipeline inputs, outputs, runtime resources, licences and breaking changes. Tell site operators when an update needs attention or reconfiguration. **Location:** Individual pipeline documentation generated from specs, plus release notes in the [pipelines repository](https://github.com/Australian-Imaging-Service/pipelines).

- **Validation and failures:** Check generated XNAT commands, the release catalogue and reconciliation results. Explain how to diagnose failed builds, missing catalogue assets or node-side failures and who should be contacted. **Location:** [Pipelines release guide](releasing-pipelines.md) for build and catalogue failures; [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines) for reconciliation.

## Existing technical references

- [Releasing pipelines](releasing-pipelines.md) — catalogue, reconciler image, configuration and release process.
- [Pipeline naming](pipeline-naming.md) — pipeline IDs and selection patterns.
- [pydra2app-xnat reconciler documentation](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines) — command behavior and options.
