#!/usr/bin/env python3
"""
Native Pydra implementation of phantom sub-metrics computation
Translates compute_sub_metrics_ants_ss.sh into pure Python/Pydra
No Docker required - uses local ANTs and MRtrix3 installations
"""
import subprocess
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple
import pydra


class PhantomProcessor:
    """
    Native Pydra phantom processing without Docker
    Direct translation of compute_sub_metrics_ants_ss.sh
    """

    def __init__(
        self, template_dir: str, output_base_dir: str, rotation_library_file: str
    ):
        """
        Initialize processor

        Parameters
        ----------
        template_dir : str
            Directory with ImageTemplate.nii.gz and VialsLabelled/
        output_base_dir : str
            Base output directory
        rotation_library_file : str
            Path to rotations.txt
        """
        self.template_dir = Path(template_dir)
        self.output_base_dir = Path(output_base_dir)
        self.rotation_library_file = rotation_library_file

        # Template files
        self.template_phantom = self.template_dir / "ImageTemplate.nii.gz"
        self.vial_dir = self.template_dir / "VialsLabelled"
        self.vial_masks = sorted(
            self.vial_dir.glob("*.nii.gz")
        )  # Fixed to accept .nii.gz files

        # Load rotation library
        self.rotations = self._load_rotations()

        if not self.template_phantom.exists():
            raise FileNotFoundError(f"Template not found: {self.template_phantom}")
        if len(self.vial_masks) == 0:
            raise FileNotFoundError(f"No vial masks found in: {self.vial_dir}")

    def _load_rotations(self) -> List[str]:
        """Load rotation matrices from file"""
        import re

        rotations = []

        with open(self.rotation_library_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extract matrix from quotes
                match = re.search(r'"([^"]+)"', line)
                if match:
                    matrix_str = match.group(1)
                    rotations.append(matrix_str)

        return rotations

    def _create_rotation_matrix_file(self, rotation_str: str, output_file: str):
        """Convert rotation string to 4x4 affine matrix"""
        values = rotation_str.split()

        with open(output_file, "w") as f:
            f.write(f"{values[0]} {values[1]} {values[2]} 0\n")
            f.write(f"{values[3]} {values[4]} {values[5]} 0\n")
            f.write(f"{values[6]} {values[7]} {values[8]} 0\n")
            f.write("0 0 0 1\n")

    def _run_ants_registration(
        self, input_image: str, output_prefix: str
    ) -> Tuple[str, str, str]:
        """Run ANTs registration - returns warped, transform, and inverse_warped"""
        cmd = [
            "antsRegistrationSyN.sh",
            "-d",
            "3",
            "-f",
            str(self.template_phantom),
            "-m",
            input_image,
            "-o",
            output_prefix,
            "-t",
            "r",
            "-n",
            "8",
            "-j",
            "1",
        ]

        print(f"Running ANTs registration...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ANTs failed: {result.stderr}")

        warped = f"{output_prefix}Warped.nii.gz"
        transform = f"{output_prefix}0GenericAffine.mat"
        inverse_warped = f"{output_prefix}InverseWarped.nii.gz"

        return warped, transform, inverse_warped

    def _check_registration(self, warped_image: str) -> bool:
        """
        Check if registration is correct based on vial intensities
        Returns True if correct, False otherwise
        """
        vial_means = {}

        for vial_mask in self.vial_masks:
            # Handle both .nii and .nii.gz extensions properly
            vial_name = vial_mask.name.replace(".nii.gz", "").replace(".nii", "")
            vial_name = vial_name.replace("Vial", "").replace("vial", "").strip()

            # Regrid vial mask to match warped image - use pipe chaining
            cmd_regrid = [
                "mrgrid",
                str(vial_mask),
                "-template",
                warped_image,
                "-interp",
                "nearest",
                "-quiet",
                "regrid",
                "-",
            ]

            # Get mean - pipe regridded mask directly to mrstats
            cmd_mean = [
                "mrstats",
                "-quiet",
                warped_image,
                "-output",
                "mean",
                "-mask",
                "-",
            ]

            # Chain commands: mrgrid output -> mrstats input
            proc_regrid = subprocess.Popen(
                cmd_regrid, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            proc_mean = subprocess.Popen(
                cmd_mean,
                stdin=proc_regrid.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc_regrid.stdout.close()

            mean_output, mean_error = proc_mean.communicate()

            if proc_mean.returncode != 0:
                print(f"  ✗ Error computing mean for {vial_name}")
                print(f"    stderr: {mean_error}")
                raise RuntimeError(f"mrstats failed for {vial_name}: {mean_error}")

            if not mean_output.strip():
                print(f"  ✗ Empty output from mrstats for {vial_name}")
                raise RuntimeError(f"mrstats returned empty output for {vial_name}")

            try:
                mean_val = float(mean_output.strip())
            except ValueError:
                print(f"  ✗ Could not parse mean value for {vial_name}")
                print(f"    Output: '{mean_output.strip()}'")
                raise ValueError(
                    f"Invalid mean value for {vial_name}: {mean_output.strip()}"
                )

            vial_means[vial_name] = mean_val

            # Check std - same regrid + pipe approach
            proc_regrid = subprocess.Popen(
                cmd_regrid, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            cmd_std = [
                "mrstats",
                "-quiet",
                warped_image,
                "-output",
                "std",
                "-mask",
                "-",
            ]
            proc_std = subprocess.Popen(
                cmd_std,
                stdin=proc_regrid.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc_regrid.stdout.close()

            std_output, std_error = proc_std.communicate()

            if proc_std.returncode != 0 or not std_output.strip():
                print(f"  ✗ Error computing std for {vial_name}")
                continue

            std_val = float(std_output.strip())

            if std_val > 50:
                return False

        # Check top and bottom vials
        sorted_vials = sorted(vial_means.items(), key=lambda x: x[1], reverse=True)
        top5 = [v[0] for v in sorted_vials[:5]]
        bottom5 = [v[0] for v in sorted_vials[-5:]]

        required_top = ["A", "O", "Q"]
        required_bottom = ["S", "D", "P"]

        for v in required_top:
            if v not in top5:
                return False

        for v in required_bottom:
            if v not in bottom5:
                return False

        print(f"  ✓ Registration check passed")
        print(f"    Top 5 vials: {top5}")
        print(f"    Bottom 5 vials: {bottom5}")

        return True

    def _apply_rotation(
        self, input_image: str, rotation_matrix_file: str, output_image: str
    ):
        """Apply rotation to image using mrtransform"""
        cmd = [
            "mrtransform",
            input_image,
            output_image,
            "-linear",
            rotation_matrix_file,
            "-interp",
            "nearest",
            "-force",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Rotation failed: {result.stderr}")

    def _register_with_iteration(
        self, input_image: str, session_name: str, tmp_dir: Path
    ) -> Tuple[str, str, str, int, str, str]:
        """
        Register with iterative rotation attempts
        Returns: (warped, transform, inverse_warped, iteration, current_input, rotation_matrix_file)
        """
        iteration = 0
        correct_orientation = False
        current_input = input_image
        rotation_matrix_file = None
        warped = None
        transform = None
        inverse_warped = None

        while not correct_orientation and iteration < len(self.rotations):
            iteration += 1
            print(f"\n=== Iteration {iteration} ===")

            # Run registration
            output_prefix = str(tmp_dir / f"{session_name}_Transformed{iteration}_")
            warped, transform, inverse_warped = self._run_ants_registration(
                current_input, output_prefix
            )

            # Check registration
            correct_orientation = self._check_registration(warped)

            if not correct_orientation and iteration < len(self.rotations):
                # Try next rotation
                print(f"  ✗ Registration check failed, trying rotation {iteration}")

                # Create rotation matrix file for NEXT iteration
                rotation_str = self.rotations[iteration]
                rotation_matrix_file = str(tmp_dir / f"rotation_{iteration + 1}.txt")
                self._create_rotation_matrix_file(rotation_str, rotation_matrix_file)

                # Apply rotation to original input
                rotated_input = str(
                    tmp_dir / f"{session_name}_iteration{iteration + 1}.nii.gz"
                )
                self._apply_rotation(input_image, rotation_matrix_file, rotated_input)
                current_input = rotated_input

            elif correct_orientation:
                print(f"  ✓ Correct orientation found at iteration {iteration}")
                break

        if not correct_orientation:
            raise RuntimeError(
                f"Failed to find correct orientation after {iteration} attempts"
            )

        # Return rotation_matrix_file (will be None if iteration == 1)
        return (
            warped,
            transform,
            inverse_warped,
            iteration,
            current_input,
            rotation_matrix_file,
        )

    def _transform_vials_to_subject_space(
        self,
        reference_image: str,
        transform_matrix: str,
        rotation_matrix_file: str,
        iteration: int,
        output_vial_dir: Path,
    ):
        """Transform vial masks from template to subject space"""
        output_vial_dir.mkdir(parents=True, exist_ok=True)
        tmp_vial_dir = output_vial_dir.parent / "tmp_vials"
        tmp_vial_dir.mkdir(parents=True, exist_ok=True)

        transformed_vials = []

        for vial_mask in self.vial_masks:
            # Clean vial name - handle .nii.gz properly
            vial_name = Path(vial_mask).name.replace(".nii.gz", "").replace(".nii", "")
            if vial_name.endswith(".mif"):
                vial_name = vial_name[:-4]
            # Remove any remaining dots/extensions
            vial_name = vial_name.split(".")[0]

            tmp_vial = str(tmp_vial_dir / f"{vial_name}.nii")
            output_vial = str(output_vial_dir / f"{vial_name}.nii.gz")

            # Apply ANTs inverse transform
            cmd = [
                "antsApplyTransforms",
                "-d",
                "3",
                "-i",
                str(vial_mask),
                "-r",
                reference_image,
                "-o",
                tmp_vial,
                "-t",
                f"[{transform_matrix}, 1]",
                "-n",
                "NearestNeighbor",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Transform failed for {vial_name}: {result.stderr}")

            # If rotation was applied, apply inverse rotation
            if iteration > 1 and rotation_matrix_file:
                cmd = [
                    "mrtransform",
                    tmp_vial,
                    output_vial,
                    "-linear",
                    rotation_matrix_file,
                    "-interp",
                    "nearest",
                    "-inverse",
                    "-force",
                ]
            else:
                cmd = ["mrconvert", "-quiet", tmp_vial, output_vial, "-force"]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Final conversion failed for {vial_name}: {result.stderr}"
                )

            transformed_vials.append(output_vial)

        return transformed_vials

    def _extract_metrics_from_contrast(
        self,
        contrast_file: Path,
        vial_masks: List[str],
        output_metrics_dir: Path,
        session_name: str,
    ):
        """Extract metrics from one contrast image across all vials"""
        contrast_name = contrast_file.stem

        # Remove file extensions from contrast name for cleaner labels
        clean_contrast_name = contrast_name.replace(".nii", "").replace(".gz", "")

        # Get number of volumes
        cmd = ["mrinfo", "-size", str(contrast_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        size_info = result.stdout.strip().split()

        if len(size_info) >= 4 and int(size_info[3]) > 0:
            nvols = int(size_info[3])
        else:
            nvols = 1

        print(
            f"  Processing {clean_contrast_name} ({nvols} volume{'s' if nvols > 1 else ''})"
        )

        # Initialize metric dictionaries
        metrics_data = {"mean": {}, "median": {}, "std": {}, "min": {}, "max": {}}

        # Create temp directory for volume extraction
        tmp_vol_dir = output_metrics_dir.parent / "tmp_vols"
        tmp_vol_dir.mkdir(parents=True, exist_ok=True)

        for vial_mask in vial_masks:
            # Clean vial name - handle .nii.gz properly
            vial_name = Path(vial_mask).name.replace(".nii.gz", "").replace(".nii", "")
            if vial_name.endswith(".mif"):
                vial_name = vial_name[:-4]  # Remove .mif if present
            # Remove any remaining extensions
            vial_name = vial_name.split(".")[0]

            # Initialize rows for this vial
            for metric in metrics_data.keys():
                metrics_data[metric][vial_name] = []

            # Regrid vial to contrast space
            regridded_mask = str(tmp_vol_dir / f"{contrast_name}_{vial_name}.nii")
            cmd = [
                "mrgrid",
                vial_mask,
                "-template",
                str(contrast_file),
                "-interp",
                "nearest",
                "-quiet",
                "regrid",
                regridded_mask,
                "-force",
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            # Extract metrics for each volume
            for vol_idx in range(nvols):
                if nvols == 1:
                    vol_file = str(contrast_file)
                else:
                    vol_file = str(tmp_vol_dir / f"{contrast_name}_vol{vol_idx}.nii.gz")
                    cmd = [
                        "mrconvert",
                        str(contrast_file),
                        "-coord",
                        "3",
                        str(vol_idx),
                        vol_file,
                        "-quiet",
                        "-force",
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)

                # Extract all metrics
                cmd = [
                    "mrstats",
                    "-quiet",
                    vol_file,
                    "-output",
                    "mean",
                    "-output",
                    "median",
                    "-output",
                    "std",
                    "-output",
                    "min",
                    "-output",
                    "max",
                    "-mask",
                    regridded_mask,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                # Check for errors
                if result.returncode != 0:
                    print(
                        f"    ✗ mrstats failed for vial {vial_name}, volume {vol_idx}"
                    )
                    print(f"      stderr: {result.stderr}")
                    # Skip this vial/volume
                    continue

                values = result.stdout.strip().split()

                # Check if we got the expected 5 values
                if len(values) != 5:
                    print(
                        f"    ⚠ Warning: Expected 5 values from mrstats, got {len(values)} for vial {vial_name}, volume {vol_idx}"
                    )
                    print(f"      Output: '{result.stdout.strip()}'")
                    print(f"      Stderr: '{result.stderr.strip()}'")
                    # Skip this vial/volume if no valid output
                    if len(values) == 0:
                        print(
                            f"    ✗ Skipping vial {vial_name} - empty output (mask may not overlap with image)"
                        )
                        continue

                metrics_data["mean"][vial_name].append(float(values[0]))
                metrics_data["median"][vial_name].append(float(values[1]))
                metrics_data["std"][vial_name].append(float(values[2]))
                metrics_data["min"][vial_name].append(float(values[3]))
                metrics_data["max"][vial_name].append(float(values[4]))

        # Write CSV files with clean column names (no file extensions)
        for metric_name, vial_data in metrics_data.items():
            csv_file = (
                output_metrics_dir
                / f"{session_name}_{contrast_name}_{metric_name}_matrix.csv"
            )

            # Create DataFrame with clean column names
            rows = []
            for vial_name, values in vial_data.items():
                row = {"vial": vial_name}
                for vol_idx, val in enumerate(values):
                    # Use clean_contrast_name instead of contrast_name
                    row[f"{clean_contrast_name}_vol{vol_idx}"] = val
                rows.append(row)

            df = pd.DataFrame(rows)
            df.to_csv(csv_file, index=False)
            print(f"    Saved: {csv_file.name}")

        return metrics_data

    def _generate_mrview_screenshot(
        self, contrast_file: Path, roi_overlay: str, output_image: str
    ):
        """Generate ROI overlay screenshot using mrview"""
        cmd = [
            "mrview",
            str(contrast_file),
            "-mode",
            "1",
            "-plane",
            "2",
            "-roi.load",
            roi_overlay,
            "-roi.colour",
            "1,0,0",
            "-roi.opacity",
            "1",
            "-comments",
            "0",
            "-noannotations",
            "-fullscreen",
            "-capture.folder",
            str(Path(output_image).parent),
            "-capture.prefix",
            Path(output_image).stem,
            "-capture.grab",
            "-exit",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    ⚠ mrview screenshot failed: {result.stderr}")
            return None

        # mrview appends 0000 to the filename
        actual_file = str(
            Path(output_image).parent / f"{Path(output_image).stem}0000.png"
        )
        return actual_file if Path(actual_file).exists() else None

    def _generate_plots(
        self,
        contrast_files: List[Path],
        metrics_dir: Path,
        vial_dir: Path,
        session_name: str,
    ):
        """Generate visualization plots for all contrasts"""

        # Check if plotting scripts exist
        plot_vial_script = (
            self.template_dir.parent / "Functions" / "plot_vial_intensity.py"
        )

        if not plot_vial_script.exists():
            print(f"  ⚠ Plotting script not found: {plot_vial_script}")
            print(f"  ⚠ Skipping plot generation")
            return

        tmp_vial_dir = vial_dir / "tmp"
        tmp_vial_dir.mkdir(exist_ok=True)

        # Generate plots for each contrast
        for contrast_file in contrast_files:
            contrast_name = contrast_file.stem

            # CSV files
            mean_csv = metrics_dir / f"{session_name}_{contrast_name}_mean_matrix.csv"
            std_csv = metrics_dir / f"{session_name}_{contrast_name}_std_matrix.csv"

            if not mean_csv.exists():
                continue

            # Output plot
            output_plot = (
                metrics_dir / f"{session_name}_{contrast_name}_PLOTmeanstd.png"
            )

            # Create combined ROI overlay
            roi_overlay = str(tmp_vial_dir / f"{contrast_name}_VialsCombined.nii.gz")
            vial_masks_list = list(vial_dir.glob("*.nii.gz"))

            if vial_masks_list:
                # Regrid each vial to contrast space and combine
                regridded_vials = []
                for vial_mask in vial_masks_list:
                    vial_name = vial_mask.name.replace(".nii.gz", "").replace(
                        ".nii", ""
                    )
                    regridded = str(tmp_vial_dir / f"{contrast_name}_{vial_name}.nii")

                    cmd = [
                        "mrgrid",
                        str(vial_mask),
                        "-template",
                        str(contrast_file),
                        "-interp",
                        "nearest",
                        "-quiet",
                        "regrid",
                        regridded,
                        "-force",
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    regridded_vials.append(regridded)

                # Combine vials: mrcat along axis 3, then mrmath max
                if len(regridded_vials) > 0:
                    cmd_cat = ["mrcat"] + regridded_vials + ["-", "-axis", "3"]
                    cmd_math = [
                        "mrmath",
                        "-",
                        "max",
                        roi_overlay,
                        "-axis",
                        "3",
                        "-force",
                    ]

                    proc_cat = subprocess.Popen(
                        cmd_cat, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    proc_math = subprocess.Popen(
                        cmd_math,
                        stdin=proc_cat.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    proc_cat.stdout.close()
                    proc_math.communicate()

            # Generate mrview screenshot
            mrview_image = str(tmp_vial_dir / f"{contrast_name}_roi_overlay.png")
            actual_screenshot = self._generate_mrview_screenshot(
                contrast_file, roi_overlay, mrview_image
            )

            # Call plotting script
            cmd = [
                "python",
                str(plot_vial_script),
                str(mean_csv),
                "scatter",
                "--std_csv",
                str(std_csv),
                "--output",
                str(output_plot),
            ]

            if actual_screenshot and Path(actual_screenshot).exists():
                cmd.extend(["--roi_image", actual_screenshot])

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"    ✓ Generated plot: {output_plot.name}")
            else:
                print(f"    ✗ Plot generation failed for {contrast_name}")
                if result.stderr:
                    print(f"      {result.stderr}")

        # Generate parametric map plots (IR and TE)
        self._generate_parametric_plots(
            contrast_files, metrics_dir, tmp_vial_dir, session_name
        )

    def _generate_parametric_plots(
        self,
        contrast_files: List[Path],
        metrics_dir: Path,
        tmp_vial_dir: Path,
        session_name: str,
    ):
        """Generate T1/T2 parametric map plots"""

        # Check for IR contrasts
        # Filter for files with 'ir' in name, but exclude:
        # - t1map files (processed maps, not raw contrasts)
        # - files without numbers after 'ir' (not actual contrast images)
        ir_contrasts = [
            f
            for f in contrast_files
            if "ir" in f.stem.lower()
            and "t1map" not in f.stem.lower()  # Exclude processed T1 maps
            and "t1_map" not in f.stem.lower()  # Exclude alternative naming
        ]
        if ir_contrasts:
            print(
                f"  Found {len(ir_contrasts)} IR contrasts: {[f.name for f in ir_contrasts]}"
            )
            plot_script = self.template_dir.parent / "plot_maps_ir.py"
            if plot_script.exists():
                output_plot = (
                    metrics_dir / f"{session_name}_ir_map_PLOTmeanstd_TEmapping.png"
                )

                # Generate ROI overlay for first IR image
                roi_overlay_base = str(tmp_vial_dir / "roi_overlay_ir.png")

                # Create combined ROI overlay for IR
                first_ir = ir_contrasts[0]
                roi_overlay_file = str(tmp_vial_dir / "ir_VialsCombined.nii.gz")
                vial_dir = metrics_dir.parent / "vial_segmentations"
                vial_masks_list = list(vial_dir.glob("*.nii.gz"))

                if vial_masks_list:
                    # Regrid vials and combine
                    regridded_vials = []
                    for vial_mask in vial_masks_list:
                        vial_name = vial_mask.name.replace(".nii.gz", "").replace(
                            ".nii", ""
                        )
                        regridded = str(tmp_vial_dir / f"ir_{vial_name}.nii")

                        cmd = [
                            "mrgrid",
                            str(vial_mask),
                            "-template",
                            str(first_ir),
                            "-interp",
                            "nearest",
                            "-quiet",
                            "regrid",
                            regridded,
                            "-force",
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        regridded_vials.append(regridded)

                    # Combine vials
                    if len(regridded_vials) > 0:
                        cmd_cat = ["mrcat"] + regridded_vials + ["-", "-axis", "3"]
                        cmd_math = [
                            "mrmath",
                            "-",
                            "max",
                            roi_overlay_file,
                            "-axis",
                            "3",
                            "-force",
                        ]

                        proc_cat = subprocess.Popen(
                            cmd_cat, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                        proc_math = subprocess.Popen(
                            cmd_math,
                            stdin=proc_cat.stdout,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        proc_cat.stdout.close()
                        proc_math.communicate()

                    # Generate mrview screenshot
                    actual_screenshot = self._generate_mrview_screenshot(
                        first_ir, roi_overlay_file, roi_overlay_base
                    )

                    if actual_screenshot and Path(actual_screenshot).exists():
                        roi_image_arg = actual_screenshot
                    else:
                        roi_image_arg = (
                            roi_overlay_base  # Use base name even if screenshot failed
                        )
                else:
                    roi_image_arg = roi_overlay_base

                cmd = (
                    ["python3", str(plot_script)]
                    + [str(f) for f in ir_contrasts]
                    + [
                        "-m",
                        str(metrics_dir),
                        "-o",
                        str(output_plot),
                        "--roi_image",
                        roi_image_arg,
                    ]
                )

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"    ✓ Generated IR map plot")
                else:
                    print(f"    ✗ IR map plot failed: {result.stderr}")
            else:
                print(f"    ⚠ IR plotting script not found: {plot_script}")
        else:
            print(f"  No IR contrasts found (searched for 'ir' in filenames)")

        # Check for TE contrasts
        # Filter for files with 'te' in name, but exclude:
        # - t2map files (processed maps, not raw contrasts)
        # - files without numbers after 'te' (not actual contrast images)
        te_contrasts = [
            f
            for f in contrast_files
            if "te" in f.stem.lower()
            and "t2map" not in f.stem.lower()  # Exclude processed T2 maps
            and "t2_map" not in f.stem.lower()  # Exclude alternative naming
        ]
        if te_contrasts:
            print(
                f"  Found {len(te_contrasts)} TE contrasts: {[f.name for f in te_contrasts]}"
            )
            plot_script = self.template_dir.parent / "plot_maps_TE.py"
            if plot_script.exists():
                output_plot = (
                    metrics_dir / f"{session_name}_TE_map_PLOTmeanstd_TEmapping.png"
                )

                # Generate ROI overlay for first TE image
                roi_overlay_base = str(tmp_vial_dir / "roi_overlay_te.png")

                # Create combined ROI overlay for TE
                first_te = te_contrasts[0]
                roi_overlay_file = str(tmp_vial_dir / "te_VialsCombined.nii.gz")
                vial_dir = metrics_dir.parent / "vial_segmentations"
                vial_masks_list = list(vial_dir.glob("*.nii.gz"))

                if vial_masks_list:
                    # Regrid vials and combine
                    regridded_vials = []
                    for vial_mask in vial_masks_list:
                        vial_name = vial_mask.name.replace(".nii.gz", "").replace(
                            ".nii", ""
                        )
                        regridded = str(tmp_vial_dir / f"te_{vial_name}.nii")

                        cmd = [
                            "mrgrid",
                            str(vial_mask),
                            "-template",
                            str(first_te),
                            "-interp",
                            "nearest",
                            "-quiet",
                            "regrid",
                            regridded,
                            "-force",
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        regridded_vials.append(regridded)

                    # Combine vials
                    if len(regridded_vials) > 0:
                        cmd_cat = ["mrcat"] + regridded_vials + ["-", "-axis", "3"]
                        cmd_math = [
                            "mrmath",
                            "-",
                            "max",
                            roi_overlay_file,
                            "-axis",
                            "3",
                            "-force",
                        ]

                        proc_cat = subprocess.Popen(
                            cmd_cat, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                        proc_math = subprocess.Popen(
                            cmd_math,
                            stdin=proc_cat.stdout,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        proc_cat.stdout.close()
                        proc_math.communicate()

                    # Generate mrview screenshot
                    actual_screenshot = self._generate_mrview_screenshot(
                        first_te, roi_overlay_file, roi_overlay_base
                    )

                    if actual_screenshot and Path(actual_screenshot).exists():
                        roi_image_arg = actual_screenshot
                    else:
                        roi_image_arg = (
                            roi_overlay_base  # Use base name even if screenshot failed
                        )
                else:
                    roi_image_arg = roi_overlay_base

                cmd = (
                    ["python3", str(plot_script)]
                    + [str(f) for f in te_contrasts]
                    + [
                        "-m",
                        str(metrics_dir),
                        "-o",
                        str(output_plot),
                        "--roi_image",
                        roi_image_arg,
                    ]
                )

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"    ✓ Generated TE map plot")
                else:
                    print(f"    ✗ TE map plot failed: {result.stderr}")
            else:
                print(f"    ⚠ TE plotting script not found: {plot_script}")
        else:
            print(f"  No TE contrasts found (searched for 'te' in filenames)")

    def process_session(self, input_image: str):
        """
        Process a single phantom session

        Parameters
        ----------
        input_image : str
            Path to primary input image

        Returns
        -------
        results : dict
            Processing results and output paths
        """
        input_path = Path(input_image)
        session_name = input_path.parent.name

        # Create output directories
        output_dir = self.output_base_dir / session_name
        tmp_dir = output_dir / "tmp"
        vial_dir = output_dir / "vial_segmentations"
        metrics_dir = output_dir / "metrics"

        for d in [tmp_dir, vial_dir, metrics_dir]:
            d.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Processing Session: {session_name}")
        print(f"Input: {input_image}")
        print(f"Output: {output_dir}")
        print(f"{'='*60}\n")

        # Step 1: Registration with iteration
        print("Step 1: Registration with orientation correction")
        (
            warped,
            transform,
            inverse_warped,
            iteration,
            rotated_input,
            rotation_matrix_file,
        ) = self._register_with_iteration(str(input_image), session_name, tmp_dir)

        # Save template phantom in scanner space
        template_scanner_space = str(output_dir / "TemplatePhantom_ScannerSpace.nii.gz")
        if iteration == 1:
            cmd = [
                "mrconvert",
                "-quiet",
                inverse_warped,
                template_scanner_space,
                "-force",
            ]
        else:
            cmd = [
                "mrtransform",
                inverse_warped,
                template_scanner_space,
                "-linear",
                rotation_matrix_file,
                "-interp",
                "nearest",
                "-inverse",
                "-force",
            ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  ✓ Saved template in scanner space")

        # Step 2: Transform vials to subject space
        print("\nStep 2: Transforming vials to subject space")
        transformed_vials = self._transform_vials_to_subject_space(
            reference_image=str(input_image),
            transform_matrix=transform,
            rotation_matrix_file=rotation_matrix_file,
            iteration=iteration,
            output_vial_dir=vial_dir,
        )
        print(f"  ✓ Transformed {len(transformed_vials)} vial masks")

        # Step 3: Extract metrics from all contrasts
        print("\nStep 3: Extracting metrics from all contrasts")
        contrast_files = list(input_path.parent.glob("*.nii.gz"))
        print(f"  Found {len(contrast_files)} contrast images")

        all_metrics = {}
        for contrast_file in contrast_files:
            metrics_data = self._extract_metrics_from_contrast(
                contrast_file=contrast_file,
                vial_masks=transformed_vials,
                output_metrics_dir=metrics_dir,
                session_name=session_name,
            )
            all_metrics[contrast_file.name] = metrics_data

        # Step 4: Generate plots
        print("\nStep 4: Generating plots")
        self._generate_plots(
            contrast_files=contrast_files,
            metrics_dir=metrics_dir,
            vial_dir=vial_dir,
            session_name=session_name,
        )

        # Clean up temp directory
        import shutil

        shutil.rmtree(tmp_dir)

        print(f"\n{'='*60}")
        print(f"✓ Session {session_name} complete!")
        print(f"  Metrics: {metrics_dir}")
        print(f"  Vial masks: {vial_dir}")
        print(f"{'='*60}\n")

        return {
            "session": session_name,
            "output_dir": str(output_dir),
            "metrics_dir": str(metrics_dir),
            "vial_dir": str(vial_dir),
            "iteration": iteration,
            "metrics": all_metrics,
        }


# ============================================================================
# Pydra Wrapper Functions
# ============================================================================


@pydra.mark.task
@pydra.mark.annotate(
    {
        "input_image": str,
        "template_dir": str,
        "output_dir": str,
        "rotation_lib": str,
        "return": {"results": dict},
    }
)
def process_phantom_session(input_image, template_dir, output_dir, rotation_lib):
    """Pydra task wrapper for phantom processing"""
    processor = PhantomProcessor(
        template_dir=template_dir,
        output_base_dir=output_dir,
        rotation_library_file=rotation_lib,
    )

    results = processor.process_session(input_image)
    return results


def create_batch_workflow(
    input_images: List[str],
    template_dir: str,
    output_dir: str,
    rotation_lib: str,
    name: str = "phantom_batch",
):
    """Create Pydra workflow for batch processing"""
    wf = pydra.Workflow(
        name=name, input_spec=["images"], cache_dir=str(Path.cwd() / ".pydra_cache")
    )

    wf.inputs.images = input_images

    # Split to process each image
    wf.split("images")

    # Add processing task for each image
    wf.add(
        process_phantom_session(
            name="process_session",
            input_image=wf.lzin.images,
            template_dir=template_dir,
            output_dir=output_dir,
            rotation_lib=rotation_lib,
        )
    )

    wf.combine("images")

    wf.set_output([("results", wf.process_session.lzout.results)])

    return wf


# ============================================================================
# Command-line Interface
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Native Pydra phantom processing (no Docker)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Processing mode")

    # Single session command
    single_parser = subparsers.add_parser("single", help="Process single session")
    single_parser.add_argument("input_image", help="Input NIfTI file")
    single_parser.add_argument(
        "--template-dir", required=True, help="Template directory"
    )
    single_parser.add_argument("--output-dir", required=True, help="Output directory")
    single_parser.add_argument(
        "--rotation-lib", required=True, help="Rotation library file (rotations.txt)"
    )

    # Batch command
    batch_parser = subparsers.add_parser(
        "batch", help="Batch process multiple sessions"
    )
    batch_parser.add_argument("data_dir", help="Directory with session folders")
    batch_parser.add_argument(
        "--template-dir", required=True, help="Template directory"
    )
    batch_parser.add_argument("--output-dir", required=True, help="Output directory")
    batch_parser.add_argument(
        "--rotation-lib", required=True, help="Rotation library file"
    )
    batch_parser.add_argument(
        "--pattern", default="*t1*mprage*.nii.gz", help="Pattern for finding images"
    )
    batch_parser.add_argument(
        "--plugin",
        default="cf",
        choices=["cf", "serial"],
        help="Pydra execution plugin",
    )

    args = parser.parse_args()

    if args.command == "single":
        # Single session processing
        print("=" * 60)
        print("SINGLE SESSION MODE")
        print("=" * 60)

        processor = PhantomProcessor(
            template_dir=args.template_dir,
            output_base_dir=args.output_dir,
            rotation_library_file=args.rotation_lib,
        )

        results = processor.process_session(args.input_image)

        print("\n✓ Processing complete!")
        print(f"Results: {results['output_dir']}")

    elif args.command == "batch":
        # Batch processing
        print("=" * 60)
        print("BATCH PROCESSING MODE")
        print("=" * 60)

        # Find all matching images
        data_path = Path(args.data_dir)
        images = sorted(data_path.glob(f"*/{args.pattern}"))
        images = [str(img) for img in images]

        print(f"\nFound {len(images)} images to process:")
        for img in images:
            print(f"  - {img}")
        print()

        if not images:
            print("ERROR: No images found!")
            exit(1)

        # Create workflow
        wf = create_batch_workflow(
            input_images=images,
            template_dir=args.template_dir,
            output_dir=args.output_dir,
            rotation_lib=args.rotation_lib,
            name="phantom_batch",
        )

        # Execute
        print("Starting batch processing...")
        with pydra.Submitter(plugin=args.plugin) as sub:
            sub(wf)

        results = wf.result()

        print("\n✓ All sessions processed!")
        print(f"Results: {args.output_dir}")

    else:
        parser.print_help()
