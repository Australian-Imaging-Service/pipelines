from pathlib import Path
from pydra2app.core import App
from australianimagingservice.mri.human.neuro.t1w.preprocess import AllParcellations

PKG_DIR = (
    Path(__file__).parent / ".." / ".." / ".." / ".." / ".." / ".." / ".."
).resolve()


def test_t1w_preprocess():
    wf = AllParcellations(
        t1w=,
        subjects_dir=,
        freesurfer_home=,
        mrtrix_lut_dir=,
        fs_license=,
        "/opt/FastSurfer",
        "/opt/mrtrix3/3.0.4/share/mrtrix3/labelconvert",
        cache_dir="/Users/tclose/Desktop/cache-dir",
        "/Users/tclose/Desktop/file1.txt",
    )

    outputs = wf()
    print(outputs)


def test_t1w_preprocess_yaml(tmp_path: Path):
    app = App.load(
        PKG_DIR
        / "specs"
        / "australian-imaging-service"
        / "mri"
        / "human"
        / "neuro"
        / "t1w"
        / "preprocess.yaml"
    )

    app.make(
        build_dir=tmp_path, generate_only=True, resources_dir=PKG_DIR / "resources"
    )
