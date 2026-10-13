"""
Gate 3 Acceptance Tests: Belief and Hazard Interface Contract (P0-5).
Verifies:
1. Directional separation: static, reactive, and budgeted-interdiction hypotheses
   give distinguishable, directionally correct hazards as robot positions and targeting change.
2. Simulator and planner use the exact same event definitions for proximity and interdiction cuts.
3. Grep test fails if planning code calls marginal functions with unpopulated default state.
"""

import re
import pytest
import numpy as np
import networkx as nx

from acalib.env.adversaries import (
    AdversaryType,
    ReactiveAdversary,
    BudgetedInterdictionAdversary,
    StochasticAdversary,
    canonical_edge,
    compute_edge_robot_count,
    compute_fleet_edge_robot_counts,
    compute_interdiction_cut,
)
from acalib.agents.belief import BayesianTypeFilter
from acalib.agents.robot import RobotAgent
from acalib.alloc.aca import ACAAllocator
from acalib.env.comm import CommunicationNetwork


def test_directional_hazard_separation_under_state_changes():
    """
    1. With equal inputs, static / reactive / budgeted-interdiction hypotheses give
       distinguishable, directionally correct hazards as robot positions and targeting change.
    """
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    G.add_edge(0, 3, weight=5.0)

    e_target = canonical_edge(1, 2)
    bayes_filter = BayesianTypeFilter()

    # Scenario A: Robot 0 is far away at node 0 (no proximity to (1, 2))
    state_far = {0: {"current_node": 0, "next_node": None, "target_node": None}}
    count_far = compute_edge_robot_count(G, e_target, state_far)
    assert count_far == 0.0

    h_stoch_far = bayes_filter.get_hazard_under_type(AdversaryType.STOCHASTIC, e_target, edge_robot_count=count_far, is_targeted_by_interdiction=False)
    h_react_far = bayes_filter.get_hazard_under_type(AdversaryType.REACTIVE, e_target, edge_robot_count=count_far, is_targeted_by_interdiction=False)
    h_budget_far = bayes_filter.get_hazard_under_type(AdversaryType.BUDGETED_INTERDICTION, e_target, edge_robot_count=count_far, is_targeted_by_interdiction=False)

    # Scenario B: Robot 0 is actively traversing (1, 2) (high proximity)
    state_near = {0: {"current_node": 1, "next_node": 2, "target_node": 3}}
    count_near = compute_edge_robot_count(G, e_target, state_near)
    assert count_near == 1.0

    h_stoch_near = bayes_filter.get_hazard_under_type(AdversaryType.STOCHASTIC, e_target, edge_robot_count=count_near, is_targeted_by_interdiction=False)
    h_react_near = bayes_filter.get_hazard_under_type(AdversaryType.REACTIVE, e_target, edge_robot_count=count_near, is_targeted_by_interdiction=False)

    # Scenario C: Edge (1, 2) is targeted by interdiction cut
    h_budget_targeted = bayes_filter.get_hazard_under_type(AdversaryType.BUDGETED_INTERDICTION, e_target, edge_robot_count=0.0, is_targeted_by_interdiction=True)

    # Directional verifications:
    # 1. Stochastic hazard is invariant to fleet motion
    assert h_stoch_far == h_stoch_near == 0.15

    # 2. Reactive hazard strictly increases with robot proximity
    assert h_react_near > h_react_far
    assert h_react_far == 0.05
    assert h_react_near == 0.05 + 0.35 * 1.0

    # 3. Budgeted interdiction strictly distinguishes targeted bottleneck vs non-targeted
    assert h_budget_targeted > h_budget_far
    assert h_budget_far == 0.05
    assert h_budget_targeted == 0.85

    # 4. Across all three hypotheses, the hazards are distinguishable under state change
    assert len({h_stoch_near, h_react_near, h_budget_targeted}) == 3


def test_planner_and_simulator_use_identical_event_definitions():
    """
    2. Planner and simulator share the exact same event definition for proximity and interdiction cuts.
    """
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    risky_edges = {canonical_edge(u, v) for u, v in G.edges()}

    fleet_states = {
        0: {"current_node": 0, "next_node": 1, "target_node": 3},
        1: {"current_node": 2, "next_node": None, "target_node": 3},
    }

    # Simulator evaluation
    sim_reactive = ReactiveAdversary(p0=0.05, alpha=0.35)
    sim_hazards = sim_reactive.get_onset_hazards(G, risky_edges, set(), fleet_states, step=0)

    # Estimator / Planner evaluation
    plan_counts = compute_fleet_edge_robot_counts(G, risky_edges, fleet_states)
    for e in risky_edges:
        expected_h = min(1.0, 0.05 + 0.35 * plan_counts.get(e, 0.0))
        assert np.isclose(sim_hazards[e], expected_h), f"Simulator hazard {sim_hazards[e]} != planner {expected_h}"

    # Interdiction cut identity
    sim_interdict = BudgetedInterdictionAdversary(budget_k=2)
    sim_cuts = sim_interdict._compute_interdiction_cut(G, risky_edges, fleet_states)
    plan_cuts = compute_interdiction_cut(G, risky_edges, fleet_states, budget_k=2)
    assert sim_cuts == plan_cuts, f"Simulator cut {sim_cuts} != planner cut {plan_cuts}"


def test_grep_fails_if_planning_code_calls_marginal_functions_with_default_state():
    """
    3. Grep test fails if planning code calls get_edge_marginals or get_hazard_under_type
       without explicit fleet state and interdiction indicators.
    """
    import os
    alloc_dir = os.path.join(os.path.dirname(__file__), "..", "acalib", "alloc")
    
    # 1. Assert no unpopulated get_edge_marginals() calls in acalib/alloc
    for fname in os.listdir(alloc_dir):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(alloc_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            # Must not contain "get_edge_marginals()" with no arguments
            bad_calls = re.findall(r"get_edge_marginals\(\s*\)", content)
            assert len(bad_calls) == 0, f"Found unpopulated get_edge_marginals() in {fname}: {bad_calls}"

    # 2. In acalib/alloc/aca.py, check get_hazard_under_type passes edge_robot_count
    aca_path = os.path.join(alloc_dir, "aca.py")
    with open(aca_path, "r", encoding="utf-8") as f:
        aca_code = f.read()
        # Find calls to get_hazard_under_type
        matches = re.findall(r"get_hazard_under_type\(([^)]+)\)", aca_code)
        assert len(matches) > 0, "Expected get_hazard_under_type calls in aca.py"
        for call_args in matches:
            assert "edge_robot_count" in call_args, f"Call lacks edge_robot_count: get_hazard_under_type({call_args})"
            assert "is_targeted_by_interdiction" in call_args, f"Call lacks is_targeted_by_interdiction: get_hazard_under_type({call_args})"
