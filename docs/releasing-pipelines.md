# Releasing pipelines

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

## Reconciler image

Each tag release also publishes
`ghcr.io/australian-imaging-service/pipelines-reconciler:<tag>`, built from
[`reconciler/`](../reconciler). An existing tag is never overwritten. Nodes run it to
install and update the catalogue's commands in their XNAT instance:

```bash
docker run --rm \
  -e XNAT_HOST=https://xnat.example.org \
  -e XNAT_USER=username \
  -e XNAT_PASS=password \
  -v "$PWD/reconciler.yaml:/config/reconciler.yaml:ro" \
  -e PIPELINE_RECONCILER_CONFIG=/config/reconciler.yaml \
  ghcr.io/australian-imaging-service/pipelines-reconciler:<tag>
```

Each run performs one reconciliation using `pydra2app ext xnat deploy-pipelines`,
reports every pipeline as `installed`, `updated`, `unchanged` or `failed` with an
`enabled=N` count of its commands enabled by that run, and exits nonzero if any
pipeline fails. For example:

```text
mri.human.neuro.t1w.preprocess: installed (installed=1, updated=0, unchanged=0, enabled=1)
```

It reads the latest release's catalogue unless `PIPELINE_CATALOGUE_URL` is set.
Existing commands are updated in place, keeping their enablement, and nothing is
removed. The XNAT user must be an administrator or Container Service manager.

The config file is optional. It selects which pipelines are reconciled and
whether their commands are enabled:

```yaml
include:              # optional; leave out to take every pipeline
  - mri.human.neuro.*
exclude:              # optional; wins over include
  - mri.human.neuro.bidsapp.*
enablement: approval  # or "auto"; default is approval
```

Patterns are case-sensitive wildcards matched against the whole catalogue
pipeline ID, where `*` also matches `.`. Excluded pipelines are left untouched,
even if already installed. An invalid config fails before XNAT is contacted. A
pattern that matches no pipeline logs a warning. Without a config, every pipeline
is reconciled in `approval` mode.

- `approval`: new commands are installed disabled until an administrator enables
  them.
- `auto`: every selected command is enabled for the site on each run, including
  any an administrator has disabled. To block a pipeline, exclude it, then disable
  it in XNAT.

In both modes, project owners still enable commands for their own projects.

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
