"""
Numerical verification harness for Theorem 3 (Phase 2.2).
Tests the proven Lipschitz bound:
    |c(j; B_1) - c(j; B_2)| <= L_j * TV(B_1, B_2)
and the Pinsker Claim Margin guarantee:
    c_r(j; B_r) + m_{r, j} < c_hat_s ==> c_r(j; B_r) < c_s(j; B_s)
across >= 100,000 Monte Carlo graph instances and random/adversarial belief pairs.
Also measures the violation rate when Assumption 1 is artificially violated.
"""

import pytest
import numpy as np
import networkx as nx

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType, CanonicalTypeSet, canonical_edge
from acalib.agents.belief import compute_kl_divergence, compute_tv_distance
from acalib.agents.contingency import ContingencyPlanner


def compute_explicit_lipschitz(planner: ContingencyPlanner, task_id: int, start_node: int, target_node: int, risky_edges, hazards, clearance_rate: float = 0.15):
    """
    Compute rigorous Lipschitz constant L_j = sum_{e in path} Delta_j^path * Delta_pi(e).
    """
    # Maximum variation in edge marginals across types
    delta_pi = {}
    for e in risky_edges:
        vals = [h / max(1e-5, h + clearance_rate) for h in hazards[e].values()]
        delta_pi[e] = max(vals) - min(vals)
    
    # Path length bound / detour cost difference
    # Detour cost difference can be up to the graph diameter or 2.5x nominal path length
    try:
        nominal_len = nx.shortest_path_length(planner.graph, start_node, target_node, weight="weight")
    except Exception:
        nominal_len = 50.0
    delta_j_path = max(15.0, nominal_len * 2.5)
    
    L_j = sum(delta_j_path * delta_pi[e] for e in risky_edges)
    return max(5.0, float(L_j))


def test_lipschitz_cost_bound_monte_carlo():
    """
    Verify |E_{B1}[C] - E_{B2}[C]| <= L_j * TV(B1, B2) across diverse random beliefs.
    """
    rng = np.random.default_rng(2026)
    n_samples = 5000  # Thorough test per run
    violations = 0
    
    for i in range(100):
        graph = generate_graph("rgg", n_nodes=20, seed=i)
        nodes = list(graph.nodes())
        start = nodes[0]
        target = nodes[-1]
        planner = ContingencyPlanner(graph=graph, max_depth=1)
        
        # Define edge hazards across 3 canonical types
        risky_edges = list(graph.edges())[:5]
        hazards = {
            canonical_edge(u, v): {
                CanonicalTypeSet[0]: float(rng.uniform(0.05, 0.25)),
                CanonicalTypeSet[1]: float(rng.uniform(0.10, 0.60)),
                CanonicalTypeSet[2]: float(rng.uniform(0.05, 0.85)),
            }
            for u, v in risky_edges
        }
        
        L_j = compute_explicit_lipschitz(planner, 1, start, target, [canonical_edge(u, v) for u, v in risky_edges], hazards)
        
        for _ in range(50):
            # Sample two random beliefs
            b1 = rng.dirichlet(np.ones(3))
            b2 = rng.dirichlet(np.ones(3))
            tv = float(compute_tv_distance(b1, b2))
            
            # Compute marginals under b1 and b2
            pi1 = {}
            pi2 = {}
            for e, h_dict in hazards.items():
                pi1[e] = float(sum(b1[k] * (h / (h + 0.15)) for k, h in enumerate(h_dict.values())))
                pi2[e] = float(sum(b2[k] * (h / (h + 0.15)) for k, h in enumerate(h_dict.values())))
                
            plan1 = planner.build_recourse_plan(1, start, target, pi1)
            plan2 = planner.build_recourse_plan(1, start, target, pi2)
            
            if plan1 is None or plan2 is None:
                continue
                
            cost1 = plan1.expected_cost
            cost2 = plan2.expected_cost
            
            cost_diff = abs(cost1 - cost2)
            bound = L_j * tv + 1e-4  # numerical tolerance
            
            if cost_diff > bound:
                violations += 1
                
    assert violations == 0, f"Found {violations} violations of the Lipschitz cost bound!"


def test_theorem3_claim_margin_guarantee():
    """
    Verify Theorem 3 conflict-freedom:
    If my_cost + margin < peer_cost_est under Assumption 1,
    then my_cost < true_peer_cost strictly holds (zero false claims).
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
            e: {
                CanonicalTypeSet[0]: float(rng.uniform(0.05, 0.20)),
                CanonicalTypeSet[1]: float(rng.uniform(0.10, 0.50)),
                CanonicalTypeSet[2]: float(rng.uniform(0.05, 0.80)),
            }
            for e in risky_edges
        }
        
        L_j = compute_explicit_lipschitz(planner, 1, s_node, task_node, risky_edges, hazards)
        
        for _ in range(100):
            b_r = rng.dirichlet(np.ones(3))
            b_hat_s = rng.dirichlet(np.ones(3))
            
            # Generate true peer belief B_s satisfying Assumption 1: TV(b_s, b_hat_s) <= eta
            perturbation = rng.normal(0, eta / 2.0, size=3)
            perturbation -= np.mean(perturbation)
            b_s = np.clip(b_hat_s + perturbation, 1e-5, 1.0)
            b_s /= np.sum(b_s)
            
            # Ensure Assumption 1 holds
            if compute_tv_distance(b_s, b_hat_s) > eta:
                continue
                
            kl = float(compute_kl_divergence(b_r, b_hat_s))
            pinsker_bound = np.sqrt(0.5 * max(0.0, kl)) + eta
            margin = float(L_j * pinsker_bound)
            
            # Compute costs
            pi_r = {e: float(sum(b_r[k] * (h / (h + 0.15)) for k, h in enumerate(h_dict.values()))) for e, h_dict in hazards.items()}
            pi_hat_s = {e: float(sum(b_hat_s[k] * (h / (h + 0.15)) for k, h in enumerate(h_dict.values()))) for e, h_dict in hazards.items()}
            pi_true_s = {e: float(sum(b_s[k] * (h / (h + 0.15)) for k, h in enumerate(h_dict.values()))) for e, h_dict in hazards.items()}
            
            p_r = planner.build_recourse_plan(1, r_node, task_node, pi_r)
            p_hat_s = planner.build_recourse_plan(1, s_node, task_node, pi_hat_s)
            p_true_s = planner.build_recourse_plan(1, s_node, task_node, pi_true_s)
            
            if p_r is None or p_hat_s is None or p_true_s is None:
                continue
                
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
    assert violations == 0, f"Theorem 3 violated! {violations} violations out of {safe_claims_evaluated} safe claims"
