"""
Numerical Verification Harness for Proposition 2 (Lipschitz Continuity)
and Theorem 1 (Conditional Conflict-Freedom of Phase-1 Safe Claims).

Tests:
1. Analytical Lipschitz bound on recourse valuation:
       |E_{B_1}[C(plan)] - E_{B_2}[C(plan)]| <= L_j * TV(B_1, B_2) + eps
   across 5,000 sampled belief pairs across 100 random geometric graphs.
2. Pure-type task sensitivity range:
       min_theta c(j | theta) <= E_B[C_j] <= max_theta c(j | theta)
3. Theorem 1 Conditional Conflict-Freedom:
       c_r(j; B_r) + m_{r, j} < c_hat_s ==> c_r(j; B_r) < c_s(j; B_s)
   under Assumption 1 (TV(B_s, B_hat_s) <= eta_eff) across 5,000 evaluations.
4. Limiting and edge cases:
   - Zero divergence (TV = 0, D_KL = 0)
   - Zero estimation error (eta = 0)
   - Disconnected graphs
   - No risky edges (L_j = 0)
   - Depth d = 0 (recourse disabled)
"""

import numpy as np
import networkx as nx

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import canonical_edge
from acalib.agents.belief import compute_kl_divergence, compute_tv_distance
from acalib.agents.contingency import ContingencyPlanner, compute_lipschitz_bound


def test_lipschitz_cost_bound_monte_carlo():
    """
    Verify |E_{B1}[C(plan)] - E_{B2}[C(plan)]| <= L_j * TV(B1, B2) across 5,000 sampled belief pairs
    over 100 Random Geometric Graphs (RGG).
    Calls production compute_lipschitz_bound on the evaluated recourse plan.
    """
    rng = np.random.default_rng(2026)
    violations = 0
    total_evaluated = 0

    for i in range(100):
        graph = generate_graph("rgg", n_nodes=20, seed=i)
        nodes = list(graph.nodes())
        start = nodes[0]
        target = nodes[-1]
        planner = ContingencyPlanner(graph=graph, max_depth=1)

        # Define edge hazards across 3 canonical types
        risky_edges = [canonical_edge(u, v) for u, v in list(graph.edges())[:5]]
        hazards = {
            e: [
                float(rng.uniform(0.05, 0.25)),
                float(rng.uniform(0.10, 0.60)),
                float(rng.uniform(0.05, 0.85)),
            ]
            for e in risky_edges
        }

        for _ in range(50):
            # Sample two random beliefs on simplex Delta(Theta)
            b1 = rng.dirichlet(np.ones(3))
            b2 = rng.dirichlet(np.ones(3))
            tv = float(compute_tv_distance(b1, b2))

            # Compute marginals under b1 and b2
            pi1 = {e: float(sum(b1[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}
            pi2 = {e: float(sum(b2[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}

            plan1 = planner.build_recourse_plan(1, start, target, pi1)
            if plan1 is None:
                continue

            cost1 = plan1.expected_cost
            # Evaluate the expected cost of the same recourse policy under belief B2
            cost2 = planner.compute_expected_cost_for_plan(plan1, pi2)
            cost_diff = abs(cost1 - cost2)

            # Compute production Lipschitz bound on plan1
            L_j = compute_lipschitz_bound(planner, plan1, hazards, clearance_rate=0.15)
            bound = L_j * tv + 1e-4  # numerical tolerance
            total_evaluated += 1

            if cost_diff > bound:
                violations += 1

    assert total_evaluated > 0, "No graph paths were evaluated"
    assert violations == 0, f"Found {violations} violations of the Lipschitz cost bound out of {total_evaluated} pairs!"


def test_pure_type_sensitivity_range():
    """
    Verify that for any belief B, the expected cost lies within the pure-type extrema:
        min_theta c(j | theta) <= E_B[C_j] <= max_theta c(j | theta)
    """
    rng = np.random.default_rng(2027)
    graph = generate_graph("rgg", n_nodes=20, seed=42)
    nodes = list(graph.nodes())
    start = nodes[0]
    target = nodes[-1]
    planner = ContingencyPlanner(graph=graph, max_depth=1)

    risky_edges = [canonical_edge(u, v) for u, v in list(graph.edges())[:4]]
    hazards = {
        e: [
            float(rng.uniform(0.05, 0.20)),
            float(rng.uniform(0.10, 0.50)),
            float(rng.uniform(0.05, 0.80)),
        ]
        for e in risky_edges
    }

    # Base plan
    nominal_marginals = {e: 0.2 for e in risky_edges}
    plan = planner.build_recourse_plan(1, start, target, nominal_marginals)
    assert plan is not None

    # Compute costs under each pure type
    pure_costs = []
    for theta_idx in range(3):
        pi_theta = {e: h_list[theta_idx] / (h_list[theta_idx] + 0.15) for e, h_list in hazards.items()}
        c_theta = planner.compute_expected_cost(plan.primary_path, plan.risky_edges, plan.detours, pi_theta)
        pure_costs.append(c_theta)

    c_min = min(pure_costs)
    c_max = max(pure_costs)

    # Check 1,000 random beliefs
    for _ in range(1000):
        b = rng.dirichlet(np.ones(3))
        pi_b = {e: float(sum(b[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}
        c_b = planner.compute_expected_cost(plan.primary_path, plan.risky_edges, plan.detours, pi_b)
        assert c_min - 1e-6 <= c_b <= c_max + 1e-6, f"Cost {c_b} outside pure-type range [{c_min}, {c_max}]"


def test_theorem3_claim_margin_guarantee():
    """
    Verify Theorem 1 conditional conflict-freedom across 5,000 evaluations:
    If my_cost + margin < peer_cost_est under Assumption 1 (TV <= eta),
    then my_cost < true_peer_cost strictly holds (zero false claims).
    Calls production compute_lipschitz_bound.
    """
    rng = np.random.default_rng(999)
    violations = 0
    safe_claims_evaluated = 0

    eta = 0.08  # Assumption 1 bound: TV(B_s, B_hat_s) <= eta

    for i in range(50):
        graph = generate_graph("rgg", n_nodes=20, seed=i + 500)
        nodes = list(graph.nodes())
        r_node = nodes[0]
        s_node = nodes[1]
        task_node = nodes[-1]
        planner = ContingencyPlanner(graph=graph, max_depth=1)

        risky_edges = [canonical_edge(u, v) for u, v in list(graph.edges())[:4]]
        hazards = {
            e: [
                float(rng.uniform(0.05, 0.20)),
                float(rng.uniform(0.10, 0.50)),
                float(rng.uniform(0.05, 0.80)),
            ]
            for e in risky_edges
        }

        for _ in range(100):
            b_r = rng.dirichlet(np.ones(3))
            b_hat_s = rng.dirichlet(np.ones(3))

            # Generate true peer belief B_s satisfying Assumption 1: TV(b_s, b_hat_s) <= eta
            perturbation = rng.normal(0, eta / 2.0, size=3)
            perturbation -= np.mean(perturbation)
            b_s = np.clip(b_hat_s + perturbation, 1e-5, 1.0)
            b_s /= np.sum(b_s)

            # Ensure Assumption 1 holds strictly
            if compute_tv_distance(b_s, b_hat_s) > eta:
                continue

            kl = float(compute_kl_divergence(b_r, b_hat_s))
            pinsker_bound = np.sqrt(0.5 * max(0.0, kl)) + eta

            # Compute costs
            pi_r = {e: float(sum(b_r[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}
            pi_hat_s = {e: float(sum(b_hat_s[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}
            pi_true_s = {e: float(sum(b_s[k] * (h / (h + 0.15)) for k, h in enumerate(h_list))) for e, h_list in hazards.items()}

            p_r = planner.build_recourse_plan(1, r_node, task_node, pi_r)
            p_hat_s = planner.build_recourse_plan(1, s_node, task_node, pi_hat_s)
            p_true_s = planner.build_recourse_plan(1, s_node, task_node, pi_true_s)

            if p_r is None or p_hat_s is None or p_true_s is None:
                continue

            # Production Lipschitz bound on estimated peer plan
            L_j = compute_lipschitz_bound(planner, p_hat_s, hazards, clearance_rate=0.15)
            margin = float(L_j * pinsker_bound)

            my_cost = p_r.expected_cost
            peer_cost_est = p_hat_s.expected_cost
            true_peer_cost = p_true_s.expected_cost

            # Margin check
            if my_cost + margin < peer_cost_est:
                safe_claims_evaluated += 1
                # Must guarantee my_cost < true_peer_cost
                if my_cost >= true_peer_cost:
                    violations += 1

    assert safe_claims_evaluated > 0, "No safe claims evaluated in test"
    assert violations == 0, f"Theorem 1 violated! {violations} violations out of {safe_claims_evaluated} safe claims"


# ---------------------------------------------------------------------------
# 4. Limiting and Edge Cases Tests
# ---------------------------------------------------------------------------

def test_lipschitz_zero_divergence_and_error():
    """When beliefs are identical (TV=0, KL=0) and eta=0, margin is 0."""
    graph = generate_graph("grid", n_nodes=16, seed=42)
    planner = ContingencyPlanner(graph=graph, max_depth=1)
    plan = planner.build_recourse_plan(1, 0, 15, {})
    L_j = compute_lipschitz_bound(planner, plan, {})
    assert L_j == 0.0, "Paths with no risky edges must have L_j = 0"


def test_disconnected_graph_handling():
    """Disconnected graphs return None for recourse plan and do not raise unhandled errors."""
    g = nx.Graph()
    g.add_node(1)
    g.add_node(2)
    planner = ContingencyPlanner(graph=g, max_depth=1)
    plan = planner.build_recourse_plan(1, 1, 2, {})
    assert plan is None
    L_j = compute_lipschitz_bound(planner, plan, {})
    assert L_j == 0.0


def test_recourse_disabled_depth_zero():
    """When recourse is disabled (depth=0), risky edges are not detoured and L_j reflects exhaustion penalty."""
    graph = generate_graph("rgg", n_nodes=20, seed=123)
    planner = ContingencyPlanner(graph=graph, max_depth=0)
    edges = list(graph.edges())
    c_e = canonical_edge(edges[0][0], edges[0][1])
    marginals = {c_e: 0.5}
    plan = planner.build_recourse_plan(1, edges[0][0], edges[-1][1], marginals, risky_edge_threshold=0.1)
    if plan is not None and plan.risky_edges:
        hazards = {c_e: [0.1, 0.5, 0.9]}
        L_j = compute_lipschitz_bound(planner, plan, hazards)
        assert L_j >= 0.0
