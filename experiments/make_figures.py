"""
Publication-Quality Figure Generator for IEEE RA-L Manuscript.
Reads empirical trials from results/raw_results.csv and outputs vector PDF and PNG figures:
- Fig 2: Completion Rate & Conflicts Comparison (boxplots)
- Fig 3: Net Welfare vs Communication Overhead
"""

import os
import sys
import shutil
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 13,
    "font.family": "serif",
})

METHOD_LABELS = {
    "aca": "ACA (Ours)",
    "cbba": "CBBA",
    "cbba_partial": "CBBA-Partial",
    "cc_cbba": "CC-CBBA",
    "implicit": "Implicit",
    "ssi": "SSI",
    "pessimistic": "Pessimistic",
    "oracle": "Oracle",
}


def plot_main_comparison(df: pd.DataFrame, out_dirs: list) -> None:
    """Plot Figure 2: Completion rate and Conflicts across methods."""
    df_plot = df.copy()
    df_plot["Method"] = df_plot["method"].map(lambda m: METHOD_LABELS.get(m, m))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))

    order = [METHOD_LABELS[m] for m in METHOD_LABELS if m in df["method"].unique()]
    palette = sns.color_palette("Set2", len(order))

    # Subplot 1: Completion Rate
    sns.boxplot(
        data=df_plot,
        x="Method",
        y="completion_rate_pct",
        ax=axes[0],
        palette=palette,
        boxprops=dict(alpha=0.8),
    )
    axes[0].set_ylabel("Task Completion Rate (%)")
    axes[0].set_xlabel("")
    axes[0].set_xticklabels(axes[0].get_xticklabels(), rotation=35, ha="right")
    axes[0].set_title("(a) Mission Success Rate")

    # Subplot 2: Distinct Conflicts (or Total Conflicts if distinct not present)
    conflict_col = "distinct_conflicts" if "distinct_conflicts" in df_plot.columns else "total_conflicts"
    conflict_label = "Distinct Double-Claimed Tasks" if conflict_col == "distinct_conflicts" else "Total Task Conflicts"

    sns.barplot(
        data=df_plot,
        x="Method",
        y=conflict_col,
        ax=axes[1],
        palette=palette,
        capsize=0.1,
        err_kws={"linewidth": 1.2},
    )
    axes[1].set_ylabel(conflict_label)
    axes[1].set_xlabel("")
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=35, ha="right")
    axes[1].set_title("(b) Conflicts Under Divergent Beliefs")

    plt.tight_layout()

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = os.path.join(out_dir, "fig_completion_conflicts.pdf")
        png_path = os.path.join(out_dir, "fig_completion_conflicts.png")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight", pad_inches=0.1)
        fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.1)
        print(f"Saved Figure 2 to {png_path}")

    plt.close(fig)


def plot_welfare_and_messages(df: pd.DataFrame, out_dirs: list) -> None:
    """Plot Figure 3: Net Welfare vs Communication Overhead."""
    df_plot = df.copy()
    df_plot["Method"] = df_plot["method"].map(lambda m: METHOD_LABELS.get(m, m))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    order = [METHOD_LABELS[m] for m in METHOD_LABELS if m in df["method"].unique()]
    palette = sns.color_palette("muted", len(order))

    # Net Welfare
    sns.boxplot(
        data=df_plot,
        x="Method",
        y="net_welfare",
        ax=axes[0],
        palette=palette,
        boxprops=dict(alpha=0.8),
    )
    axes[0].set_ylabel("Net Welfare (Reward - Travel Cost)")
    axes[0].set_xlabel("")
    axes[0].set_xticklabels(axes[0].get_xticklabels(), rotation=35, ha="right")
    axes[0].set_title("(a) Fleet Net Welfare")

    # Total Messages
    sns.barplot(
        data=df_plot,
        x="Method",
        y="total_messages",
        ax=axes[1],
        palette=palette,
        capsize=0.1,
    )
    axes[1].set_ylabel("Total Messages Exchanged")
    axes[1].set_xlabel("")
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=35, ha="right")
    axes[1].set_title("(b) Communication Overhead")

    plt.tight_layout()

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = os.path.join(out_dir, "fig_welfare_messages.pdf")
        png_path = os.path.join(out_dir, "fig_welfare_messages.png")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight", pad_inches=0.1)
        fig.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.1)
        print(f"Saved Figure 3 to {png_path}")

    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="results/raw_results.csv")
    parser.add_argument("--out_dir", type=str, default="results")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: {args.csv} not found.")
        return

    df = pd.read_csv(args.csv)
    print(f"Generating figures from {args.csv}...")
    out_dirs = [args.out_dir, "static/images"]
    plot_main_comparison(df, out_dirs)
    plot_welfare_and_messages(df, out_dirs)


if __name__ == "__main__":
    main()
