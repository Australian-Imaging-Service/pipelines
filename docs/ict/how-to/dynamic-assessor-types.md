---
title: "Enabling dynamic assessor types"
weight: 30
draft: true
owner: "James"
---

<!-- Diátaxis: how-to. Owner: James. Remove `draft: true` from the front matter when the page is ready to publish. -->

## Documentation points

- Prerequisites: XNAT 1.10+, Container Service, and a compatible reconciler and pipeline image.
- Register types and forms using `deploy-pipelines` or `install-command` with an XNAT site administrator account; image-label discovery alone does not register them.
- Explain how registration permissions differ from ordinary reconciliation, and where site credentials and deployment settings are managed.
- Cover existing type and form checks, schema or permission failures, form revisions and preserving existing results.
- Explain older-XNAT fallback, monitoring, result-upload failures and local support contacts.
- Link to [pydra2app-xnat](https://github.com/ArcanaFramework/pydra2app-xnat/blob/issue72-dynamic-assessors/README.md#pipeline-assessor-outputs-xnat-110) for implementation details.
