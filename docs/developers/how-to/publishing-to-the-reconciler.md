---
title: "Publishing a new pipeline to the reconciler"
weight: 30
draft: true
owner: "James"
---

<!-- Diátaxis: how-to. Owner: James. Remove `draft: true` from the front matter when the page is ready to publish. -->

## Documentation points

- Explain the path from a reviewed spec and version bump to an image, XNAT command assets, release catalogue and scheduled node reconciliation.
- Explain stable pipeline IDs, command names, site filters and the effects of renaming.
- Cover version increments, digest-pinned images and checksummed command assets; an image build alone is not a published catalogue.
- Document inputs, outputs, resources, licences and breaking changes in pipeline docs and release notes; notify site operators of required action.
- Cover validation of command assets and the catalogue, and diagnosis of build, publication and node-side failures.
- Link to the [release process](../explanation/release-process.md), [pipeline naming](../reference/pipeline-naming.md), [catalogue reference](../reference/release-catalogue.md) and [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat#reconcile-xnat-pipelines).
