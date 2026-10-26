"""
Unit and regression test for UI displayed metrics vs raw simulation telemetry and exports.
Verifies Finding L:
- Zero mismatch between displayed KPI metrics and exported JSON/CSV artifacts.
- Active detours vs cumulative detour activations semantic consistency.
"""

import os
import sys
import json
import re
import pandas as pd
import pytest

pytest.importorskip("gradio")
pytestmark = [pytest.mark.ui]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.demo.ui.callbacks import (
    run_sim_action,
    replay_from_start,
    scrub_action,
    export_json_action,
    export_csv_action,
)


def _parse_kpi_value(html_str: str) -> str:
    m = re.search(r"<div class='kpi-val'>([^<]+)</div>", html_str)
    if m:
        return m.group(1).strip()
    # If sub-element exists:
    m2 = re.search(r"<div class='kpi-val'>\s*(\d+)\s*<span", html_str)
    if m2:
        return m2.group(1).strip()
    return ""


def _parse_kpi_sub(html_str: str) -> str:
    m = re.search(r"<span class='kpi-sub'>\(([^)]+)\)</span>", html_str)
    return m.group(1).strip() if m else ""


def test_ui_kpi_metrics_match_raw_and_export():
    """Run a simulation and ensure UI KPI cards match raw history and exported files."""
    # Execute run_sim_action with small test parameters
    res = run_sim_action(
        map_choice="MovingAI Warehouse 10-20-10-2-1 (real MAPF benchmark)",
        coarsen_choice="~38 nodes (B=8)",
        work_zones_active=False,
        robots=2,
        tasks=4,
        adv_choice="Reactive (Corridor Interdiction)",
        alloc_choice="ACA (Ours)",
        max_steps=30,
        comm_regime="benign (50m, 2% loss)",
        comm_range=50.0,
        p_drop=0.02,
        depth=1,
        seed=101,
    )

    (
        history, events, env_info, summary,
        fig, title_md, banner_vis, banner_txt,
        kpi_done, kpi_rate, kpi_conf, kpi_msgs, kpi_trav, kpi_blkd, kpi_detr,
        scrubber, ev_box, telem_df, narrative, fail_df, repro_md
    ) = res

    assert len(history) > 0
    final_frame = history[-1]

    # Verify KPI Done
    done_val = _parse_kpi_value(kpi_done)
    completed = summary["completed_tasks"]
    total_t = summary["total_tasks"]
    assert done_val == f"{completed} / {total_t}"

    # Verify KPI Conflicts
    conf_val = _parse_kpi_value(kpi_conf)
    assert int(conf_val) == summary["total_conflicts"]

    # Verify KPI Messages
    msgs_val = _parse_kpi_value(kpi_msgs)
    assert int(msgs_val) == summary["total_messages"]

    # Verify KPI Blocked
    blkd_val = _parse_kpi_value(kpi_blkd)
    assert int(blkd_val) == len(final_frame.get("blocked_edges", []))

    # Verify KPI Detours: Active vs Cumulative
    active_detours = len(final_frame.get("active_detours", []))
    cum_detours = sum(1 for ev in events if ev.get("category") == "Detour")
    detr_val = _parse_kpi_value(kpi_detr)
    detr_sub = _parse_kpi_sub(kpi_detr)
    assert int(detr_val) == active_detours
    assert detr_sub == f"{cum_detours} cum"

    # Verify that summary sentence matches
    assert f"{active_detours} active detours" in banner_txt
    assert f"{cum_detours} cumulative activations" in banner_txt

    # Verify export_json_action
    json_path = export_json_action(history, summary, env_info)
    assert os.path.exists(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        export_data = json.load(f)
    assert export_data["summary"]["completed_tasks"] == completed
    assert export_data["summary"]["total_conflicts"] == summary["total_conflicts"]
    assert export_data["summary"]["total_messages"] == summary["total_messages"]

    # Verify export_csv_action
    csv_path = export_csv_action(history)
    assert os.path.exists(csv_path)
    df_csv = pd.read_csv(csv_path)
    assert len(df_csv) == len(history)
    assert "conflicts" in df_csv.columns
    assert "completed_tasks" in df_csv.columns


def test_ui_run_20_seeds_action_no_deprecation_warnings():
    """Verify run_20_seeds_action produces boxplot with zero MatplotlibDeprecationWarnings."""
    import warnings
    from acalib.demo.ui.callbacks import run_20_seeds_action

    with warnings.catch_warnings():
        warnings.simplefilter("error", category=DeprecationWarning)
        summary_df, fig = run_20_seeds_action(
            map_choice="MovingAI Warehouse 10-20-10-2-1 (real MAPF benchmark)",
            coarsen_choice="~38 nodes (B=8)",
            robots=2,
            tasks=3,
            adv_choice="Reactive (Corridor Interdiction)",
            alloc_choice="ACA (Ours)",
            max_steps=5,
            comm_regime="benign (50m, 2% loss)",
            comm_range=50.0,
            p_drop=0.02,
            seed=101,
            progress=lambda frac, desc=None: None,
        )
        assert summary_df is not None
        assert fig is not None
