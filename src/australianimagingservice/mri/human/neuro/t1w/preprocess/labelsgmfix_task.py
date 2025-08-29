# ######################
# # labelsgm spec info #
# ######################

@shell.define(outputs=["output"])
class LabelSgmFix(shell.Task["LabelSgmFix.Outputs"]):
    
    parc: File = shell.arg(
        help="The input FreeSurfer parcellation image",
        position=0,
        argstr="{parc}",
    )
    t1: File = shell.arg(
        help="The T1 image to be provided to FIRST",
        position=1,
        argstr="{t1}",
    )
    lut: File = shell.arg(
        help="The lookup table file that the parcellated image is based on",
        position=2,
        argstr="{lut}",
    )
    output: File = shell.arg(
        help="The output parcellation image",
        position=3,
        argstr="{output}",
    )
    premasked: bool = shell.arg(
        help="Indicate that brain masking has been applied to the T1 input image",
        argstr="-premasked",
    )
    sgm_amyg_hipp: bool = shell.arg(
        help="Use FIRST segmentation for amygdala and hippocampus",
        argstr="-sgm_amyg_hipp",
    )

    class Outputs(shell.Outputs):
        output: File = shell.outarg()
