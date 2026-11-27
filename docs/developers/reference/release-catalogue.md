---
title: "Release catalogue"
weight: 20
---

Each successful tag release contains:

- `pipeline-release.json`: the complete catalogue, validated against
  [`schemas/pipeline-release.schema.json`](../../../schemas/pipeline-release.schema.json).
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
spec changes its stable ID. Spec paths follow the
[pipeline naming convention](../reference/pipeline-naming.md).
