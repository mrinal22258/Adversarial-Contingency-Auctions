"""
Callback handlers and telemetry computation for ACA Mission Control interface.
"""

import os
import sys
import json
import tempfile
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import gradio as gr

from acalib.demo.provenance import get_map_provenance, format_provenance_markdown
from acalib.demo.render import plot_simulation_state, get_boston_work_zone_edges
from acalib.demo.narrate import (
    generate_event_log,
    format_event_log_html,
    generate_what_happened_narrative,
)
from acalib.demo.runner import (
    get_cached_run,
    run_single_simulation,
    run_paired_comparison,
    get_paper_aggregate_comparison,
    run_20_seeds_paired,
    diagnose_task_failures,
    METHOD_NAME_MAP,
    ADVERSARY_NAME_MAP,
    parse_allocator_name,
    parse_adversary_name,
    DEFAULT_MAX_STEPS,
)

# Active spatial graph and layout cache
CURRENT_MISSION_GRAPH = {
    "graph": None,
    "pos": None,
    "fam": None,
    "variant": None,
}

MAP_OPTIONS = {
    "Boston Downtown (OSMnx road network, 216 nodes)": ("road_osmnx", 216, "none"),
    "MovingAI Warehouse 10-20-10-2-1 (real MAPF benchmark)": ("warehouse_movingai", 38, "10-20-10-2-1"),
    "MovingAI Warehouse 20-40-10-2-1 (real MAPF benchmark)": ("warehouse_movingai", 125, "20-40-10-2-1"),
}

ALLOCATOR_OPTIONS = list(METHOD_NAME_MAP.values())
ADVERSARY_OPTIONS = list(ADVERSARY_NAME_MAP.values())

COMM_REGIMES = {
    "benign (50m, 2% loss)": (50.0, 0.02),
    "constrained (25m, 15% loss)": (25.0, 0.15),
    "lossy (20m, 30% loss)": (20.0, 0.30),
}


def create_empty_comparison_plot():
    """Placeholder figure for the comparison tab before a run is executed."""
    fig, ax = plt.subplots(figsize=(9.5, 3.8), dpi=100)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")
    ax.text(
        0.5, 0.5,
        "Click 'Run Paired Comparison' to generate visual benchmark",
        ha="center", va="center", transform=ax.transAxes,
        fontsize=12, color="#64748b", fontweight="500",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#e2e8f0")
    return fig


def get_metrics_table(history: list, tick_idx: int) -> pd.DataFrame:
    """Extract metrics table at specific tick."""
    if not history or tick_idx >= len(history):
        return pd.DataFrame()

    frame = history[tick_idx]
    total_tasks = len(frame.get("tasks", []))
    completed = frame.get("completed_tasks", 0)
    pct = (completed / max(1, total_tasks)) * 100.0

    data = {
        "Metric": [
            "Completed Tasks",
            "Completion Rate",
            "Cumulative Conflicts",
            "Total Messages",
            "Total Travel Distance",
            "Cumulative Net Welfare",
            "Safe Claims Admitted",
            "Claims Deferred to Consensus",
            "Re-Auctions Triggered",
        ],
        "Value": [
            f"{completed} / {total_tasks}",
            f"{pct:.1f}%",
            str(frame.get("conflicts", 0)),
            str(frame.get("messages", 0)),
            f"{frame.get('travel', 0.0):.1f}",
            f"{frame.get('welfare', 0.0):.1f}",
            str(frame.get("safe_claims", 0)),
            str(frame.get("deferred_claims", 0)),
            str(frame.get("reauction_events", 0)),
        ]
    }
    df = pd.DataFrame(data)
    df["Simulation Metric"] = df["Metric"]
    return df


def run_simulation_wrapper(
    num_robots: int = 4,
    num_tasks: int = 15,
    graph_family: str = "road_osmnx",
    num_nodes: int = 216,
    adversary_str: str = "Reactive",
    allocator_str: str = "ACA (Ours)",
    random_seed: int = 10001,
    comm_regime: str = "benign",
    comm_range: float = 50.0,
    p_drop: float = 0.02,
    max_steps: int = DEFAULT_MAX_STEPS,
    contingency_depth: int = 1,
    variant: str = "10-20-10-2-1",
):
    """Backwards-compatible wrapper matching test expectations."""
    fam = graph_family.lower()
    if fam in ("rgg", "er", "warehouse", "grid"):
        fam = "warehouse_movingai"
        num_nodes = 38

    run_res = get_cached_run(
        graph_family=fam,
        n_nodes=int(num_nodes),
        adversary_str=adversary_str,
        allocator_str=allocator_str,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=int(num_robots),
        n_tasks=int(num_tasks),
        seed=int(random_seed),
        max_steps=int(max_steps),
        contingency_depth=contingency_depth,
        variant=variant,
    )
    return run_res["history"], run_res["graph"], run_res["pos"]


def update_map_choice(map_choice):
    """Update map dropdown choice, coarsening visibility, and provenance card."""
    fam, n_nodes, variant = MAP_OPTIONS[map_choice]
    if "warehouse" in fam:
        if "20-40" in variant:
            coarsen_choices = ["~125 nodes (B=8)", "~208 nodes (B=10)", "~1,681 nodes (B=4) (slow: ~15s)"]
            default_coarsen = "~125 nodes (B=8)"
        else:
            coarsen_choices = ["~38 nodes (B=8)", "~56 nodes (B=10)", "~420 nodes (B=4)"]
            default_coarsen = "~38 nodes (B=8)"
        coarsen_vis = True
        prov_md = format_provenance_markdown(get_map_provenance(fam, n_nodes, variant))
    else:
        coarsen_choices = ["216 nodes"]
        default_coarsen = "216 nodes"
        coarsen_vis = False
        prov_md = format_provenance_markdown(get_map_provenance("road_osmnx", 216))

    return (
        gr.Radio(choices=coarsen_choices, value=default_coarsen, visible=coarsen_vis),
        prov_md,
    )


def update_alloc_choice(alloc_choice):
    """Display UI note for ablation identity."""
    if alloc_choice == "ACA (Depth-2)":
        note = "Depth-2 is identical to ACA on these graphs because single-level contingency recourse branches bypass primary corridor interdictions, and recursive detours saturate on these horizons and topologies."
        return gr.Markdown(value=note, visible=True)
    elif alloc_choice == "ACA-Adaptive (Entropy Calibrated)":
        note = "ACA-Adaptive automatically calibrates the Pinsker margin scaling factor based on Dirichlet entropy of the adversary belief distribution."
        return gr.Markdown(value=note, visible=True)
    elif alloc_choice == "ACA+ (Adaptive + Corridor Pruning)":
        note = "ACA+ combines entropy-calibrated adaptive margin with Bayesian corridor probability pruning (pruning threshold = 0.06)."
        return gr.Markdown(value=note, visible=True)
    return gr.Markdown(value="", visible=False)


def run_sim_action(
    map_choice, coarsen_choice, work_zones_active,
    robots, tasks, adv_choice, alloc_choice,
    max_steps, comm_regime, comm_range, p_drop,
    depth, seed,
    progress=gr.Progress(track_tqdm=False),
):
    fam, n_nodes, variant = MAP_OPTIONS[map_choice]
    if "warehouse" in fam:
        if "125" in coarsen_choice:
            n_nodes = 125
        elif "208" in coarsen_choice:
            n_nodes = 208
        elif "1,681" in coarsen_choice:
            n_nodes = 1681
        elif "38" in coarsen_choice:
            n_nodes = 38
        elif "56" in coarsen_choice:
            n_nodes = 56
        elif "420" in coarsen_choice:
            n_nodes = 420

    progress(0.2, desc="Executing Discrete Multi-Agent Simulation...")
    run_res = run_single_simulation(
        graph_family=fam,
        n_nodes=int(n_nodes),
        adversary_str=adv_choice,
        allocator_str=alloc_choice,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=int(robots),
        n_tasks=int(tasks),
        seed=int(seed),
        max_steps=int(max_steps),
        contingency_depth=int(depth),
        variant=variant,
        record_history=True,
    )
    progress(0.85, desc="Rendering Spatial Canvas & Telemetry...")

    history = run_res["history"]
    graph = run_res["graph"]
    pos = run_res["pos"]
    summary = run_res["summary"]

    CURRENT_MISSION_GRAPH["graph"] = graph
    CURRENT_MISSION_GRAPH["pos"] = pos
    CURRENT_MISSION_GRAPH["fam"] = fam
    CURRENT_MISSION_GRAPH["variant"] = variant

    final_tick_idx = len(history) - 1
    final_frame = history[final_tick_idx]

    # Generate events
    events = generate_event_log(history)
    events_html = format_event_log_html(events, active_tick=final_tick_idx + 1, filter_category="All")

    # Quantitative narrative & task failures
    env_info = {
        "map_name": map_choice.split("(")[0].strip(),
        "adversary_name": adv_choice,
        "allocator_name": alloc_choice,
        "family": fam,
        "variant": variant,
        "n_nodes": n_nodes,
    }
    narrative = generate_what_happened_narrative(summary, history, env_info)
    failures_df = diagnose_task_failures(run_res)

    # Render plot at FINAL tick
    progress(0.9, desc="Rendering spatial canvas...")
    fig = plot_simulation_state(
        history, graph, pos, final_tick_idx,
        graph_family=fam, variant=variant,
        show_work_zones=work_zones_active,
    )

    # Build KPI HTML strings
    completed = final_frame.get("completed_tasks", 0)
    total_t = len(final_frame.get("tasks", []))
    pct = (completed / max(1, total_t)) * 100.0
    confs = final_frame.get("conflicts", 0)
    msgs = final_frame.get("messages", 0)
    trav = final_frame.get("travel", 0.0)
    blks = len(final_frame.get("blocked_edges", []))
    active_detours = len(final_frame.get("active_detours", []))
    cum_detours = sum(1 for ev in events if ev.get("category") == "Detour")

    kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
    kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
    kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
    kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
    kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
    kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
    kpi_detr_h = (
        f"<div class='kpi-card' title='Active detour routes executing right now: {active_detours} | Cumulative local detour activations across mission history: {cum_detours}'>"
        f"<div class='kpi-val'>{active_detours} <span class='kpi-sub'>({cum_detours} cum)</span></div>"
        f"<div class='kpi-lbl'>Detours (Act/Cum)</div>"
        f"</div>"
    )

    outcome_sent = f"Run Result: {completed}/{total_t} tasks completed in {len(history)} steps, {confs} conflicts, {msgs} messages, {blks} active blockages, {active_detours} active detours ({cum_detours} cumulative activations)."
    banner_vis = gr.Row(visible=True)
    banner_txt = outcome_sent

    title_md = f"### Spatial Telemetry View — Tick {final_tick_idx + 1} of {len(history)} ({completed}/{total_t} Tasks Completed)"

    alloc_code = parse_allocator_name(alloc_choice)
    repro_md = f"""### Exact Reproduction Command
- **Environment:** `{fam}` ({n_nodes} nodes, variant `{variant}`)
- **Fleet & Tasks:** {robots} robots, {tasks} tasks
- **Adversary Profile:** `{adv_choice}`
- **Allocator Mechanism:** `{alloc_choice}` (`{alloc_code}`)
- **Random Seed (CRN):** `{int(seed)}`
- **Mission Horizon:** `{len(history)}` ticks
- **Communication Regime:** `{comm_regime}` (range: {comm_range}m, drop rate: {p_drop})

**Exact CLI Reproduction Command:**
```bash
python -c "from acalib.demo.runner import run_single_simulation; res = run_single_simulation('{fam}', {n_nodes}, '{adv_choice}', '{alloc_code}', seed={int(seed)}, n_robots={int(robots)}, n_tasks={int(tasks)}, max_steps={len(history)}); print('Tasks Completed:', res['summary']['completed_tasks'], '/', res['summary']['total_tasks'], '| Net Welfare:', round(res['summary']['net_welfare'], 2))"
```
"""

    scrubber_upd = gr.Slider(maximum=len(history), value=len(history), step=1)
    telemetry_df = get_metrics_table(history, final_tick_idx)

    progress(1.0, desc="Simulation complete.")
    return (
        history, events, env_info, summary,
        fig, title_md, banner_vis, banner_txt,
        kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
        scrubber_upd, events_html, telemetry_df,
        narrative, failures_df, repro_md,
    )


def replay_from_start(history, env_info, work_zones_active):
    """Jump back to tick 1."""
    if not history:
        return gr.Slider(value=1), None, "", "", "", "", "", "", "", ""
    tick_idx = 0
    graph = CURRENT_MISSION_GRAPH["graph"]
    pos = CURRENT_MISSION_GRAPH["pos"]
    fam = env_info.get("family", "road_osmnx")
    variant = env_info.get("variant", "none")

    fig = plot_simulation_state(
        history, graph, pos, tick_idx,
        graph_family=fam, variant=variant,
        show_work_zones=work_zones_active,
    )
    final_frame = history[tick_idx]
    completed = final_frame.get("completed_tasks", 0)
    total_t = len(final_frame.get("tasks", []))
    pct = (completed / max(1, total_t)) * 100.0
    confs = final_frame.get("conflicts", 0)
    msgs = final_frame.get("messages", 0)
    trav = final_frame.get("travel", 0.0)
    blks = len(final_frame.get("blocked_edges", []))
    active_detours = len(final_frame.get("active_detours", []))
    cum_detours = 0

    kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
    kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
    kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
    kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
    kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
    kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
    kpi_detr_h = (
        f"<div class='kpi-card' title='Active detour routes executing right now: {active_detours} | Cumulative local detour activations across mission history: {cum_detours}'>"
        f"<div class='kpi-val'>{active_detours} <span class='kpi-sub'>({cum_detours} cum)</span></div>"
        f"<div class='kpi-lbl'>Detours (Act/Cum)</div>"
        f"</div>"
    )

    title_md = f"### Spatial Telemetry View — Tick 1 of {len(history)}"
    return (
        gr.Slider(value=1), fig, title_md,
        kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
    )


def scrub_action(tick, history, events, filter_category, env_info, work_zones_active):
    """Scrub to a specific simulation tick."""
    if not history:
        return None, "", "", "", "", "", "", "", "", "", pd.DataFrame()
    tick_idx = max(0, min(len(history) - 1, int(tick) - 1))
    graph = CURRENT_MISSION_GRAPH["graph"]
    pos = CURRENT_MISSION_GRAPH["pos"]
    fam = env_info.get("family", "road_osmnx")
    variant = env_info.get("variant", "none")

    fig = plot_simulation_state(
        history, graph, pos, tick_idx,
        graph_family=fam, variant=variant,
        show_work_zones=work_zones_active,
    )
    final_frame = history[tick_idx]
    completed = final_frame.get("completed_tasks", 0)
    total_t = len(final_frame.get("tasks", []))
    pct = (completed / max(1, total_t)) * 100.0
    confs = final_frame.get("conflicts", 0)
    msgs = final_frame.get("messages", 0)
    trav = final_frame.get("travel", 0.0)
    blks = len(final_frame.get("blocked_edges", []))
    active_detours = len(final_frame.get("active_detours", []))
    cum_detours = sum(1 for ev in (events or []) if ev.get("category") == "Detour" and ev.get("tick", 0) <= tick_idx + 1)

    kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
    kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
    kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
    kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
    kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
    kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
    kpi_detr_h = (
        f"<div class='kpi-card' title='Active detour routes executing right now: {active_detours} | Cumulative local detour activations through tick {tick_idx + 1}: {cum_detours}'>"
        f"<div class='kpi-val'>{active_detours} <span class='kpi-sub'>({cum_detours} cum)</span></div>"
        f"<div class='kpi-lbl'>Detours (Act/Cum)</div>"
        f"</div>"
    )

    title_md = f"### Spatial Telemetry View — Tick {tick_idx + 1} of {len(history)}"
    events_html = format_event_log_html(events, active_tick=tick_idx + 1, filter_category=filter_category)
    telemetry_df = get_metrics_table(history, tick_idx)

    return (
        fig, title_md,
        kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
        events_html, telemetry_df,
    )


def step_tick(delta, current_tick, history_len):
    if history_len <= 0:
        return 1
    new_tick = max(1, min(history_len, int(current_tick) + delta))
    return new_tick


def run_compare_action(
    map_choice, coarsen_choice, robots, tasks, adv_choice, alloc_choice,
    max_steps, comm_regime, comm_range, p_drop, depth, seed,
    progress=gr.Progress(track_tqdm=False),
):
    fam, n_nodes, variant = MAP_OPTIONS[map_choice]
    if "warehouse" in fam:
        if "125" in coarsen_choice:
            n_nodes = 125
        elif "208" in coarsen_choice:
            n_nodes = 208
        elif "1,681" in coarsen_choice:
            n_nodes = 1681
        elif "38" in coarsen_choice:
            n_nodes = 38
        elif "56" in coarsen_choice:
            n_nodes = 56
        elif "420" in coarsen_choice:
            n_nodes = 420

    progress(0.1, desc="Running paired simulation...")
    paired_res = run_paired_comparison(
        graph_family=fam,
        n_nodes=int(n_nodes),
        adversary_str=adv_choice,
        selected_allocator_str=alloc_choice,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=int(robots),
        n_tasks=int(tasks),
        seed=int(seed),
        max_steps=int(max_steps),
        contingency_depth=int(depth),
        variant=variant,
    )
    progress(0.8, desc="Compiling comparison table...")

    s_main = paired_res["selected"]["summary"]
    s_cblr = paired_res["cbba_partial_lr"]["summary"]
    s_cb = paired_res["cbba"]["summary"]
    s_ctp = paired_res["ctp_replan"]["summary"]

    comp_df = pd.DataFrame({
        "Metric": [
            "Completion Rate (%)",
            "Completed Tasks",
            "Cumulative Conflicts",
            "Total Messages",
            "Total Travel Distance",
            "Net Welfare",
        ],
        f"Selected ({alloc_choice})": [
            f"{s_main['completion_rate_pct']:.1f}%",
            f"{s_main['completed_tasks']}/{s_main['total_tasks']}",
            str(s_main["total_conflicts"]),
            str(s_main["total_messages"]),
            f"{s_main['total_travel_distance']:.1f}",
            f"{s_main['net_welfare']:.1f}",
        ],
        "CBBA-PR (+LR)": [
            f"{s_cblr['completion_rate_pct']:.1f}%",
            f"{s_cblr['completed_tasks']}/{s_cblr['total_tasks']}",
            str(s_cblr["total_conflicts"]),
            str(s_cblr["total_messages"]),
            f"{s_cblr['total_travel_distance']:.1f}",
            f"{s_cblr['net_welfare']:.1f}",
        ],
        "CBBA (Plain)": [
            f"{s_cb['completion_rate_pct']:.1f}%",
            f"{s_cb['completed_tasks']}/{s_cb['total_tasks']}",
            str(s_cb["total_conflicts"]),
            str(s_cb["total_messages"]),
            f"{s_cb['total_travel_distance']:.1f}",
            f"{s_cb['net_welfare']:.1f}",
        ],
        "CTP Replan": [
            f"{s_ctp['completion_rate_pct']:.1f}%",
            f"{s_ctp['completed_tasks']}/{s_ctp['total_tasks']}",
            str(s_ctp["total_conflicts"]),
            str(s_ctp["total_messages"]),
            f"{s_ctp['total_travel_distance']:.1f}",
            f"{s_ctp['net_welfare']:.1f}",
        ],
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.8), dpi=100)
    fig.patch.set_facecolor("#ffffff")

    short_alloc = alloc_choice.replace(" (Ours)", "").replace("Adversarial Contingency Auctions", "ACA")
    methods = [short_alloc, "CBBA-PR+LR", "CBBA", "CTP Replan"]
    comps = [
        s_main["completion_rate_pct"],
        s_cblr["completion_rate_pct"],
        s_cb["completion_rate_pct"],
        s_ctp["completion_rate_pct"],
    ]
    msgs = [
        s_main["total_messages"],
        s_cblr["total_messages"],
        s_cb["total_messages"],
        s_ctp["total_messages"],
    ]
    colors = ["#4f46e5", "#0284c7", "#64748b", "#059669"]

    ax1.set_facecolor("#f8fafc")
    ax1.grid(axis="y", linestyle="--", alpha=0.4, color="#cbd5e1")
    ax1.set_axisbelow(True)
    bars1 = ax1.bar(methods, comps, color=colors, width=0.52, edgecolor="#ffffff", linewidth=1.5)
    ax1.set_ylabel("Completion Rate (%)", fontsize=10, fontweight="600", color="#334155")
    ax1.set_title("Task Completion Rate", fontsize=11, fontweight="700", color="#0f172a", pad=8)
    ax1.set_ylim(0, 115)
    for bar in bars1:
        h = bar.get_height()
        ax1.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color="#1e293b")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color("#cbd5e1")
    ax1.spines["bottom"].set_color("#cbd5e1")
    ax1.tick_params(axis="x", labelsize=9.5)

    ax2.set_facecolor("#f8fafc")
    ax2.grid(axis="y", linestyle="--", alpha=0.4, color="#cbd5e1")
    ax2.set_axisbelow(True)
    bars2 = ax2.bar(methods, msgs, color=colors, width=0.52, edgecolor="#ffffff", linewidth=1.5)
    ax2.set_ylabel("Total Messages Sent", fontsize=10, fontweight="600", color="#334155")
    ax2.set_title("Decentralized Communication", fontsize=11, fontweight="700", color="#0f172a", pad=8)
    max_m = max(msgs) if msgs else 100
    ax2.set_ylim(0, max_m * 1.18 + 10)
    for bar in bars2:
        h = bar.get_height()
        ax2.annotate(f"{int(h)}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color="#1e293b")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color("#cbd5e1")
    ax2.spines["bottom"].set_color("#cbd5e1")
    ax2.tick_params(axis="x", labelsize=9.5)

    plt.subplots_adjust(bottom=0.18, top=0.88, left=0.09, right=0.96, wspace=0.28)

    paper_df = get_paper_aggregate_comparison(fam, variant=variant)
    if paper_df is None:
        p_table = pd.DataFrame()
        p_note = "No pre-registered aggregate for this map"
    else:
        p_table = paper_df
        p_note = "Pre-registered empirical aggregate (n=50 seeds) from results/stats/instance_aggregated.csv"

    progress(1.0, desc="Comparison complete.")
    return comp_df, fig, p_table, p_note


def run_20_seeds_action(
    map_choice, coarsen_choice, robots, tasks, adv_choice, alloc_choice,
    max_steps, comm_regime, comm_range, p_drop, seed,
    progress=gr.Progress(track_tqdm=False),
):
    fam, n_nodes, variant = MAP_OPTIONS[map_choice]
    if "warehouse" in fam:
        if "125" in coarsen_choice:
            n_nodes = 125
        elif "208" in coarsen_choice:
            n_nodes = 208
        elif "1,681" in coarsen_choice:
            n_nodes = 1681
        elif "38" in coarsen_choice:
            n_nodes = 38
        elif "56" in coarsen_choice:
            n_nodes = 56
        elif "420" in coarsen_choice:
            n_nodes = 420

    base_seed = int(seed)
    seeds = [base_seed + i for i in range(20)]
    progress(0.05, desc="Executing 20-seed Monte Carlo sweep...")

    df_20 = run_20_seeds_paired(
        graph_family=fam,
        n_nodes=int(n_nodes),
        adversary_str=adv_choice,
        selected_allocator_str=alloc_choice,
        seeds=seeds,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=int(robots),
        n_tasks=int(tasks),
        max_steps=int(max_steps),
        variant=variant,
    )
    progress(0.85, desc="Computing bootstrap confidence intervals...")

    # Plot performance distributions across 20 seeds
    fig, ax = plt.subplots(figsize=(9.5, 3.8), dpi=100)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.set_axisbelow(True)

    summary_rows = []
    methods = df_20["Method"].unique()
    colors = {"ACA": "#4f46e5", "CBBA-PR+LR": "#0284c7", "CBBA": "#64748b", "CTP Replan": "#059669"}

    for m in methods:
        sub = df_20[df_20["Method"] == m]
        vals = sub["Completion (%)"].values
        mean_v = float(np.mean(vals))
        std_v = float(np.std(vals))
        summary_rows.append({
            "Method": m,
            "Mean Completion (%)": f"{mean_v:.1f}%",
            "Std Dev (%)": f"{std_v:.1f}%",
            "Mean Conflicts": f"{sub['Conflicts'].mean():.1f}",
            "Mean Messages": f"{sub['Messages'].mean():.0f}",
            "Mean Net Welfare": f"{sub['Net Welfare'].mean():.1f}",
        })

    summary_df = pd.DataFrame(summary_rows)

    box_data = [df_20[df_20["Method"] == m]["Completion (%)"].values for m in methods]
    bp = ax.boxplot(box_data, patch_artist=True, labels=methods, widths=0.45)
    for patch, m in zip(bp["boxes"], methods):
        color = colors.get(m, "#4f46e5")
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    for median in bp["medians"]:
        median.set_color("#0f172a")
        median.set_linewidth(2)

    ax.set_ylabel("Completion Rate (%)", fontsize=10, fontweight="600", color="#334155")
    ax.set_title("20-Seed Monte Carlo Completion Rate Distribution", fontsize=11, fontweight="700", color="#0f172a", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    plt.subplots_adjust(bottom=0.15, top=0.88, left=0.08, right=0.96)

    progress(1.0, desc="Monte Carlo evaluation complete.")
    return summary_df, fig


def export_json_action(history, summary, env_meta):
    """Export run history and metadata as downloadable JSON."""
    if not history:
        return None
    export_payload = {
        "metadata": env_meta,
        "summary": summary,
        "history": history,
    }
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
    json.dump(export_payload, tmp, indent=2)
    tmp.close()
    return tmp.name


def export_csv_action(history):
    """Export step-by-step telemetry as downloadable CSV."""
    if not history:
        return None
    rows = []
    for step in history:
        rows.append({
            "tick": step.get("tick", 0),
            "completed_tasks": step.get("completed_tasks", 0),
            "conflicts": step.get("conflicts", 0),
            "messages": step.get("messages", 0),
            "travel": step.get("travel", 0.0),
            "welfare": step.get("welfare", 0.0),
            "safe_claims": step.get("safe_claims", 0),
            "deferred_claims": step.get("deferred_claims", 0),
            "reauction_events": step.get("reauction_events", 0),
        })
    df = pd.DataFrame(rows)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
    df.to_csv(tmp.name, index=False)
    tmp.close()
    return tmp.name
