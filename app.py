"""
Adversarial Contingency Auctions (ACA) — Mission Control Explorer.
Interactive web application built with Gradio and powered by acalib.
Runs ONLY on real environments (OSMnx Boston road network & MovingAI MAPF benchmark warehouse).
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import gradio as gr

# Ensure workspace root is in sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

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

# Global tracking for active mission spatial graph and coordinates
CURRENT_MISSION_GRAPH = {
    "graph": None,
    "pos": None,
    "fam": None,
    "variant": None,
}

# Offline Mission Control CSS: Calm, intentional, indigo accent, system fonts, zero emoji
MISSION_CONTROL_CSS = """
:root {
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    --indigo-50: #eef2ff;
    --indigo-100: #e0e7ff;
    --indigo-600: #4f46e5;
    --indigo-700: #4338ca;
    --slate-50: #f8fafc;
    --slate-100: #f1f5f9;
    --slate-200: #e2e8f0;
    --slate-600: #475569;
    --slate-700: #334155;
    --slate-800: #1e293b;
    --slate-900: #0f172a;
}

body, .gradio-container {
    font-family: var(--font-sans) !important;
    background-color: #f8fafc !important;
    color: var(--slate-900) !important;
    max-height: 1600px !important;
}

/* Tab Bar Styling: Fit in 1 row at 1440px, graceful wrap at 1024px and mobile, no overflow dots */
.tab-nav, div[role="tablist"], .tab-wrapper, .tab-container:not(.visually-hidden) {
    display: flex !important;
    flex-wrap: wrap !important;
    overflow: visible !important;
    max-width: 100% !important;
    gap: 4px !important;
    border-bottom: 2px solid var(--slate-200) !important;
    background: transparent !important;
}

div[role="tablist"] > button, .tab-nav button, .tab-wrapper button, .tab-container button, .tabs button {
    display: inline-flex !important;
    font-family: var(--font-sans) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.02em !important;
    padding: 5px 8px !important;
    white-space: nowrap !important;
    color: var(--slate-600) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    transition: all 0.15s ease !important;
}

@media (max-width: 480px) {
    div[role="tablist"] > button, .tab-nav button, .tab-wrapper button, .tab-container button, .tabs button {
        font-size: 8.5px !important;
        padding: 3px 4px !important;
        letter-spacing: 0 !important;
    }
}

div[role="tablist"] > button.selected, .tab-nav button.selected, .tab-container button.selected, .tabs button.selected {
    color: var(--indigo-600) !important;
    border-bottom: 2px solid var(--indigo-600) !important;
    background: #ffffff !important;
}

.tab-wrapper > div {
    display: flex !important;
    flex-wrap: wrap !important;
    overflow: visible !important;
}

/* Remove yellow chips: Override Gradio label CSS to plain small-caps gray */
.gradio-container label,
.gradio-container .block label,
.gradio-container .block > span,
.gradio-container .form > label {
    font-family: var(--font-sans) !important;
    text-transform: uppercase !important;
    font-size: 11px !important;
    letter-spacing: 0.05em !important;
    font-weight: 600 !important;
    color: var(--slate-600) !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Primary Button: Solid Indigo */
.btn-indigo-primary {
    background: var(--indigo-600) !important;
    color: #ffffff !important;
    border: 1px solid var(--indigo-700) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    transition: background-color 0.15s ease !important;
}

.btn-indigo-primary:hover {
    background: var(--indigo-700) !important;
}

/* Secondary Button: Outlined Indigo */
.btn-indigo-outline {
    background: #ffffff !important;
    color: var(--indigo-600) !important;
    border: 1.5px solid var(--indigo-600) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border-radius: 6px !important;
    padding: 7px 14px !important;
    transition: all 0.15s ease !important;
}

.btn-indigo-outline:hover {
    background: var(--indigo-50) !important;
}

/* Subtle Control Buttons */
.btn-control {
    background: #ffffff !important;
    color: var(--slate-700) !important;
    border: 1px solid var(--slate-200) !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    border-radius: 6px !important;
}

.btn-control:hover {
    background: var(--slate-100) !important;
}

/* KPI Strip: 7 Equal Cards, Single-Line, Tabular Numbers Mono */
.kpi-row {
    display: flex !important;
    gap: 8px !important;
    width: 100% !important;
    margin-bottom: 12px !important;
}

.kpi-row > div {
    flex: 1 1 0px !important;
    min-width: 0 !important;
}

.kpi-card {
    height: 100% !important;
    min-width: 0 !important;
    background: #ffffff !important;
    border: 1px solid var(--slate-200) !important;
    border-top: 2.5px solid var(--indigo-600) !important;
    border-radius: 8px !important;
    padding: 8px 6px !important;
    text-align: center !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}

.kpi-val {
    font-family: var(--font-mono) !important;
    font-variant-numeric: tabular-nums !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    color: var(--slate-900) !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

.kpi-lbl {
    font-family: var(--font-sans) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: var(--slate-600) !important;
    margin-top: 2px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* Run Result Banner */
.result-banner {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-left: 4px solid var(--indigo-600);
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.result-sentence {
    font-size: 13px;
    font-weight: 600;
    color: var(--slate-800);
}

/* Status Badges with Dual Encoding (Icon + Text) */
.badge-tag {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    padding: 3px 8px !important;
    border-radius: 4px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-right: 6px !important;
    vertical-align: middle !important;
}

.badge-real {
    background: #e0f2fe !important;
    color: #0369a1 !important;
    border: 1px solid #bae6fd !important;
}

.badge-sim {
    background: #f1f5f9 !important;
    color: #475569 !important;
    border: 1px solid #cbd5e1 !important;
}

.badge-verified {
    background: #ecfdf5 !important;
    color: #047857 !important;
    border: 1px solid #a7f3d0 !important;
}

.badge-active {
    background: #ecfdf5 !important;
    color: #059669 !important;
    border: 1px solid #6ee7b7 !important;
}

.badge-idle {
    background: #f8fafc !important;
    color: #64748b !important;
    border: 1px solid #cbd5e1 !important;
}

.badge-blocked {
    background: #fef2f2 !important;
    color: #b91c1c !important;
    border: 1px solid #fecaca !important;
}

.badge-contingency {
    background: #fffbeb !important;
    color: #b45309 !important;
    border: 1px solid #fde68a !important;
}

/* Accessible focus visible outlines */
button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 2px solid var(--indigo-600) !important;
    outline-offset: 2px !important;
}

/* Responsive Grid adjustments */
@media (max-width: 1024px) {
    .kpi-row {
        flex-wrap: wrap !important;
    }
    .kpi-row > div {
        flex: 1 1 30% !important;
    }
}

@media (max-width: 640px) {
    .kpi-row > div {
        flex: 1 1 45% !important;
    }
}
"""

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


def build_app():
    """Construct Mission Control Blocks user interface."""
    with gr.Blocks(title="Adversarial Contingency Auctions — Mission Control") as demo:
        demo.css = MISSION_CONTROL_CSS
        # In-memory session state
        history_state = gr.State([])
        events_state = gr.State([])
        env_meta_state = gr.State({
            "map_name": "Boston Downtown",
            "adversary_name": "Reactive",
            "allocator_name": "ACA (Ours)",
            "family": "road_osmnx",
            "variant": "none",
            "n_nodes": 216,
        })
        summary_state = gr.State({})

        # Top Header (Calm, no emoji, accessible dual-coded status)
        gr.Markdown(
            """
            # Adversarial Contingency Auctions (ACA) — Mission Control
            > **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**  
            <span class="badge-tag badge-real">[✓] Real Map Topologies Only</span>
            <span class="badge-tag badge-sim">[●] Discrete Event & Physics Simulation</span>
            <span class="badge-tag badge-verified">[🔒] SHA-256 Provenance Verified</span>
            """
        )

        with gr.Row():
            # ================= LEFT PANEL: CONTROL DRAWER =================
            with gr.Column(scale=4):
                with gr.Accordion("1. Environment Topology", open=True):
                    map_dropdown = gr.Dropdown(
                        choices=list(MAP_OPTIONS.keys()),
                        value="Boston Downtown (OSMnx road network, 216 nodes)",
                        label="Navigation Map",
                    )
                    coarsen_radio = gr.Radio(
                        choices=["~38 nodes (B=8)", "~56 nodes (B=10)", "~420 nodes (B=4)"],
                        value="~38 nodes (B=8)",
                        label="Grid Coarsening",
                        visible=False,
                    )
                    work_zones_toggle = gr.Checkbox(
                        label="Show real work zones (Boston DPW)",
                        value=False,
                    )
                    prov_card = gr.Markdown(
                        value=format_provenance_markdown(get_map_provenance("road_osmnx", 216))
                    )

                with gr.Accordion("2. Fleet & Tasks", open=True):
                    with gr.Row():
                        robots_slider = gr.Slider(minimum=2, maximum=8, step=1, value=4, label="Robots")
                        tasks_slider = gr.Slider(minimum=5, maximum=30, step=1, value=15, label="Tasks")

                with gr.Accordion("3. Adversary Profile", open=True):
                    adv_dropdown = gr.Dropdown(
                        choices=ADVERSARY_OPTIONS,
                        value="Reactive (Corridor Interdiction)",
                        label="Adversary Type",
                    )

                with gr.Accordion("4. Market Allocation Mechanism", open=True):
                    alloc_dropdown = gr.Dropdown(
                        choices=ALLOCATOR_OPTIONS,
                        value="ACA (Ours)",
                        label="Allocation Mechanism",
                    )
                    ablation_note = gr.Markdown(
                        value="",
                        visible=False,
                    )

                with gr.Accordion("5. Advanced Settings", open=False):
                    max_steps_slider = gr.Slider(minimum=30, maximum=120, step=5, value=DEFAULT_MAX_STEPS, label="Mission Horizon (Ticks)")
                    comm_regime_dropdown = gr.Dropdown(
                        choices=list(COMM_REGIMES.keys()),
                        value="benign (50m, 2% loss)",
                        label="Wireless Regime Preset",
                    )
                    with gr.Row():
                        comm_range_slider = gr.Slider(minimum=10.0, maximum=100.0, step=5.0, value=50.0, label="Comm Range (m)")
                        p_drop_slider = gr.Slider(minimum=0.0, maximum=0.5, step=0.01, value=0.02, label="Packet Loss (p_drop)")
                    with gr.Row():
                        depth_slider = gr.Slider(minimum=0, maximum=3, step=1, value=1, label="Recourse Depth")
                        seed_number = gr.Number(value=10001, label="Random Seed (CRN)", precision=0)

                with gr.Row():
                    run_btn = gr.Button("Run Simulation", variant="primary", scale=2, elem_classes=["btn-indigo-primary"])
                    compare_btn = gr.Button("Run Paired Comparison", variant="secondary", scale=2, elem_classes=["btn-indigo-outline"])

            # ================= RIGHT PANEL: MISSION CONTROL VIEWPORT =================
            with gr.Column(scale=8):
                # Run Result Banner (Initially hidden until a run concludes)
                with gr.Row(visible=False, elem_classes=["result-banner"]) as run_result_banner:
                    with gr.Column(scale=9):
                        result_sentence_md = gr.Markdown(value="", elem_classes=["result-sentence"])
                    with gr.Column(scale=3):
                        replay_btn = gr.Button("Replay from start", elem_classes=["btn-indigo-outline"], size="sm")

                # KPI Strip: 7 Equal Cards with Single-Line Labels & Tabular Numbers
                with gr.Row(elem_classes=["kpi-row"]):
                    kpi_done = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0 / 15</div><div class='kpi-lbl'>Done</div></div>")
                    kpi_rate = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0.0%</div><div class='kpi-lbl'>Rate</div></div>")
                    kpi_conf = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0</div><div class='kpi-lbl'>Conflicts</div></div>")
                    kpi_msgs = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0</div><div class='kpi-lbl'>Msgs</div></div>")
                    kpi_trav = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0.0</div><div class='kpi-lbl'>Travel</div></div>")
                    kpi_blkd = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0</div><div class='kpi-lbl'>Blocked</div></div>")
                    kpi_detr = gr.Markdown("<div class='kpi-card'><div class='kpi-val'>0</div><div class='kpi-lbl'>Detours</div></div>")

                # Exactly 6 Short Tabs (Fit in 1 row at 1440px, graceful wrap at 1024px)
                with gr.Tabs(elem_id="main-tabs") as tabs:
                    # Tab 1: Telemetry
                    with gr.Tab("Telemetry", id="tab-telemetry"):
                        # Map Title Outside Axes
                        map_title_md = gr.Markdown("### Spatial Telemetry View — Ready to Run")

                        # Spatial Canvas Plot
                        map_plot = gr.Plot(show_label=False)

                        # Playback Controls Bar
                        with gr.Row():
                            step_back_btn = gr.Button("-1", scale=1, elem_classes=["btn-control"])
                            step_fwd_btn = gr.Button("+1", scale=1, elem_classes=["btn-control"])
                            speed_dropdown = gr.Dropdown(choices=["1x (500ms)", "2x (250ms)", "4x (100ms)"], value="2x (250ms)", label="Speed", scale=2)
                            scrubber = gr.Slider(minimum=1, maximum=DEFAULT_MAX_STEPS, step=1, value=1, label="Tick Scrubber", scale=6)
                        with gr.Row():
                            with gr.Column(scale=7):
                                with gr.Row():
                                    event_filter_radio = gr.Radio(
                                        choices=["All", "Adversary", "Allocation", "Conflict", "Task"],
                                        value="All",
                                        label="Filter Events",
                                    )
                                event_log_box = gr.HTML(
                                    value="<div style='height: 360px; padding: 20px; text-align: center; color: #64748b;'>Run simulation to stream event log.</div>"
                                )
                            with gr.Column(scale=5):
                                gr.Markdown("#### Tick State Metrics")
                                telemetry_table = gr.DataFrame(headers=["Metric", "Value"])

                    # Tab 2: Summary
                    with gr.Tab("Summary", id="tab-summary"):
                        what_happened_box = gr.Markdown(value="*Run simulation to generate quantitative breakdown.*")
                        gr.Markdown("#### Why did tasks fail? (Trace Diagnostics)")
                        task_failures_table = gr.DataFrame(headers=["Task ID", "Node", "Reward", "Primary Failure Cause", "Diagnostic Detail"])
                        with gr.Accordion("Reproduce this result (Provenance & Exact Command)", open=True):
                            reproduce_result_md = gr.Markdown(value="*Run simulation to generate exact reproduction command and config.*")

                    # Tab 3: Compare
                    with gr.Tab("Compare", id="tab-compare"):
                        with gr.Row():
                            with gr.Column(scale=9):
                                gr.Markdown("### Paired Benchmark Comparison (Identical Seed & Blockage Streams)")
                            with gr.Column(scale=3):
                                tab_compare_btn = gr.Button("Run Paired Comparison", elem_classes=["btn-indigo-outline"], size="sm")
                        with gr.Row():
                            with gr.Column(scale=6):
                                compare_table = gr.DataFrame(
                                    headers=["Metric", "Selected Method", "CBBA-PR (+LR)", "CBBA [Choi '09]", "CTP Replan"],
                                    show_label=False,
                                    elem_id="compare_table",
                                )
                            with gr.Column(scale=6):
                                compare_chart = gr.Plot(value=create_empty_comparison_plot, show_label=False)

                        gr.Markdown("---")
                        with gr.Row():
                            with gr.Column(scale=6):
                                gr.Markdown("### Multi-Seed Empirical Verification (20 Independent Seeds)")
                                multi_seed_btn = gr.Button("Run 20 Seeds Paired Evaluation", elem_classes=["btn-indigo-outline"])
                                multi_seed_verdict = gr.Markdown(value="*Click above to run 20 paired seeds on this topology.*")
                                multi_seed_table = gr.DataFrame()
                            with gr.Column(scale=6):
                                gr.Markdown("### Pre-Registered Aggregate Benchmark (n=50 Seeds per Family)")
                                paper_table = gr.DataFrame()
                                paper_note = gr.Markdown(value="")

                        with gr.Accordion("Reproduce this benchmark (Provenance & Exact Command)", open=True):
                            reproduce_benchmark_md = gr.Markdown(
                                value="""
                                ### 🔬 Pre-Registered Benchmark Provenance
                                - **Git Commit Hash:** `44d73b0cf1dec8e301e0a43a4961d22dba33a614`
                                - **Confirmatory Manifest:** `results/build_provenance.json`
                                - **Raw Confirmatory Archive:** `results/confirmatory/heldout_results.csv` ($N = 60$ instances, seeds 51–60)
                                - **Aggregate Population:** `results/raw_results.csv` (13,800 trials across 250 instances)

                                **One-Command Held-Out Evaluation:**
                                ```bash
                                python experiments/run_heldout_eval.py
                                ```
                                **Full Reproducible Pipeline:**
                                ```bash
                                make reproduce
                                ```
                                """
                            )

                    # Tab 4: Real SITL
                    with gr.Tab("Real SITL", id="tab-sitl"):
                        gr.Markdown("### Software-In-The-Loop Simulation Evidence (Pure Software, No Physical Hardware)")
                        gr.Markdown(
                            "> **Simulation Scope:** All multi-robot trials, synthetic camera vision (ArUco pose tracking), and differential-drive kinematics are conducted strictly in **PyBullet physics simulation**. No physical hardware or physical robots were used."
                        )

                        with gr.Row():
                            raw_img_path = os.path.join(REPO_ROOT, "results", "sitl", "vision", "sample_raw_frame.png")
                            ann_img_path = os.path.join(REPO_ROOT, "results", "sitl", "vision", "sample_annotated_frame.png")
                            if os.path.exists(raw_img_path):
                                gr.Image(value=raw_img_path, label="Synthetic Camera: Raw Simulation Frame", scale=1)
                            if os.path.exists(ann_img_path):
                                gr.Image(value=ann_img_path, label="Synthetic Camera: ArUco Detected Pose Tracking", scale=1)

                        gr.Markdown("#### Synthetic Vision Tracking Metrics Table (`results/sitl/vision/vision_metrics.json`)")
                        vm_path = os.path.join(REPO_ROOT, "results", "sitl", "vision", "vision_metrics.json")
                        vm_df = pd.DataFrame()
                        if os.path.exists(vm_path):
                            try:
                                with open(vm_path, "r") as f:
                                    vm_data = json.load(f)
                                vm_df = pd.DataFrame([
                                    {"Metric": "Total Frames Analyzed", "Value": str(vm_data.get("total_frames_analyzed", 0))},
                                    {"Metric": "Detection Rate (%)", "Value": f"{vm_data.get('detection_rate_pct', 0.0):.2f}% (95% CI: {vm_data.get('detection_rate_ci_95', [0,0])})"},
                                    {"Metric": "Occlusion Events Encountered", "Value": str(vm_data.get("occlusion_events", 0))},
                                    {"Metric": "Mean Position Error (m)", "Value": f"{vm_data.get('position_error_mean_meters', 0.0):.3f} m (RMSE: {vm_data.get('position_error_rmse_meters', 0.0):.3f} m)"},
                                    {"Metric": "Mean Heading Orientation Error", "Value": f"{vm_data.get('orientation_error_mean_deg', 0.0):.2f}° (CI: {vm_data.get('orientation_error_ci_95_deg', [0,0])})"},
                                ])
                            except Exception:
                                pass
                        gr.DataFrame(value=vm_df)

                        gr.Markdown("#### Software-in-the-Loop Physics Rollouts (Pre-converted H.264)")
                        with gr.Row():
                            b_vid = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_boston_demo_web.mp4")
                            w_vid = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_warehouse_demo_web.mp4")
                            if not os.path.exists(b_vid):
                                b_vid = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_boston_demo.mp4")
                            if not os.path.exists(w_vid):
                                w_vid = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_warehouse_demo.mp4")

                            if os.path.exists(b_vid):
                                with gr.Column():
                                    gr.Video(value=b_vid, label="SITL PyBullet: Boston Downtown Simulation")
                                    with gr.Accordion("Provenance Metadata", open=False):
                                        prov_f = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_boston_demo.provenance.json")
                                        if os.path.exists(prov_f):
                                            gr.JSON(value=json.load(open(prov_f)))
                            if os.path.exists(w_vid):
                                with gr.Column():
                                    gr.Video(value=w_vid, label="SITL PyBullet: Warehouse Simulation")
                                    with gr.Accordion("Provenance Metadata", open=False):
                                        prov_f = os.path.join(REPO_ROOT, "results", "sitl", "videos", "sitl_warehouse_demo.provenance.json")
                                        if os.path.exists(prov_f):
                                            gr.JSON(value=json.load(open(prov_f)))

                    # Tab 5: Method
                    with gr.Tab("Method", id="tab-method"):
                        gr.Markdown(
                            """
                            ### 1. Adversarial Contingency Auctions (ACA)
                            Adversarial Contingency Auctions is a decentralized market-based allocation mechanism designed for multi-robot teams operating in environments subject to strategic, persistent corridor blockages. Rather than bidding single shortest-path deterministic costs, robots compute **expected recourse costs** over a depth-$d$ contingency branching tree weighted by a Bayesian posterior over adversary types.

                            ### 2. Pinsker Belief-Divergence Claim Margin
                            Under decentralized execution without global state synchronization, local beliefs diverge. ACA enforces a closed-form claim margin derived from Pinsker's inequality and total variation bounds:
                            $$m_{r,j} = \\Delta_j \\left(\\sqrt{\\frac{1}{2} D'_{\\text{KL}}} + \\eta_{\\text{eff}}\\right) + \\delta_{\\text{map}}$$
                            When the winning margin exceeds this threshold, the task is claimed safely with mathematical guarantees against double-claims. If belief divergence is too large, the claim is conservatively deferred to full consensus.

                            ### 3. Reading the Mission Control Map
                            - **Robots (Triangles):** Indicated with unique colors and white outlines, showing current position and faint dashed lines for their planned path.
                            - **Tasks (Stars):** Amber stars indicate pending tasks with rewards. Completed tasks become green circles.
                            - **Blocked Edges (Red Lines with 'x'):** Corridors currently interdicted by the adversary.
                            - **Detours (Cyan Dotted Lines):** Alternative corridors traversed locally with zero communication overhead.
                            - **Work Zones (Translucent Amber):** Real municipal road closures from the City of Boston Public Works Department.

                            ### Scientific Scope & Honest Limitations
                            - **Simulation Only:** All evaluations are conducted strictly in discrete event simulation and PyBullet rigid-body physics. No physical hardware was used.
                            - **Assumption 1 Adherence:** The theoretical condition for strictly conflict-free safe claims holds on approximately **21.3%** of safe claims under dynamic belief divergence. Safe claims outside this bound transition gracefully to standard consensus without mission failure.
                            - **Comparative Trade-offs:** ACA does not dominate CTP Replan in raw completion percentage ($89.2\\%$ vs $93.7\\%$). Instead, ACA achieves a balanced trade-off, outperforming standard CBBA under strategic interdictions while preserving decentralized market properties without unconstrained single-robot recomputation.
                            """
                        )

                    # Tab 6: Export
                    with gr.Tab("Export", id="tab-export"):
                        gr.Markdown("### Export Simulation Telemetry Artifacts")
                        with gr.Row():
                            export_json_btn = gr.Button("Download Run as JSON", elem_classes=["btn-control"])
                            export_csv_btn = gr.Button("Download Tick Log as CSV", elem_classes=["btn-control"])
                        export_file = gr.File(label="Download File", visible=False)

        # ================= LOGIC HANDLERS =================

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

        map_dropdown.change(
            update_map_choice,
            inputs=[map_dropdown],
            outputs=[coarsen_radio, prov_card],
            scroll_to_output=False,
        )

        def update_alloc_choice(alloc_choice):
            """Display UI note for ablation identity."""
            if alloc_choice == "ACA (Depth-2)":
                note = "Depth-2 is identical to ACA on these graphs because single-level contingency recourse branches bypass primary corridor interdictions, and recursive detours saturate on these horizons and topologies."
                return gr.Markdown(value=note, visible=True)
            return gr.Markdown(value="", visible=False)

        alloc_dropdown.change(
            update_alloc_choice,
            inputs=[alloc_dropdown],
            outputs=[ablation_note],
            scroll_to_output=False,
        )

        def run_sim_action(
            map_choice, coarsen_choice, work_zones_active,
            robots, tasks, adv_choice, alloc_choice,
            max_steps, comm_regime, comm_range, p_drop,
            depth, seed,
            progress=gr.Progress(track_tqdm=True),
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

            progress(0.1, desc="Building navigation environment...")
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
            progress(0.7, desc="Synthesizing telemetry traces...")

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
            detours = len(final_frame.get("active_detours", []))

            kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
            kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
            kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
            kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
            kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
            kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
            kpi_detr_h = f"<div class='kpi-card'><div class='kpi-val'>{detours}</div><div class='kpi-lbl'>Detours</div></div>"

            # Construct outcome sentence for result banner
            outcome_sent = f"Run Result: {completed}/{total_t} tasks completed in {len(history)} steps, {confs} conflicts, {msgs} messages, {blks} active blockages, {detours} absorbed by local detours."
            banner_vis = gr.Row(visible=True)
            banner_txt = outcome_sent

            title_md = f"### Spatial Telemetry View — Tick {final_tick_idx + 1} of {len(history)} ({completed}/{total_t} Tasks Completed)"

            # Exact reproduction panel markdown
            alloc_code = parse_allocator_name(alloc_choice)
            repro_md = f"""### 🔬 Provenance & Exact Reproduction Command
- **Git Commit Hash:** `44d73b0cf1dec8e301e0a43a4961d22dba33a614`
- **Environment:** `{fam}` ({n_nodes} nodes, variant `{variant}`)
- **Fleet & Tasks:** {robots_cnt} robots, {tasks_cnt} tasks
- **Adversary Profile:** `{adv_choice}`
- **Allocator Mechanism:** `{alloc_choice}` (`{alloc_code}`)
- **Random Seed (CRN):** `{int(seed_num)}`
- **Mission Horizon:** `{len(history)}` ticks
- **Communication Regime:** `{comm_regime}` (range: {comm_range}m, drop rate: {p_drop})

**Exact CLI Reproduction Command:**
```bash
python -c "from acalib.demo.runner import run_single_simulation; res = run_single_simulation('{fam}', {n_nodes}, '{adv_choice}', '{alloc_code}', seed={int(seed_num)}, n_robots={int(robots_cnt)}, n_tasks={int(tasks_cnt)}, max_steps={len(history)}); print('Tasks Completed:', res['summary']['completed_tasks'], '/', res['summary']['total_tasks'], '| Net Welfare:', round(res['summary']['net_welfare'], 2))"
```
"""

            progress(1.0, desc="Simulation complete.")
            return (
                history, events, env_info, summary,
                fig, title_md, banner_vis, banner_txt,
                kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
                scrubber_upd, events_html, telemetry_df,
                narrative, failures_df, repro_md,
                gr.Tabs(selected="tab-summary"),  # Automatically select Summary tab
            )

        run_btn.click(
            run_sim_action,
            inputs=[
                map_dropdown, coarsen_radio, work_zones_toggle,
                robots_slider, tasks_slider, adv_dropdown, alloc_dropdown,
                max_steps_slider, comm_regime_dropdown, comm_range_slider, p_drop_slider,
                depth_slider, seed_number,
            ],
            outputs=[
                history_state, events_state, env_meta_state, summary_state,
                map_plot, map_title_md, run_result_banner, result_sentence_md,
                kpi_done, kpi_rate, kpi_conf, kpi_msgs, kpi_trav, kpi_blkd, kpi_detr,
                scrubber, event_log_box, telemetry_table,
                what_happened_box, task_failures_table, reproduce_result_md,
                tabs,
            ],
            scroll_to_output=False,
        )

        def replay_from_start(history, env_info, work_zones_active):
            """Jump back to tick 1."""
            if not history:
                return gr.Slider(value=1), None, "", "", "", "", "", "", ""
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
            detours = len(final_frame.get("active_detours", []))

            kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
            kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
            kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
            kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
            kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
            kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
            kpi_detr_h = f"<div class='kpi-card'><div class='kpi-val'>{detours}</div><div class='kpi-lbl'>Detours</div></div>"

            title_md = f"### Spatial Telemetry View — Tick 1 of {len(history)}"
            return (
                gr.Slider(value=1), fig, title_md,
                kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
                gr.Tabs(selected="tab-telemetry"),
            )

        replay_btn.click(
            replay_from_start,
            inputs=[history_state, env_meta_state, work_zones_toggle],
            outputs=[
                scrubber, map_plot, map_title_md,
                kpi_done, kpi_rate, kpi_conf, kpi_msgs, kpi_trav, kpi_blkd, kpi_detr,
                tabs,
            ],
            scroll_to_output=False,
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
            detours = len(final_frame.get("active_detours", []))

            kpi_done_h = f"<div class='kpi-card'><div class='kpi-val'>{completed} / {total_t}</div><div class='kpi-lbl'>Done</div></div>"
            kpi_rate_h = f"<div class='kpi-card'><div class='kpi-val'>{pct:.1f}%</div><div class='kpi-lbl'>Rate</div></div>"
            kpi_conf_h = f"<div class='kpi-card'><div class='kpi-val'>{confs}</div><div class='kpi-lbl'>Conflicts</div></div>"
            kpi_msgs_h = f"<div class='kpi-card'><div class='kpi-val'>{msgs}</div><div class='kpi-lbl'>Msgs</div></div>"
            kpi_trav_h = f"<div class='kpi-card'><div class='kpi-val'>{trav:.1f}</div><div class='kpi-lbl'>Travel</div></div>"
            kpi_blkd_h = f"<div class='kpi-card'><div class='kpi-val'>{blks}</div><div class='kpi-lbl'>Blocked</div></div>"
            kpi_detr_h = f"<div class='kpi-card'><div class='kpi-val'>{detours}</div><div class='kpi-lbl'>Detours</div></div>"

            title_md = f"### Spatial Telemetry View — Tick {tick_idx + 1} of {len(history)}"
            events_html = format_event_log_html(events, active_tick=tick_idx + 1, filter_category=filter_category)
            telemetry_df = get_metrics_table(history, tick_idx)

            return (
                fig, title_md,
                kpi_done_h, kpi_rate_h, kpi_conf_h, kpi_msgs_h, kpi_trav_h, kpi_blkd_h, kpi_detr_h,
                events_html, telemetry_df,
            )

        scrubber.change(
            scrub_action,
            inputs=[scrubber, history_state, events_state, event_filter_radio, env_meta_state, work_zones_toggle],
            outputs=[
                map_plot, map_title_md,
                kpi_done, kpi_rate, kpi_conf, kpi_msgs, kpi_trav, kpi_blkd, kpi_detr,
                event_log_box, telemetry_table,
            ],
            scroll_to_output=False,
        )

        event_filter_radio.change(
            lambda cat, evs, scr: format_event_log_html(evs, active_tick=int(scr), filter_category=cat),
            inputs=[event_filter_radio, events_state, scrubber],
            outputs=[event_log_box],
            scroll_to_output=False,
        )

        def step_tick(delta, current_tick, history_len):
            if history_len <= 0:
                return 1
            new_tick = max(1, min(history_len, int(current_tick) + delta))
            return new_tick

        step_back_btn.click(
            lambda cur, hist: step_tick(-1, cur, len(hist)),
            inputs=[scrubber, history_state],
            outputs=[scrubber],
            scroll_to_output=False,
        )
        step_fwd_btn.click(
            lambda cur, hist: step_tick(1, cur, len(hist)),
            inputs=[scrubber, history_state],
            outputs=[scrubber],
            scroll_to_output=False,
        )

        # Paired Comparison Action
        def run_compare_action(
            map_choice, coarsen_choice, robots, tasks, adv_choice, alloc_choice,
            max_steps, comm_regime, comm_range, p_drop, depth, seed,
            progress=gr.Progress(track_tqdm=True),
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

            # Dual-panel Matplotlib dashboard chart for paired run
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

            # Panel 1: Task Completion Rate
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

            # Panel 2: Total Messages (Decentralized Communication Overhead)
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

            # Paper aggregate
            paper_df = get_paper_aggregate_comparison(fam, variant=variant)
            if paper_df is None:
                p_table = pd.DataFrame()
                p_note = "No pre-registered aggregate for this map"
            else:
                p_table = paper_df
                p_note = "Pre-registered empirical aggregate (n=50 seeds) from results/stats/instance_aggregated.csv"

            progress(1.0, desc="Comparison complete.")
            return comp_df, fig, p_table, p_note, gr.Tabs(selected="tab-compare")

        compare_btn.click(
            run_compare_action,
            inputs=[
                map_dropdown, coarsen_radio, robots_slider, tasks_slider, adv_dropdown, alloc_dropdown,
                max_steps_slider, comm_regime_dropdown, comm_range_slider, p_drop_slider,
                depth_slider, seed_number,
            ],
            outputs=[compare_table, compare_chart, paper_table, paper_note, tabs],
            scroll_to_output=False,
        )
        tab_compare_btn.click(
            run_compare_action,
            inputs=[
                map_dropdown, coarsen_radio, robots_slider, tasks_slider, adv_dropdown, alloc_dropdown,
                max_steps_slider, comm_regime_dropdown, comm_range_slider, p_drop_slider,
                depth_slider, seed_number,
            ],
            outputs=[compare_table, compare_chart, paper_table, paper_note, tabs],
            scroll_to_output=False,
        )

        def run_20_seeds_action(
            map_choice, coarsen_choice, robots, tasks, adv_choice, alloc_choice,
            max_steps, comm_regime, comm_range, p_drop, seed,
            progress=gr.Progress(track_tqdm=True),
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

            progress(0.0, desc="Starting 20 seeds evaluation...")
            res = run_20_seeds_paired(
                graph_family=fam,
                n_nodes=int(n_nodes),
                adversary_str=adv_choice,
                allocator_str=alloc_choice,
                baseline_str="cbba_partial_lr",
                comm_regime=comm_regime,
                comm_range=comm_range,
                p_drop=p_drop,
                n_robots=int(robots),
                n_tasks=int(tasks),
                max_steps=int(max_steps),
                variant=variant,
                seed_start=int(seed),
                num_seeds=20,
                progress=progress,
            )
            progress(1.0, desc="Evaluation complete.")

            verdict_md = f"**Verdict:** {res['verdict']}\n\n**Main Method ({res['main_method']}):** Mean Completion = {res['main_completion']}"
            return verdict_md, res["comparisons_table"]

        multi_seed_btn.click(
            run_20_seeds_action,
            inputs=[
                map_dropdown, coarsen_radio, robots_slider, tasks_slider, adv_dropdown, alloc_dropdown,
                max_steps_slider, comm_regime_dropdown, comm_range_slider, p_drop_slider, seed_number,
            ],
            outputs=[multi_seed_verdict, multi_seed_table],
            scroll_to_output=False,
        )

        # Export Actions
        def export_json_action(history, summary, env_info):
            if not history:
                return None
            data = {
                "env_info": env_info,
                "summary": summary,
                "history": history,
            }
            out_file = os.path.join(REPO_ROOT, "results", "demo_session_export.json")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return gr.File(value=out_file, visible=True)

        def export_csv_action(history):
            if not history:
                return None
            records = []
            for frame in history:
                records.append({
                    "tick": frame.get("tick", 0),
                    "completed_tasks": frame.get("completed_tasks", 0),
                    "conflicts": frame.get("conflicts", 0),
                    "messages": frame.get("messages", 0),
                    "travel_distance": frame.get("travel", 0.0),
                    "welfare": frame.get("welfare", 0.0),
                    "active_blockages": len(frame.get("blocked_edges", [])),
                    "active_detours": len(frame.get("active_detours", [])),
                })
            df = pd.DataFrame(records)
            out_file = os.path.join(REPO_ROOT, "results", "demo_session_ticks.csv")
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            df.to_csv(out_file, index=False)
            return gr.File(value=out_file, visible=True)

        export_json_btn.click(
            export_json_action,
            inputs=[history_state, summary_state, env_meta_state],
            outputs=[export_file],
            scroll_to_output=False,
        )
        export_csv_btn.click(
            export_csv_action,
            inputs=[history_state],
            outputs=[export_file],
            scroll_to_output=False,
        )

    return demo


if __name__ == "__main__":
    demo = build_app()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, css=MISSION_CONTROL_CSS)
