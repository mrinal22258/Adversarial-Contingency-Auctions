"""Unit tests for Bayesian filtering, belief convergence, and marginal calculation."""

import numpy as np

from acalib.agents.belief import (
    BayesianTypeFilter,
    compute_tv_distance,
)
from acalib.env.adversaries import AdversaryType, CanonicalTypeSet
from acalib.env.blockage_process import EdgeState


def test_no_double_counting_observations():
    """Verify that duplicate observations at the same step do not double-update posterior (Audit Bug 5)."""
    filter_inst = BayesianTypeFilter()
    b_initial = filter_inst.get_belief_vector().copy()

    # First update
    filter_inst.update_observation(
        step=1,
        edge=(0, 1),
        observed_state=EdgeState.BLOCKED,
        prior_state=EdgeState.OPEN,
    )
    b_after_first = filter_inst.get_belief_vector().copy()
    assert not np.allclose(b_initial, b_after_first), "Belief should change on observation"

    # Second call with identical step and edge
    filter_inst.update_observation(
        step=1,
        edge=(0, 1),
        observed_state=EdgeState.BLOCKED,
        prior_state=EdgeState.OPEN,
    )
    b_after_second = filter_inst.get_belief_vector().copy()
    assert np.allclose(b_after_first, b_after_second), "Duplicate observation at same step should be ignored"


def test_posterior_concentration():
    """Verify Theorem 2 posterior concentration: informative observations concentrate belief on true type."""
    filter_inst = BayesianTypeFilter()
    rng = np.random.default_rng(42)

    # Simulate sequence of observations consistent with Reactive adversary (high hazard when robot count > 0)
    for step in range(1, 40):
        # High traffic edge transitions to blocked frequently
        robot_count = 2.0
        h_true = min(1.0, 0.05 + 0.35 * robot_count)
        obs_state = EdgeState.BLOCKED if rng.random() < h_true else EdgeState.OPEN

        filter_inst.update_observation(
            step=step,
            edge=(step, step + 1),
            observed_state=obs_state,
            prior_state=EdgeState.OPEN,
            edge_robot_count=robot_count,
        )

    b_vec = filter_inst.get_belief_vector()
    # Canonical types: [stochastic, reactive, budgeted_interdiction]
    reactive_idx = CanonicalTypeSet.index(AdversaryType.REACTIVE)
    assert b_vec[reactive_idx] > 0.50, f"Belief should concentrate on reactive type, got {b_vec}"


def test_edge_marginal_calculation():
    """Verify edge marginal pi_r(e) is bounded in [0, 1] and reflects Bayesian expectation."""
    filter_inst = BayesianTypeFilter()
    # Equal prior
    pi_idle = filter_inst.compute_edge_marginal((0, 1), edge_robot_count=0.0)
    pi_crowded = filter_inst.compute_edge_marginal((0, 1), edge_robot_count=3.0)

    assert 0.01 <= pi_idle <= 0.99
    assert pi_crowded > pi_idle, "Marginal risk should increase with traffic"


def test_belief_pooling():
    """Verify log-linear belief pooling converges beliefs between agents."""
    agent1 = BayesianTypeFilter()
    agent2 = BayesianTypeFilter()

    agent1.set_belief_vector(np.array([0.8, 0.1, 0.1]))
    agent2.set_belief_vector(np.array([0.1, 0.8, 0.1]))

    v1 = agent1.get_belief_vector()
    v2 = agent2.get_belief_vector()
    init_tv = compute_tv_distance(v1, v2)

    # Pool beliefs
    agent1.pool_beliefs([v2], weights=[0.5, 0.5])
    agent2.pool_beliefs([v1], weights=[0.5, 0.5])

    pooled_tv = compute_tv_distance(agent1.get_belief_vector(), agent2.get_belief_vector())
    assert pooled_tv < init_tv, "Pooling must strictly reduce belief disagreement"


def test_set_oracle_rejects_unsupported_types():
    """Verify P1-05: set_oracle explicitly rejects out-of-model types like CYCLIC_PATROL."""
    import pytest
    agent = BayesianTypeFilter()
    
    # Valid canonical type succeeds and freezes
    agent.set_oracle(AdversaryType.STOCHASTIC)
    assert agent.frozen
    b = agent.get_belief_vector()
    assert b[CanonicalTypeSet.index(AdversaryType.STOCHASTIC)] == 1.0

    # Unsupported type must raise ValueError, not silently collapse to uniform
    with pytest.raises(ValueError, match="Unsupported oracle adversary type"):
        agent.set_oracle(AdversaryType.CYCLIC_PATROL)


def test_calibration_brier_and_reliability():
    """Verify calibration metrics (Brier score and reliability curve)."""
    from acalib.agents.belief import compute_brier_score, compute_reliability_curve

    forecasts = np.array([0.9, 0.8, 0.2, 0.1])
    outcomes = np.array([1.0, 1.0, 0.0, 0.0])

    bs = compute_brier_score(forecasts, outcomes)
    # Mean of (0.1^2, 0.2^2, 0.2^2, 0.1^2) = (0.01 + 0.04 + 0.04 + 0.01) / 4 = 0.025
    assert np.isclose(bs, 0.025)

    centers, freqs, counts = compute_reliability_curve(forecasts, outcomes, n_bins=2)
    assert len(centers) == 2
    assert counts[0] == 2  # [0.2, 0.1]
    assert counts[1] == 2  # [0.9, 0.8]
    assert freqs[0] == 0.0
    assert freqs[1] == 1.0

