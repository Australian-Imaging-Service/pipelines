#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import argparse
import sys
import csv
import os
import numpy as np

def detect_separator(file_path):
    """Detects the most likely CSV separator by sniffing the first line."""
    try:
        with open(file_path, "r", newline="") as f:
            first_line = f.readline()
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(first_line)
            return dialect.delimiter
    except Exception as e:
        sys.exit(f"Error detecting separator: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Plot vial vs intensity (mean ± std) for 3D or 4D contrasts, with optional ROI overlay."
    )
    parser.add_argument("csv_file", help="CSV file containing mean values (vial, mean[, vol1, vol2...]).")
    parser.add_argument("plot_type", choices=["line", "bar", "scatter"],
                        help="Type of plot to generate.")
    parser.add_argument("--std_csv", help="Optional CSV file containing standard deviations (same shape as mean).")
    parser.add_argument("--roi_image", help="Optional PNG image (e.g. mrview screenshot with ROI overlay).")
    parser.add_argument("--annotate", action="store_true", help="Annotate points with mean ± std values.")
    parser.add_argument("--output", default="vial_subplot.png",
                        help="Filename for saving the plot (default: vial_subplot.png).")
    args = parser.parse_args()

    # --- Load mean CSV ---
    sep = detect_separator(args.csv_file)
    mean_df = pd.read_csv(args.csv_file, sep=sep)
    if mean_df.shape[1] < 2:
        sys.exit("Error: mean CSV must have at least two columns (vial + at least one volume).")

    vials = mean_df.iloc[:, 0].astype(str).str.replace(r"\.mif$", "", regex=True)
    mean_values = mean_df.iloc[:, 1:].to_numpy()   # shape (n_vials, n_vols)
    n_vols = mean_values.shape[1]

    # --- Load std CSV (optional) ---
    std_values = None
    if args.std_csv:
        sep_std = detect_separator(args.std_csv)
        std_df = pd.read_csv(args.std_csv, sep=sep_std)
        if std_df.shape[1] < 2:
            sys.exit("Error: std CSV must have at least two columns (vial + at least one volume).")
        std_values = std_df.iloc[:, 1:].to_numpy()  # shape (n_vials, n_vols)

    # --- Setup figure: one plot + optional ROI image ---
    ncols = 2 if args.roi_image else 1
    fig, axes = plt.subplots(1, ncols, figsize=(8*ncols, 6), squeeze=False)
    axes = axes[0]  # flatten row

    ax = axes[0]

    # --- Plot each volume in a different colour ---
    cmap = plt.get_cmap("tab10")
    for vol_idx in range(n_vols):
        means = mean_values[:, vol_idx]
        stds = std_values[:, vol_idx] if std_values is not None else None
        color = cmap(vol_idx % 10)

        if args.plot_type == "line":
            ax.errorbar(vials, means, yerr=stds, fmt='-o', capsize=5, color=color, label=f"Vol {vol_idx}")
        elif args.plot_type == "bar":
            # Offset bars for each volume slightly so they don't overlap
            x = np.arange(len(vials)) + (vol_idx - n_vols/2) * 0.1
            ax.bar(x, means, yerr=stds, capsize=5, color=color, width=0.1, label=f"Vol {vol_idx}")
            ax.set_xticks(np.arange(len(vials)))
            ax.set_xticklabels(vials)
        elif args.plot_type == "scatter":
            ax.errorbar(vials, means, yerr=stds, fmt='o', capsize=5, color=color, label=f"Vol {vol_idx}")

        if args.annotate:
            for vial, mean, std in zip(vials, means, stds if stds is not None else [0]*len(means)):
                ax.text(vial, mean + (max(means) * 0.02),
                        f"{mean:.1f}±{std:.1f}" if stds is not None else f"{mean:.1f}",
                        ha='center', fontsize=8, color=color)

    ax.set_xlabel("Vial")
    ax.set_ylabel("Intensity")
    ax.set_title("Vial vs Intensity (Mean ± Std)")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(title="Volumes")

    # --- ROI overlay subplot ---
    if args.roi_image:
        ax_img = axes[1]
        img = mpimg.imread(args.roi_image)
        ax_img.imshow(img)
        ax_img.axis("off")
        ax_img.set_title("Contrast with Vial ROIs")

    plt.tight_layout()
    output_file = os.path.abspath(args.output)
    plt.savefig(output_file, bbox_inches="tight", dpi=300)
    print(f"[INFO] Plot saved to: {output_file}")
    plt.close(fig)

if __name__ == "__main__":
    main()
