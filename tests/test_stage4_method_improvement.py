"""
Stage 4 Method Improvement Unit & Verification Tests.
Tests the adaptive entropy-calibrated margin and recourse pruning mechanisms in ACAAllocator.
"""

import networkx as nx

from acalib.alloc.aca import ACAAllocator
from acalib.sim.engine import SimulationEngine
from acalib.env.adversaries import AdversaryType
from acalib.agents.robot import RobotAgent
from acalib.env.comm import CommunicationNetwork


def test_aca_adaptive_initialization():
    """Verify ACAAllocator correctly stores adaptive_margin and prune_threshold attributes."""
    g = nx.cycle_graph(6)
    for u, v in g.edges():
        g[u][v]["weight"] = 10.0

    comm = CommunicationNetwork(comm_range=50.0, p_drop=0.0)
    robots = {
        0: RobotAgent(0, start_node=0, graph=g, fleet_ids=[0, 1], speed=5.0),
        1: RobotAgent(1, start_node=3, graph=g, fleet_ids=[0, 1], speed=5.0),
    }

    alloc_default = ACAAllocator(graph=g, robots=robots, comm_net=comm)
    assert not alloc_default.adaptive_margin
    assert alloc_default.prune_threshold == 0.0

    alloc_adapt = ACAAllocator(graph=g, robots=robots, comm_net=comm, adaptive_margin=True, prune_threshold=0.03)
    assert alloc_adapt.adaptive_margin
    assert alloc_adapt.prune_threshold == 0.03


def test_aca_adaptive_simulation_smoke():
    """Verify SimulationEngine runs cleanly with acalib allocator 'aca_adaptive'."""
    g = nx.grid_2d_graph(4, 4)
    g = nx.convert_node_labels_to_integers(g)
    for u, v in g.edges():
        g[u][v]["weight"] = 1.0

    engine = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.REACTIVE,
        allocator_type="aca_adaptive",
        n_robots=2,
        n_tasks=5,
        max_steps=20,
        comm_range=10.0,
        p_drop=0.05,
        contingency_depth=1,
        seed=42,
    )

    metrics = engine.run(max_steps=20)
    summary = metrics.compute_summary()

    assert "completed_tasks" in summary
    assert "total_messages" in summary
    assert "total_conflicts" in summary
    assert "mean_tick_runtime_ms" in summary


def test_aca_plus_simulation_smoke():
    """Verify SimulationEngine runs cleanly with 'aca_plus' (adaptive + pruning)."""
    g = nx.grid_2d_graph(4, 4)
    g = nx.convert_node_labels_to_integers(g)
    for u, v in g.edges():
        g[u][v]["weight"] = 1.0

    engine = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca_plus",
        n_robots=2,
        n_tasks=5,
        max_steps=20,
        comm_range=10.0,
        p_drop=0.05,
        contingency_depth=1,
        seed=123,
    )

    metrics = engine.run(max_steps=20)
    summary = metrics.compute_summary()
    assert summary["completed_tasks"] >= 0
    assert summary["total_messages"] >= 0
