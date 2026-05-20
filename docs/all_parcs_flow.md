# AllParcellations Pipeline — Flow Diagram

```mermaid
flowchart TD
    T1W([T1w NIfTI]) --> AP

    subgraph AP["AllParcellations (×23 parcellations)"]
        direction TB

        subgraph SP["SingleParcellation"]
            direction TB

            FS["Fastsurfer<br/>(Docker / Native)"]

            FS --> FTT

            subgraph FTT["5TT Generation (run once, cached)"]
                direction LR
                HSVS["FivettGen_Hsvs<br/>→ Fivett2Vis"]
                FREE["FivettGen_Freesurfer<br/>→ Fivett2Vis"]
                FSL["FivettGen_Fsl<br/>→ Fivett2Vis"]
            end

            FS --> JT["JoinTaskCatalogue<br/>(resolve paths / LUTs)"]

            JT --> BRANCH{parcellation type?}

            BRANCH -->|schaefer · aparc<br/>vosdewael · economo<br/>glasser360| V2["SurfaceTransform lh + rh<br/>→ Aparc2Aseg<br/>→ Label2Vol<br/>→ Reorient2Std<br/>→ Threshold<br/>→ LabelConvert"]

            BRANCH -->|hcpmmp1 · Yeo17 · Yeo7| ORIG["SurfaceTransform lh + rh<br/>→ Aparc2Aseg"]

            ORIG --> SGMFIX["LabelConvert<br/>→ LabelSgmfirst"]

            BRANCH -->|desikan · destrieux| SGMFIX

            V2 --> PARC_OUT([parc_image])
            SGMFIX --> PARC_OUT
        end

        PARC_OUT --> FIN
        FTT --> FIN

        FIN["FinalizeOutputs\n(python task)"]
    end

    FIN --> OUT

    subgraph OUT["final_outputs/"]
        direction LR
        ATL["Atlases/<br/>Atlas_&lt;name&gt;.mif.gz ×23"]
        TTI["5TTimages/<br/>5TT_hsvs/fsl/freesurfer<br/>5TTvis_hsvs/fsl/freesurfer"]
        FSO["FS_outputs/<br/>(FastSurfer dir)"]
        LUT["LUT/<br/>&lt;parc&gt;_LUT.txt ×23"]
    end
```

**Notes:**
- Fastsurfer and the 5TT block each run once — pydra's cache reuses the result across all 23 `SingleParcellation` calls.
- `LabelSgmfirst` is shared by `desikan`, `destrieux`, `hcpmmp1`, `Yeo17`, and `Yeo7`.
- `FinalizeOutputs` receives all 23 `parc_image` outputs plus 5TT/vis/FS wired from the `desikan` run.
