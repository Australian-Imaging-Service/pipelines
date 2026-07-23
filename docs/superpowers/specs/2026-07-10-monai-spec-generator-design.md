# MONAI model registry + spec generator — design

## Context

The Australian Imaging Service `pipelines` repo builds container images for
XNAT by way of `pydra2app`/`pipeline2app` YAML specs
(`specs/australian-imaging-service/<modality>/<species>/<region>/<name>.yaml`).
Today every spec points `command.task` at a conventional pydra-tasks package
(e.g. FastSurfer, FSL). We want to add **MONAI Model Zoo bundles** as a first
class source of pipelines.

The sibling package **`pydra-compose-monai`** (`../pydra-compose-monai`, on
PyPI) already turns a MONAI bundle on disk into a runnable
`pydra.compose.base.Task` subclass: `define(bundle_path)` parses the bundle's
`configs/metadata.json` (`network_data_format.inputs/outputs`), maps each field
to a fileformats datatype, and builds a `MonaiTask`. Running the task loads
`inference.json` and runs the bundle evaluator. What it does **not** have:
YAML-spec serialization, and any Model Zoo *listing* / whitelist / version
tracking.

The goal: a scheduled process in `pipelines` that fetches the MONAI model list,
filters it to a whitelist, detects new/updated models, generates/updates a
`pipeline2app` spec per model, and writes those specs into the `specs/` tree so
the existing `pydra2app xnat make` build path can turn them into XNAT images.

This work targets the existing **`monai-test`** branch of `pipelines`.

## Target spec contract (confirmed from pipeline2app/frametree source)

- Specs are consumed by **`pipeline2app`** (module `pydra2app`), built with
  `pydra2app xnat make <spec>`. `pipelines/tests/test_monai.py` already exercises
  this via `XnatApp.load(SPEC_PATH)` + iterating `image_spec.commands`.
- The **current 2.x schema** applies (not the older `schema_version: 1.0`
  sample): top-level `commands:` is a **list**; per-command keys are `task`,
  `operates_on`, `sources`, `sinks`, `parameters`, `configuration`.
- **`command.task`** must resolve to an **importable subclass of
  `pydra.compose.base.Task`** (`module:ClassName`) whose fields pipeline2app
  introspects via `pydra.utils.get_fields`. A `MonaiTask` qualifies.
- **`configuration`** is a dict of constant task-constructor kwargs not exposed
  to the user; every key must be a real task input field. Passed at runtime as
  `task(**configuration)`.
- **`operates_on`** = the dataset row frequency (e.g. `session`); sinks must be
  at that frequency.
- Datatypes are fileformats MIME-like strings (e.g. `medimage/nifti-gz`).

## Architecture

Two repos; one small addition to `pydra-compose-monai`, the bulk in `pipelines`.

### Division of responsibility

- **pydra-compose-monai** adds the MONAI→fileformats *serialization* (see below)
  so that mapping stays in one tested place, plus the generic parametric task
  that specs point at.
- **pipelines** owns the registry pipeline (`MonaiModels`), the whitelist, the
  overlays, the generated specs, and the scheduled Action.

### Execution model (decided)

Each model's **bundle is baked into the image at build time** (downloaded and
vendored during the build), and the spec's `command.task` points at a **generic
parametric MONAI task** — Option B below — with the baked-in bundle directory
supplied via `configuration: {bundle: /opt/bundles/<model>}`.

**command.task binding — Option B (prototype) with Option A fallback:**
- **B (prototype):** one hand-written class `pydra.compose.monai:BundleTask` for
  all models; the specific bundle is selected via `configuration`. The
  per-model `sources`/`sinks`/`parameters` come from the spec, generated from
  the bundle. No per-model code generation.
- **A (fallback):** if pipeline2app rejects spec-declared fields that are not
  static attrs fields on the task, generate a real importable per-model class
  (e.g. `pydra.tasks.monai:SpleenCtSegmentation`) with the bundle baked in.
  Only `MonaiModels.generate_spec` changes.

The go/no-go test for B vs A is whether `XnatApp.load(<generated spec>)` +
`.commands` introspection succeeds — the assertion `test_monai.py` already makes.

## Component 1 — addition to `pydra-compose-monai`

One public function, serializing what `parse_monai_spec()` already computes:

```python
spec_fragment(bundle_path) -> {"sources": {...}, "sinks": {...}, "parameters": {...}}
```

- Emits fileformats datatype strings (`medimage/nifti-gz`), `help`, and output
  `path`s — the per-command field block in 2.x vocabulary.
- Reuses `parse_monai_spec` / `_map_type` / `_input_help` / `_output_help`
  (`pydra/compose/monai/spec_parser.py`) — no new mapping logic.

Plus the generic `BundleTask` (Option B) whose `bundle` input is set via the
command `configuration`. (`MonaiTask` already resolves a bundle *directory*,
`pydra/compose/monai/task.py:_resolve_bundle_dir`.)

## Component 2 — `MonaiModels` (in `pipelines/scripts/monai_specs.py`)

Placement: **`scripts/` for the PoC** (tooling that generates specs, excluded
from the shipped package — `pyproject.toml` already excludes `scripts/` from
mypy). Promote reusable pieces into `src/australianimagingservice/...` later.

| Method | Responsibility | Depends on |
|---|---|---|
| `fetch_available()` | List Model Zoo bundles + latest versions | `monai.bundle` (`get_all_bundles_list`, `get_bundle_versions`) |
| `filter_whitelist()` | Keep only whitelisted models | `scripts/monai_whitelist.yaml` |
| `detect_changes()` | Diff available versions vs versions recorded in existing specs → new/updated set | existing `monai/` specs' `version` field |
| `generate_spec(model)` | Download+vendor bundle → call `pydra_compose_monai.spec_fragment` → deep-merge with the model's overlay → full `XnatApp` 2.x spec dict | pydra-compose-monai, per-model overlay |
| `write_spec(model, spec)` | Write to the `monai/` namespace path | PyYAML |
| `sync()` | End-to-end; entry point the Action calls | — |

**Control surfaces (hand-authored for the PoC):**
- `scripts/monai_whitelist.yaml` — which models, optional version pins, and the
  anatomy placement (modality/species/region) for each.
- Per-model **overlay** — fields not derivable from a bundle: `title`,
  `authors`, `docs.info_url`, `base_image`, `packages`, `operates_on`. The
  generator deep-merges so MONAI-derived `sources`/`sinks` refresh each run
  while hand-authored fields survive. This is the seam for later auto-generation
  (swap overlay → template).

### Spec output location (decided: dedicated `monai/` namespace)

Generated specs land under a `monai/` subtree keyed by anatomy, e.g.
`specs/australian-imaging-service/<modality>/<species>/<region>/monai/<model>.yaml`.
Keeping auto-generated specs in their own namespace lets the Action regenerate/
overwrite them safely without touching hand-authored specs.

## Component 3 — scheduled GitHub Action

- `cron`-scheduled workflow in `pipelines/.github/workflows/`.
- Runs `python -m scripts.monai_specs sync`.
- Opens a **PR** with changed specs (not a direct push) so regenerated specs are
  reviewed before merge.

## Verification

- **Unit** — test each `MonaiModels` method against a synthetic bundle (reuse
  pydra-compose-monai's synthetic-bundle fixtures); no network.
- **Contract (go/no-go for B vs A)** — `XnatApp.load(<generated spec>)` succeeds
  and `.commands` introspects, matching `pipelines/tests/test_monai.py`.
- **Build** — `pydra2app xnat make <spec> --generate-only` (the `SKIP_BUILD`
  path already in `test_monai.py`).
- **End-to-end** (optional, network) — full `--build` + XNAT container-service
  launch, as `test_monai.py` already drives.

## Open items / later work

- Auto-generate overlay metadata (replace hand-authored overlays with a MONAI
  runtime template + repo defaults).
- Decide baked-in bundle path convention (`/opt/bundles/<model>`) and how the
  build downloads/vendors the bundle (neurodocker `packages` vs a build hook).
- Confirm Model Zoo listing API surface across the pinned `monai` version.
