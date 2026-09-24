# T1 Pipeline Sample Size Calculator

A single self-contained HTML page for turning this lab's own T1 pipeline pilot data into
sample-size estimates for a new study — point it at an outputs directory, pick a variable
of interest, and get a required-N (or minimum-detectable-difference) estimate grounded in
the pilot cohort's actual mean and variance.

## How to use it

Open `index.html` directly in a browser (Chrome, Edge or Firefox recommended for the folder
picker). No server or build step is required. If your browser blocks the folder picker when
opened via `file://`, serve it locally instead:

```
python3 -m http.server -d tools/sample_size_calculator 8000
# then open http://localhost:8000/
```

1. **Load pilot outputs** — click the drop zone (or drag a folder onto it) and select any
   directory that contains one or more `FS_outputs/stats/` folders somewhere underneath it.
   Nesting depth doesn't matter (e.g. `t1w_preprocess/FS_outputs/stats/` and
   `t1w_preprocess/t1w_preprocess/FS_outputs/stats/` both work), and you can point it at a
   single participant's output or a folder containing many participants.
2. **Choose a variable of interest** — search across every parsed FreeSurfer structure and
   metric (subcortical volumes, cortical thickness/area/volume across the DKT/Desikan/
   Destrieux atlases, cerebellum, hypothalamus, white matter parcellation, Brodmann areas,
   global measures like eTIV and total cortical volume, etc.).
3. **Review pilot descriptive statistics** — mean, SD, CV%, and a per-participant strip plot.
   Points are flagged (drawn as triangles) if they fall outside 1.5×IQR or 3 SD, since
   FastSurfer/FreeSurfer segmentation can silently fail on individual structures for
   individual participants — click a point to include/exclude it and see the stats update
   live.
4. **Sample size & power** — enter alpha, power, tails, and (optionally) a Bonferroni
   correction for multiple planned comparisons, then either:
   - enter a target difference (as % of the pilot mean, raw units, or Cohen's d) to get the
     required N per group, or
   - enter an N per group to see the minimum detectable difference and achieved power.

   A power curve chart sweeps N per group so you can see the full curve, not just one point.
5. **Share with the researcher** — "Copy summary" puts a plain-text write-up of the chosen
   variable and every computed number on the clipboard; "Print / save as PDF" gives a clean
   printable version of the whole page.

## v1 scope and limitations

- **Study design**: independent two-group comparisons only (e.g. patient vs. control). There
  is no paired/longitudinal mode — the pilot data is single-timepoint per participant, so a
  paired design would need an assumed test-retest correlation with nothing to ground it.
- **Stats file coverage**: only the standard FreeSurfer tabular `.stats` files are parsed
  (anything with a `# ColHeaders` table — subcortical/global volumes, cortical parcellation,
  cerebellum, hypothalamus, white matter parcellation, Brodmann areas, w-g.pct).
  `lh/rh.curv.stats` (unstructured free-text surface curvature summaries) and
  `callosum.CC.*.json` (corpus callosum shape metrics) are **not** parsed — they use different
  formats and are deferred to a future iteration. Files outside this allowlist are counted and
  shown as "skipped" rather than silently ignored.
- **Statistics**: sample-size formulas use the standard two-sample-mean-difference formula.
  Since no stats library is available client-side, critical values come from a rational
  approximation to the inverse normal CDF (Acklam's algorithm) plus a Cornish–Fisher-expansion
  approximation to the Student-t quantile for a small-pilot-N-adjusted estimate. Treat the
  t-adjusted number as the more conservative of the two, especially when the pilot cohort is
  small (the tool flags this below N=15).
- **Outlier flagging** is a QA aid, not a guarantee — it flags points worth a second look
  (likely segmentation failures) but a real decision about exclusion should still involve
  checking the actual FastSurfer/FreeSurfer output for that participant/structure.

## Expected input directory shape

```
<some folder>/
└── .../FS_outputs/
    └── stats/
        aseg.stats, wmparc.stats, brainvol.stats, cerebellum.CerebNet.stats,
        hypothalamus.HypVINN.stats, lh/rh.aparc*.stats, lh/rh.BA_exvivo*.stats,
        lh/rh.w-g.pct.stats, ...
```

For multiple participants, point the picker at a parent folder containing one such tree per
participant (participant IDs are inferred from the folder names that differ between them).
