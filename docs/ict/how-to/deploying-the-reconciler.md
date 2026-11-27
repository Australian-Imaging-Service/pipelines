---
title: "Deploying the reconciler"
weight: 10
owner: "James"
---

Each tag release also publishes
`ghcr.io/australian-imaging-service/pipelines-reconciler:<tag>`, built from
[`reconciler/`](../../../reconciler). An existing tag is never overwritten. Nodes run it to
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
human.neuro.mri.anat.t1w-preprocess: installed (installed=1, updated=0, unchanged=0, enabled=1)
```

It reads the latest release's catalogue unless `PIPELINE_CATALOGUE_URL` is set.
Existing commands are updated in place, keeping their enablement, and nothing is
removed. The XNAT user must be an administrator or Container Service manager.

The config file is optional. It selects which pipelines are reconciled and
whether their commands are enabled:

```yaml
include:              # optional; leave out to take every pipeline
  - human.*.mri.*
exclude:              # optional; wins over include
  - human.neuro.mri.func.fmriprep
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

<!-- Documentation points:
- Explain the reconciler's purpose, prerequisites and node responsibilities.
- Cover image tags, credentials, secure storage, non-root execution and scheduling.
- Document the site's Kubernetes setup, monitoring and support contacts once decided.
- Explain the catalogue choice separately from the reconciler image version.
- Cover selection patterns, approval and auto enablement, including project enablement.
- Explain updates, preserved enablement, exclusions and handling renamed commands.
- Cover result counts, nonzero exits, retries, invalid config, unmatched patterns,
  authentication, access, checksum errors and duplicate command names.
- Refer to pydra2app-xnat for command behavior and the pipeline naming guide for IDs.
-->
