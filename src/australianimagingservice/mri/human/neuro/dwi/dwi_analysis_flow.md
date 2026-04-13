# DWI Analysis Pipeline

```mermaid
flowchart TD
    IN1([dwi_preproc_mif])
    IN2([FS_dir])
    IN3([fTTvis_image_T1space])
    IN4([fTT_image_T1space])
    IN5([parcellation_image_T1space])

    subgraph PREPROC["DWI Preprocessing"]
        A[DwiGradcheck] --> B["MrConvert<br/>corrected grad"]
        IN1 --> A
        IN1 --> B
        B --> C[DwiDenoise]
        C --> D["MrDegibbs<br/>unring"]

        D --> E1["DwiExtract<br/>early b0"]
        E1 --> E2["MrcalcMax<br/>non-negative b0"]
        E2 --> E3["MrMath<br/>mean b0 NIfTI"]
        E3 --> E4["MriSynthstrip<br/>brain mask"]
        E4 --> E5["MrConvert<br/>mask to MIF"]

        D --> F["DwiBiascorrect_Ants<br/>bias correction"]
        E5 --> F
        F --> G["MrGrid<br/>crop DWI"]
        E5 --> G
        E5 --> H["MrGrid<br/>crop mask"]
    end

    subgraph FS["FreeSurfer Path Construction"]
        IN2 --> I["JoinTask\nbuild FS paths"]
        I --> K["MrConvert<br/>brainmask.mgz to nii"]
        I --> L["MrConvert<br/>wm.seg.mgz to nii"]
        I --> M["MrConvert<br/>normimg.mgz to nii"]
        L --> Q["MrcalcMax<br/>WM binary mask"]
    end

    subgraph REG["Registration - DWI to T1 space"]
        G --> N["DwiExtract\nb0 volumes"]
        N --> O["MrcalcMax\nnon-negative b0"]
        O --> P["MrMath\nmean b0 NIfTI"]
        P --> R["EpiReg<br/>DWI to T1 reg"]
        M --> R
        K --> R
        Q --> R
        R --> S["TransformConvert<br/>flirt_import"]
        P --> S
        K --> S
        S --> T["MrTransform<br/>apply to DWI<br/>reorient_fod=no"]
        G --> T
        IN3 --> T
        S --> U["MrTransform<br/>apply to mask<br/>reorient_fod=no"]
        H --> U
        IN3 --> U
    end

    subgraph TRACT["Tractography and Connectomics"]
        T --> V["Dwi2Response<br/>Dhollander"]
        U --> V
        T --> W["Dwi2Fod<br/>msmt_csd<br/>wm / gm / csf"]
        U --> W
        V --> W
        W --> X["MtNormalise<br/>FOD normalisation"]
        U --> X
        X --> Y["TckGen<br/>iFOD2"]
        IN4 --> Y
        X --> Z[TckSift2]
        Y --> Z
        IN4 --> Z
        Y --> AA[Tck2Connectome]
        Z --> AA
        IN5 --> AA
        Y --> AB["TckMap TDI"]
        Z --> AB
        IN4 --> AB
        Y --> AC["TckMap DEC-TDI"]
        Z --> AC
        IN4 --> AC
    end

    T --> OUT1([DWI_processed<br/>T1 space .mif.gz])
    U --> OUT2([DWImask_processed<br/>T1 space .mif.gz])
    X --> OUT3([wm_fod_norm<br/>.mif.gz])
    AB --> OUT4([TDI_file])
    AC --> OUT5([DECTDI_file])
```
