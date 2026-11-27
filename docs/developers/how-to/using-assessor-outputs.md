---
title: "Using assessor outputs"
weight: 40
draft: true
owner: "James"
---

<!-- Diátaxis: how-to. Remove `draft: true` when the page is ready to publish. -->

## Documentation points

- Opt in per command with `assessor_outputs: true`, then rebuild, release and install the image. Commands without opt-in retain their existing behavior.
- Explain session, subject and dataset result scopes and Container Service REST wrapper input names.
- Cover file outputs, explicitly declared scalar sinks and supported scalar types.
- Explain staging until success, `internal_upload` incompatibility and the separate work needed to read assessors as FrameTree derivatives.
- Cover stable types, form revisions, reruns and output reconciliation.
- Test registration, file and scalar outputs, provenance and failed runs on XNAT 1.10+.
- Link to [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat/blob/issue72-dynamic-assessors/README.md#pipeline-assessor-outputs-xnat-110); the implementation is not yet on main.
