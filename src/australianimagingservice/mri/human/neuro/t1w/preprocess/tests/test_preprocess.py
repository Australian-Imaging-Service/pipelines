import os
from pathlib import Path
from pydra2app.core import App
from australianimagingservice.mri.human.neuro.t1w.preprocess import AllParcellations
import xnat
import pytest
from conftest import upload_test_dataset_to_xnat, test_data_dir

home_dir = Path("~").expanduser()


@pytest.mark.skip
def test_t1w_preprocess(tmp_path: Path):

    test_data = test_data_dir / "src" / "mri" / "human" / "neuro" / "t1w" / "preprocess"

    wf = AllParcellations(
        t1w=test_data / "t1w.nii.gz",
        subjects_dir=tmp_path / "subjects",
        freesurfer_home=os.environ["FREESURFER_HOME"],
        mrtrix_lut_dir=(
            Path(os.environ["MRTRIX3_HOME"]) / "share" / "mrtrix3" / "labelconvert"
        ),
        fs_license=Path(os.environ["FREESURFER_HOME"]).parent / "licence.txt",
    )

    outputs = wf()
    print(outputs)
