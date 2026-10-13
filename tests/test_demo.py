"""
Comprehensive Verification and Regression Test Suite for Interactive Demo (app.py).
Tests:
1. Legacy and modern wrapper smoke test across mechanisms.
2. B5: Wrapper metrics match experiments/run_sweep.py on identical seed (CRN fidelity).
3. E2: Headless smoke test on real maps x {aca, cbba, ctp_replan, oracle} x 3 seeds:
   - No exception
   - Messages > 0 for decentralized methods
   - Positions come strictly from "pos" attribute (zero spring_layout fallback)
   - Runtime < 5s for Boston
"""

import time
import pytest
import os
import sys
import numpy as np
import networkx as nx

pytest.importorskip("gradio")
pytestmark = [pytest.mark.ui]

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import run_simulation_wrapper, plot_simulation_state, get_metrics_table
from experiments.run_sweep import run_single_trial
from acalib.demo.runner import run_single_simulation


def test_demo_simulation_wrapper_smoke():
    """Verify that run_simulation_wrapper runs through 60 steps cleanly across allocators."""
    for alloc in ["ACA (Ours)", "ACA (No Margin)", "CBBA", "Centralized Oracle"]:
        history, graph, pos = run_simulation_wrapper(
            num_robots=4,
            num_tasks=8,
            graph_family="warehouse_movingai",
            num_nodes=38,
            adversary_str="Reactive",
            allocator_str=alloc,
            random_seed=42,
            max_steps=60,
        )

        assert 0 < len(history) <= 60
        assert graph is not None
        assert pos is not None
        assert "tick" in history[0]
        assert "robots" in history[0]
        assert "tasks" in history[0]

        # Test plot generation for first and last frame
        fig_first = plot_simulation_state(history, graph, pos, 0)
        assert fig_first is not None
        fig_last = plot_simulation_state(history, graph, pos, len(history) - 1)
        assert fig_last is not None

        # Test metrics table
        df_m = get_metrics_table(history, len(history) - 1)
        assert not df_m.empty
        assert "Simulation Metric" in df_m.columns


def test_app_wrapper_matches_sweep_metrics():
    """
    B5 Verification: Assert that app's simulation engine run matches
    experiments/run_sweep.py run_single_trial on identical seed and CRN environment.
    """
    seed = 10001
    graph_family = "warehouse_movingai"
    n_nodes = 38
    allocator_name = "aca"
    comm_regime = "benign"
    comm_range = 50.0
    p_drop = 0.02
    n_robots = 4
    n_tasks = 15
    max_steps = 80

    # 1. Sweep run
    res_sweep = run_single_trial(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_type_str="theta_2_reactive",
        allocator_name=allocator_name,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=1,
        traces_dir=None,
        runs_jsonl=None,
    )

    # 2. App simulation run
    res_app = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str="Reactive (Corridor Interdiction)",
        allocator_str="ACA (Ours)",
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=1,
    )

    sum_app = res_app["summary"]

    # Assert metrics match identically
    assert res_sweep["completed_tasks"] == sum_app["completed_tasks"]
    assert res_sweep["total_messages"] == sum_app["total_messages"]
    assert res_sweep["total_conflicts"] == sum_app["total_conflicts"]
    assert np.isclose(res_sweep["net_welfare"], sum_app["net_welfare"], rtol=1e-5)
    assert sum_app["total_messages"] > 0, "Messages must be real and positive"


@pytest.mark.parametrize("graph_family,n_nodes", [
    ("warehouse_movingai", 38),
    ("road_osmnx", 216),
])
@pytest.mark.parametrize("allocator_name", [
    "aca",
    "cbba",
    "ctp_replan",
    "clairvoyant_greedy",
])
@pytest.mark.parametrize("seed", [10001, 10002, 10003])
def test_headless_smoke_real_maps_methods_and_seeds(graph_family, n_nodes, allocator_name, seed):
    """
    E2 Smoke Test: Both real maps x {aca, cbba, ctp_replan, oracle} x 3 seeds.
    Asserts:
    1. No exceptions
    2. Messages > 0 for decentralized methods
    3. Positions strictly from 'pos' attribute (never spring_layout)
    4. Boston runtime < 5s
    """
    t_start = time.perf_counter()

    res = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str="theta_2_reactive",
        allocator_str=allocator_name,
        comm_regime="benign",
        comm_range=50.0,
        p_drop=0.02,
        n_robots=4,
        n_tasks=10,
        seed=seed,
        max_steps=40,
    )

    t_elapsed = time.perf_counter() - t_start

    summary = res["summary"]
    graph = res["graph"]
    pos = res["pos"]

    # 1. Assert no exception and non-empty history
    assert len(res["history"]) > 0

    # 2. Assert messages > 0 for decentralized methods
    if allocator_name in ("aca", "cbba", "ctp_replan"):
        assert summary["total_messages"] > 0, (
            f"Decentralized method {allocator_name} on {graph_family} reported 0 messages!"
        )

    # 3. Assert positions come strictly from 'pos' attribute (no spring_layout distortion)
    raw_pos = nx.get_node_attributes(graph, "pos")
    assert len(pos) == len(graph.nodes())
    for n in graph.nodes():
        assert n in pos
        assert pos[n] == raw_pos[n], f"Position for node {n} was altered from graph 'pos' attribute!"

    # 4. Assert runtime < 5s for Boston
    if graph_family == "road_osmnx":
        assert t_elapsed < 5.0, f"Boston execution exceeded 5.0s (took {t_elapsed:.2f}s)"
