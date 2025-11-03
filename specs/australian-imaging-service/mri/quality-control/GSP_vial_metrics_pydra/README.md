# GSP Vial Metrics - Pydra Pipeline

Automated phantom analysis pipeline for MRI quality control using Pydra workflow management.

## Quick Start

### 1. Initial Setup

```bash
# Make setup script executable
chmod +x setup_environment.sh

# Run setup script
./setup_environment.sh
```

This will:
- Set up Python 3.13.7 with pyenv
- Create virtual environment `gsp_vial_metrics`
- Install all Python dependencies
- Check for external tool dependencies (ANTs, MRtrix3)

### 2. Manual Activation (if needed)

The environment should activate automatically when you `cd` into this directory. If not:

```bash
pyenv activate gsp_vial_metrics
```

### 3. Run Pipeline

```bash
python pydra_phantom_iterative.py single \
    /path/to/your/t1_mprage.nii.gz \
    --template-dir /path/to/TemplateData \
    --output-dir /path/to/Outputs \
    --rotation-lib /path/to/TemplateData/rotations.txt
```

---

## Repository Structure

```
GSP_vial_metrics_pydra/
├── pydra_phantom_iterative.py    # Main processing script
├── plot_maps_ir.py                # T1 inversion recovery plotting
├── plot_maps_TE.py                # T2 echo time plotting
├── Functions/
│   └── plot_vial_intensity.py    # Individual contrast plotting
├── setup_environment.sh           # Environment setup script
├── requirements.txt               # Python dependencies
├── .python-version                # Auto-activates environment
└── README.md                      # This file
```

---

## Dependencies

### Python Packages (installed by setup script)
- `numpy` - Numerical computing
- `pandas` - Data manipulation
- `matplotlib` - Plotting
- `scipy` - Scientific computing (curve fitting)
- `pydra` - Workflow management

### External Tools (must be installed separately)

#### ANTs (Advanced Normalization Tools)
**Purpose:** Image registration

**Installation:**
```bash
# macOS
brew install ants

# Or download from: https://github.com/ANTsX/ANTs/releases
```

**Required commands:**
- `antsRegistrationSyN.sh`

#### MRtrix3
**Purpose:** Image processing and manipulation

**Installation:**
```bash
# macOS
brew install mrtrix3

# Or download from: https://www.mrtrix.org/download/
```

**Required commands:**
- `mrinfo` - Image information
- `mrconvert` - Format conversion
- `mrgrid` - Image regridding
- `mrstats` - Image statistics
- `mrtransform` - Image transformation
- `mrcat` - Concatenate images
- `mrmath` - Image mathematics
- `mrview` - Image visualization (optional, for QC)

---

## Usage

### Single Session Processing

Process one phantom session:

```bash
python pydra_phantom_iterative.py single \
    /path/to/t1_mprage.nii.gz \
    --template-dir /path/to/TemplateData \
    --output-dir /path/to/Outputs \
    --rotation-lib /path/to/TemplateData/rotations.txt
```

**Arguments:**
- `input_image` - Path to primary T1 MPRAGE image
- `--template-dir` - Directory containing:
  - `ImageTemplate.nii.gz` - Template phantom image
  - `VialsLabelled/` - Directory with vial masks (A.nii.gz, B.nii.gz, etc.)
  - `rotations.txt` - Rotation library file
- `--output-dir` - Output directory for results
- `--rotation-lib` - Path to rotations.txt file

### Batch Processing

Process multiple sessions in parallel:

```bash
python pydra_phantom_iterative.py batch \
    /path/to/data/directory \
    --template-dir /path/to/TemplateData \
    --output-dir /path/to/Outputs \
    --rotation-lib /path/to/TemplateData/rotations.txt \
    --pattern '*t1*mprage*.nii.gz' \
    --plugin cf
```

**Additional arguments:**
- `data_dir` - Directory containing session subdirectories
- `--pattern` - Glob pattern to find T1 images (default: `*t1*mprage*.nii.gz`)
- `--plugin` - Pydra execution plugin: `cf` (concurrent) or `serial`

---

## Expected Data Structure

### Input Data
```
Data/
├── Session1/
│   ├── t1_mprage_sag.nii.gz       # Primary input (T1-weighted)
│   ├── se_ir_100.nii.gz           # Inversion recovery (100ms TI)
│   ├── se_ir_250.nii.gz           # Inversion recovery (250ms TI)
│   ├── se_ir_500.nii.gz           # etc.
│   ├── t2_se_TE_14.nii.gz         # Spin echo (14ms TE)
│   ├── t2_se_TE_20.nii.gz         # Spin echo (20ms TE)
│   └── ...
└── Session2/
    └── ...
```

### Template Data
```
TemplateData/
├── ImageTemplate.nii.gz           # Template phantom image
├── VialsLabelled/                 # Vial ROI masks
│   ├── A.nii.gz
│   ├── B.nii.gz
│   ├── C.nii.gz
│   └── ... (through T.nii.gz)
└── rotations.txt                  # Rotation matrix library
```

**Note:** Vial masks must be `.nii.gz` format (compressed NIfTI)

---

## Output Structure

```
Outputs/
└── SessionName/
    ├── metrics/                           # Extracted metrics
    │   ├── SessionName_contrast_mean_matrix.csv
    │   ├── SessionName_contrast_std_matrix.csv
    │   ├── SessionName_contrast_PLOTmeanstd.png
    │   ├── SessionName_ir_map_PLOTmeanstd_TEmapping.png
    │   ├── SessionName_ir_map_PLOTmeanstd_TEmapping_T1_fits.csv
    │   ├── SessionName_TE_map_PLOTmeanstd_TEmapping.png
    │   └── SessionName_TE_map_PLOTmeanstd_TEmapping_T2_fits.csv
    ├── vial_segmentations/                # Transformed vial masks
    │   ├── A.nii.gz
    │   ├── B.nii.gz
    │   └── ...
    └── TemplatePhantom_ScannerSpace.nii.gz  # Template in subject space
```

### Output Files

**Metrics CSVs:**
- `*_mean_matrix.csv` - Mean intensity per vial per timepoint
- `*_std_matrix.csv` - Standard deviation per vial per timepoint
- `*_T1_fits.csv` - Fitted T1 values per vial (S0, T1_ms, R2)
- `*_T2_fits.csv` - Fitted T2 values per vial (S0, T2_ms, R2)

**Plots:**
- `*_PLOTmeanstd.png` - Individual contrast plots (scatter + error bars)
- `*_ir_map_PLOTmeanstd_TEmapping.png` - T1 parametric maps with fitted curves
- `*_TE_map_PLOTmeanstd_TEmapping.png` - T2 parametric maps with fitted curves

---

## Pipeline Overview

### Processing Steps

1. **Registration with Orientation Correction**
   - Registers input T1 image to template
   - Iteratively tests rotation matrices if needed
   - Validates registration quality

2. **Vial Transformation**
   - Transforms vial masks from template to subject space
   - Applies registration + rotation transforms

3. **Metric Extraction**
   - Extracts mean, std, min, max, median for each vial
   - Processes all contrast images in session

4. **Plot Generation**
   - Individual contrast plots (scatter with error bars)
   - T1 parametric maps (inversion recovery fitting)
   - T2 parametric maps (exponential decay fitting)

### Fitting Models

**T1 (Inversion Recovery):**
```
S(TI) = |S₀ · (1 - 2 · exp(-TI/T₁))|
```

**T2 (Spin Echo):**
```
S(TE) = S₀ · exp(-TE/T₂)
```

---

## Troubleshooting

### Environment Issues

**Problem:** `pyenv: python: command not found`

**Solution:** Run setup script or manually activate:
```bash
./setup_environment.sh
# OR
pyenv activate gsp_vial_metrics
```

---

**Problem:** Environment doesn't auto-activate

**Solution:** Ensure `.python-version` exists:
```bash
echo "gsp_vial_metrics" > .python-version
```

---

### Data Issues

**Problem:** `No vial masks found in: .../VialsLabelled`

**Solution:** 
- Check that vial masks are `.nii.gz` (not `.nii`)
- Verify TemplateData structure matches expected format

---

**Problem:** `IndexError: list index out of range` during metric extraction

**Solution:**
- Registration may be poor quality
- Image FOV may not include all vials
- Run with updated script that has error handling
- Visually inspect registration with `mrview`

---

**Problem:** Registration check passes but vials don't overlap

**Solution:**
- Contrast images may have different geometry than T1
- Check image dimensions: `mrinfo your_image.nii.gz`
- Visually verify: `mrview contrast.nii.gz -overlay.load vial_mask.nii.gz`

---

## Development Notes

### Version History

**Checkpoint 1 (Current):**
- ✅ Full pipeline functional
- ✅ Supports `.nii.gz` vial masks
- ✅ Scatter plots with no connecting lines
- ✅ Proper vial name extraction for compressed files
- ✅ Error handling for empty mrstats output
- ✅ T1/T2 curve fitting with R² goodness-of-fit metrics

### Key Fixes Applied

1. **Vial mask extension handling** - Changed from `.nii` to `.nii.gz`
2. **Vial name extraction** - Fixed for double extensions (`A.nii.gz` → `A`)
3. **Scatter plot implementation** - Separated `ax.errorbar()` and `ax.scatter()`
4. **Error handling** - Graceful handling of empty mrstats output

---

## Citation

If you use this pipeline, please cite:

[Citation information to be added]

---

## Support

For issues or questions:
- Check the troubleshooting section above
- Review documentation in `/docs` (if available)
- Contact: [contact information]

---

## License

[License information to be added]