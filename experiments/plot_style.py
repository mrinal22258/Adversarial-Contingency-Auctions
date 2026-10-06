"""
Plot Styling and Color Palette for IEEE RA-L Manuscript (Phase 5).
Adheres strictly to IEEE formatting guidelines:
- Widths: 3.5 in (single column) and 7.16 in (double column)
- Colorblind-safe Okabe-Ito palette
- Vector PDF (fonttype 42) and high-resolution PNG
- Standardized method markers, colors, and line widths
"""

import json
import subprocess
import matplotlib.pyplot as plt

# IEEE Publication Standard Dimensions (inches)
IEEE_SINGLE_COL_WIDTH = 3.5
IEEE_DOUBLE_COL_WIDTH = 7.16

# Colorblind-safe Okabe-Ito Palette
# Black, Orange, Sky Blue, Bluish Green, Yellow, Blue, Vermillion, Reddish Purple
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "reddish_purple": "#CC79A7",
    "grey": "#999999",
}

# Standardized method visual mapping
METHOD_STYLES = {
    "aca": {"label": "ACA (Ours)", "color": OKABE_ITO["vermillion"], "marker": "o", "zorder": 10, "lw": 2.2},
    "aca_no_margin": {"label": "ACA (No Margin)", "color": OKABE_ITO["orange"], "marker": "s", "zorder": 8, "lw": 1.6},
    "aca_depth_0": {"label": "ACA (Depth 0)", "color": OKABE_ITO["yellow"], "marker": "^", "zorder": 7, "lw": 1.6},
    "cbba_lr": {"label": "CBBA+LR", "color": OKABE_ITO["blue"], "marker": "D", "zorder": 6, "lw": 1.6},
    "cbba": {"label": "CBBA", "color": OKABE_ITO["sky_blue"], "marker": "d", "zorder": 5, "lw": 1.4},
    "cbba_partial_lr": {"label": "CBBA-PR+LR", "color": OKABE_ITO["bluish_green"], "marker": "v", "zorder": 6, "lw": 1.6},
    "cbba_partial": {"label": "CBBA-PR", "color": "#20B2AA", "marker": "<", "zorder": 4, "lw": 1.4},
    "ssi_lr": {"label": "SSI+LR", "color": OKABE_ITO["reddish_purple"], "marker": "P", "zorder": 6, "lw": 1.6},
    "ssi": {"label": "SSI", "color": "#DA70D6", "marker": "p", "zorder": 4, "lw": 1.4},
    "implicit": {"label": "Implicit", "color": OKABE_ITO["grey"], "marker": "x", "zorder": 3, "lw": 1.2},
    "pessimistic": {"label": "Pessimistic Ref.", "color": "#708090", "marker": "*", "zorder": 2, "lw": 1.2},
    "oracle": {"label": "Clairvoyant Greedy", "color": OKABE_ITO["black"], "marker": "+", "zorder": 2, "lw": 1.2},
}


def apply_ieee_style():
    """Apply publication-grade Matplotlib rcParams."""
    plt.rcParams.update({
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif", "STIXGeneral"],
        "font.size": 8.5,
        "axes.labelsize": 9.0,
        "axes.titlesize": 9.5,
        "legend.fontsize": 8.0,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "axes.linewidth": 0.8,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.5,
        "lines.linewidth": 1.5,
        "lines.markersize": 5.0,
        "figure.constrained_layout.use": True,
        "figure.dpi": 300,
    })


def get_git_commit():
    """Retrieve git commit hash for provenance."""
    git_cmd = r"C:\Program Files\Git\cmd\git.exe"
    try:
        commit = subprocess.check_output([git_cmd, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode("ascii").strip()
        return commit
    except Exception:
        return "unknown"


def write_figure_provenance(fig_path: str, source_files: list, n_instances: int, extra_meta: dict = None):
    """Write sidecar .provenance.json file."""
    provenance = {
        "figure_file": fig_path,
        "git_commit": get_git_commit(),
        "source_files": source_files,
        "n_instances": n_instances,
        "metadata": extra_meta or {},
    }
    json_path = fig_path + ".provenance.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2)
