# Releasing pipelines

The release workflow produces container images and a complete, versioned catalogue.

## Selection and building

The approved set is the workflow's `HAND_LISTED` entries plus committed generated
MONAI specs. Generated MONAI Python modules and their bundle configuration must be
committed alongside the specs. The planning job installs the pipelines package so
those task classes resolve.

`pydra2app plan-builds` checks this set against GHCR and produces `release-plan.json`
with `build` and `unchanged` lists. New and incremented versions are built in
independent matrix jobs; version decreases and changed specs without a version
increment fail planning.

`release-inventory.json` records the resolved image reference and commands for
every selected spec. Explicit image names/organisations and Pydra2App version
normalisation are respected rather than reconstructed independently by the
workflow. Stable catalogue IDs come from the spec path, not the image name.

Pull requests, branch pushes, and manual workflow runs build selected changes and
retain command JSON as Actions artifacts. Only a **tag push** pushes images and
publishes a catalogue. An all-unchanged tag release still assembles a complete
catalogue even though its build matrix is skipped.

## Published release

Each successful tag release contains:

- `pipeline-release.json`: the complete catalogue, validated against
  [`schemas/pipeline-release.schema.json`](../schemas/pipeline-release.schema.json).
- Individually named XNAT command JSON assets referenced by the catalogue.

Every pipeline entry records a stable ID, spec path, pipeline version, source image
tag, immutable image reference, and command assets. The catalogue also identifies
its release tag and source repository/commit. Command assets are checksummed, and
their top-level `image` field is rewritten to the same digest-pinned image reference
as the catalogue entry. Other XNAT command configuration is preserved.

The catalogue fields are `release.tag`, `source.repository`, `source.commit`, and
`pipelines[]` entries containing `id`, `spec`, `version`, `image_tag`, `image`, and
`commands[]`. Each command has `name`, `path`, `url`, and `sha256`. The hash covers
the exact downloadable file bytes. `image` is immutable; `image_tag` records
provenance.

The previous published catalogue supplies unchanged entries and command assets.
When no suitable previous entry exists, including the first catalogue release,
the workflow retrieves the already-published image and extracts its commands
without executing the container or rebuilding it. This bootstrap can download
large images and requires sufficient runner disk space and registry read access.
Authentication and extraction errors fail the release; they are not interpreted
as empty successful results.

Only the currently selected pipelines enter the catalogue. Removing a selection
removes its catalogue entry but does not delete its published image. Renaming a
spec changes its stable ID.

## Publication and retries

Push a tag at the intended commit and let the workflow publish the GitHub Release.
Alternatively, publish the release from the GitHub web UI (which creates the tag);
the workflow then attaches the catalogue assets to that published release, as
long as it has no `pipeline-release.json` yet and contains no unexpected
catalogue assets. The catalogue is uploaded last, so its presence marks the
asset set as complete; the release notes and any other assets are left as-is.
For tag-only pushes, the workflow:

1. Waits for every required build and immutable entry artifact.
2. Retrieves the preceding non-prerelease catalogue and checks commit ancestry.
3. Assembles and validates the complete catalogue and command assets.
4. Uploads assets to a draft GitHub Release and verifies the uploaded bytes.
5. Publishes the draft and marks it as the latest release.

Drafts are the staging area. Partial uploads and failed builds never become a
published catalogue. Images may have been pushed before another job fails: they
are not an advertised release until the catalogue is published. Subsequent
attempts can reuse these images rather than rebuilding an already-published
pipeline version.

Re-running a tag must not mutate a published catalogue. A matching published
release is a no-op; conflicting published content is an error. Failed draft
uploads can be retried. Do not move published Git tags or overwrite pipeline
image tags. Releases whose previous catalogue commit is not an ancestor of the
requested commit are rejected rather than rolling the latest channel backwards.

Tag pushes share a non-cancelling concurrency group with `queue: max` to prevent
overlapping publication without replacing pending releases. GitHub allows up to
100 pending runs in this queue. Ordering is based on when runs enter the queue. 
The ancestry check still protects against publishing an older commit after a newer one.

The publisher uses the repository's `GITHUB_TOKEN` with `contents: write`.
GHCR access uses `GHCR_TOKEN` when configured, otherwise `GITHUB_TOKEN`.
The selected token must be able to read all selected packages; the build job also
needs permission to push them. Downloading private release assets requires GitHub
authentication in addition to any GHCR credentials.
