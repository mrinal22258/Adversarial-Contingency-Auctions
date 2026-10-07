"""
Benchmark Map Topologies Visualization Suite (Step 2.1).
Reads strictly from data/maps/** and generates publication-grade figures:
- Figure 1: Raw MovingAI warehouse grid + coarsened graph overlay + node/edge counts
- Figure 2: Downtown Boston road network graph with tasks, risk corridors, robot starts, and comm circles
- Figure 3: Synthetic graph families (RGG, Warehouse Grid, Erdős–Rényi) labeled "Synthetic Stress Test"

Writes vector PDF, 300 DPI PNG, and cryptographic .provenance.json sidecars to results/figures/ and static/images/.
"""

import os
import sys
import json
import shutil
import hashlib
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.plot_style import (
    IEEE_SINGLE_COL_WIDTH,
    IEEE_DOUBLE_COL_WIDTH,
    OKABE_ITO,
    apply_ieee_style,
    write_figure_provenance,
)
from acalib.env.real_maps import (
    generate_movingai_warehouse,
    generate_real_road_network,
    DATA_MAPS_DIR,
)
from acalib.env.graph_families import (
    generate_random_geometric,
    generate_warehouse_grid,
    generate_erdos_renyi,
)
from acalib.env.adversaries import canonical_edge

apply_ieee_style()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_FIG_DIR = os.path.join(REPO_ROOT, "results", "figures")
STATIC_IMG_DIR = os.path.join(REPO_ROOT, "static", "images")
os.makedirs(RESULTS_FIG_DIR, exist_ok=True)
os.makedirs(STATIC_IMG_DIR, exist_ok=True)


def parse_movingai_raw_grid(map_path: str):
    """Parse MovingAI .map ASCII file into 2D boolean numpy array (True=passable)."""
    with open(map_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    idx = 0
    header = {}
    while idx < len(lines) and not lines[idx].startswith("map"):
        parts = lines[idx].split()
        if len(parts) >= 2:
            header[parts[0]] = parts[1]
        idx += 1
    idx += 1  # Skip 'map'

    grid_lines = lines[idx:]
    height = len(grid_lines)
    width = len(grid_lines[0]) if height > 0 else 0
    grid = np.zeros((height, width), dtype=bool)

    for r in range(height):
        for c in range(width):
            if grid_lines[r][c] == ".":
                grid[r, c] = True

    return grid, header, height, width


def generate_figure1_movingai(out_dirs: list):
    """Figure 1: Raw MovingAI warehouse grid + coarsened graph overlay + node/edge counts."""
    map_file = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
    grid, header, height, width = parse_movingai_raw_grid(map_file)
    coarsened_g = generate_movingai_warehouse(variant="10-20-10-2-1", n_nodes=38, filepath=map_file)

    n_nodes = coarsened_g.number_of_nodes()
    n_edges = coarsened_g.number_of_edges()
    n_passable = int(np.sum(grid))

    fig, axes = plt.subplots(1, 2, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.7))

    # Panel (a): Raw MovingAI Grid
    ax0 = axes[0]
    # Display grid: 1 (passable, white) vs 0 (obstacle, dark grey)
    grid_img = np.where(grid, 0.95, 0.15)
    ax0.imshow(grid_img, cmap="gray", origin="upper", aspect="equal", extent=[0, width, height, 0])
    ax0.set_title(f"(a) Raw MovingAI Warehouse ({height}$\\times${width})\n{n_passable:,} Passable Cells", fontsize=8.5, fontweight="bold")
    ax0.set_xlabel("X (cells)")
    ax0.set_ylabel("Y (cells)")
    ax0.tick_params(labelsize=7)

    # Panel (b): Coarsened Graph Overlay
    ax1 = axes[1]
    ax1.imshow(grid_img, cmap="gray", origin="upper", aspect="equal", extent=[0, 100, 100, 0], alpha=0.35)

    pos = nx.get_node_attributes(coarsened_g, "pos")
    # In MovingAI coarsening, pos is in [0, 100] x [0, 100] with y inverted for image display
    # pos_display: x = pos[0], y = 100 - pos[1]
    pos_display = {u: (p[0], 100.0 - p[1]) for u, p in pos.items()}

    # Draw edges
    for u, v in coarsened_g.edges():
        pu = pos_display[u]
        pv = pos_display[v]
        ax1.plot([pu[0], pv[0]], [pu[1], pv[1]], color=OKABE_ITO["blue"], lw=1.2, alpha=0.8, zorder=2)

    # Draw nodes
    xs = [pos_display[u][0] for u in coarsened_g.nodes()]
    ys = [pos_display[u][1] for u in coarsened_g.nodes()]
    ax1.scatter(xs, ys, color=OKABE_ITO["vermillion"], s=28, edgecolors="black", linewidths=0.6, zorder=3)

    ax1.set_title(f"(b) Coarsened Topology Overlay\n$|V|={n_nodes}$ Nodes, $|E|={n_edges}$ Edges", fontsize=8.5, fontweight="bold")
    ax1.set_xlabel("X (normalized)")
    ax1.set_ylabel("Y (normalized)")
    ax1.set_xlim(-2, 102)
    ax1.set_ylim(102, -2)
    ax1.tick_params(labelsize=7)

    # Legend
    legend_elements = [
        Line2D([0], [0], color=OKABE_ITO["blue"], lw=1.5, label=f"Corridor Edge ($|E|={n_edges}$)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=OKABE_ITO["vermillion"], markeredgecolor="black", markersize=6, label=f"Waystation ($|V|={n_nodes}$)"),
    ]
    ax1.legend(handles=legend_elements, loc="upper right", framealpha=0.9, fontsize=7)

    fig.tight_layout()

    out_name = "fig_map_movingai_warehouse"
    for d in out_dirs:
        pdf_path = os.path.join(d, f"{out_name}.pdf")
        png_path = os.path.join(d, f"{out_name}.png")
        fig.savefig(pdf_path, dpi=300)
        fig.savefig(png_path, dpi=300)
        write_figure_provenance(
            pdf_path,
            source_files=["data/maps/warehouse-10-20-10-2-1.map"],
            n_instances=1,
            extra_meta={
                "map_type": "warehouse_movingai",
                "grid_height": height,
                "grid_width": width,
                "n_passable": n_passable,
                "n_nodes": n_nodes,
                "n_edges": n_edges,
                "source_hash": hashlib.sha256(open(map_file, "rb").read()).hexdigest(),
            },
        )
        write_figure_provenance(
            png_path,
            source_files=["data/maps/warehouse-10-20-10-2-1.map"],
            n_instances=1,
            extra_meta={"map_type": "warehouse_movingai", "n_nodes": n_nodes, "n_edges": n_edges},
        )
    plt.close(fig)
    print(f"Generated {out_name}: MovingAI warehouse grid and coarsened graph overlay.")


def generate_figure2_boston(out_dirs: list):
    """Figure 2: Boston street graph with task nodes, risk corridors, robot starts, and comm radius circles."""
    map_file = os.path.join(DATA_MAPS_DIR, "boston_downtown_drive.graphml")
    g = generate_real_road_network(filepath=map_file)
    pos = nx.get_node_attributes(g, "pos")

    n_nodes = g.number_of_nodes()
    n_edges = g.number_of_edges()

    # Pre-determined representative trial configuration (CRN seed 42)
    rng = np.random.default_rng(42)
    node_list = sorted(list(g.nodes()))

    # Sample 4 robots
    robot_nodes = rng.choice(node_list, size=4, replace=False).tolist()
    # Sample 8 tasks
    avail_nodes = [n for n in node_list if n not in robot_nodes]
    task_nodes = rng.choice(avail_nodes, size=8, replace=False).tolist()

    # Identify candidate risk corridors (adversary edges from betweenness centrality or degree)
    edge_bc = nx.edge_betweenness_centrality(g)
    sorted_edges = sorted(edge_bc.items(), key=lambda x: x[1], reverse=True)
    risk_edges = [e for e, _ in sorted_edges[:6]]

    fig, ax = plt.subplots(figsize=(IEEE_SINGLE_COL_WIDTH * 1.15, 3.4))

    # Base road network
    for u, v in g.edges():
        pu, pv = pos[u], pos[v]
        if (u, v) in risk_edges or (v, u) in risk_edges:
            continue
        ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color="#A0A0A0", lw=0.9, zorder=1)

    # Risk corridors
    for u, v in risk_edges:
        pu, pv = pos[u], pos[v]
        ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color=OKABE_ITO["vermillion"], lw=2.4, ls="--", zorder=3)

    # Road nodes
    xs = [pos[u][0] for u in g.nodes()]
    ys = [pos[u][1] for u in g.nodes()]
    ax.scatter(xs, ys, color="#666666", s=8, alpha=0.6, zorder=2)

    # Comm radius circles around robots (comm_range = 25)
    comm_r = 25.0
    for r_idx, r_node in enumerate(robot_nodes):
        r_pos = pos[r_node]
        circle = Circle(r_pos, comm_r, color=OKABE_ITO["sky_blue"], alpha=0.18, zorder=4)
        ax.add_patch(circle)
        # Robot marker
        ax.scatter([r_pos[0]], [r_pos[1]], color=OKABE_ITO["blue"], s=55, marker="s", edgecolors="black", linewidths=0.8, zorder=6)
        ax.text(r_pos[0] + 1.2, r_pos[1] + 1.2, f"$R_{r_idx+1}$", fontsize=7.5, fontweight="bold", color=OKABE_ITO["blue"], zorder=7)

    # Tasks
    for t_idx, t_node in enumerate(task_nodes):
        t_pos = pos[t_node]
        ax.scatter([t_pos[0]], [t_pos[1]], color=OKABE_ITO["bluish_green"], s=45, marker="*", edgecolors="black", linewidths=0.6, zorder=6)
        ax.text(t_pos[0] + 1.2, t_pos[1] - 1.5, f"$T_{t_idx+1}$", fontsize=6.5, color=OKABE_ITO["bluish_green"], zorder=7)

    ax.set_title(f"Downtown Boston Arterial Network\n$|V|={n_nodes}$ Intersections, $|E|={n_edges}$ Segments", fontsize=8.5, fontweight="bold")
    ax.set_xlabel("X coordinate (normalized)")
    ax.set_ylabel("Y coordinate (normalized)")
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.tick_params(labelsize=7)

    # Legend
    legend_elements = [
        Line2D([0], [0], color="#A0A0A0", lw=1.0, label=f"Road Segment ($|E|={n_edges}$)"),
        Line2D([0], [0], color=OKABE_ITO["vermillion"], lw=2.0, ls="--", label="Risk (Blockable) Corridor"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=OKABE_ITO["blue"], markeredgecolor="black", markersize=6, label="Robot Start ($R=4$)"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor=OKABE_ITO["bluish_green"], markeredgecolor="black", markersize=7, label="Task Location ($M=8$)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=OKABE_ITO["sky_blue"], alpha=0.5, markeredgecolor="none", markersize=9, label="Comm Range ($r=25$)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.92, fontsize=6.8)

    fig.tight_layout()

    out_name = "fig_map_boston_road"
    for d in out_dirs:
        pdf_path = os.path.join(d, f"{out_name}.pdf")
        png_path = os.path.join(d, f"{out_name}.png")
        fig.savefig(pdf_path, dpi=300)
        fig.savefig(png_path, dpi=300)
        write_figure_provenance(
            pdf_path,
            source_files=["data/maps/boston_downtown_drive.graphml"],
            n_instances=1,
            extra_meta={
                "map_type": "road_osmnx",
                "n_nodes": n_nodes,
                "n_edges": n_edges,
                "source_hash": hashlib.sha256(open(map_file, "rb").read()).hexdigest(),
                "comm_radius": comm_r,
                "robots_count": len(robot_nodes),
                "tasks_count": len(task_nodes),
            },
        )
        write_figure_provenance(
            png_path,
            source_files=["data/maps/boston_downtown_drive.graphml"],
            n_instances=1,
            extra_meta={"map_type": "road_osmnx", "n_nodes": n_nodes, "n_edges": n_edges},
        )
    plt.close(fig)
    print(f"Generated {out_name}: Boston road network with risk corridors and comm radius.")


def generate_figure3_synthetic(out_dirs: list):
    """Figure 3: Synthetic families stress test (RGG, Warehouse Grid, ER)."""
    seed = 42
    scale = 100.0

    g_rgg = generate_random_geometric(n_nodes=35, radius=25.0, seed=seed, scale=scale)
    g_wh = generate_warehouse_grid(rows=6, cols=5, aisle_spacing=2, seed=seed, cell_size=scale / 6.0)
    g_er = generate_erdos_renyi(n_nodes=35, p=0.15, seed=seed, scale=scale)

    families = [
        ("Random Geometric Graph (RGG)", g_rgg, "(a) Synthetic RGG Stress Test"),
        ("Grid Picking Warehouse", g_wh, "(b) Synthetic Warehouse Stress Test"),
        ("Erdős–Rényi Random Graph", g_er, "(c) Synthetic ER Stress Test"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(IEEE_DOUBLE_COL_WIDTH, 2.7))

    for idx, (fam_name, g, panel_title) in enumerate(families):
        ax = axes[idx]
        pos = nx.get_node_attributes(g, "pos")
        n_v = g.number_of_nodes()
        n_e = g.number_of_edges()

        # Draw edges
        for u, v in g.edges():
            pu, pv = pos[u], pos[v]
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color="#777777", lw=1.0, zorder=1)

        # Draw nodes
        xs = [pos[u][0] for u in g.nodes()]
        ys = [pos[u][1] for u in g.nodes()]
        ax.scatter(xs, ys, color=OKABE_ITO["blue"], s=22, edgecolors="black", linewidths=0.5, zorder=2)

        # Representative task and robot markers
        rng = np.random.default_rng(seed + idx)
        node_order = list(g.nodes())
        r_sample = rng.choice(node_order, size=3, replace=False)
        t_sample = rng.choice([n for n in node_order if n not in r_sample], size=5, replace=False)

        for r in r_sample:
            ax.scatter([pos[r][0]], [pos[r][1]], color=OKABE_ITO["vermillion"], s=38, marker="s", edgecolors="black", zorder=3)
        for t in t_sample:
            ax.scatter([pos[t][0]], [pos[t][1]], color=OKABE_ITO["bluish_green"], s=35, marker="*", edgecolors="black", zorder=3)

        ax.set_title(f"{panel_title}\n$|V|={n_v}$, $|E|={n_e}$", fontsize=7.8, fontweight="bold")
        ax.set_xlabel("X (normalized)")
        if idx == 0:
            ax.set_ylabel("Y (normalized)")
        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        ax.tick_params(labelsize=6.5)

    # Shared legend on center panel
    legend_elements = [
        Line2D([0], [0], color="#777777", lw=1.2, label="Edge"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=OKABE_ITO["blue"], markeredgecolor="black", markersize=5, label="Node"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=OKABE_ITO["vermillion"], markeredgecolor="black", markersize=6, label="Robot ($R=3$)"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor=OKABE_ITO["bluish_green"], markeredgecolor="black", markersize=7, label="Task ($M=5$)"),
    ]
    axes[1].legend(handles=legend_elements, loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=4, fontsize=7)

    fig.tight_layout()

    out_name = "fig_map_synthetic_families"
    for d in out_dirs:
        pdf_path = os.path.join(d, f"{out_name}.pdf")
        png_path = os.path.join(d, f"{out_name}.png")
        fig.savefig(pdf_path, dpi=300)
        fig.savefig(png_path, dpi=300)
        write_figure_provenance(
            pdf_path,
            source_files=["acalib/env/graph_families.py"],
            n_instances=3,
            extra_meta={
                "synthetic_families": ["rgg", "warehouse", "er"],
                "seed": seed,
                "label": "synthetic stress test",
            },
        )
        write_figure_provenance(
            png_path,
            source_files=["acalib/env/graph_families.py"],
            n_instances=3,
            extra_meta={"synthetic_families": ["rgg", "warehouse", "er"], "seed": seed},
        )
    plt.close(fig)
    print(f"Generated {out_name}: Synthetic graph families stress test.")


def main():
    out_dirs = [RESULTS_FIG_DIR, STATIC_IMG_DIR]
    print(f"Generating map figures into {out_dirs}...")
    generate_figure1_movingai(out_dirs)
    generate_figure2_boston(out_dirs)
    generate_figure3_synthetic(out_dirs)
    print("Step 2.1 Map figures complete!")


if __name__ == "__main__":
    main()
