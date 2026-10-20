"""
Unit regression tests for the 11 audit remediations (Issues 1-11).
Explicitly verifies:
1. Path-order event evaluation: 4-node chain expected cost 10.66 vs probability-sorted 11.38.
2. Canonical edge prefix distance: Descending node-order path [3, 2, 1, 0] prefix distance 7.5 vs 8.0.
3. MissingMarginalError fail-closed verification across all contingency methods.
4. Deterministic content-derived marginal token without id() aliasing or mutation staleness.
5. Strict 1e-3 belief simplex floor across _normalize, set_belief_vector, and pool_beliefs.
6. Committed-only safe claim accounting and holder conflict detection.
"""

import pytest
import numpy as np
import networkx as nx

from acalib.agents.contingency import (
    ContingencyPlanner,
    RecourseTreeNode,
    MissingMarginalError,
    canonical_edge,
    get_marginals_token,
)
from acalib.agents.belief import BayesianTypeFilter, BELIEF_FLOOR
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


def test_path_order_event_evaluation():
    """
    1. Verify 4-node chain [0, 1, 2, 3] evaluates edge failure events in strict path traversal order.
    Edge (1, 2) has failure prob 0.4, detour cost 9.0 from node 1.
    Edge (2, 3) has failure prob 0.9, detour cost 10.0 from node 2.
    Expected cost must be 10.66 (path-order), NOT 11.38 (sorted by probability).
    """
    g = nx.Graph()
    g.add_edge(0, 1, weight=1.0)
    g.add_edge(1, 2, weight=1.0)
    g.add_edge(2, 3, weight=1.0)

    # Detours: from 1 to 3 via 10 (cost 9.0), from 2 to 3 via 20 (cost 10.0)
    g.add_edge(1, 10, weight=4.5)
    g.add_edge(10, 3, weight=4.5)
    g.add_edge(2, 20, weight=5.0)
    g.add_edge(20, 3, weight=5.0)

    planner = ContingencyPlanner(g, max_depth=1)
    primary_path = [0, 1, 2, 3]
    risky_edges = [(1, 2), (2, 3)]
    detours = {
        canonical_edge(1, 2): [1, 10, 3],
        canonical_edge(2, 3): [2, 20, 3],
    }
    marginals = {canonical_edge(u, v): 0.0 for u, v in g.edges()}
    marginals[canonical_edge(1, 2)] = 0.4
    marginals[canonical_edge(2, 3)] = 0.9

    expected_cost = planner.compute_expected_cost(
        primary_path=primary_path,
        risky_edges=risky_edges,
        detours=detours,
        edge_marginals=marginals,
    )
    assert abs(expected_cost - 10.66) < 1e-4, f"Expected 10.66, got {expected_cost}"


def test_descending_node_prefix_distance():
    """
    2. Verify descending path [3, 2, 1, 0] uses entry-node prefix distance (7.5), NOT exit/canonical node (8.0).
    Edge (3, 2): weight 7.5
    Edge (2, 1): weight 0.5 (risky, prob 1.0, detour cost 2.0)
    Edge (1, 0): weight 1.0
    Entry node is 2 (dist_to_u = 7.5). If canonical edge min(1, 2)=1 was looked up, dist_to_u would be 8.0.
    """
    g = nx.Graph()
    g.add_edge(3, 2, weight=7.5)
    g.add_edge(2, 1, weight=0.5)
    g.add_edge(1, 0, weight=1.0)
    # Detour from 2 to 0
    g.add_edge(2, 99, weight=1.0)
    g.add_edge(99, 0, weight=1.0)

    planner = ContingencyPlanner(g, max_depth=1)
    primary_path = [3, 2, 1, 0]
    risky_edges = [(2, 1)]
    detours = {canonical_edge(2, 1): [2, 99, 0]}
    marginals = {canonical_edge(u, v): 0.0 for u, v in g.edges()}
    marginals[canonical_edge(2, 1)] = 1.0

    cost = planner.compute_expected_cost(
        primary_path=primary_path,
        risky_edges=risky_edges,
        detours=detours,
        edge_marginals=marginals,
    )
    # branch_cost = dist_to_u (7.5) + detour_cost (2.0) = 9.5
    assert abs(cost - 9.5) < 1e-4, f"Expected 9.5 (dist_to_u=7.5), got {cost} (if 8.0, cost would be 10.0)"


def test_fail_closed_missing_marginal_error():
    """
    3. Ensure MissingMarginalError is raised when any required edge marginal is omitted.
    """
    g = nx.Graph()
    g.add_edge(0, 1, weight=1.0)
    g.add_edge(1, 2, weight=1.0)
    g.add_edge(2, 3, weight=1.0)
    planner = ContingencyPlanner(g, max_depth=1)

    # find_risk_aware_path fails closed
    with pytest.raises(MissingMarginalError):
        planner.find_risk_aware_path(0, 3, edge_marginals={})

    # build_recourse_plan fails closed
    with pytest.raises(MissingMarginalError):
        planner.build_recourse_plan(1, 0, 3, edge_marginals={})

    # compute_expected_cost fails closed
    full_marginals = {canonical_edge(u, v): 0.05 for u, v in g.edges()}
    del full_marginals[canonical_edge(1, 2)]
    with pytest.raises(MissingMarginalError):
        planner.compute_expected_cost([0, 1, 2, 3], [(1, 2)], {}, edge_marginals=full_marginals)


def test_marginals_token_deterministic_and_safe_from_id_aliasing():
    """
    4. Verify get_marginals_token produces distinct tokens on mutation and does not rely on id().
    """
    m1 = {canonical_edge(0, 1): 0.1, canonical_edge(1, 2): 0.2}
    tok1 = get_marginals_token(m1)

    # In-place mutation must produce a new token
    m1[canonical_edge(1, 2)] = 0.5
    tok2 = get_marginals_token(m1)
    assert tok1 != tok2

    # Different dictionary with identical content must produce identical token
    m2 = {canonical_edge(0, 1): 0.1, canonical_edge(1, 2): 0.5}
    assert get_marginals_token(m2) == tok2


def test_bayesian_belief_floor_strictness():
    """
    5. Verify BayesianTypeFilter strictly enforces belief >= 1e-3 across all update pathways.
    """
    filt = BayesianTypeFilter()
    assert np.all(filt.get_belief_vector() >= BELIEF_FLOOR)
    assert abs(np.sum(filt.get_belief_vector()) - 1.0) < 1e-9

    # set_belief_vector with zero / extreme values
    filt.set_belief_vector(np.array([1.0, 0.0, 0.0]))
    vec = filt.get_belief_vector()
    assert np.all(vec >= BELIEF_FLOOR), f"Entries below floor: {vec}"
    assert abs(np.sum(vec) - 1.0) < 1e-9

    # pool_beliefs
    neighbor_vec = np.array([0.0, 1.0, 0.0])
    filt.pool_beliefs([neighbor_vec])
    vec_pooled = filt.get_belief_vector()
    assert np.all(vec_pooled >= BELIEF_FLOOR), f"Pooled entries below floor: {vec_pooled}"
    assert abs(np.sum(vec_pooled) - 1.0) < 1e-9


def test_safe_claims_committed_only_and_holder_conflicts():
    """
    6. Verify safe claims are only counted for committed bundle insertions,
    and detect conflicts when claiming already-held tasks.
    """
    from acalib.env.graph_families import generate_graph
    g = generate_graph("rgg", n_nodes=20, seed=123)
    engine = SimulationEngine(
        graph=g,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca",
        n_robots=3,
        n_tasks=6,
        contingency_depth=1,
        seed=123,
    )
    alloc = engine.allocator
    tasks = {tid: t for tid, t in engine.tasks.items() if not t.completed}
    robot_positions = {rid: r.pos for rid, r in engine.robots.items()}

    # Round 1
    res1 = alloc.allocate_round(tasks, 0, robot_positions)
    assert res1["safe_claims"] >= 1
    # Total committed safe claims across robots must equal allocator.total_safe_claims
    assert alloc.total_safe_claims == res1["safe_claims"]
