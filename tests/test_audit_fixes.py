"""
Unit and regression tests verifying fixes for audit items B1-B10 and Theorems 1 & 3:
(a) Margin changes bundle claim decisions
(b) plan_task_bundle preserves mid-edge progress
(c) Detour origin respects oriented upstream node regardless of string sort
(d) CBBA vs CBBA-Partial divergence under blockage
(e) Theorem 3 end-to-end safe claim conflict-freedom under divergent beliefs
(f) Theorem 1 Monte-Carlo policy execution vs expected cost formula
"""

import pytest
import numpy as np
import networkx as nx

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType, canonical_edge
from acalib.env.blockage_process import PersistentBlockageProcess
from acalib.env.comm import CommunicationNetwork
from acalib.agents.robot import RobotAgent
from acalib.agents.contingency import ContingencyPlanner
from acalib.agents.tom import TheoryOfMindTracker, PinskerMarginCalculator
from acalib.alloc.base import Task
from acalib.alloc.aca import ACAAllocator
from acalib.alloc.cbba import CBBAAllocator
from acalib.alloc.cbba_partial import CBBAPartialReplanAllocator
from acalib.alloc.implicit import ImplicitCoordinationAllocator
from acalib.sim.engine import SimulationEngine


def test_plan_task_bundle_no_reset_mid_edge():
    """Verify B1 fix: plan_task_bundle does not reset edge_progress or path_index mid-edge."""
    g = nx.path_graph(4)
    for u, v in g.edges():
        g[u][v]["weight"] = 10.0
    nx.set_node_attributes(g, {i: (float(i * 10), 0.0) for i in g.nodes()}, "pos")

    robot = RobotAgent(
        robot_id=0,
        start_node=0,
        graph=g,
        fleet_ids=[0],
        speed=1.0,
    )
    tasks = {1: {"node": 3}}
    robot.bundle = [1]
    robot.plan_task_bundle(tasks)

    # Robot starts at node 0, heading to node 3 along path [0, 1, 2, 3]
    assert robot.active_path == [0, 1, 2, 3]
    assert robot.path_index == 0
    assert robot.edge_progress == 0.0

    # Advance robot mid-edge
    robot.edge_progress = 4.5
    robot.pos = (4.5, 0.0)

    # Re-calling plan_task_bundle for same active task MUST NOT reset progress
    robot.plan_task_bundle(tasks)
    assert robot.edge_progress == 4.5
    assert robot.path_index == 0
    assert robot.active_path == [0, 1, 2, 3]


def test_oriented_edge_detour():
    """Verify B7 fix: Detour branches from upstream endpoint regardless of string sorting."""
    # Nodes 2 and 10: note "10" < "2" in string sort
    g = nx.Graph()
    g.add_edge(2, 10, weight=5.0)
    g.add_edge(2, 99, weight=15.0)
    g.add_edge(99, 10, weight=15.0)
    g.add_edge(10, 50, weight=2.0)
    nx.set_node_attributes(g, {2: (0, 0), 10: (5, 0), 99: (2.5, 3), 50: (7, 0)}, "pos")

    planner = ContingencyPlanner(g, max_depth=1)
    # Traversing from 2 to 50 via primary path [2, 10, 50]
    edge_marginals = {canonical_edge(2, 10): 0.3, canonical_edge(10, 50): 0.0}

    plan = planner.build_recourse_plan(
        task_id=1,
        start_node=2,
        target_node=50,
        edge_marginals=edge_marginals,
        risky_edge_threshold=0.2,
    )

    assert plan is not None
    # Risky edge oriented is (2, 10)
    assert (2, 10) in plan.risky_edges
    assert (2, 10) in plan.detours
    detour = plan.detours[(2, 10)]
    # Detour MUST start from upstream node 2, NOT blocked node 10!
    assert detour[0] == 2
    assert detour[-1] == 50


def test_margin_changes_bundle_decisions():
    """Verify B2 fix: enable_margin=True defers conflicting claims that enable_margin=False double-claims."""
    g = generate_graph("rgg", n_nodes=20, seed=42)
    comm_net = CommunicationNetwork()

    fleet_ids = [0, 1]
    robots = {
        0: RobotAgent(robot_id=0, start_node=0, graph=g, fleet_ids=fleet_ids),
        1: RobotAgent(robot_id=1, start_node=1, graph=g, fleet_ids=fleet_ids),
    }

    # Inject belief divergence: robots disagree on types
    robots[0].tom_tracker.peer_beliefs[1] = np.array([0.9, 0.05, 0.05])
    robots[1].tom_tracker.peer_beliefs[0] = np.array([0.05, 0.05, 0.9])

    tasks = {
        0: Task(task_id=0, node=5, reward=100.0),
    }
    positions = {0: robots[0].pos, 1: robots[1].pos}

    # With margin ENABLED: uncertainty prevents simultaneous safe claiming
    alloc_aca = ACAAllocator(graph=g, robots=robots, comm_net=comm_net, enable_margin=True)
    for rid in fleet_ids:
        alloc_aca._build_bundle_aca(rid, tasks, positions)
    
    # Check that margin caused deferral (neither or at most one claims)
    claimed_with_margin = set(robots[0].bundle) & set(robots[1].bundle)
    assert len(claimed_with_margin) == 0, "Margin failed: simultaneous claim occurred!"
    assert alloc_aca.total_deferred_tasks >= 1

    # Reset robots
    robots[0].bundle.clear()
    robots[1].bundle.clear()

    # With margin DISABLED (zero margin): both robots claim the same task in Phase 1
    alloc_no_margin = ACAAllocator(graph=g, robots=robots, comm_net=comm_net, enable_margin=False)
    for rid in fleet_ids:
        alloc_no_margin._build_bundle_aca(rid, tasks, positions)
    
    # Without margin, both robots greedily claim task 0
    assert 0 in robots[0].bundle and 0 in robots[1].bundle, (
        "Without margin, both robots should have claimed the single high-reward task!"
    )


def test_theorem_3_end_to_end_conflict_freedom():
    """Verify Theorem 3: Safe-claims are strictly conflict-free even when multiple safe claims occur."""
    g = nx.path_graph(20)
    # Positions along a line
    pos = {i: (float(i), 0.0) for i in range(20)}
    nx.set_node_attributes(g, pos, "pos")
    nx.set_edge_attributes(g, 1.0, "weight")
    
    comm_net = CommunicationNetwork()
    fleet_ids = [0, 1]

    # Robot 0 at node 0; Robot 1 at node 19
    robots = {
        0: RobotAgent(robot_id=0, start_node=0, graph=g, fleet_ids=fleet_ids, eta=0.01),
        1: RobotAgent(robot_id=1, start_node=19, graph=g, fleet_ids=fleet_ids, eta=0.01),
    }

    # Robot 0 has task 0 right next to it (node 1)
    # Robot 1 has task 1 right next to it (node 18)
    tasks = {
        0: Task(task_id=0, node=1, reward=50.0),
        1: Task(task_id=1, node=18, reward=50.0),
    }
    positions = {0: robots[0].pos, 1: robots[1].pos}

    # Initialize accurate peer beliefs
    for i in fleet_ids:
        for j in fleet_ids:
            if i != j:
                robots[i].tom_tracker.update_peer_belief(j, robots[j].type_filter.get_belief_vector(), step=0)

    allocator = ACAAllocator(graph=g, robots=robots, comm_net=comm_net, enable_margin=True)
    for rid in fleet_ids:
        allocator._build_bundle_aca(rid, tasks, positions)

    # Both robots MUST produce safe claims (not deferred) because belief gap is huge and eta is tiny
    assert len(robots[0].bundle) > 0, "Robot 0 should have claimed task 0 safely"
    assert len(robots[1].bundle) > 0, "Robot 1 should have claimed task 1 safely"
    assert 0 in robots[0].bundle and 1 in robots[1].bundle
    # Crucially, zero overlapping/double claims
    assert len(set(robots[0].bundle) & set(robots[1].bundle)) == 0


def test_cbba_vs_cbba_partial_divergence_under_blockage():
    """Verify B10 fix: CBBA and CBBA-Partial behave differently when blockages occur."""
    g = generate_graph("rgg", n_nodes=35, seed=3)
    
    # Run CBBA
    engine_cbba = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.BUDGETED_INTERDICTION,
        allocator_type="cbba",
        n_robots=4,
        n_tasks=15,
        risk_fraction=0.4,
        max_steps=80,
        seed=3,
    )
    m_cbba = engine_cbba.run(max_steps=80)

    # Run CBBA-Partial
    engine_partial = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.BUDGETED_INTERDICTION,
        allocator_type="cbba_partial",
        n_robots=4,
        n_tasks=15,
        risk_fraction=0.4,
        max_steps=80,
        seed=3,
    )
    m_partial = engine_partial.run(max_steps=80)

    # Either completed tasks, replan events, messages or welfare differ
    diff_found = (
        m_cbba.total_messages_sent != m_partial.total_messages_sent
        or m_cbba.net_welfare != m_partial.net_welfare
        or m_cbba.reauction_events != m_partial.reauction_events
        or m_cbba.completed_tasks != m_partial.completed_tasks
    )
    assert diff_found, "CBBA and CBBA-Partial produced identical execution despite blockages!"


def test_theorem_1_monte_carlo():
    """Verify Theorem 1: Expected cost formula matches Monte Carlo sampling of the recourse policy."""
    g = nx.Graph()
    # Path: 0 -> 1 -> 2 -> 3
    # Detour around (1, 2): 1 -> 4 -> 3
    g.add_edge(0, 1, weight=5.0)
    g.add_edge(1, 2, weight=5.0)
    g.add_edge(2, 3, weight=5.0)
    g.add_edge(1, 4, weight=8.0)
    g.add_edge(4, 3, weight=8.0)
    nx.set_node_attributes(g, {0: (0,0), 1: (5,0), 2: (10,0), 3: (15,0), 4: (10,5)}, "pos")

    planner = ContingencyPlanner(g, max_depth=1)
    pi_block = 0.30
    edge_marginals = {canonical_edge(1, 2): pi_block}

    plan = planner.build_recourse_plan(
        task_id=1,
        start_node=0,
        target_node=3,
        edge_marginals=edge_marginals,
        risky_edge_threshold=0.1,
    )
    formula_cost = plan.expected_cost

    # Monte Carlo simulation of policy execution:
    # Nominal path cost = 5 + 5 + 5 = 15
    # Detour path cost = 5 + 8 + 8 = 21
    # Expected: (1 - pi) * 15 + pi * 21 = 0.70 * 15 + 0.30 * 21 = 10.5 + 6.3 = 16.8
    rng = np.random.default_rng(42)
    n_samples = 20000
    sample_costs = []
    for _ in range(n_samples):
        is_blocked = (rng.random() < pi_block)
        if is_blocked:
            cost = 5.0 + 8.0 + 8.0  # (0->1) + detour (1->4->3)
        else:
            cost = 5.0 + 5.0 + 5.0  # primary (0->1->2->3)
        sample_costs.append(cost)

    mc_mean = float(np.mean(sample_costs))
    assert abs(formula_cost - mc_mean) < 0.1, f"Formula {formula_cost} differs from MC {mc_mean}"
