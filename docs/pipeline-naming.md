# Pipeline naming

Pipeline specs are filed under `specs/australian-imaging-service/` by the images they
operate on, not by the tool that implements them. A spec's path, with `/` replaced
by `.`, is its stable pipeline ID. The ID appears in the release catalogue, in image
names (`ghcr.io/australian-imaging-service/<id>`) and in reconciler patterns.

```
<species>/<anatomy>/<technique>[/<datatype>]/<pipeline>.yaml
```

| Level | What it is | Values in use |
|---|---|---|
| species | The species the images are of | `human`, `mouse`, `rat` |
| anatomy | The part of the body the images cover | `neuro`, `abdomen`, `msk`, `whole-body`, `skin` |
| technique | The imaging technique | `mri`, `ct`, `pet`, `us`, `tbp`, `dermoscopy` |
| datatype | The BIDS datatype, for MRI only | `anat`, `func`, `dwi`, `perf`, `fmap` |
| pipeline | A short name for what the pipeline does | `fmriprep`, `t1w-preprocess` |

Examples:

```
human.neuro.mri.anat.smriprep
human.neuro.mri.func.fmriprep
human.neuro.mri.dwi.preprocess
human.neuro.pet.<pipeline>
human.whole-body.ct.monai-segmentation
mouse.neuro.mri.anat.<pipeline>
human.any-anatomy.any-technique.phi-finder
```

Under `neuro`, names follow BIDS. BIDS groups its datatypes by modality: MRI covers
`anat`, `func`, `dwi`, `perf` and `fmap`, while PET, EEG, MEG and the others each
have a single datatype of the same name. So the `datatype` level only appears under
`mri`. For other anatomy, and for techniques BIDS doesn't cover (ultrasound, total
body photography, dermoscopy), use the technique name.

Use lowercase and hyphens. Generated MONAI specs are named `monai-<pipeline>`, so they
stand out from the hand-written ones. By default `<pipeline>` is the model's Model Zoo
name in lowercase and hyphens. When that repeats the levels above it, a shorter
name is set in `scripts/monai_whitelist.yaml`: `wholeBody_ct_segmentation` becomes
`human.whole-body.ct.monai-segmentation`. The Zoo name is given in the pipeline's
description.

## Where a pipeline goes

File a pipeline under the technique and anatomy of its main input, which is the
image its outputs describe. For example:

- smriprep and mriqc go under `mri/anat`, because their main (and only required)
  input is the T1w.
- fmriprep goes under `mri/func`, although it also uses the T1w and fieldmaps.
- A PET pipeline that uses a T1w for co-registration goes under `pet`.

## Pipelines that span techniques or anatomy

When a pipeline isn't tied to a single value at a level, name the level by what it
needs:

| Case | Name | Example |
|---|---|---|
| Needs a combination | `<a>-and-<b>` | `human.neuro.ct-and-pet.<pipeline>` |
| Runs on any one of a few | `<a>-or-<b>` | `human.msk.ct-or-mri.<pipeline>` |
| No restriction | `any-<level>` | `any-technique`, `any-anatomy`, `any-species` |

- List the values in alphabetical order, so each set has only one name
  (`ct-or-mri`, never `mri-or-ct`).
- When there are too many to list (four or more), use `multimodal` for a
  combination and `multi-technique` for alternatives.
- Use `any-<level>` only when the pipeline really has no restriction at that level.
  Keep the level in the path even then, so every ID has the same depth.
- `whole-body` is not a placeholder. It means images that cover the whole body.

The ID should stay stable when a pipeline later gains support for another technique,
because the reconciler treats a changed ID as a new pipeline. So choose the primary
placement by what the pipeline was designed for, not by every technique it happens to
support.

## Selecting pipelines for a site

Sites choose pipelines in their reconciler config with wildcard patterns on the ID,
where `*` also matches `.` (see [Releasing pipelines](releasing-pipelines.md)):

```yaml
include:
  - human.*.mri.*                 # clinical MRI, any anatomy
  - human.any-anatomy.*           # tools that work on any image, e.g. phi-finder
```

```yaml
include:
  - mouse.*.mri.*                 # preclinical MRI
  - rat.*.mri.*
```

Patterns on the technique level don't match combined names: `human.*.mri.*` matches
neither `ct-or-mri` nor `ct-and-pet`. A planned `techniques` field in the spec will
record every technique a pipeline supports or needs, so sites can select by what
they acquire rather than by path.

## Changes in this release

The pipeline IDs below have changed. The reconciler never removes commands, so a site
that has installed a pipeline under its old ID keeps that command, and gets the new ID
as a separate pipeline. Disable or remove the old commands in XNAT once the new ones
are installed.

| Old ID | New ID |
|---|---|
| `mri.human.neuro.bidsapp.fmriprep` | `human.neuro.mri.func.fmriprep` |
| `mri.human.neuro.bidsapp.mriqc` | `human.neuro.mri.anat.mriqc` |
| `mri.human.neuro.bidsapp.smriprep` | `human.neuro.mri.anat.smriprep` |
| `mri.human.neuro.dwi.preprocess` | `human.neuro.mri.dwi.preprocess` |
| `mri.human.neuro.t1w.preprocess` | `human.neuro.mri.anat.t1w-preprocess` |
| `quality-control.phi-finder` | `human.any-anatomy.any-technique.phi-finder` |
| `wholebody_ct_segmentation` | `human.whole-body.ct.monai-segmentation` |

`human.neuro.mri.anat.t1w-preprocess` is also upgraded from FastSurfer 2.2.0 to 2.6.1,
so its segmentations and surfaces differ from those of
`mri.human.neuro.t1w.preprocess` 1.1.4. Its GPU image needs an NVIDIA driver that
supports CUDA 12.6 or later.

Images are published under the new names. Reconciler configs that use the old
patterns (e.g. `mri.human.neuro.*`) need updating, because they no longer match
anything.

The Python package in `src/` follows the same layout:

| Old module | New module |
|---|---|
| `australianimagingservice.mri.human.neuro.dwi` | `australianimagingservice.human.neuro.mri.dwi` |
| `australianimagingservice.mri.human.neuro.t1w.preprocess` | `australianimagingservice.human.neuro.mri.anat.t1w_preprocess` |

In `scripts/monai_whitelist.yaml`, the `modality` and `region` fields are now
`technique` and `anatomy`. There's also an optional `datatype` field for MRI
models. Generated MONAI specs no longer sit in a `monai/` folder. They're recognised
by their `projectmonai/monai` base image.

Generated MONAI specs no longer set `name`, so their ID comes from the file path like
every other spec. In 26.11.0 the whole-body CT model was published as
`wholebody_ct_segmentation`, outside the naming scheme. Its file is now
`monai-segmentation.yaml`, set by a new optional `pipeline` field in the whitelist,
and its XNAT command is `monai-segmentation`.
