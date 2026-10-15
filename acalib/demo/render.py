"""
Mission-Control Map and Telemetry Rendering Engine.
Renders real-environment geometry with ASCII grid/OSM road backdrops, dynamic robot trajectories,
contingency detours, and adversary blockages without spring_layout distortion.
"""

import os
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx

ROBOT_COLORS = [
    "#2563eb",  # Blue
    "#059669",  # Emerald
    "#7c3aed",  # Violet
    "#0891b2",  # Cyan
    "#4338ca",  # Indigo
    "#0d9488",  # Teal
    "#475569",  # Slate
    "#6b21a8",  # Deep Purple
]

MAPS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "maps")
)


def load_warehouse_ascii_grid(variant: str = "10-20-10-2-1") -> Tuple[np.ndarray, int, int]:
    """Parse MovingAI .map ASCII grid into a 2D numpy mask (1=aisle/passable, 0=obstacle)."""
    map_file = os.path.join(MAPS_DIR, f"warehouse-{variant}.map")
    if not os.path.exists(map_file):
        return np.ones((50, 50), dtype=float), 50, 50

    with open(map_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    idx = 0
    while idx < len(lines) and not lines[idx].startswith("map"):
        idx += 1
    idx += 1

    grid_lines = lines[idx:]
    height = len(grid_lines)
    width = len(grid_lines[0]) if height > 0 else 0

    grid_array = np.zeros((height, width), dtype=float)
    for r in range(height):
        row_str = grid_lines[r]
        for c in range(min(width, len(row_str))):
            if row_str[c] == ".":
                grid_array[r, c] = 1.0  # Passable aisle
            else:
                grid_array[r, c] = 0.0  # Obstacle shelf

    return grid_array, height, width


def get_boston_work_zone_edges(graph: nx.Graph) -> Set[Tuple[int, int]]:
    """Identify real work zone edges from boston_work_zones.csv matching graph street names."""
    wz_file = os.path.join(MAPS_DIR, "boston_work_zones.csv")
    if not os.path.exists(wz_file):
        return set()

    try:
        import pandas as pd
        df = pd.read_csv(wz_file)

        def normalize_street(s):
            if not isinstance(s, str):
                return ""
            s = s.upper().strip()
            for suffix in [" STREET", " ST", " AVENUE", " AVE", " COURT", " CT", " PLACE", " PL", " ROAD", " RD", " WAY"]:
                if s.endswith(suffix):
                    s = s[:-len(suffix)].strip()
            return s

        df["norm"] = df["Street"].apply(normalize_street)
        wz_names = set(df["norm"].unique()) - {""}

        matched = set()
        for u, v, d in graph.edges(data=True):
            raw_name = d.get("name", "")
            if isinstance(raw_name, list):
                names = [normalize_street(x) for x in raw_name if x]
            else:
                names = [normalize_street(raw_name)] if raw_name else []
            if any(n in wz_names for n in names):
                matched.add(tuple(sorted([u, v])))
        return matched
    except Exception:
        return set()


def _stagger_labels(
    anchors: List[Tuple[float, float, str, str, Dict[str, Any]]],
    span_x: float,
    span_y: float,
) -> List[Tuple[float, float, str, str, Dict[str, Any]]]:
    """
    Collision-avoidance offset search for label placement.
    anchors: list of (x, y, text_label, kind, style_dict)
    Returns: list of (placed_x, placed_y, text_label, kind, style_dict)
    """
    placed_boxes: List[Tuple[float, float, float, float]] = []
    results = []

    # Standard candidate offsets (dx, dy) in map units
    step_y = 0.024 * span_y
    step_x = 0.035 * span_x

    offsets_priority = [
        (0.0, step_y),        # Top
        (0.0, -step_y),       # Bottom
        (step_x, 0.0),        # Right
        (-step_x, 0.0),       # Left
        (step_x, step_y),     # Top-Right
        (-step_x, step_y),    # Top-Left
        (step_x, -step_y),    # Bottom-Right
        (-step_x, -step_y),   # Bottom-Left
        (0.0, 1.8 * step_y),  # High Top
        (0.0, -1.8 * step_y), # Low Bottom
    ]

    approx_w = step_x * 1.5
    approx_h = step_y * 1.0

    for ax_pt, ay_pt, text, kind, style in anchors:
        best_pos = (ax_pt, ay_pt + step_y)
        min_overlap = float("inf")

        for dx, dy in offsets_priority:
            cx = ax_pt + dx
            cy = ay_pt + dy
            b_left, b_right = cx - approx_w / 2, cx + approx_w / 2
            b_bottom, b_top = cy - approx_h / 2, cy + approx_h / 2

            # Compute overlap area with existing placed boxes
            overlap_area = 0.0
            for ex_l, ex_r, ex_b, ex_t in placed_boxes:
                ox = max(0.0, min(b_right, ex_r) - max(b_left, ex_l))
                oy = max(0.0, min(b_top, ex_t) - max(b_bottom, ex_b))
                overlap_area += ox * oy

            # Slight penalty for larger distance from anchor
            cost = overlap_area + 0.05 * (abs(dx) + abs(dy))
            if cost < min_overlap:
                min_overlap = cost
                best_pos = (cx, cy)
                if overlap_area == 0.0:
                    break

            if min_overlap == 0.0:
                break

        cx, cy = best_pos
        placed_boxes.append((cx - approx_w / 2, cx + approx_w / 2, cy - approx_h / 2, cy + approx_h / 2))
        results.append((cx, cy, text, kind, style))

    return results


def plot_simulation_state(
    history: List[Dict[str, Any]],
    graph: nx.Graph,
    pos: Dict[int, Tuple[float, float]],
    tick_idx: int,
    graph_family: str = "warehouse_movingai",
    variant: str = "10-20-10-2-1",
    work_zone_edges: Optional[Set[Tuple[int, int]]] = None,
    show_work_zones: bool = False,
) -> Optional[plt.Figure]:
    """
    Render a single simulation frame with calm, intentional mission-control design.
    Never uses spring_layout. Title is outside axes. Legend is single-row below map.
    Collision-avoid labels for tasks/robots. Road nodes on Boston are never labeled.
    Work-zone edges are thin translucent amber and toggleable.
    """
    if not history or tick_idx >= len(history):
        return None

    frame = history[tick_idx]
    # Figure sized to fit neatly in standard viewport without excessive vertical height
    fig, ax = plt.subplots(figsize=(9.2, 5.6), dpi=100)
    fig.patch.set_facecolor("#131d31")
    ax.set_facecolor("#182236")  # Calm tactical slate background

    # Extract coordinates bounds
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    min_x, max_x = (min(xs), max(xs)) if xs else (0.0, 100.0)
    min_y, max_y = (min(ys), max(ys)) if ys else (0.0, 100.0)
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    max_span = max(span_x, span_y)

    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)
    half_span = 0.53 * max_span

    ax.set_xlim(center_x - half_span, center_x + half_span)
    ax.set_ylim(center_y - half_span, center_y + half_span)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    num_nodes = len(graph.nodes())
    is_road_map = "road" in graph_family.lower()

    # 1. Base Layer: Real ASCII Grid Backdrop for MovingAI
    if not is_road_map:
        grid_array, h, w = load_warehouse_ascii_grid(variant=variant)
        flipped = grid_array[::-1, :]
        rgb_img = np.zeros((h, w, 3), dtype=float)
        for r in range(h):
            for c in range(w):
                if flipped[r, c] > 0.5:
                    rgb_img[r, c] = [0.10, 0.15, 0.23]  # Aisles: tactical slate
                else:
                    rgb_img[r, c] = [0.04, 0.06, 0.10]  # Shelves: dark navy
        ax.imshow(
            rgb_img,
            extent=[min_x, max_x, min_y, max_y],
            origin="lower",
            zorder=1,
            interpolation="nearest",
            alpha=0.92,
        )

    # 2. Road Edges & Topologies
    blocked_edges = set(tuple(sorted(e)) for e in frame.get("blocked_edges", []))
    newly_blocked = set(tuple(sorted(e)) for e in frame.get("newly_blocked", []))
    detour_edges = set(tuple(sorted(e)) for e in frame.get("active_detours", []))

    if work_zone_edges is None and is_road_map:
        work_zone_edges = get_boston_work_zone_edges(graph)

    # Open regular edges
    regular_edges = []
    wz_to_draw = []
    for u, v in graph.edges():
        c_e = tuple(sorted((u, v)))
        if c_e in blocked_edges:
            continue
        if show_work_zones and work_zone_edges and c_e in work_zone_edges:
            wz_to_draw.append((u, v))
        else:
            regular_edges.append((u, v))

    # Draw regular open edges (tactile dark grid)
    edge_color = "#38475c" if not is_road_map else "#334155"
    edge_width = 1.1 if num_nodes > 100 else 1.8
    nx.draw_networkx_edges(
        graph, pos, edgelist=regular_edges,
        ax=ax, edge_color=edge_color, width=edge_width, alpha=0.75,
    )

    # Draw Boston Permitted Work Zones: thin translucent amber
    if wz_to_draw and show_work_zones:
        nx.draw_networkx_edges(
            graph, pos, edgelist=wz_to_draw,
            ax=ax, edge_color="#f59e0b", width=1.2, alpha=0.45, style="solid",
        )

    # Draw Recently Traversed Detours (zero-comm local pivots)
    if detour_edges:
        nx.draw_networkx_edges(
            graph, pos, edgelist=list(detour_edges),
            ax=ax, edge_color="#0284c7", width=2.4, style="dotted", alpha=0.9,
        )

    # Draw Blocked Edges (Strictly Red)
    if blocked_edges:
        nx.draw_networkx_edges(
            graph, pos, edgelist=list(blocked_edges),
            ax=ax, edge_color="#dc2626", width=3.4, style="solid", alpha=0.95,
        )
        for u, v in blocked_edges:
            if u in pos and v in pos:
                mid_x = 0.5 * (pos[u][0] + pos[v][0])
                mid_y = 0.5 * (pos[u][1] + pos[v][1])
                is_new = (u, v) in newly_blocked or (v, u) in newly_blocked
                x_color = "#dc2626" if is_new else "#991b1b"
                ax.plot(mid_x, mid_y, marker="x", markersize=8, color=x_color, markeredgewidth=2.2, zorder=8)

    # 3. Base Nodes (Clean Slate)
    node_size = 28 if num_nodes > 100 else 130
    node_color = "#38bdf8" if num_nodes > 100 else "#60a5fa"
    nx.draw_networkx_nodes(
        graph, pos, ax=ax,
        node_color=node_color, node_size=node_size, edgecolors="#ffffff", linewidths=0.9,
    )

    # Road nodes on Boston: NEVER label. Only warehouse with <= 60 nodes gets background node labels
    if not is_road_map and num_nodes <= 60:
        sub_labels = {n: str(n) for n in graph.nodes() if n in pos}
        nx.draw_networkx_labels(
            graph, pos, labels=sub_labels, ax=ax,
            font_size=7, font_color="#475569", font_weight="normal",
        )

    # 4. Faint Robot Planned Paths
    for r in frame.get("robots", []):
        rid = r["id"]
        color = ROBOT_COLORS[rid % len(ROBOT_COLORS)]
        plan_nodes = r.get("planned_route", [])
        if plan_nodes and len(plan_nodes) >= 2:
            pts = [pos[n] for n in plan_nodes if n in pos]
            if len(pts) >= 2:
                xs_p, ys_p = zip(*pts)
                ax.plot(xs_p, ys_p, color=color, linestyle="--", linewidth=1.5, alpha=0.45, zorder=4)

    # 5. Prepare Tasks & Robots Markers and Collect Label Anchors for Staggering
    label_anchors = []

    # Tasks
    for t in frame.get("tasks", []):
        loc = t.get("location")
        if loc not in pos:
            continue
        tx, ty = pos[loc]
        tid = t["id"]
        rew = int(t.get("reward", 100))

        if t.get("is_completed", False):
            # Completed: green circle (strictly green)
            ax.plot(tx, ty, marker="o", markersize=8, color="#10b981", markeredgecolor="#ffffff", markeredgewidth=1.2, zorder=6)
        else:
            # Pending: amber star (strictly amber)
            ax.plot(tx, ty, marker="*", markersize=14, color="#f59e0b", markeredgecolor="#b45309", markeredgewidth=1.0, zorder=7)
            label_anchors.append((
                tx, ty, f"T{tid} (+{rew})", "task",
                {
                    "facecolor": "#fffbeb",
                    "edgecolor": "#f59e0b",
                    "textcolor": "#92400e",
                    "fontsize": 8,
                }
            ))

    # Robots
    for r in frame.get("robots", []):
        rid = r["id"]
        loc = r.get("location")
        if loc not in pos:
            continue
        rx, ry = pos[loc]
        color = ROBOT_COLORS[rid % len(ROBOT_COLORS)]

        # Robot marker: triangle with crisp white outline
        ax.plot(rx, ry, marker="^", markersize=14, color=color, markeredgecolor="#ffffff", markeredgewidth=2.2, zorder=10)
        label_anchors.append((
            rx, ry, f"R{rid}", "robot",
            {
                "facecolor": color,
                "edgecolor": "#ffffff",
                "textcolor": "#ffffff",
                "fontsize": 8,
            }
        ))

    # Collision-avoidance placement of labels
    staggered_labels = _stagger_labels(label_anchors, span_x, span_y)
    for lx, ly, text_val, kind, style in staggered_labels:
        ax.text(
            lx, ly, text_val,
            color=style["textcolor"],
            fontsize=style["fontsize"],
            fontweight="bold",
            ha="center", va="center",
            zorder=12,
            bbox=dict(
                boxstyle="round,pad=0.2",
                facecolor=style["facecolor"],
                edgecolor=style["edgecolor"],
                alpha=0.95,
                linewidth=1.0,
            ),
        )

    # 6. Single-Row Legend Below Map (never over data)
    legend_elements = [
        Line2D([0], [0], marker="^", color="w", label="Robot", markerfacecolor="#2563eb", markersize=9, markeredgecolor="#ffffff"),
        Line2D([0], [0], marker="*", color="w", label="Pending Task", markerfacecolor="#f59e0b", markersize=10, markeredgecolor="#b45309"),
        Line2D([0], [0], marker="o", color="w", label="Completed Task", markerfacecolor="#10b981", markersize=7, markeredgecolor="#ffffff"),
        Line2D([0], [0], color="#dc2626", lw=2.8, label="Blocked Edge"),
    ]
    if show_work_zones and wz_to_draw:
        legend_elements.append(
            Line2D([0], [0], color="#f59e0b", lw=1.2, alpha=0.6, label="Work Zone (Permitted)")
        )
    if detour_edges:
        legend_elements.append(
            Line2D([0], [0], color="#0284c7", lw=2.2, linestyle=":", label="Local Detour (0 msgs)")
        )

    leg = ax.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.03),
        ncol=len(legend_elements),
        facecolor="#182236",
        edgecolor="#475569",
        labelcolor="#f1f5f9",
        fontsize=8.5,
        framealpha=0.98,
        columnspacing=1.2,
        handletextpad=0.4,
    )
    leg.set_zorder(15)

    # Note: Axes title is deliberately omitted here so title is OUTSIDE the axes in the UI
    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.08)
    return fig
