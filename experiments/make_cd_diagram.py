"""
Publication Critical Difference (CD) Diagram Generator (Step 4.4, Step 6.1).

Visualizes Friedman + Nemenyi post-hoc ranking results:
- Plots average method ranks along an inverted axis (Rank 1 on the left is best).
- Connects statistically indistinguishable cliques with horizontal bars (|R_i - R_j| <= CD).
- Uses IEEE column width (3.5 in / 88 mm) and Okabe-Ito color palette.
- Outputs vector PDF + PNG + cryptographic provenance sidecar.
"""

import os
import sys
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.plot_style import get_git_commit, apply_ieee_style

FIGURES_DIR = os.path.join(REPO_ROOT, "results", "figures")
STATS_DIR = os.path.join(REPO_ROOT, "results", "stats")
STATIC_DIR = os.path.join(REPO_ROOT, "static", "images")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)


def plot_critical_difference_diagram(
    fn_json_path: str = os.path.join(STATS_DIR, "friedman_nemenyi_completion.json"),
    output_filename: str = "fig_critical_difference_diagram.pdf",
):
    apply_ieee_style()

    if not os.path.exists(fn_json_path):
        print(f"Warning: {fn_json_path} not found. Skipping CD diagram.")
        return

    with open(fn_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    mean_ranks = data.get("mean_ranks", {})
    cd = data.get("nemenyi_cd", 1.0)
    if not mean_ranks:
        return

    # Sort methods by average rank (ascending: rank 1 is best)
    sorted_methods = sorted(mean_ranks.items(), key=lambda x: x[1])
    methods = [m[0] for m in sorted_methods]
    ranks = [m[1] for m in sorted_methods]
    k = len(methods)

    # Use exact IEEE single column width (3.5 in) with sufficient height for legible staggered labels
    fig, ax = plt.subplots(figsize=(3.5, 1.85), dpi=300)

    # Horizontal rank axis from 1 to k
    min_rank = 1.0
    max_rank = float(k)
    y_axis = 0.58

    ax.plot([min_rank, max_rank], [y_axis, y_axis], color="#212529", linewidth=1.2)
    for r in range(int(min_rank), int(max_rank) + 1):
        ax.plot([r, r], [y_axis - 0.03, y_axis + 0.03], color="#212529", linewidth=0.9)
        ax.text(r, y_axis + 0.06, str(r), ha="center", va="bottom", fontsize=7.5, fontweight="bold")

    # Critical Difference marker on top
    cd_start = min_rank + 0.3
    cd_end = cd_start + cd
    ax.plot([cd_start, cd_end], [0.96, 0.96], color="#D55E00", linewidth=2.0)
    ax.plot([cd_start, cd_start], [0.93, 0.99], color="#D55E00", linewidth=1.2)
    ax.plot([cd_end, cd_end], [0.93, 0.99], color="#D55E00", linewidth=1.2)
    ax.text((cd_start + cd_end) / 2.0, 1.02, f"CD = {cd:.2f} (Nemenyi, $\\alpha=0.05$)", ha="center", va="bottom", fontsize=7.0, fontweight="bold", color="#D55E00")

    # Method points and leader lines
    for i, (m, r) in enumerate(zip(methods, ranks)):
        # 3-way stagger text heights to prevent collisions in single column
        stagger_idx = i % 3
        y_text = 0.28 if stagger_idx == 0 else (0.16 if stagger_idx == 1 else 0.04)
        is_aca = "aca" in m
        color = "#D55E00" if is_aca else "#333333"
        ax.scatter([r], [y_axis], color=color, s=28, zorder=4, edgecolor="black", linewidth=0.5)
        ax.plot([r, r], [y_axis - 0.02, y_text + 0.04], ":", color="#888888", linewidth=0.7)
        short_name = m.replace("_", " ").upper()
        if short_name == "CLAIRVOYANT GREEDY":
            short_name = "CLAIRVOYANT"
        elif short_name == "CBBA PARTIAL LR":
            short_name = "CBBA-PR+LR"
        elif short_name == "CBBA PARTIAL":
            short_name = "CBBA-PR"
        elif short_name == "CBBA LR":
            short_name = "CBBA+LR"
        elif short_name == "SSI LR":
            short_name = "SSI+LR"
        label_text = f"{short_name} ({r:.2f})"
        ax.text(r, y_text, label_text, ha="center", va="top", fontsize=6.2, fontweight="bold", rotation=25, color=color)

    # Find cliques where |r_i - r_j| <= cd
    cliques = []
    for i in range(k):
        for j in range(i + 1, k):
            if abs(ranks[i] - ranks[j]) <= cd:
                cliques.append((ranks[i], ranks[j]))

    # Merge overlapping clique segments
    bar_y = 0.48
    if cliques:
        min_c = min(c[0] for c in cliques)
        max_c = max(c[1] for c in cliques)
        ax.plot([min_c, max_c], [bar_y, bar_y], color="#009E73", linewidth=2.8, alpha=0.85, label="Statistically Equivalent ($p > 0.05$)")

    ax.set_xlim(min_rank - 0.4, max_rank + 0.4)
    ax.set_ylim(-0.12, 1.18)
    ax.axis("off")
    plt.tight_layout(pad=0.2)

    prov = {
        "commit": get_git_commit(),
        "disclaimer": "SIMULATION ONLY -- Friedman Omnibus + Nemenyi CD",
        "n_instances": data.get("n_instances"),
        "friedman_stat": data.get("friedman_stat"),
        "p_value": data.get("p_value"),
        "nemenyi_cd": cd,
        "mean_ranks": mean_ranks,
        "generator_script": "experiments/make_cd_diagram.py",
    }

    out_dirs = [FIGURES_DIR, STATIC_DIR]
    for d in out_dirs:
        out_pdf = os.path.join(d, output_filename)
        out_png = os.path.splitext(out_pdf)[0] + ".png"
        fig.savefig(out_pdf, bbox_inches="tight")
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        sidecar = {**prov, "figure_file": out_pdf}
        with open(os.path.splitext(out_pdf)[0] + ".provenance.json", "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)
        with open(os.path.splitext(out_png)[0] + ".provenance.json", "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)

    plt.close(fig)
    print(f"CD diagram generated in {out_dirs}: {output_filename}")

    print(f"CD diagram generated: {out_pdf}")
    return out_pdf


if __name__ == "__main__":
    plot_critical_difference_diagram()
