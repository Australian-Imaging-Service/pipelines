#!/usr/bin/env python3
"""
================================================================================
T2 Multi-Echo Spin Echo Plotting Script
================================================================================
This script reads mean and standard deviation data from CSV files for multiple
echo time (TE) contrast images, plots them grouped by vials, and fits a
mono-exponential T2 decay model to estimate T2 relaxation times.

Key outputs:
- Publication-quality 3x3 grid plot of intensity vs echo time
- CSV file with fitted T2 values and R² statistics
================================================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import argparse
import re
from scipy.optimize import curve_fit


def find_csv_file(metric_dir, contrast_name, suffix):
    """
    Find a CSV file in a directory that matches the contrast name and suffix.

    Args:
        metric_dir: Directory containing CSV files
        contrast_name: Base name of the contrast to search for
        suffix: File suffix to match (e.g., '_mean_matrix.csv')

    Returns:
        Full path to the matched CSV file

    Raises:
        FileNotFoundError: If no matching file is found
    """
    for f in os.listdir(metric_dir):
        if contrast_name in f and f.endswith(suffix):
            return os.path.join(metric_dir, f)
    raise FileNotFoundError(
        f"No CSV file found for contrast '{contrast_name}' with suffix '{suffix}' in {metric_dir}"
    )


def extract_numeric(label):
    """
    Extract the last numeric value from a string label.

    Used to extract echo times from filenames (e.g., 'SE_80' → 80)

    Args:
        label: String containing numbers (e.g., 'contrast_100')

    Returns:
        Last integer found in the string, or None if no numbers found
    """
    numbers = re.findall(r"\d+", label)
    return int(numbers[-1]) if numbers else None


def mono_exp(te, S0, T2):
    """
    Mono-exponential T2 decay model for spin echo MRI data.

    Model: S0 * exp(-TE/T2)

    Args:
        te: Echo time (ms) - can be scalar or array
        S0: Initial signal intensity at TE=0
        T2: Transverse relaxation time (ms)

    Returns:
        Signal intensity at given echo time(s)
    """
    return S0 * np.exp(-te / T2)


def calc_r2(y_true, y_pred):
    """
    Calculate coefficient of determination (R²) for model fit quality.

    R² = 1 - (SS_res / SS_tot)
    where SS_res = sum of squared residuals
          SS_tot = total sum of squares

    Args:
        y_true: Observed data values
        y_pred: Predicted values from model

    Returns:
        R² value (1.0 = perfect fit, 0.0 = no better than mean)
    """
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot)


def plot_vial_means_std_pub_from_nifti(
    contrast_files,
    metric_dir,
    output_file="vial_summary_pub.png",
    annotate=False,
    roi_image=None,
):
    """
    Create publication-quality plots of vial intensity data with T2 curve fitting.

    Generates a 3x3 grid of subplots showing intensity vs echo time for
    different vial groups, with fitted T2 decay curves overlaid on the measured data.

    Args:
        contrast_files: List of NIfTI file paths for different echo times
        metric_dir: Directory containing mean/std CSV files
        output_file: Output filename for the plot (default: 'vial_summary_pub.png')
        annotate: Whether to annotate points with mean ± std (not currently used)
        roi_image: Optional path to ROI overlay image for extra subplot
    """

    # ========================================================================
    # CONFIGURATION: Vial groupings for subplots
    # ========================================================================
    # Define which vials appear together in each subplot
    # Single-element lists get their own subplot (plotted in black)
    # Multi-element lists share a subplot (each vial gets a different color)
    vial_groups = [
        ["S"],  # Subplot 1: Vial S alone
        ["D", "P"],  # Subplot 2: Vials D and P together
        ["M"],  # Subplot 3: Vial M alone
        ["C", "N"],  # Subplot 4: Vials C and N together
        ["B", "T"],  # Subplot 5: Vials B and T together
        ["A", "R"],  # Subplot 6: Vials A and R together
        ["O"],  # Subplot 7: Vial O alone
        ["Q"],  # Subplot 8: Vial Q alone
        # Subplot 9: Reserved for ROI overlay image (if provided)
    ]

    # ========================================================================
    # DATA LOADING: Read mean and std deviation from CSV files
    # ========================================================================
    vial_labels = None  # Vial identifiers (e.g., ['A', 'B', 'C', ...])
    contrast_numbers = []  # Echo times extracted from filenames
    mean_matrix = []  # Mean intensity values for each vial at each TE
    std_matrix = []  # Standard deviation values

    # Loop through each contrast file (different echo times)
    for nifti_path in contrast_files:
        # Extract base filename without extension
        base_name = os.path.basename(nifti_path).replace(".nii.gz", "")

        # Find corresponding CSV files with mean and std data
        mean_csv = find_csv_file(metric_dir, base_name, "_mean_matrix.csv")
        std_csv = find_csv_file(metric_dir, base_name, "_std_matrix.csv")

        # Read CSV files (auto-detect delimiter: comma, tab, etc.)
        mean_df = pd.read_csv(mean_csv, sep=None, engine="python")
        std_df = pd.read_csv(std_csv, sep=None, engine="python")

        # Get vial labels from first file (column 0)
        if vial_labels is None:
            vial_labels = mean_df.iloc[:, 0].astype(str).tolist()

        # Extract intensity values (column 1) and echo time from filename
        mean_matrix.append(mean_df.iloc[:, 1].to_numpy())
        std_matrix.append(std_df.iloc[:, 1].to_numpy())
        contrast_numbers.append(extract_numeric(base_name))

    # Convert lists to numpy arrays for easier manipulation
    mean_matrix = np.array(mean_matrix)
    std_matrix = np.array(std_matrix)

    # ========================================================================
    # DATA ORGANIZATION: Sort by echo time and transpose
    # ========================================================================
    # Sort all data by echo time (ascending order)
    sort_idx = np.argsort(contrast_numbers)
    contrast_numbers = np.array(contrast_numbers)[sort_idx]
    mean_matrix = mean_matrix[sort_idx].T  # Transpose so rows=vials, cols=TE
    std_matrix = std_matrix[sort_idx].T

    # Create mapping from vial label to row index for quick lookup
    vial_to_idx = {label: i for i, label in enumerate(vial_labels)}

    # Define y-axis limits for all subplots (consistent across all plots)
    yticks = [-100, 1000, 2000, 3000, 4000]

    # ========================================================================
    # FIGURE SETUP: Create 3x3 subplot grid
    # ========================================================================
    fig, axes = plt.subplots(3, 3, figsize=(18, 12))
    axes = axes.flatten()  # Convert 2D array to 1D for easier indexing
    cmap = plt.get_cmap("tab10")  # Color map for multi-vial plots (10 colors)

    # Storage for fitted parameters (will be saved to CSV)
    fit_results = []

    # ========================================================================
    # MAIN PLOTTING LOOP: Process each vial group
    # ========================================================================
    for g_idx, group in enumerate(vial_groups):
        ax = axes[g_idx]  # Get current subplot

        # --------------------------------------------------------------------
        # CASE 1: Single vial subplot
        # --------------------------------------------------------------------
        if len(group) == 1:
            vial = group[0]
            if vial not in vial_to_idx:
                continue
            i = vial_to_idx[vial]  # Get row index for this vial

            # ================================================================
            # *** RAW DATA PLOTTING SECTION ***
            # ================================================================
            # Plot measured intensity data with error bars
            # This is the experimental data before any curve fitting

            # Plot error bars only (no markers, no line)
            ax.errorbar(
                contrast_numbers,  # x-axis: echo times (ms)
                mean_matrix[i, :],  # y-axis: mean intensity values
                yerr=std_matrix[i, :],  # error bars: ± standard deviation
                fmt="none",  # NO markers or lines (error bars only)
                capsize=5,  # width of error bar caps
                color="black",  # error bar color
                alpha=0.5,  # slight transparency for error bars
            )

            # Plot scatter points on top
            ax.scatter(
                contrast_numbers,  # x-axis: echo times (ms)
                mean_matrix[i, :],  # y-axis: mean intensity values
                s=50,  # marker size
                color="black",  # marker color
                marker="o",  # circle markers
                label=f"Vial {vial}",  # legend label
                zorder=3,  # draw on top of error bars
            )
            # ================================================================

            # Attempt to fit T2 mono-exponential decay curve to the data
            try:
                # Non-linear least squares curve fitting
                # Keep covariance matrix for CI calculation
                popt, pcov = curve_fit(
                    mono_exp,  # Model function to fit
                    contrast_numbers,  # x data (echo times)
                    mean_matrix[i, :],  # y data (intensities)
                    p0=(mean_matrix[i, 0], 100),  # Initial guesses: [S0, T2]
                )
                S0_fit, T2_fit = popt  # Extract fitted parameters

                # Calculate fitted curve and goodness of fit (R²)
                fit_signal = mono_exp(contrast_numbers, *popt)
                r2 = calc_r2(mean_matrix[i, :], fit_signal)

                # Store fit results for CSV output
                fit_results.append(
                    {"Vial": vial, "S0": S0_fit, "T2_ms": T2_fit, "R2": r2}
                )

                # ============================================================
                # *** 95% CONFIDENCE INTERVAL CALCULATION ***
                # ============================================================
                # Create fine grid for smooth curve visualization
                x_fit = np.linspace(min(contrast_numbers), max(contrast_numbers), 200)

                # Calculate 95% CI via Monte Carlo sampling from parameter covariance
                ci_lower = None
                ci_upper = None
                try:
                    # Sample parameter space (1000 samples from multivariate normal)
                    n_samples = 1000
                    param_samples = np.random.multivariate_normal(popt, pcov, n_samples)

                    # Generate predictions for each parameter sample
                    predictions = np.array(
                        [
                            mono_exp(x_fit, sample[0], sample[1])
                            for sample in param_samples
                        ]
                    )

                    # Calculate 2.5th and 97.5th percentiles (95% CI)
                    ci_lower = np.percentile(predictions, 2.5, axis=0)
                    ci_upper = np.percentile(predictions, 97.5, axis=0)

                except (np.linalg.LinAlgError, ValueError) as e:
                    # Covariance matrix might be singular or ill-conditioned
                    print(f"[WARN] Could not calculate 95% CI for vial {vial}: {e}")

                # ============================================================
                # *** FITTED CURVE AND CI BAND PLOTTING ***
                # ============================================================
                # Plot 95% confidence interval band (if calculated successfully)
                if ci_lower is not None and ci_upper is not None:
                    ax.fill_between(
                        x_fit,
                        ci_lower,
                        ci_upper,
                        color="gray",  # Gray to match fitted curve
                        alpha=0.2,  # Transparent (subtle background)
                        zorder=1,  # Behind fitted curve and data
                        label="95% CI",  # Legend label
                    )

                # Plot smooth fitted curve (dashed line) over data
                ax.plot(
                    x_fit,
                    mono_exp(x_fit, *popt),
                    "--",  # Dashed line style
                    color="gray",  # Gray color for fitted curve
                    alpha=0.8,  # Slight transparency
                    zorder=2,  # On top of CI band, below data
                    label="T₂ fit",  # Legend label
                )
            except RuntimeError:
                # Curve fitting failed for this vial
                print(f"[WARN] Could not fit T₂ for vial {vial}")

        # --------------------------------------------------------------------
        # CASE 2: Multiple vials in one subplot
        # --------------------------------------------------------------------
        else:
            for j, vial in enumerate(group):
                if vial not in vial_to_idx:
                    continue
                i = vial_to_idx[vial]  # Get row index for this vial

                # ============================================================
                # *** RAW DATA PLOTTING SECTION ***
                # ============================================================
                # Plot measured intensity data with error bars
                # Each vial in the group gets a different color

                # Plot error bars only (no markers, no line)
                ax.errorbar(
                    contrast_numbers,  # x-axis: echo times (ms)
                    mean_matrix[i, :],  # y-axis: mean intensity values
                    yerr=std_matrix[i, :],  # error bars: ± standard deviation
                    fmt="none",  # NO markers or lines (error bars only)
                    capsize=5,  # width of error bar caps
                    color=cmap(j % 10),  # error bar color matches vial color
                    alpha=0.5,  # slight transparency for error bars
                )

                # Plot scatter points on top
                ax.scatter(
                    contrast_numbers,  # x-axis: echo times (ms)
                    mean_matrix[i, :],  # y-axis: mean intensity values
                    s=50,  # marker size
                    color=cmap(j % 10),  # marker color from colormap
                    marker="o",  # circle markers
                    label=f"Vial {vial}",  # legend label
                    zorder=3,  # draw on top of error bars
                )
                # ============================================================

                # Attempt to fit T2 mono-exponential decay curve
                try:
                    # Non-linear least squares curve fitting
                    # Keep covariance matrix for CI calculation
                    popt, pcov = curve_fit(
                        mono_exp,
                        contrast_numbers,
                        mean_matrix[i, :],
                        p0=(mean_matrix[i, 0], 100),
                    )
                    S0_fit, T2_fit = popt

                    # Calculate fitted curve and R²
                    fit_signal = mono_exp(contrast_numbers, *popt)
                    r2 = calc_r2(mean_matrix[i, :], fit_signal)

                    # Store fit results
                    fit_results.append(
                        {"Vial": vial, "S0": S0_fit, "T2_ms": T2_fit, "R2": r2}
                    )

                    # ========================================================
                    # *** 95% CONFIDENCE INTERVAL CALCULATION ***
                    # ========================================================
                    # Create fine grid for smooth curve
                    x_fit = np.linspace(
                        min(contrast_numbers), max(contrast_numbers), 200
                    )

                    # Calculate 95% CI via Monte Carlo sampling
                    ci_lower = None
                    ci_upper = None
                    try:
                        # Sample parameter space
                        n_samples = 1000
                        param_samples = np.random.multivariate_normal(
                            popt, pcov, n_samples
                        )

                        # Generate predictions
                        predictions = np.array(
                            [
                                mono_exp(x_fit, sample[0], sample[1])
                                for sample in param_samples
                            ]
                        )

                        # Calculate percentiles (95% CI)
                        ci_lower = np.percentile(predictions, 2.5, axis=0)
                        ci_upper = np.percentile(predictions, 97.5, axis=0)

                    except (np.linalg.LinAlgError, ValueError) as e:
                        print(f"[WARN] Could not calculate 95% CI for vial {vial}: {e}")

                    # ========================================================
                    # *** PLOT CI BAND AND FITTED CURVE ***
                    # ========================================================
                    # Plot 95% CI band (if calculated)
                    if ci_lower is not None and ci_upper is not None:
                        ax.fill_between(
                            x_fit,
                            ci_lower,
                            ci_upper,
                            color=cmap(j % 10),  # Match vial color
                            alpha=0.15,  # Very transparent
                            zorder=1,  # Behind everything
                        )

                    # Plot smooth fitted curve (dashed, same color as data)
                    ax.plot(
                        x_fit,
                        mono_exp(x_fit, *popt),
                        "--",  # Dashed line
                        color=cmap(j % 10),  # Match data color
                        alpha=0.8,
                        zorder=2,  # On top of CI, below data
                    )
                except RuntimeError:
                    print(f"[WARN] Could not fit T₂ for vial {vial}")

            # Add legend for multi-vial subplots
            ax.legend(loc="upper right", fontsize=8)

        # --------------------------------------------------------------------
        # SUBPLOT FORMATTING: Set titles, limits, and labels
        # --------------------------------------------------------------------
        ax.set_title(" & ".join(group), fontsize=10)  # e.g., "D & P"
        ax.set_ylim(min(yticks), max(yticks))  # Consistent y-axis range
        ax.grid(True, axis="y", linestyle="--", alpha=0.5)  # Horizontal gridlines

        # Only show y-axis labels on leftmost column
        if g_idx % 3 == 0:
            ax.set_yticks(yticks)
            ax.set_yticklabels([str(t) for t in yticks])
            ax.set_ylabel("Intensity", fontsize=9)
        else:
            ax.set_yticks(yticks)
            ax.set_yticklabels([])  # Hide labels but keep tick marks

    # ========================================================================
    # SPECIAL SUBPLOT: ROI Overlay (bottom-right position)
    # ========================================================================
    ax = axes[-1]  # Last subplot (position 9)
    if roi_image and os.path.exists(roi_image):
        # Display ROI overlay image if provided
        img = plt.imread(roi_image)
        ax.imshow(
            img,
            extent=[
                contrast_numbers[0],
                contrast_numbers[-1],
                min(yticks),
                max(yticks),
            ],
            aspect="auto",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title("ROI Overlay", fontsize=10)
    else:
        # Hide subplot if no ROI image provided
        ax.axis("off")

    # ========================================================================
    # SAVE OUTPUTS: Plot and fitted parameters
    # ========================================================================
    plt.tight_layout(rect=[0, 0, 1, 1])
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"[INFO] Publication-ready plot saved to {output_file}")

    # Save fitted T2 values to CSV
    csv_output = os.path.splitext(output_file)[0] + "_T2_fits.csv"
    pd.DataFrame(fit_results).to_csv(csv_output, index=False)
    print(f"[INFO] Fitted parameters saved to {csv_output}")

    plt.close(fig)


def main():
    """
    Command-line interface for the T2 plotting script.
    
    Example usage:
        python plot_maps_TE.py echo1.nii.gz echo2.nii.gz \
               -m /path/to/metrics/ -o output_plot.png
    """
    parser = argparse.ArgumentParser(
        description="Plot grouped vial mean ± std with mono-exponential T₂ fitting and save fit metrics."
    )
    parser.add_argument(
        "contrast_files", nargs="+", help="Full paths to NIfTI contrast images."
    )
    parser.add_argument(
        "-m",
        "--metric_dir",
        required=True,
        help="Directory containing the mean/std CSV files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="vial_summary_pub.png",
        help="Output filename for the plot.",
    )
    parser.add_argument(
        "--annotate", action="store_true", help="Annotate each point with mean ± std."
    )
    parser.add_argument(
        "--roi_image", help="Path to ROI overlay PNG image for the extra subplot."
    )

    args = parser.parse_args()
    plot_vial_means_std_pub_from_nifti(
        args.contrast_files,
        metric_dir=args.metric_dir,
        output_file=args.output,
        annotate=args.annotate,
        roi_image=args.roi_image,
    )


if __name__ == "__main__":
    main()
