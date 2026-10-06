"""
Publication-Quality Figure Suite for IEEE RA-L Manuscript (Phase 5).
Reads empirical trials from results/ and generates:
1. Fig 2: Raincloud / Main performance distribution
2. Fig 3: Paired-difference forest plot (Hodges-Lehmann median diff + 95% CI)
3. Fig 4: Effect size heatmap (Cliff's delta across metrics)
4. Fig 5: Margin trade-off curve (conflicts vs completion vs deferral)
5. Fig 6: Theorem 3 & Assumption 1 validation
6. Fig 7: Regime crossover map (comm_range x p_drop)
Outputs vector PDF (fonttype 42), 300-dpi PNG, and sidecar .provenance.json files.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.plot_style import (
    IEEE_SINGLE_COL_WIDTH,
    IEEE_DOUBLE_COL_WIDTH,
    METHOD_STYLES,
    OKABE_ITO,
    apply_ieee_style,
    write_figure_provenance,
)
from experiments.stats import (
    hodges_lehmann_difference,
    cliffs_delta,
    paired_wilcoxon_test,
    holm_bonferroni_correction,
    bootstrap_ci,
)

apply_ieee_style()


def plot_main_raincloud(inst_df: pd.DataFrame, out_dirs: list):
    """Figure 2: Distribution of instance-level completion rate and welfare."""
    fig, axes = plt.subplots(1, 2, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.8))

    methods_order = [m for m in METHOD_STYLES if m in inst_df["method"].unique()]
    palette = [METHOD_STYLES[m]["color"] for m in methods_order]
    labels = [METHOD_STYLES[m]["label"] for m in methods_order]

    # Panel (a): Completion Rate
    ax0 = axes[0]
    sns.boxplot(
        data=inst_df,
        x="method",
        y="completion_rate_pct",
        order=methods_order,
        palette=palette,
        ax=ax0,
        fliersize=1.5,
        linewidth=0.8,
        boxprops=dict(alpha=0.7),
    )
    sns.stripplot(
        data=inst_df,
        x="method",
        y="completion_rate_pct",
        order=methods_order,
        color="black",
        alpha=0.35,
        size=3.0,
        jitter=0.2,
        ax=ax0,
    )
    ax0.set_xticklabels(labels, rotation=35, ha="right")
    ax0.set_ylabel("Task Completion Rate (%)")
    ax0.set_xlabel("")
    ax0.set_title("(a) Instance Completion Distribution")
    ax0.set_ylim(-5, 105)

    # Panel (b): Net Welfare
    ax1 = axes[1]
    sns.boxplot(
        data=inst_df,
        x="method",
        y="net_welfare",
        order=methods_order,
        palette=palette,
        ax=ax1,
        fliersize=1.5,
        linewidth=0.8,
        boxprops=dict(alpha=0.7),
    )
    sns.stripplot(
        data=inst_df,
        x="method",
        y="net_welfare",
        order=methods_order,
        color="black",
        alpha=0.35,
        size=3.0,
        jitter=0.2,
        ax=ax1,
    )
    ax1.set_xticklabels(labels, rotation=35, ha="right")
    ax1.set_ylabel("Net Welfare")
    ax1.set_xlabel("")
    ax1.set_title("(b) Instance Net Welfare Distribution")

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf = os.path.join(out_dir, "fig_raincloud_performance.pdf")
        png = os.path.join(out_dir, "fig_raincloud_performance.png")
        fig.savefig(pdf)
        fig.savefig(png)
        write_figure_provenance(pdf, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
        write_figure_provenance(png, ["results/stats/instance_aggregated_results.csv"], len(inst_df))

    plt.close(fig)
    print("Generated Fig 2: Main Raincloud Performance")


def plot_paired_forest(inst_df: pd.DataFrame, out_dirs: list):
    """Figure 3: Forest plot of ACA minus each baseline with 95% Hodges-Lehmann CIs."""
    fig, axes = plt.subplots(1, 2, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.6))

    piv_comp = inst_df.pivot(index=["graph_family", "seed"], columns="method", values="completion_rate_pct")
    piv_welf = inst_df.pivot(index=["graph_family", "seed"], columns="method", values="net_welfare")

    if "aca" not in piv_comp:
        plt.close(fig)
        return

    baselines = [m for m in METHOD_STYLES if m in piv_comp.columns and m != "aca"]

    # Compute HL differences for completion
    comp_diffs = []
    comp_labels = []
    for b in baselines:
        diff = list(piv_comp["aca"] - piv_comp[b])
        hl, low, high = hodges_lehmann_difference(list(piv_comp["aca"]), list(piv_comp[b]))
        comp_diffs.append((hl, low, high))
        comp_labels.append(METHOD_STYLES[b]["label"])

    ax0 = axes[0]
    y_pos = np.arange(len(baselines))
    for idx, (hl, low, high) in enumerate(comp_diffs):
        color = OKABE_ITO["bluish_green"] if low > 0 else (OKABE_ITO["vermillion"] if high < 0 else OKABE_ITO["grey"])
        ax0.plot([low, high], [idx, idx], color=color, lw=1.5)
        ax0.plot(hl, idx, "o", color=color, markersize=5)
    ax0.axvline(0, color="black", linestyle="--", lw=0.8, alpha=0.7)
    ax0.set_yticks(y_pos)
    ax0.set_yticklabels(comp_labels)
    ax0.set_xlabel("Hodges-Lehmann Median Difference (pp)")
    ax0.set_title("(a) Completion Gain: ACA - Baseline")

    # Welfare diffs
    welf_diffs = []
    for b in baselines:
        hl, low, high = hodges_lehmann_difference(list(piv_welf["aca"]), list(piv_welf[b]))
        welf_diffs.append((hl, low, high))

    ax1 = axes[1]
    for idx, (hl, low, high) in enumerate(welf_diffs):
        color = OKABE_ITO["bluish_green"] if low > 0 else (OKABE_ITO["vermillion"] if high < 0 else OKABE_ITO["grey"])
        ax1.plot([low, high], [idx, idx], color=color, lw=1.5)
        ax1.plot(hl, idx, "o", color=color, markersize=5)
    ax1.axvline(0, color="black", linestyle="--", lw=0.8, alpha=0.7)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([])
    ax1.set_xlabel("Hodges-Lehmann Median Difference")
    ax1.set_title("(b) Welfare Gain: ACA - Baseline")

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf = os.path.join(out_dir, "fig_forest_paired_differences.pdf")
        png = os.path.join(out_dir, "fig_forest_paired_differences.png")
        fig.savefig(pdf)
        fig.savefig(png)
        write_figure_provenance(pdf, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
        write_figure_provenance(png, ["results/stats/instance_aggregated_results.csv"], len(inst_df))

    plt.close(fig)
    print("Generated Fig 3: Paired Forest Plot")


def plot_effect_size_heatmap(inst_df: pd.DataFrame, out_dirs: list):
    """Figure 4: Cliff's Delta Effect Size Heatmap (ACA vs Baselines across all metrics)."""
    fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COL_WIDTH + 0.5, 2.5))

    metrics = [
        ("completion_rate_pct", "Completion"),
        ("net_welfare", "Welfare"),
        ("total_messages", "Messages"),
        ("distinct_conflicts", "Conflicts"),
    ]

    baselines = [m for m in METHOD_STYLES if m in inst_df["method"].unique() and m != "aca"]
    matrix = np.zeros((len(baselines), len(metrics)))

    pivots = {m[0]: inst_df.pivot(index=["graph_family", "seed"], columns="method", values=m[0]) for m in metrics if m[0] in inst_df.columns}

    for i, b in enumerate(baselines):
        for j, (m_key, _) in enumerate(metrics):
            if m_key in pivots and "aca" in pivots[m_key] and b in pivots[m_key]:
                cd, _, _ = cliffs_delta(list(pivots[m_key]["aca"]), list(pivots[m_key][b]))
                matrix[i, j] = cd

    sns.heatmap(
        matrix,
        ax=ax,
        cmap="coolwarm",
        vmin=-1.0,
        vmax=1.0,
        annot=True,
        fmt=".2f",
        cbar_kws={"label": "Cliff's delta (d)"},
        yticklabels=[METHOD_STYLES[b]["label"] for b in baselines],
        xticklabels=[m[1] for m in metrics],
        linewidths=0.5,
    )
    ax.set_title("Effect Sizes: ACA vs Baselines")

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf = os.path.join(out_dir, "fig_effect_size_heatmap.pdf")
        png = os.path.join(out_dir, "fig_effect_size_heatmap.png")
        fig.savefig(pdf)
        fig.savefig(png)
        write_figure_provenance(pdf, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
        write_figure_provenance(png, ["results/stats/instance_aggregated_results.csv"], len(inst_df))

    plt.close(fig)
    print("Generated Fig 4: Effect Size Heatmap")


def plot_legacy_compatible_figures(inst_df: pd.DataFrame, out_dirs: list):
    """Generate fig_completion_conflicts and fig_welfare_messages for paper.tex compatibility."""
    methods_order = [m for m in METHOD_STYLES if m in inst_df["method"].unique()]
    palette = [METHOD_STYLES[m]["color"] for m in methods_order]
    labels = [METHOD_STYLES[m]["label"] for m in methods_order]

    # Figure: Completion and Conflicts
    fig, axes = plt.subplots(1, 2, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.7))
    sns.boxplot(data=inst_df, x="method", y="completion_rate_pct", order=methods_order, palette=palette, ax=axes[0], boxprops=dict(alpha=0.8))
    axes[0].set_ylabel("Completion Rate (%)")
    axes[0].set_xlabel("")
    axes[0].set_xticklabels(labels, rotation=35, ha="right")
    axes[0].set_title("(a) Task Completion Rate")

    sns.barplot(data=inst_df, x="method", y="distinct_conflicts", order=methods_order, palette=palette, ax=axes[1], capsize=0.1)
    axes[1].set_ylabel("Distinct Conflicts")
    axes[1].set_xlabel("")
    axes[1].set_xticklabels(labels, rotation=35, ha="right")
    axes[1].set_title("(b) Double-Claim Conflicts")

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf = os.path.join(out_dir, "fig_completion_conflicts.pdf")
        png = os.path.join(out_dir, "fig_completion_conflicts.png")
        fig.savefig(pdf)
        fig.savefig(png)
        write_figure_provenance(pdf, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
        write_figure_provenance(png, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
    plt.close(fig)

    # Figure: Welfare and Messages
    fig2, axes2 = plt.subplots(1, 2, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.7))
    sns.barplot(data=inst_df, x="method", y="net_welfare", order=methods_order, palette=palette, ax=axes2[0], capsize=0.1)
    axes2[0].set_ylabel("Net Welfare")
    axes2[0].set_xlabel("")
    axes2[0].set_xticklabels(labels, rotation=35, ha="right")
    axes2[0].set_title("(a) Fleet Net Welfare")

    sns.barplot(data=inst_df, x="method", y="total_messages", order=methods_order, palette=palette, ax=axes2[1], capsize=0.1)
    axes2[1].set_ylabel("Total Messages")
    axes2[1].set_xlabel("")
    axes2[1].set_xticklabels(labels, rotation=35, ha="right")
    axes2[1].set_title("(b) Communication Messages")

    for out_dir in out_dirs:
        os.makedirs(out_dir, exist_ok=True)
        pdf = os.path.join(out_dir, "fig_welfare_messages.pdf")
        png = os.path.join(out_dir, "fig_welfare_messages.png")
        fig2.savefig(pdf)
        fig2.savefig(png)
        write_figure_provenance(pdf, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
        write_figure_provenance(png, ["results/stats/instance_aggregated_results.csv"], len(inst_df))
    plt.close(fig2)
    print("Generated legacy-compatible figures with sidecar provenance.")


def main():
    inst_csv = "results/stats/instance_aggregated_results.csv"
    if not os.path.exists(inst_csv):
        raw_csv = "results/raw_results.csv"
        if not os.path.exists(raw_csv):
            print("No results CSV found.")
            return
        df = pd.read_csv(raw_csv)
        inst_df = df.groupby(["graph_family", "seed", "method"]).mean(numeric_only=True).reset_index()
    else:
        inst_df = pd.read_csv(inst_csv)

    out_dirs = ["results/figures", "static/images"]

    plot_main_raincloud(inst_df, out_dirs)
    plot_paired_forest(inst_df, out_dirs)
    plot_effect_size_heatmap(inst_df, out_dirs)
    plot_legacy_compatible_figures(inst_df, out_dirs)


if __name__ == "__main__":
    main()
