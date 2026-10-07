"""
Confidence Interval Width vs Sample Size Scaling Analysis (Step 4.4).

Demonstrates convergence of estimation uncertainty under Hodges-Lehmann
median differences as sample size n scales from 10 to N:
- Resamples sub-cohorts of size n in [10, 20, 30, ..., N]
- Computes empirical 95% CI width W(n) = CI_upper - CI_lower
- Fits asymptotic rate W(n) ~ c / sqrt(n)
- Generates vector PDF + PNG + provenance sidecar.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.plot_style import get_git_commit, apply_ieee_style
from experiments.stats import hodges_lehmann_difference

FIGURES_DIR = os.path.join(REPO_ROOT, "results", "figures")
STATS_DIR = os.path.join(REPO_ROOT, "results", "stats")
os.makedirs(FIGURES_DIR, exist_ok=True)


def plot_ci_width_vs_n(
    inst_csv_path: str = os.path.join(STATS_DIR, "instance_aggregated_results.csv"),
    output_filename: str = "fig_ci_width_scaling.pdf",
    n_resamples: int = 100,
    seed: int = 42,
):
    apply_ieee_style()

    if not os.path.exists(inst_csv_path):
        print(f"Warning: {inst_csv_path} not found. Skipping CI scaling plot.")
        return

    df = pd.read_csv(inst_csv_path)
    piv = df.pivot(index=["graph_family", "seed"], columns="method", values="completion_rate_pct")

    if "aca" not in piv.columns or "aca_depth_0" not in piv.columns:
        return

    x = piv["aca"].dropna()
    y = piv["aca_depth_0"].dropna()
    common = x.index.intersection(y.index)
    N = len(common)
    if N < 15:
        return

    x_c = x.loc[common].values
    y_c = y.loc[common].values

    rng = np.random.default_rng(seed)
    n_steps = np.arange(10, N + 1, step=max(5, (N - 10) // 10))
    mean_ci_widths = []
    sd_ci_widths = []

    for n_sub in n_steps:
        sub_widths = []
        for _ in range(n_resamples):
            idx = rng.choice(N, size=n_sub, replace=False)
            _, low, high = hodges_lehmann_difference(list(x_c[idx]), list(y_c[idx]))
            sub_widths.append(high - low)
        mean_ci_widths.append(float(np.mean(sub_widths)))
        sd_ci_widths.append(float(np.std(sub_widths)))

    mean_ci_widths = np.array(mean_ci_widths)
    sd_ci_widths = np.array(sd_ci_widths)

    fig, ax = plt.subplots(figsize=(5.5, 3.5), dpi=300)

    # Plot empirical scaling
    ax.errorbar(
        n_steps, mean_ci_widths, yerr=sd_ci_widths,
        fmt="-o", color="#0072B2", ecolor="#56B4E9", capsize=3,
        linewidth=1.8, label="Empirical HL 95% CI Width"
    )

    # Theoretical O(1/sqrt(n)) curve
    c_fit = mean_ci_widths[0] * np.sqrt(n_steps[0])
    theo_curve = c_fit / np.sqrt(n_steps)
    ax.plot(n_steps, theo_curve, "--", color="#D55E00", linewidth=1.5, label=r"Asymptotic $\mathcal{O}(1/\sqrt{n})$ Bound")

    ax.set_title("Estimation Precision Scaling: 95% CI Width vs. Sample Size", fontsize=10, fontweight="bold")
    ax.set_xlabel("Independent Instances ($n$)", fontsize=9)
    ax.set_ylabel("Hodges-Lehmann 95% CI Width [pp]", fontsize=9)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=8.5)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()

    out_pdf = os.path.join(FIGURES_DIR, output_filename)
    out_png = os.path.splitext(out_pdf)[0] + ".png"
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)

    prov = {
        "figure_file": out_pdf,
        "commit": get_git_commit(),
        "disclaimer": "SIMULATION ONLY -- CI Width Scaling Analysis",
        "sample_sizes": n_steps.tolist(),
        "mean_widths": mean_ci_widths.tolist(),
        "n_total_instances": N,
    }
    with open(os.path.splitext(out_pdf)[0] + ".provenance.json", "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2)

    print(f"CI scaling figure generated: {out_pdf}")
    return out_pdf


if __name__ == "__main__":
    plot_ci_width_vs_n()
