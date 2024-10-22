from pathlib import Path
from pipeline2app.core import App
from australianimagingservice.mri.human.neuro.t1w.preprocess import all_parcs

PKG_DIR = (
    Path(__file__).parent / ".." / ".." / ".." / ".." / ".." / ".." / ".."
).resolve()


def test_t1w_preprocess():
    wf = all_parcs(
        "/opt/FastSurfer",
        "/opt/mrtrix3/3.0.4/share/mrtrix3/labelconvert",
        "/Users/tclose/Desktop/cache-dir",
        "/Users/tclose/Desktop/file1.txt",
    )


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

    app.make(build_dir=tmp_path, generate_only=True)
