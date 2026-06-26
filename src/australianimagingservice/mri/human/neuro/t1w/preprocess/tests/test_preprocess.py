import os
import shutil
from pathlib import Path
from pydra2app.core import App
from australianimagingservice.mri.human.neuro.t1w.preprocess import AllParcellations
import xnat
import pytest
from conftest import upload_test_dataset_to_xnat, test_data_dir

home_dir = Path("~").expanduser()


CACHE_DIR = Path("~").expanduser() / ".pydra-cache" / "t1w-preprocess-test"


def test_t1w_preprocess():

    test_data = test_data_dir / "src" / "mri" / "human" / "neuro" / "t1w" / "preprocess"
    subjects_dir = CACHE_DIR / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    wf = AllParcellations(
        t1w=test_data / "sub-01_ses-test_T1w.nii.gz",
        subjects_dir=subjects_dir,
        freesurfer_home=os.environ["FREESURFER_HOME"],
        mrtrix_lut_dir=(
            Path(shutil.which("mrconvert")).resolve().parents[1] / "share" / "mrtrix3" / "labelconvert"
        ),
        fs_license=Path(os.environ["FREESURFER_HOME"]).parent / "license.txt",
        resources_dir=Path(__file__).parents[8] / "resources",
    )

    outputs = wf(cache_root=CACHE_DIR)
    print(outputs)
