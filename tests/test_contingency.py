"""Verification of Theorem 1: Exact Expected-Recourse Cost Valuation vs Monte Carlo."""

import networkx as nx
import numpy as np

from acalib.agents.contingency import ContingencyPlanner
from acalib.env.adversaries import canonical_edge


def test_theorem_1_expected_cost_vs_monte_carlo():
    """
    Theorem 1 Verification:
    Compare analytical expected cost formula against 20,000 Monte Carlo trials.
    Sample mean should match analytical expected cost within 3 standard errors.
    """
    g = nx.Graph()
    # Construct a diamond graph with risky primary edge and detour:
    # 0 -> 1 -> 3 (primary path, edge (1,3) is risky)
    # 1 -> 2 -> 3 (detour)
    g.add_node(0, pos=(0, 0))
    g.add_node(1, pos=(10, 0))
    g.add_node(2, pos=(20, 10))
    g.add_node(3, pos=(30, 0))

    g.add_edge(0, 1, weight=10.0, length=10.0)
    g.add_edge(1, 3, weight=20.0, length=20.0)  # Primary risky edge
    g.add_edge(1, 2, weight=15.0, length=15.0)  # Detour part 1
    g.add_edge(2, 3, weight=15.0, length=15.0)  # Detour part 2

    planner = ContingencyPlanner(g, max_depth=1, risk_weight=0.0)
    risky_edge = canonical_edge(1, 3)
    pi_blockage = 0.35  # 35% probability of blockage on (1, 3)

    marginals = {
        risky_edge: pi_blockage,
        canonical_edge(0, 1): 0.0,
        canonical_edge(1, 2): 0.0,
        canonical_edge(2, 3): 0.0,
    }

    plan = planner.build_recourse_plan(
        task_id=1,
        start_node=0,
        target_node=3,
        edge_marginals=marginals,
        risky_edge_threshold=0.1,
    )

    assert plan is not None
    analytical_expected_cost = plan.expected_cost

    # Nominal cost = 10 + 20 = 30
    # Detour cost = 10 + 15 + 15 = 40
    # Exact E[C] = (1 - pi) * 30 + pi * 40 = 0.65 * 30 + 0.35 * 40 = 19.5 + 14 = 33.5
    assert np.isclose(analytical_expected_cost, 33.5, atol=1e-3)

    # Monte Carlo simulation: 20,000 trials
    rng = np.random.default_rng(42)
    n_trials = 20000
    mc_costs = []

    for _ in range(n_trials):
        is_blocked = rng.random() < pi_blockage
        if not is_blocked:
            mc_costs.append(30.0)
        else:
            mc_costs.append(40.0)

    sample_mean = float(np.mean(mc_costs))
    std_err = float(np.std(mc_costs) / np.sqrt(n_trials))

    # Test within 3 standard errors (99.7% confidence interval)
    diff = abs(sample_mean - analytical_expected_cost)
    assert diff <= 3 * std_err, (
        f"Analytical {analytical_expected_cost} differs from MC {sample_mean} "
        f"by {diff} > 3 * SE ({3 * std_err})"
    )
