# Plan: keep MONAI weights out of git

**Decision (project):** MONAI model weights are NOT committed to this repo.

**Status of investigation:** the mechanism below is verified against the real
`spleen_ct_segmentation` bundle, not assumed. See "Evidence" at the end.

---

## The core problem

`pipeline2app` introspects the task class **eagerly, at spec-load /
Dockerfile-generation time, on the build host** — before the image exists.
The generated module builds its class with `monai.define(BUNDLE_PATH)`.

So the bundle must be readable in two different places:

| | Build host (CI runner) | Runtime (inside container) |
|---|---|---|
| when | `pydra2app make` / spec load | XNAT session runs inference |
| needs | `configs/metadata.json` only | `configs/` **and** `models/` |
| path | repo-relative (module-adjacent) | container path |

These are different paths, which is the whole design tension.

## The split that resolves it

`parse_monai_spec` reads **only** `configs/metadata.json`. Weights are never
touched at introspection time. Therefore:

- **`configs/` committed** beside the generated module (~72 KB/model).
  Diffable, reviewable in a sync PR, satisfies build-host introspection.
- **`models/` never committed** (~37 MB/model). Fetched in CI, delivered into
  the image via the existing `resources:` mechanism.
- **`bundle` overridden at runtime** via `command.configuration` to point at
  the in-container path where the weights were copied.

`configuration` is the right hook: pipeline2app documents it as "constant
values used to configure the task, i.e. not presented to the user", and
`ContainerCommand._bind` does `task_kwargs = copy(self.configuration)` —
so entries are passed straight to the task as kwargs. It also *excludes*
those fields from `sources`/`parameters`, so `bundle` correctly stops being
a user-facing input.

## Runtime bundle assembly

The runtime bundle dir must contain both `configs/` and `models/`.
`_resolve_bundle_dir` rejects a dir without `configs/metadata.json`.

Two options — **decide before implementing**:

- **(a) Resource holds the whole bundle.** CI downloads the full bundle into
  `resources/<model>-bundle/`, `resources:` copies it to
  `/monai-bundles/<model>`, and `configuration.bundle` points there. The
  committed configs are then used *only* for build-host introspection and are
  redundant at runtime. Simplest; slight duplication.
- **(b) Resource holds weights only,** copied *into* the committed bundle dir
  inside the image. Avoids duplication but depends on the image layout of the
  installed package (site-packages path), which is fragile.

**Recommend (a).** The duplication is 72 KB; the fragility of (b) is not
worth it.

## Work items

1. **`vendor_bundle` → configs-only.** Add an allowlist (`configs/`, plus
   `LICENSE`/`docs/` if wanted for provenance) so `models/` is never vendored.
   Test: vendored dir has `configs/metadata.json`, has no `models/`.

2. **`generate_spec` → emit `configuration.bundle`** pointing at the runtime
   container path (e.g. `/monai-bundles/<model>`), and emit a `resources:`
   entry mapping the resource name to that path.
   Test: generated spec's `configuration["bundle"]` matches the `resources:`
   destination; `bundle` absent from `parameters`.

3. **`.gitignore`** — ignore `src/**/[a-z]*_bundle/models/` so a stray local
   sync can never stage 37 MB.

4. **CI: weights fetch step.** Both `monai-sync.yml` and `release.yml` need
   the weights present before `pydra2app make`. Add a step that reads each
   spec's model name + version and downloads into `./resources/<model>-bundle/`.
   Must pin to the spec's `version`, not "latest", or the image drifts from
   the spec describing it.

5. **`release.yml` matrix.** Currently hand-maintained (`quality-control/phi-finder`
   only). Generated MONAI specs need adding — ideally discovered rather than
   hand-listed, since sync creates them automatically.

## At-merge checklist (do these when `monai-test` merges)

These are correct as-is *while the feature lives on a branch*, and become
wrong the moment it lands. Easy to forget, hence recorded here.

1. **Repoint `monai-sync.yml` off `monai-test`.** Change **both**
   `ref:` (line 14) and `base:` (line 28) — they are separate controls:
   `ref` is what the runner checks out and branches from, `base` is what the
   PR merges into. Changing only `base` would open a PR from a
   `monai-test`-derived branch into `main`, dragging all 15 MONAI commits with
   it. Cannot be done before the merge: `scripts/monai_specs.py` does not
   exist on `main`, so the sync step would fail at import.

2. **Choose `main` vs `develop` as the sync target.** `release.yml` builds
   both. If `develop` is the integration branch, a weekly automated PR belongs
   there rather than on `main`.

3. **Resolves the build-flow question.** `monai-sync.yml` PRs into
   `monai-test`; `release.yml` triggers on push to `main`/`develop` + tags.
   So synced specs are not built until the work reaches a release branch —
   a consequence of the feature branch, not a design flaw, and it disappears
   at merge.

## Bug found while reviewing `monai-sync.yml` (fix independent of merge)

`add-paths` (lines 32-34) **drops the intermediate `__init__.py` files**.
Verified with real git pathspecs, not assumed:

| file | matched by `add-paths`? |
|---|---|
| `src/australianimagingservice/__init__.py` | ❌ |
| `src/australianimagingservice/ct/__init__.py` | ❌ |
| `.../ct/human/__init__.py`, `.../abdomen/__init__.py` | ❌ |
| `.../abdomen/monai/**` (module, bundle, configs) | ✅ |

`src/australianimagingservice/**/monai/**` only matches paths *containing* a
`monai` segment, but `write_task_module` creates `__init__.py` at every level
from `src/australianimagingservice` down. A sync PR would therefore commit a
task module whose parent packages are missing `__init__.py` — the dotted
`command.task` ref would fail to import, and `XnatApp.load()` with it.

Note `src/australianimagingservice/__init__.py` is **not currently tracked**
at all (the existing DWI packages have their own `__init__.py` but the root
does not), so this is not hypothetical — the first sync PR needs to add it.

Fix — **verified against real git pathspecs**:

- `src/australianimagingservice/**/__init__.py` is **not sufficient on its
  own**: `**/` requires at least one intervening path segment, so it catches
  `ct/__init__.py` and below but still misses the package root
  `src/australianimagingservice/__init__.py`.
- Use **either** both of
  `src/australianimagingservice/__init__.py` and
  `src/australianimagingservice/**/__init__.py`,
  **or** simply widen to `src/australianimagingservice/**`.

The wider pattern is simpler and safe here, since the weights `.gitignore`
backstop already prevents anything large being staged from that tree.

## Open questions (need answers before/while implementing)
- **Runtime path convention.** `/monai-bundles/<model>` is a guess; the repo
  precedent (`/parcellations`, `/fastsurfer-run`) is short top-level paths.
- **`model.ts` vs `model.pt`.** The zoo ships both (TorchScript + state dict).
  If inference needs only one, fetch only that one.
- **Disk on runners.** `release.yml` already deletes `/usr/share/dotnet` to
  free space; MONAI base images are large. Watch when several models build.

## Evidence (all verified against the real bundle, not fixtures)

- `parse_monai_spec` (`spec_parser.py:41`) reads only `configs/metadata.json`.
- `monai.define()` succeeds with `models/` deleted → class builds, fields
  `image` in / `pred` out.
- `XnatApp.load()` succeeds with `models/` absent; `command.task` resolves to
  a real class (not left as a string).
- Configs-only bundle measures **72 KB** vs 37 MB full.
- `task._executor_name == "bundle"` — the field `configuration` would set.
- `ContainerCommand._bind`: `task_kwargs = copy(self.configuration)`.
- `resources:` is COPY-from-build-context only (`base.py:558-566`,
  `shutil.copytree` then `dockerfile.copy`) — it cannot fetch. Hence the
  separate CI download step.
