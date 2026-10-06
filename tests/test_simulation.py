"""End-to-end integration tests for SimulationEngine across all allocators and adversaries."""

import pytest
import networkx as nx

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


@pytest.mark.parametrize(
    "allocator_type",
    [
        "aca",
        "cbba",
        "cbba_partial",
        "ssi",
        "cc_cbba",
        "implicit",
        "pessimistic",
        "oracle",
    ],
)
def test_simulation_runs_all_allocators(allocator_type):
    """Verify that full mission simulations run smoothly across every literature baseline."""
    g = generate_graph(family="rgg", n_nodes=20, seed=10)
    engine = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type=allocator_type,
        n_robots=3,
        n_tasks=6,
        max_steps=50,
        seed=42,
    )

    metrics = engine.run(max_steps=50)
    summary = metrics.compute_summary()

    assert summary["total_tasks"] == 6
    assert summary["completed_tasks"] >= 0
    assert summary["makespan"] > 0
    assert summary["mean_tick_runtime_ms"] >= 0.0
    assert summary["total_wall_clock_ms"] > 0.0


def test_adversary_types_in_simulation():
    """Verify simulation works across all 4 adversary types including out-of-model cyclic patrol."""
    g = generate_graph(family="warehouse", n_nodes=25, seed=12)

    for adv in [
        AdversaryType.STOCHASTIC,
        AdversaryType.REACTIVE,
        AdversaryType.BUDGETED_INTERDICTION,
        AdversaryType.CYCLIC_PATROL,
    ]:
        engine = SimulationEngine(
            graph=g,
            adversary_type=adv,
            allocator_type="aca",
            n_robots=3,
            n_tasks=5,
            max_steps=30,
            seed=99,
        )
        metrics = engine.run(max_steps=30)
        assert metrics.total_tasks == 5
        assert metrics.makespan > 0
