from australianimagingservice.mri.human.neuro.t1w.preprocess import all_parcs


def test_t1w_preprocess():
    wf = all_parcs(
        "/opt/FastSurfer",
        "/opt/mrtrix3/3.0.4/share/mrtrix3/labelconvert",
        "/Users/tclose/Desktop/cache-dir",
        "/Users/tclose/Desktop/file1.txt",
    )
