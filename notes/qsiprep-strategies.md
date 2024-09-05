## QSIPrep steps

* peopoler: drbuddi (uses DWI information as well as b0) - requires T2w
* Grouping multiple DWI datasets into a single file


## Required steps

### Distortion Group Merge

1. Validation of gradient schemes of provided DWI datasets
    a. check whether they can be combined together appropriately given the requested operation
    b. determine whether you can run EDDY (or alternative) in a single combined dataset, or need to do it in separate runs
2. QC metrics
    a. raw and processed model-free metrics
    b. T1w vs dMRI brain mask comparison
3. Uses either AveragePEPairs or MergeDWIs to concatenate DWI datasets (after distortion correction) 


### Intra-modal template creation

1. Uses ANTs `antsMultivariateTemplateConstruction2.sh` to 
2. Anat to b0 registration (init_b0_to_anat_registration_wf) uses `ANTSRegistrationRPT`


### DWI preproc

1. Field-map logic, handle 4 cases in BIDS standard
2. Estimate runtime requirements, e.g. memory, file-size, etc...
3. 

Potentially missing expected brain-mask estimation step

### Head-motion correction (init_dwi_pre_hmc_wf)

1. Merge DWI into single dataset (option to denoise before combining)
    a. combining before may be effected by different susceptibility distortions between different phase encodings
2. Model-free QC
3. DWI denoising WF (handle special case of 2 reverse PE DWI)
4. 


#### DWI denoising (init_dwi_denoising_wf)

1. DWIDenoise or Dipy-patch2self options (future-proofing looking into complex image denoising)
2. MRdegibbs or TORTOISE-Gibbs (maybe partial-Fourier support)
3. DWIBiasCorrect (optional could be done later) - detangling the mutual dependence of bias-correction and brain mask, could look into `dwibiascorrectnormmask`
4. saving motion confounds for future use (StackConfounds)


### Head-motion correction

Option between 3d shore or FSL

#### Model-based

Potential to use NL reg over and above field-map-based correction


Table of behavior (fieldmap use-cases):

=============== =========== ============= ===============
Fieldmaps found ``use_syn`` ``force_syn``     Action
=============== =========== ============= ===============
True            *           True          Fieldmaps + SyN
True            *           False         Fieldmaps
False           *           True          SyN
False           True        False         SyN
False           False       False         HMC only
=============== =========== ============= ===============

1. split dwi datasets + bvals into separate files
2. Slice-QC
3. Combine motions (CombineMotions)
    a. Runs c3d_affine_tool to convert affine matrices
    b. Convert from real-space to FSL image-axis space (ijk)
    c. Convert from affine matrix coefficients to features of interest
4. drbuddi if fieldmap epi or rpe_series
    a. apply transforms (ANTs)
    b. GradientRotation
5. Handle all the different field-map (see table in comments for logic based on available field-maps)
    a. init_pepolar_unwrap
    b. init_fmap_wf
    c. init_phdiff_wf
    d. init_sdc_unwrap
    c. init_syn_sdc_wf


