Mrtrix_connectome
=================

ANTs
----
antsApplyTransforms
antsRegistration
N4BiasFieldCorrection

FSL
---
applywarp
eddy
eddy_squad
flirt
fnirt
fsl_anat
invwarp

Freesurfer
----------
mri_aparc2aseg
mri_ca_label
mri_label2vol
mri_surf2surf
mris_ca_label
recon-all

OTHER
-----
ROBEX



QSIPrep
=======

AFNI
----
Warp
Autobox
Resample

ANTs
----
Registration
ApplyTransforms
N4BiasFieldCorrection
AverageAffineTransform
AverageImages
MultiplyImages


Function utils
--------------
FramewiseDisplacement


QSIPrep - modified
==================

ANTs
----
ANTSRegistration (niworkflows.ANTSRegistrationRPT)
GetImageType

Dipy (function)
---------------
Patch2Self
TensorReconstruction

DSI Studio
----------
DSIStudioBTable
DSIStudioCreateSrc
DSIStudioFibQC
DSIStudioGQIReconstruction
DSIStudioMergeQC
DSIStudioSrcQC

Freesurfer
----------
SynthStrip (freesurfer.FixHeaderSynthStrip)
SynthSeg

Nilearn
-------
nilearn.Merge

Function utils
--------------
anatomical.DiceOverlap
anatomical.GetTemplate
confounds.DMRISummary
confounds.GatherConfounds
dwi_merge.MergeDWIs
dwi_merge.StackConfounds
fmap.ApplyScalingImages
freesurfer.PrepareSynthStripGrid
gradients.CombineMotions
gradients.ComposeTransforms
gradients.ExtractB0s
gradients.GradientRotation
gradients.MatchTransforms
gradients.SliceQC
images.ChooseInterpolator
images.Conform
images.ConformDwi
images.SplitDWIsBvals
images.TSplit
itk.AffineToRigid
itk.DisassembleTransform
utils.AddTSVHeader
utils.TestInput
shoreline.B0Mean
shoreline.CalculateCNR
shoreline.ExtractDWIsForModel
shoreline.IterationSummary
shoreline.ReorderOutputs
shoreline.SHORELineReport
shoreline.SignalPrediction


QSIPrep - Niworkflows
=====================

Function utils
--------------
images.TemplateDimensions
masks.ROIsPlot
interfaces.registration.RobustMNINormalizationRPT
interfaces.registration.SimpleBeforeAfterRPT


