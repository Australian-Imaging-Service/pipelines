# # ########################
# # # Execute the workflow #
# # ########################
parcellation_list = [
    "aparca2009s",
    "aparc",
    "desikan",
    "destrieux",
    "economo",
    "glasser360",
    "hcpmmp1",
    "schaefer100",
    "schaefer1000",
    "schaefer200",
    "schaefer300",
    "schaefer400",
    "schaefer500",
    "schaefer600",
    "schaefer700",
    "schaefer800",
    "schaefer900",
    "vosdewael100",
    "vosdewael200",
    "vosdewael300",
    "vosdewael400",
    "Yeo17",
    "Yeo7",
]  # List of different parcellations


def all_parcs(
    freesurfer_home: Path,
    mrtrix_lut_dir: Path,
    cache_dir: Path,
    fs_license: Path,
    fastsurfer_executable: ty.Union[str, ty.List[str], None] = None,
    fastsurfer_python: str = "python3",
    name: str = "t1_preprocessing_pipeline_all",
) -> Workflow:

    # Define the input values using input_spec
    input_spec = {
        "t1w": File,
        "FS_dir": str,
    }

    wf = Workflow(
        name=name,
        input_spec=input_spec,
        cache_dir=cache_dir,
    )

    wf.add(
        FunctionTask(
            collate_parcs,
            name="collate_parcs",
            input_spec=SpecInfo(
                name="CollateParcsInputs",
                bases=(BaseSpec,),
                fields=[(p, Mif) for p in parcellation_list],
            ),
            output_spec=SpecInfo(
                name="CollateParcsOutputs",
                bases=(BaseSpec,),
                fields=[("out_dir", DirectoryOf[Mif])],  # type: ignore[misc]
            ),
            out_dir="out_dir",
        )
    )

    for parcellation in parcellation_list:

        wf.add(
            single_parc(
                t1w=wf.lzin.t1w,
                parcellation=parcellation,
                freesurfer_home=freesurfer_home,
                mrtrix_lut_dir=mrtrix_lut_dir,
                cache_dir=cache_dir,
                fs_license=fs_license,
                fastsurfer_executable=fastsurfer_executable,
                fastsurfer_python=fastsurfer_python,
                name=parcellation,
            )
        )

        setattr(
            wf.collate_parcs.inputs,
            parcellation,
            getattr(wf, parcellation).lzout.parc_image,
        )

    wf.set_output(("parcellations", wf.collate_parcs.lzout.out_dir))
    wf.set_output(("vis_image_fsl", wf.desikan.lzout.vis_image_fsl))
    wf.set_output(("ftt_image_fsl", wf.desikan.lzout.ftt_image_fsl))
    wf.set_output(("vis_image_freesurfer", wf.desikan.lzout.vis_image_freesurfer))
    wf.set_output(("ftt_image_freesurfer", wf.desikan.lzout.ftt_image_freesurfer))
    wf.set_output(("vis_image_hsvs", wf.desikan.lzout.vis_image_hsvs))
    wf.set_output(("ftt_image_hsvs", wf.desikan.lzout.ftt_image_hsvs))

    return wf


def collate_parcs(out_dir: Path = None, **parcs: "Mif") -> "DirectoryOf[Mif]":  # type: ignore[type-arg]
    if out_dir is None:
        out_dir = Path("./out_dir").absolute()
    out_dir.mkdir(exist_ok=True)
    for name, parc in parcs.items():
        parc.copy(out_dir, new_stem=name)
    return DirectoryOf[Mif](out_dir)  # type: ignore[no-any-return,type-arg,misc]


if __name__ == "__main__":
    import sys

    args = sys.argv[2:]

    wf = all_parcs(*args)  # type: ignore[arg-type]
    wf(t1w=sys.argv[1])
# if __name__ == "__main__":
#     import sys

#     # Expecting the first argument to be the T1-weighted image path
#     t1w_path = sys.argv[1]

#     # Provide sensible default values or pass from command-line arguments
#     # freesurfer_home = "/Applications/freesurfer/"  # Adjust this path as per your setup
#     # mrtrix_lut_dir = "/Users/arkievdsouza/mrtrix3/share/mrtrix3/labelconvert/"  # Adjust this path as per your setup
#     # cache_dir = "/Users/arkievdsouza/git/t1-pipeline/working-dir/"  # Temporary directory for cache
#     # fs_license = (
#     #     "/Applications/freesurfer/license.txt "  # Path to the FreeSurfer license file
#     # )

#     # Pass the arguments explicitly
#     wf = all_parcs(*sys.argv[1])
#     #     freesurfer_home=freesurfer_home,
#     #     mrtrix_lut_dir=mrtrix_lut_dir,
#     #     cache_dir=cache_dir,
#     #     fs_license=fs_license,
#     # )  # type: ignore[arg-type]

#     # # Run the workflow with the T1-weighted image as input
#     wf(t1w=t1w_path)
