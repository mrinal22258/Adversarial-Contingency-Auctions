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

    # Use exact IEEE single column width (3.5 in) with sufficient height for clean Demsar labels
    fig, ax = plt.subplots(figsize=(3.5, 2.05), dpi=300)

    # Horizontal rank axis from 1 to k
    min_rank = 1.0
    max_rank = float(k)
    y_axis = 0.72

    ax.plot([min_rank, max_rank], [y_axis, y_axis], color="#212529", linewidth=1.2)
    for r in range(int(min_rank), int(max_rank) + 1):
        ax.plot([r, r], [y_axis - 0.03, y_axis + 0.03], color="#212529", linewidth=0.9)
        ax.text(r, y_axis + 0.06, str(r), ha="center", va="bottom", fontsize=7.5, fontweight="bold")

    # Critical Difference marker on top - centered to avoid any margin clipping
    cd_mid = (min_rank + max_rank) / 2.0
    cd_start = cd_mid - cd / 2.0
    cd_end = cd_mid + cd / 2.0
    ax.plot([cd_start, cd_end], [1.02, 1.02], color="#D55E00", linewidth=2.0)
    ax.plot([cd_start, cd_start], [0.98, 1.06], color="#D55E00", linewidth=1.2)
    ax.plot([cd_end, cd_end], [0.98, 1.06], color="#D55E00", linewidth=1.2)
    ax.text(cd_mid, 1.08, f"CD = {cd:.2f} (Nemenyi, $\\alpha=0.05$)", ha="center", va="bottom", fontsize=6.8, fontweight="bold", color="#D55E00")

    # Find cliques where |r_i - r_j| <= cd
    cliques = []
    for i in range(k):
        for j in range(i + 1, k):
            if abs(ranks[i] - ranks[j]) <= cd:
                cliques.append((ranks[i], ranks[j]))

    # Merge overlapping clique segments
    bar_y = 0.62
    if cliques:
        min_c = min(c[0] for c in cliques)
        max_c = max(c[1] for c in cliques)
        ax.plot([min_c, max_c], [bar_y, bar_y], color="#009E73", linewidth=2.8, alpha=0.85, label="Statistically Equivalent ($p > 0.05$)")

    # Method points and non-crossing Demsar horizontal leader lines
    # Split into left (<3.5) and right (>=3.5)
    left_indices = [i for i, r in enumerate(ranks) if r < 3.5]
    right_indices = [i for i, r in enumerate(ranks) if r >= 3.5]

    # Non-crossing y-staggering:
    # On left: larger x gets higher y so vertical drops from larger x turn left above smaller x
    y_left_steps = [0.24, 0.44] if len(left_indices) == 2 else list(np.linspace(0.20, 0.46, len(left_indices)))
    # On right: smaller x gets lower y so vertical drops from larger x turn right above smaller x
    y_right_steps = [-0.04, 0.09, 0.22, 0.35, 0.48] if len(right_indices) == 5 else list(np.linspace(-0.04, 0.48, len(right_indices)))

    def format_name(m):
        short = m.replace("_", " ").upper()
        if short == "CLAIRVOYANT GREEDY":
            return "CLAIRVOYANT"
        elif short == "CBBA PARTIAL LR":
            return "CBBA-PR+LR"
        elif short == "CBBA PARTIAL":
            return "CBBA-PR"
        elif short == "CBBA LR":
            return "CBBA+LR"
        elif short == "SSI LR":
            return "SSI+LR"
        return short

    for idx, i in enumerate(left_indices):
        m = methods[i]
        r = ranks[i]
        yl = y_left_steps[idx]
        color = "#D55E00" if "aca" in m else "#333333"
        ax.scatter([r], [y_axis], color=color, s=26, zorder=4, edgecolor="black", linewidth=0.5)
        ax.plot([r, r, 2.5], [y_axis - 0.02, yl, yl], color="#777777", linewidth=0.75, linestyle="-")
        label_text = f"{format_name(m)} ({r:.2f})"
        ax.text(2.45, yl, label_text, ha="right", va="center", fontsize=8.0, fontweight="bold", color=color)

    for idx, i in enumerate(right_indices):
        m = methods[i]
        r = ranks[i]
        yr = y_right_steps[idx]
        color = "#D55E00" if "aca" in m else "#333333"
        ax.scatter([r], [y_axis], color=color, s=28, zorder=4, edgecolor="black", linewidth=0.5)
        ax.plot([r, r, 5.2], [y_axis - 0.02, yr, yr], color="#777777", linewidth=0.75, linestyle="-")
        label_text = f"{format_name(m)} ({r:.2f})"
        ax.text(5.25, yr, label_text, ha="left", va="center", fontsize=8.0, fontweight="bold", color=color)

    ax.set_xlim(min_rank - 0.8, max_rank + 1.6)
    ax.set_ylim(-0.15, 1.25)
    ax.axis("off")

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
        fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.08)
        fig.savefig(out_png, dpi=400, bbox_inches="tight", pad_inches=0.08)
        sidecar = {**prov, "figure_file": out_pdf}
        for path_to_sidecar in [
            out_pdf + ".provenance.json",
            out_png + ".provenance.json",
            os.path.splitext(out_pdf)[0] + ".provenance.json",
        ]:
            with open(path_to_sidecar, "w", encoding="utf-8") as f:
                json.dump(sidecar, f, indent=2)

    plt.close(fig)
    print(f"CD diagram generated in {out_dirs}: {output_filename}")

    print(f"CD diagram generated: {out_pdf}")
    return out_pdf


if __name__ == "__main__":
    plot_critical_difference_diagram()
