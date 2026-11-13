from fileformats.vendor.mrtrix3.medimage import ImageFormat as Mif
from australianimagingservice.mri.human.neuro.dwi.preproc import DwiPreproc


def test_dwi_preproc():
    wf = DwiPreproc(
        in_file=Mif.sample("dwi.mif"),
        se_epi=Mif.sample("se_epi.mif"),
        field_estimation_data_formation_strategy="se_epi_standalone",
        requires_regrid=True,
        have_se_epi=True,
        have_topup=True,
        dwi_has_pe_contrast=True,
    )
