# DWI Preprocessing Pipeline

```mermaid
flowchart TD
    %% ── Pre-workflow (plain Python) ──────────────────────────────────────────
    SUBDIR(["subject_dir"])
    SUBDIR --> RESOLVE["resolve_dwi_inputs(subject_dir)<br/>glob DWI candidates · classify AP/PA pair<br/>→ rpe_mode + rpe_file + pe_dir<br/><i>plain Python — runs before workflow</i>"]

    RESOLVE --> IN1([dwi_raw_mif])
    RESOLVE --> IN2(["rpe_file<br/>(optional — rpe_pair/rpe_all only)"]):::opt

    IN1 --> DETECT["detect_shell_structure(dwi_path)<br/>mrinfo -shell_bvalues<br/><i>plain Python — runs before workflow</i>"]
    DETECT --> FOD_CHOICE(["fod_algorithm<br/>(ss3t or msmt_csd)<br/>written to manifest"])

    subgraph APPAPREP["AP/PA Preparation (Pydra tasks — inside workflow)"]
        RPE_CHOICE{"rpe_mode?"}

        DWICAT["DwiCat<br/>FWD + RPE → concat 4D DWI<br/>(AP first)"]

        FWD_B0EX["DwiExtract (fwd b0)<br/>b0 volumes from FWD DWI"]
        FWD_MEAN["MrMath<br/>mean fwd b0"]
        RPE_B0EX["DwiExtract (rpe b0)<br/>b0 volumes from rpe_file"]
        RPE_MEAN["MrMath<br/>mean rpe b0"]
        MRCAT["MrCat<br/>se_epi pair (FWD b0 · RPE b0)"]
        SE_EPI_PAIR(["se_epi_pair<br/>.mif.gz"])

        DWIPREPARED(["dwi_prepared"])

        RPE_CHOICE -- "rpe_all" --> DWICAT --> DWIPREPARED
        RPE_CHOICE -- "rpe_pair" --> FWD_B0EX --> FWD_MEAN --> MRCAT --> SE_EPI_PAIR
        RPE_CHOICE -- "rpe_none /<br/>rpe_pair /<br/>rpe_header" --> DWIPREPARED
    end

    IN1 --> RPE_CHOICE
    IN2 --> RPE_CHOICE
    IN2 --> RPE_B0EX
    RPE_B0EX --> RPE_MEAN --> MRCAT

    subgraph PREPROC["DWI Preprocessing (Steps 1 – 9)"]
        A["① DwiGradcheck<br/>export_grad_mrtrix"] --> GRADCHECK["CheckGradientCorrection<br/>warn if bvecs corrected"]
        A --> B["② MrConvert<br/>reimport with corrected grad"]
        B --> C["③ DwiDenoise<br/>MP-PCA"]
        C --> D["④ MrDegibbs<br/>Gibbs unringing"]

        D --> E1["DwiExtract (early)<br/>b0 volumes"]
        E1 --> E2["MrcalcMax<br/>non-negative b0"]
        E2 --> E3["MrMath<br/>mean b0 NIfTI"]
        E3 --> E4["⑤ MriSynthstrip (early)<br/>→ eddy_mask"]

        D --> FSL["⑥ DwiFslpreproc<br/>eddy + topup<br/>-pe_dir / -rpe_mode<br/>-eddy_options"]
        E4 -->|"-eddy_mask"| FSL

        FSL --> P1["DwiExtract (preproc)<br/>b0 volumes"]
        P1 --> P2["MrcalcMax<br/>non-negative b0"]
        P2 --> P3["MrMath<br/>mean b0 NIfTI"]
        P3 --> P5["⑦ MriSynthstrip (corrected)<br/>→ corrected brain mask"]

        FSL --> F["⑧ DwiBiascorrect_Ants<br/>bias correction"]
        P5 -->|"corrected mask"| F

        F --> G["⑨ MrGrid crop DWI<br/>dwi_processed.mif.gz"]
        P5 --> H["⑨ MrGrid crop mask<br/>dwimask_processed.mif.gz"]
    end

    DWIPREPARED --> A
    DWIPREPARED --> GRADCHECK
    DWIPREPARED --> B
    SE_EPI_PAIR -.->|"-se_epi (rpe_pair)"| FSL

    subgraph RESP["Response Function Estimation (Step 10)"]
        G --> RF["⑩ Dwi2Response_Dhollander<br/>native DWI space<br/>voxels.mif.gz"]
        H -->|"mask"| RF
        RF --> RFW(["out_sfwm<br/>response_wm"])
        RF --> RFG(["out_gm<br/>response_gm"])
        RF --> RFC(["out_csf<br/>response_csf"])
    end

    subgraph MANIFEST["Manifest + Log"]
        G --> MAN["WritePreprocessingManifest<br/>preprocessing_manifest.json<br/>(DWI · mask · responses · fod_algorithm)"]
        H --> MAN
        RFW --> MAN
        RFG --> MAN
        RFC --> MAN
        FOD_CHOICE --> MAN

        G --> LOG["WritePreprocessingLog<br/>steps · timing · RAM · warnings"]
        H --> LOG
        RFW --> LOG
        RFG --> LOG
        RFC --> LOG
        GRADCHECK --> LOG
    end

    G --> OUT1([dwi_preprocessed<br/>dwi_processed.mif.gz])
    H --> OUT2([dwimask_preprocessed<br/>dwimask_processed.mif.gz])
    RFW --> OUT3([response_wm])
    RFG --> OUT4([response_gm])
    RFC --> OUT5([response_csf])
    MAN --> OUT6([preprocessing_manifest.json<br/>→ consumed by tractography_connectomics.py])
    LOG --> OUT7([execution_log<br/>pipeline_preprocessing_log.txt])

    classDef opt fill:#f5e6ff,stroke:#aa88cc,stroke-dasharray:5 5
```

---

## Example Usage

### Auto-discovery from subject directory

```python
import datetime
from dwi_preprocessing import DwiPreprocessing, resolve_dwi_inputs, detect_shell_structure

subject_dir = "/data/subjects/100307"
output_path = "/data/output/100307_preproc"

inputs = resolve_dwi_inputs(subject_dir)
wf = DwiPreprocessing(
    **inputs,
    eddy_options="' --slm=linear'",
    fod_algorithm=detect_shell_structure(inputs["dwi_raw_mif"]),
    start_time=datetime.datetime.now().isoformat(timespec="seconds"),
    cache_root=output_path,
)
result = wf(cache_root=output_path, rerun=True)
```

---

## AP/PA preparation — what happens inside the workflow

| `rpe_mode`   | Pydra tasks added                                                                      | dwifslpreproc receives                                     |
|--------------|----------------------------------------------------------------------------------------|------------------------------------------------------------|
| `rpe_none`   | none — `dwi_raw_mif` passes straight through                                           | `-rpe_none -pe_dir`                                        |
| `rpe_pair`   | `DwiExtract` (fwd b0) → `MrMath` + `DwiExtract` (rpe b0) → `MrMath` → `MrCat`        | `-rpe_pair -se_epi <1+1 b0 pair> -align_seepi -pe_dir`    |
| `rpe_all`    | `DwiCat` — concatenates `dwi_raw_mif` + `rpe_file` (AP first)                         | `-rpe_all -pe_dir`                                         |
| `rpe_header` | none — PE info read from image header                                                  | `-rpe_header` (pe_dir and readout_time omitted)            |

---

## Key outputs consumed by `tractography_connectomics.py`

| File | Description |
|------|-------------|
| `preprocessing_manifest.json` | JSON index of all output paths and `fod_algorithm`; read by `resolve_tractography_inputs` |
| `dwi_processed.mif.gz` | Bias-corrected, cropped DWI in native DWI space |
| `dwimask_processed.mif.gz` | Corresponding brain mask |
| `response_wm/gm/csf` | Tissue response functions (native DWI space) — used by default in FOD estimation; overridable with group-averaged responses |
| `pipeline_preprocessing_log.txt` | Execution summary with timing, warnings, and step details |
