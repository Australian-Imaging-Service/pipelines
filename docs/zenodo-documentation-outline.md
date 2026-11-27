# Zenodo documentation outline

Points to cover for the intended production workflow. Production publication and
authorship classification are not yet implemented.

Zenodo records describe released pipeline versions. They are created centrally
by the release workflow and are not needed to install or run pipelines.

## Pipeline developers

- **Release setup:** Explain the Zenodo account used to publish records, who manages it, and how the release workflow's credentials are stored, rotated and authorised. **Location:** [Pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references), updated for production.

- **Required metadata:** Each selected spec needs a title, version, authors, description and explicit top-level licence accepted by Zenodo. Confirm authorship and the licence for the deposited material; runtime software licences are separate. **Location:** [pydra2app spec documentation](https://github.com/ArcanaFramework/pydra2app/blob/main/docs/source/building.rst) for fields; [pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references) for release requirements.

- **Generated specs:** Set licences for MONAI-generated specs in `scripts/monai_whitelist.yaml` so regeneration retains them. **Location:** [Pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references).

- **Release and versioning:** Tag releases create references for new pipeline versions. Explain how records for successive versions relate, how unchanged versions are reused, and that older missing references are not automatically backfilled. Changing a published spec requires a version increment. **Location:** [Pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references).

- **Record contents:** The record includes the pipeline spec and release metadata linking to the exact source commit and digest-pinned image. It does not contain the full source tree or container image. **Location:** [Pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references), linked from user documentation.

- **Validation and failures:** Explain metadata validation before release, missing or invalid fields, licence mismatches and duplicate records. Check workflow logs for drafts, publication and DOI links. GitHub and Zenodo publication are separate: a GitHub release can succeed while Zenodo fails. Explain how to inspect conflicting drafts, correct errors and rerun the workflow. **Location:** [Pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references).

- **Authorship classification:** Explain how to record whether a pipeline is AIS-developed or an XNAT wrapper around upstream software, and how to identify and credit the upstream work. **Location:** [pydra2app spec documentation](https://github.com/ArcanaFramework/pydra2app/blob/main/docs/source/building.rst) for field syntax; [pipelines release guide](releasing-pipelines.md#zenodo-sandbox-references) for AIS publication policy.

## Pipeline users

- **Finding a reference:** Where to find a pipeline's Zenodo record and the reference for a particular version. **Location:** [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io), user guide or individual pipeline pages (location to be decided).

- **Citing and attribution:** Explain how to select and cite the pipeline version used, including any required citation of upstream software. **Location:** [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io), user guide or individual pipeline pages (location to be decided).

- **What the record provides:** Explain the recorded authors, licence and description, and where the attached spec and release metadata point to the source and image. **Location:** [AIS documentation](https://github.com/Australian-Imaging-Service/Australian-Imaging-Service.github.io), user guide (location to be decided).

## Existing technical references

- [Releasing pipelines](releasing-pipelines.md#zenodo-sandbox-references) — current Sandbox implementation and release behavior.
- [Zenodo](https://zenodo.org/) — production records and accounts.
