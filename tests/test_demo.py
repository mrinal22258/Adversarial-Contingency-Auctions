"""
Smoke test for the interactive demo (app.py) simulation wrapper.
Verifies that SimulationEngine step, reset, snapshot extraction, and plotting function without errors.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import run_simulation_wrapper, plot_simulation_state, get_metrics_table


def test_demo_simulation_wrapper_smoke():
    """Verify that run_simulation_wrapper runs through 60 steps cleanly across allocators."""
    for alloc in ["ACA (Ours)", "ACA (No Margin)", "CBBA", "Centralized Oracle"]:
        history, graph, pos = run_simulation_wrapper(
            num_robots=4,
            num_tasks=8,
            graph_family="RGG",
            num_nodes=20,
            adversary_str="Reactive",
            allocator_str=alloc,
            random_seed=42,
        )

        assert len(history) == 60
        assert graph is not None
        assert pos is not None
        assert "tick" in history[0]
        assert "robots" in history[0]
        assert "tasks" in history[0]

        # Test plot generation for first and last frame
        fig_first = plot_simulation_state(history, graph, pos, 0)
        assert fig_first is not None
        fig_last = plot_simulation_state(history, graph, pos, 59)
        assert fig_last is not None

        # Test metrics table
        df_m = get_metrics_table(history, 59)
        assert not df_m.empty
        assert "Simulation Metric" in df_m.columns
