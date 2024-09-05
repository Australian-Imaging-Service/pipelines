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
afni.preprocess.Warp
afni.utils.Autobox
afni.utils.Resample


ANTs
----
ants.registration.Registration
ants.resampling.ApplyTransforms
ants.segmentation.N4BiasFieldCorrection
ants.utils.AverageAffineTransform
ants.utils.AverageImages
ants.utils.MultiplyImages


Misc
----
FramewiseDisplacement


QSIPrep - modified
----------------
anatomical.DiceOverlap
anatomical.GetTemplate
ants.GetImageType
bids.BIDSDataGrabber
bids.BIDSInfo
bids.DerivativesDataSink
confounds.DMRISummary
confounds.GatherConfounds
dipy.Patch2Self
dipy.TensorReconstruction
dsi_studio.DSIStudioBTable
dsi_studio.DSIStudioCreateSrc
dsi_studio.DSIStudioFibQC
dsi_studio.DSIStudioGQIReconstruction
dsi_studio.DSIStudioMergeQC
dsi_studio.DSIStudioSrcQC
dwi_merge.MergeDWIs
dwi_merge.StackConfounds
fmap.ApplyScalingImages
freesurfer.FixHeaderSynthStrip
freesurfer.PrepareSynthStripGrid
freesurfer.SynthSeg
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
mrtrix.MRDeGibbs
mrtrix.MRTrixGradientTable
nilearn.Merge
niworkflows.ANTSRegistrationRPT
reports.AboutSummary
reports.DiffusionSummary
reports.GradientPlot
reports.InteractiveReport
reports.SeriesQC
reports.SubjectSummary
shoreline.B0Mean
shoreline.CalculateCNR
shoreline.ExtractDWIsForModel
shoreline.IterationSummary
shoreline.ReorderOutputs
shoreline.SHORELineReport
shoreline.SignalPrediction
utils.AddTSVHeader
utils.TestInput

niworkflows
-----------
interfaces.images.TemplateDimensions
interfaces.masks.ROIsPlot
interfaces.registration.RobustMNINormalizationRPT
interfaces.registration.SimpleBeforeAfterRPT
