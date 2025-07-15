# #############################
# # fslreorient2std spec info #
# #############################

fslreorient2std_input_spec = SpecInfo(
    name="Input",
    fields=[
        (
            "input_image",
            File,
            {
                "help": "input image",
                "argstr": "{input_image}",
                "position": 0,
                "mandatory": True,
            },
        ),
        (
            "output_image",
            str,
            {
                "help": "path to output image",
                "argstr": "{output_image}",
                "path_template": "out_file_reoriented1.nii.gz",
                "position": 1,
            },
        ),
    ],
    bases=(ShellSpec,),
)

fslreorient2std_output_spec = SpecInfo(
    name="Output",
    fields=[
        (
            "output_image",
            NiftiGz,
            {
                "help": "path to output image",
                "argstr": "{output_image}",
                "path_template": "out_file_reoriented1.nii.gz",
                "position": 1,
            },
        ),
    ],
    bases=(ShellOutSpec,),
)

# ######################
# # fslmaths spec info #
# ######################

fslthreshold_input_spec = SpecInfo(
    name="Input",
    fields=[
        (
            "input_image",
            str,
            {
                "help": "input image",
                "position": 0,
                "argstr": "{input_image}",
                "mandatory": True,
            },
        ),
        (
            "output_image",
            Path,
            {
                "help": "path to output image",
                "mandatory": True,
                "argstr": " ",
                "position": 3,
            },
        ),
        (
            "threshold",
            int,
            {
                "help": "threshold value",
                "position": 1,
                "argstr": "-thr",
            },
        ),
    ],
    bases=(ShellSpec,),
)

fslthreshold_output_spec = SpecInfo(
    name="Output",
    fields=[
        (
            "output_image",
            NiftiGz,
            {
                "help": "path to output image",
                "mandatory": True,
                "argstr": "{output_image}",
                "path_template": "out_file_threshold.nii.gz",
                "position": 3,
            },
        ),
    ],
    bases=(ShellOutSpec,),
)
