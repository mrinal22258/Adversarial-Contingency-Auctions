"""
Animated Rollout Generator for Multi-Robot Auction Baselines (Step 2.2).
Renders step-by-step multi-robot execution rollouts on:
1. MovingAI Warehouse Map (warehouse-10-20-10-2-1)
2. Downtown Boston Road Network (OSMnx 2.1.1)

Compares on the EXACT SAME seed and blockage stream:
- ACA (Pinsker margin + local recourse)
- CTP Replan (Canadian Traveller Problem replan-on-discovery)
- CBBA (Standard consensus-based bundle algorithm)

Outputs:
- MP4 and GIF animations in results/videos/
- Provenance JSON sidecars
- Keyframe comparison figures for the manuscript
"""

import os
import sys
import json
import hashlib
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.lines import Line2D
import cv2
import imageio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.plot_style import (
    IEEE_SINGLE_COL_WIDTH,
    IEEE_DOUBLE_COL_WIDTH,
    METHOD_STYLES,
    OKABE_ITO,
    apply_ieee_style,
    get_git_commit,
    write_figure_provenance,
)
from acalib.env.real_maps import (
    generate_movingai_warehouse,
    generate_real_road_network,
    DATA_MAPS_DIR,
)
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_DIR = os.path.join(REPO_ROOT, "results", "videos")
RESULTS_FIG_DIR = os.path.join(REPO_ROOT, "results", "figures")
STATIC_IMG_DIR = os.path.join(REPO_ROOT, "static", "images")
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(RESULTS_FIG_DIR, exist_ok=True)
os.makedirs(STATIC_IMG_DIR, exist_ok=True)


def run_deterministic_trial(graph: nx.Graph, method: str, seed: int = 42, max_steps: int = 25):
    """Run a single deterministic simulation trial and record state snapshot per tick."""
    # Common Random Numbers (CRN) for fairness
    rng = np.random.default_rng(seed)
    nodes = sorted(list(graph.nodes()))
    
    # 4 robots, 8 tasks
    starts = rng.choice(nodes, size=4, replace=False).tolist()
    avail = [n for n in nodes if n not in starts]
    task_nodes = rng.choice(avail, size=8, replace=False).tolist()

    # Pre-draw blockage process uniforms for identical realization
    edge_list = sorted([tuple(sorted(e)) for e in graph.edges()])
    # Risk corridors: top 6 by betweenness
    edge_bc = nx.edge_betweenness_centrality(graph)
    sorted_edges = sorted(edge_bc.items(), key=lambda x: x[1], reverse=True)
    risky_edges = {tuple(sorted(e)) for e, _ in sorted_edges[:6]}

    onset_unifs = {}
    clear_unifs = {}
    for e in risky_edges:
        for s in range(max_steps + 1):
            onset_unifs[(e, s)] = float(rng.uniform())
            clear_unifs[(e, s)] = float(rng.uniform())

    engine = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.REACTIVE,
        allocator_type=method,
        n_robots=4,
        n_tasks=8,
        custom_start_nodes=starts,
        custom_risky_edges=risky_edges,
        predrawn_onset_uniforms=onset_unifs,
        predrawn_clear_uniforms=clear_unifs,
        max_steps=max_steps,
        comm_range=35.0,
        p_drop=0.05,
        contingency_depth=1 if method == "aca" else 0,
        seed=seed,
    )

    # Force task nodes
    for idx, tid in enumerate(engine.tasks):
        engine.tasks[tid].node = task_nodes[idx % len(task_nodes)]

    engine.reset()

    snapshots = []
    pos_attr = nx.get_node_attributes(graph, "pos")

    for step in range(max_steps):
        # Record state before/at step
        r_positions = {rid: np.array(r.pos) for rid, r in engine.robots.items()}
        r_bundles = {rid: list(r.bundle) for rid, r in engine.robots.items()}
        r_paths = {rid: list(r.path) if hasattr(r, "path") else [] for rid, r in engine.robots.items()}
        
        # Blocked edges
        blocked_edges = set(engine.blockage_process.get_blocked_edges())
        
        # Completed tasks
        completed_tasks = [tid for tid, t in engine.tasks.items() if t.completed]
        claimed_tasks = {tid: rid for rid, r in engine.robots.items() for tid in r.bundle}

        # Metrics snapshot
        msgs = engine.metrics.total_messages
        conflicts = engine.metrics.total_conflicts
        completed_count = len(completed_tasks)
        
        # Detour events
        detour_active = any(getattr(r, "detour_active", False) for r in engine.robots.values())

        snapshots.append({
            "step": step,
            "robot_positions": r_positions,
            "robot_bundles": r_bundles,
            "robot_paths": r_paths,
            "blocked_edges": blocked_edges,
            "completed_tasks": completed_tasks,
            "claimed_tasks": claimed_tasks,
            "total_messages": msgs,
            "total_conflicts": conflicts,
            "completed_count": completed_count,
            "detour_active": detour_active,
        })

        ongoing = engine.step(step)
        if not ongoing:
            break

    return snapshots, engine.metrics, starts, task_nodes, risky_edges


def render_trial_frame(
    graph: nx.Graph,
    snapshot: dict,
    method_name: str,
    method_color: str,
    map_label: str,
    risky_edges: set,
    task_nodes: list,
    img_size: tuple = (640, 540),
):
    """Render a single simulation step into an RGB numpy image array."""
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=100)
    pos = nx.get_node_attributes(graph, "pos")

    # Base edges
    for u, v in graph.edges():
        pu, pv = pos[u], pos[v]
        can_e = tuple(sorted((u, v)))
        if can_e in snapshot["blocked_edges"]:
            # Physical blockage barrier
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color="#D55E00", lw=3.0, ls="-", zorder=3)
            # Draw barrier X
            mid_x = (pu[0] + pv[0]) / 2.0
            mid_y = (pu[1] + pv[1]) / 2.0
            ax.scatter([mid_x], [mid_y], color="#D55E00", marker="x", s=90, lw=2.5, zorder=5)
        elif can_e in risky_edges:
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color="#E69F00", lw=1.5, ls="--", alpha=0.7, zorder=2)
        else:
            ax.plot([pu[0], pv[0]], [pu[1], pv[1]], color="#C0C0C0", lw=0.9, zorder=1)

    # Road / waypoint nodes
    xs = [pos[u][0] for u in graph.nodes()]
    ys = [pos[u][1] for u in graph.nodes()]
    ax.scatter(xs, ys, color="#888888", s=10, alpha=0.5, zorder=2)

    # Tasks
    for tid_idx, t_node in enumerate(task_nodes):
        t_pos = pos[t_node]
        if tid_idx in snapshot["completed_tasks"]:
            # Completed
            ax.scatter([t_pos[0]], [t_pos[1]], color="#009E73", s=65, marker="P", edgecolors="black", lw=0.8, zorder=4)
        elif tid_idx in snapshot["claimed_tasks"]:
            # Claimed
            ax.scatter([t_pos[0]], [t_pos[1]], color="#56B4E9", s=60, marker="*", edgecolors="black", lw=0.8, zorder=4)
        else:
            # Unclaimed
            ax.scatter([t_pos[0]], [t_pos[1]], color="#F0E442", s=50, marker="o", edgecolors="black", lw=0.8, zorder=4)

    # Robots
    robot_colors = ["#0072B2", "#CC79A7", "#009E73", "#D55E00"]
    for rid, r_pos in snapshot["robot_positions"].items():
        col = robot_colors[rid % len(robot_colors)]
        ax.scatter([r_pos[0]], [r_pos[1]], color=col, s=80, marker="s", edgecolors="black", lw=1.0, zorder=6)
        ax.text(r_pos[0] + 1.2, r_pos[1] + 1.2, f"R{rid}", fontsize=7.5, fontweight="bold", color=col, zorder=7)

    # Watermark and HUD Telemetry
    step = snapshot["step"]
    compl = snapshot["completed_count"]
    msgs = snapshot["total_messages"]
    confl = snapshot["total_conflicts"]
    detour_str = "DETOUR ACTIVE" if snapshot["detour_active"] else "NOMINAL PATH"

    ax.set_title(
        f"{method_name} on {map_label} | Tick {step:02d}\n"
        f"Tasks: {compl}/8 | Msgs: {msgs} | Conflicts: {confl} | [{detour_str}]",
        fontsize=9.0,
        fontweight="bold",
        color="#222222",
    )
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.axis("off")

    # Simulation Notice Banner
    ax.text(
        50.0,
        -3.5,
        "SIMULATION — Algorithmic Multi-Robot Rollout — No Physical Robot",
        fontsize=6.5,
        ha="center",
        color="#555555",
        fontweight="bold",
        bbox=dict(boxstyle="square,pad=0.2", facecolor="#EFEFEF", edgecolor="#CCCCCC", alpha=0.8),
    )

    fig.tight_layout()
    fig.canvas.draw()

    # Convert canvas to RGB numpy array
    rgba = np.asarray(fig.canvas.buffer_rgba())
    rgb = rgba[:, :, :3].copy()
    plt.close(fig)

    if (rgb.shape[1], rgb.shape[0]) != img_size:
        rgb = cv2.resize(rgb, img_size)

    return rgb


def render_comparison_video(
    map_type: str,
    graph: nx.Graph,
    seed: int = 42,
    max_steps: int = 20,
):
    """Render synchronized comparative rollout video for ACA vs CTP Replan vs CBBA."""
    map_label = "MovingAI Warehouse" if "warehouse" in map_type else "Downtown Boston Road"
    methods = [
        ("aca", "ACA (Ours)", OKABE_ITO["vermillion"]),
        ("ctp_replan", "CTP Replan", "#008080"),
        ("cbba", "CBBA (Standard)", OKABE_ITO["sky_blue"]),
    ]

    method_data = {}
    starts, task_nodes, risky_edges = None, None, None

    for m_key, m_label, m_col in methods:
        snaps, metrics, s_init, t_init, r_edges = run_deterministic_trial(
            graph, m_key, seed=seed, max_steps=max_steps
        )
        method_data[m_key] = snaps
        if starts is None:
            starts, task_nodes, risky_edges = s_init, t_init, r_edges

    n_frames = min(len(snaps) for snaps in method_data.values())

    video_prefix = f"rollout_{map_type}_comparison"
    mp4_path = os.path.join(VIDEOS_DIR, f"{video_prefix}.mp4")
    gif_path = os.path.join(VIDEOS_DIR, f"{video_prefix}.gif")

    # Render frames
    frames = []
    keyframe_indices = [0, 4, 8, min(14, n_frames - 1)]
    saved_keyframes = {}

    panel_w, panel_h = 360, 320
    comp_w = panel_w * 3
    comp_h = panel_h

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(mp4_path, fourcc, 3.0, (comp_w, comp_h))

    for frame_idx in range(n_frames):
        panel_imgs = []
        for m_key, m_label, m_col in methods:
            snap = method_data[m_key][frame_idx]
            rgb = render_trial_frame(
                graph,
                snap,
                m_label,
                m_col,
                map_label,
                risky_edges,
                task_nodes,
                img_size=(panel_w, panel_h),
            )
            panel_imgs.append(rgb)

        # Stitch horizontally
        combined = np.hstack(panel_imgs)
        vw.write(cv2.cvtColor(combined, cv2.COLOR_RGB2BGR))
        frames.append(combined)

        if frame_idx in keyframe_indices:
            saved_keyframes[frame_idx] = combined

    vw.release()

    # Save GIF (sampled 2 fps)
    imageio.mimsave(gif_path, frames, duration=0.5, loop=0)

    # Save provenance JSON
    prov_data = {
        "video_file": f"results/videos/{video_prefix}.mp4",
        "gif_file": f"results/videos/{video_prefix}.gif",
        "map_type": map_type,
        "seed": seed,
        "max_steps": max_steps,
        "n_frames": n_frames,
        "methods_compared": [m[0] for m in methods],
        "git_commit": get_git_commit(),
        "disclaimer": "SIMULATION ONLY — No physical robots or hardware used.",
    }
    with open(os.path.join(VIDEOS_DIR, f"{video_prefix}.provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov_data, f, indent=2)

    print(f"Generated {mp4_path} and {gif_path} ({n_frames} frames).")
    return saved_keyframes, keyframe_indices


def generate_keyframe_figure(saved_keyframes: dict, keyframe_indices: list, map_type: str, out_dirs: list):
    """Generate publication keyframe figure embedding representative progression steps."""
    map_title = "MovingAI Warehouse" if "warehouse" in map_type else "Downtown Boston Road Network"
    fig, axes = plt.subplots(len(keyframe_indices), 1, figsize=(IEEE_DOUBLE_COL_WIDTH, 5.8))

    for row_idx, k_idx in enumerate(keyframe_indices):
        ax = axes[row_idx]
        img = saved_keyframes[k_idx]
        ax.imshow(img)
        ax.set_title(f"Step {k_idx:02d}: Fleet Progression (Left: ACA | Center: CTP Replan | Right: CBBA)", fontsize=7.5, fontweight="bold")
        ax.axis("off")

    fig.tight_layout()
    out_name = f"fig_rollout_keyframes_{map_type}"

    for d in out_dirs:
        pdf_path = os.path.join(d, f"{out_name}.pdf")
        png_path = os.path.join(d, f"{out_name}.png")
        fig.savefig(pdf_path, dpi=300)
        fig.savefig(png_path, dpi=300)
        write_figure_provenance(
            pdf_path,
            source_files=[f"data/maps/{'warehouse-10-20-10-2-1.map' if 'warehouse' in map_type else 'boston_downtown_drive.graphml'}"],
            n_instances=1,
            extra_meta={
                "map_type": map_type,
                "keyframes": keyframe_indices,
                "generator_script": "make_rollout_videos.py",
            },
        )
        write_figure_provenance(
            png_path,
            source_files=[f"data/maps/{'warehouse-10-20-10-2-1.map' if 'warehouse' in map_type else 'boston_downtown_drive.graphml'}"],
            n_instances=1,
            extra_meta={"map_type": map_type, "generator_script": "make_rollout_videos.py"},
        )
    plt.close(fig)
    print(f"Generated {out_name} keyframe panel in {out_dirs}.")


def main():
    print("Loading benchmark maps for rollout generation...")
    wh_map = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
    g_wh = generate_movingai_warehouse(n_nodes=38, filepath=wh_map)

    boston_map = os.path.join(DATA_MAPS_DIR, "boston_downtown_drive.graphml")
    g_boston = generate_real_road_network(filepath=boston_map)

    out_dirs = [RESULTS_FIG_DIR, STATIC_IMG_DIR]

    # 1. MovingAI Warehouse comparative rollout
    print("Generating MovingAI warehouse animated rollout...")
    kf_wh, kf_indices = render_comparison_video("warehouse", g_wh, seed=42, max_steps=18)
    generate_keyframe_figure(kf_wh, kf_indices, "warehouse", out_dirs)

    # 2. Boston Road Network comparative rollout
    print("Generating Boston road network animated rollout...")
    kf_bos, kf_indices_b = render_comparison_video("boston", g_boston, seed=42, max_steps=18)
    generate_keyframe_figure(kf_bos, kf_indices_b, "boston", out_dirs)

    print("Step 2.2 Animated rollouts and keyframes completed successfully!")


if __name__ == "__main__":
    main()
