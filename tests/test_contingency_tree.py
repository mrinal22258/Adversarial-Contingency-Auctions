"""Unit and regression tests for recursive depth-d recourse trees and Lipschitz bound."""
import pytest
import networkx as nx
import numpy as np

from acalib.agents.contingency import (
    ContingencyPlanner,
    RecoursePlan,
    canonical_edge,
    compute_lipschitz_bound,
)


def create_two_level_corridor_graph():
    """
    Creates a 2-level blockage benchmark graph:
    Primary path: 0 -(1)-> 1 -(1)-> 3 (primary edges (0, 1) and (1, 3))
    Edge (1, 3) is risky (pi=0.4).
    Detour 1 from 1: 1 -(1)-> 2 -(1)-> 3 (detour edges (1, 2) and (2, 3))
    Edge (2, 3) is ALSO risky (pi=0.5).
    Secondary detour from 2: 2 -(2)-> 4 -(1)-> 3 (edges (2, 4) and (4, 3))
    """
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 3, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    G.add_edge(2, 4, weight=2.0)
    G.add_edge(4, 3, weight=1.0)
    return G


def test_excluded_edge_returns_none_not_1e9():
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    planner = ContingencyPlanner(G, max_depth=1)
    
    # Exclude the only edge
    path = planner.find_risk_aware_path(0, 1, {(0, 1): 0.0}, excluded_edges={(0, 1)})
    assert path is None, f"Expected None when only path is blocked, got {path}"


def test_recursive_tree_depth_branching():
    G = create_two_level_corridor_graph()
    marginals = {
        (0, 1): 0.0,
        (1, 3): 0.40,
        (1, 2): 0.0,
        (2, 3): 0.50,
        (2, 4): 0.0,
        (4, 3): 0.0,
    }
    
    planner_d0 = ContingencyPlanner(G, max_depth=0, exhaustion_penalty=10.0)
    planner_d1 = ContingencyPlanner(G, max_depth=1, exhaustion_penalty=10.0)
    planner_d2 = ContingencyPlanner(G, max_depth=2, exhaustion_penalty=10.0)
    
    plan_d0 = planner_d0.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    plan_d1 = planner_d1.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    plan_d2 = planner_d2.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    
    assert plan_d0 is not None
    assert plan_d1 is not None
    assert plan_d2 is not None
    
    # Depth 0 has 0 detours
    assert len(plan_d0.detours) == 0
    # Depth 1 plans detour for (1, 3)
    assert (1, 3) in plan_d1.detours
    assert (2, 3) not in plan_d1.detours
    # Depth 2 plans detours for both (1, 3) and (2, 3)
    assert (1, 3) in plan_d2.detours
    assert (2, 3) in plan_d2.detours
    
    # Expected cost comparison: Depth 2 strictly differs from Depth 1
    assert not np.isclose(plan_d2.expected_cost, plan_d1.expected_cost)
    
    # Hand-derived oracle:
    # d1 expected cost = (1 - 0.4) * 2.0 + 0.4 * (1.0 + 2.0) = 1.2 + 1.2 = 2.4
    # d2 expected cost = (1 - 0.4) * 2.0 + 0.4 * (1.0 + 0.5 * 1.0 + 0.5 * 3.0) = 1.2 + 1.6 = 2.8
    assert np.isclose(plan_d1.expected_cost, 2.4, atol=1e-3)
    assert np.isclose(plan_d2.expected_cost, 2.8, atol=1e-3)


def test_pure_type_lipschitz_bound_exact():
    G = create_two_level_corridor_graph()
    planner = ContingencyPlanner(G, max_depth=2, exhaustion_penalty=10.0)
    
    hazards = {
        (1, 3): [0.05, 0.20, 0.60],
        (2, 3): [0.10, 0.40, 0.70],
    }
    
    nominal_marginals = {
        (0, 1): 0.0,
        (1, 3): 0.25,
        (1, 2): 0.0,
        (2, 3): 0.35,
        (2, 4): 0.0,
        (4, 3): 0.0,
    }
    plan = planner.build_recourse_plan(1, 0, 3, nominal_marginals, risky_edge_threshold=0.12)
    assert plan is not None
    
    L = compute_lipschitz_bound(planner, plan, hazards, clearance_rate=0.15)
    assert L > 0.0
    
    # Sample 1,000 random belief pairs and verify |V1 - V2| <= L * TV(B1, B2)
    rng = np.random.default_rng(2026)
    violations = 0
    for _ in range(1000):
        b1 = rng.dirichlet(np.ones(3))
        b2 = rng.dirichlet(np.ones(3))
        tv = 0.5 * np.sum(np.abs(b1 - b2))
        
        pi1 = {
            (0, 1): 0.0,
            (1, 2): 0.0,
            (2, 4): 0.0,
            (4, 3): 0.0,
            **{e: float(sum(b1[k] * (h / (h + 0.15)) for k, h in enumerate(hl))) for e, hl in hazards.items()},
        }
        pi2 = {
            (0, 1): 0.0,
            (1, 2): 0.0,
            (2, 4): 0.0,
            (4, 3): 0.0,
            **{e: float(sum(b2[k] * (h / (h + 0.15)) for k, h in enumerate(hl))) for e, hl in hazards.items()},
        }
        
        c1 = planner.compute_expected_cost_for_plan(plan, pi1)
        c2 = planner.compute_expected_cost_for_plan(plan, pi2)
        diff = abs(c1 - c2)
        
        if diff > L * tv + 1e-6:
            violations += 1
            
    assert violations == 0, f"Lipschitz bound had {violations} violations!"


def test_missing_hazard_raises_value_error():
    G = create_two_level_corridor_graph()
    planner = ContingencyPlanner(G, max_depth=1)
    marginals = {canonical_edge(*e): (0.3 if canonical_edge(*e) == (1, 3) else 0.0) for e in G.edges()}
    plan = planner.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    
    # Missing hazard entry for risky edge (1, 3) must raise ValueError
    with pytest.raises(ValueError, match="Missing hazard"):
        compute_lipschitz_bound(planner, plan, {}, clearance_rate=0.15)
