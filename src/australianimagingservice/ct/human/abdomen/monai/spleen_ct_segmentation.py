"""Auto-generated MONAI task module. Do not edit by hand."""
from pathlib import Path
from pydra.compose import monai

BUNDLE_PATH = Path(__file__).parent / "spleen_ct_segmentation_bundle"

SpleenCtSegmentation = monai.define(BUNDLE_PATH, name="SpleenCtSegmentation")
