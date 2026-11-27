---
title: "How the release process works"
weight: 10
---

The release workflow produces container images and a complete, versioned catalogue.

## Selection and building

Every spec under `specs/australian-imaging-service` is selected unless it is
listed in the workflow's `EXCLUDED` block, each entry with a `#` comment giving
the reason. Generated MONAI specs are selected the same way. They are
self-contained: the command's sources and sinks are written into the spec at
sync time, so nothing from the bundle is committed. Before a MONAI spec is built,
the workflow runs `python -m scripts.monai_specs fetch-resources` to download
the full bundle, weights included, at the version recorded in the spec, and
passes it to the build with `--resources-dir`.

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

See [the release catalogue](../reference/release-catalogue.md) for what a release contains, [Publishing Zenodo references](../how-to/publishing-zenodo-references.md) for the Zenodo step, and [Deploying the reconciler](../../ict/how-to/deploying-the-reconciler.md) for how nodes install a release.
