---
title: "Publishing Zenodo references"
weight: 20
owner: "James"
---

Tag releases create a Zenodo Sandbox reference for each new pipeline version.
Sandbox issues **test DOIs**, not production references. Set the repository secret
`ZENODO_SANDBOX_TOKEN` to a Sandbox account token with `deposit:write` and
`deposit:actions` scopes. Do not use a production Zenodo token.

Every selected spec must explicitly declare a top-level `license` accepted by
Zenodo, plus a title, version, author names, and `docs.description`. The
licence describes the deposited spec and metadata, not necessarily every tool
in the image. Existing specs need their licence confirmed and added before this
workflow can publish a tag; editing a published spec requires a version bump.
For MONAI-generated specs, set each model's `license` in
`scripts/monai_whitelist.yaml` so regeneration retains it.

Each record contains the spec and release metadata linking to the exact source
commit and digest-pinned image. The build jobs create drafts; the catalogue job
prepares any missing drafts, publishes the GitHub release, then publishes the
Sandbox records. It logs the test DOI for each newly referenced version.
Existing versions are reused and mismatched records fail rather than overwrite.
When Zenodo returns a legacy licence alias, retries compare it using a pinned,
checksum-verified copy of Zenodo's published alias mapping fetched from GitHub.
An unavailable mapping or an unknown mismatch fails the release instead of
assuming the licences are equivalent.

Zenodo publication follows GitHub publication, so it is not atomic with the
release: a Zenodo failure can leave a published GitHub release without all its
references. Correct the failure and rerun the release workflow. An unfinished
or conflicting Zenodo draft must be inspected in Sandbox before retrying.
