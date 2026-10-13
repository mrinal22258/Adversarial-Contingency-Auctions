"""
Bayesian Type Filter and Edge Marginal Estimation.
Provides principled posterior over adversary types and edge blockage probabilities.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np

from ..env.adversaries import (
    AdversaryType,
    CanonicalTypeSet,
    canonical_edge,
)
from ..env.blockage_process import EdgeState


def compute_kl_divergence(p: np.ndarray, q: np.ndarray, eps: float = 1e-9) -> float:
    """Compute Kullback-Leibler divergence D_KL(P || Q) in nats."""
    p_safe = np.clip(p, eps, 1.0)
    q_safe = np.clip(q, eps, 1.0)
    p_safe /= np.sum(p_safe)
    q_safe /= np.sum(q_safe)
    return float(np.sum(p_safe * np.log(p_safe / q_safe)))


def compute_tv_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Compute Total Variation distance: 0.5 * sum |P_i - Q_i|."""
    return float(0.5 * np.sum(np.abs(p - q)))


class BayesianTypeFilter:
    """
    Tracks belief B_r(theta) over the canonical adversary types Theta = {theta_1, theta_2, theta_3}.
    Correctly updates beliefs using transition likelihoods without double-counting evidence.
    """

    def __init__(
        self,
        prior: Optional[Dict[AdversaryType, float]] = None,
        clearance_rate: float = 0.15,
        default_p0: float = 0.15,
        reactive_alpha: float = 0.35,
        interdiction_pcut: float = 0.85,
    ):
        self.types = list(CanonicalTypeSet)
        self.clearance_rate = clearance_rate
        self.default_p0 = default_p0
        self.reactive_alpha = reactive_alpha
        self.interdiction_pcut = interdiction_pcut

        if prior is not None:
            self.beliefs = {t: prior.get(t, 1.0 / len(self.types)) for t in self.types}
        else:
            uniform = 1.0 / len(self.types)
            self.beliefs = {t: uniform for t in self.types}
        self._normalize()

        self._processed_observations: Set[Tuple[int, Tuple[Any, Any]]] = set()
        self.frozen: bool = False

    def set_oracle(self, adv_type: AdversaryType) -> None:
        """
        Set belief strictly to 1.0 on adv_type (oracle adversary knowledge) and freeze.
        Raises ValueError if adv_type is not supported by the canonical type space.
        """
        if adv_type not in self.types:
            supported = [t.value for t in self.types]
            raise ValueError(
                f"Unsupported oracle adversary type '{adv_type}'! "
                f"Canonical belief model only represents: {supported}. "
                f"Cannot represent out-of-model dynamics without expanding the type simplex."
            )
        for t in self.types:
            self.beliefs[t] = 1.0 if t == adv_type else 0.0
        self._normalize()
        self.frozen = True

    def _normalize(self) -> None:
        total = sum(self.beliefs.values())
        if total <= 0:
            uniform = 1.0 / len(self.types)
            for t in self.types:
                self.beliefs[t] = uniform
        else:
            for t in self.types:
                self.beliefs[t] /= total

    def get_belief_vector(self) -> np.ndarray:
        """Return beliefs as a 1D numpy array ordered by CanonicalTypeSet."""
        return np.array([self.beliefs[t] for t in self.types], dtype=float)

    def set_belief_vector(self, vec: np.ndarray) -> None:
        """Set beliefs from 1D numpy array."""
        vec = np.clip(vec, 1e-6, 1.0)
        vec /= np.sum(vec)
        for i, t in enumerate(self.types):
            self.beliefs[t] = float(vec[i])

    def get_hazard_under_type(
        self,
        adv_type: AdversaryType,
        edge: Tuple[Any, Any],
        edge_robot_count: float = 0.0,
        is_targeted_by_interdiction: bool = False,
    ) -> float:
        """Compute the model onset hazard h_theta(e, s_t)."""
        if adv_type == AdversaryType.STOCHASTIC:
            return self.default_p0
        elif adv_type == AdversaryType.REACTIVE:
            return min(1.0, 0.05 + self.reactive_alpha * edge_robot_count)
        elif adv_type == AdversaryType.BUDGETED_INTERDICTION:
            return self.interdiction_pcut if is_targeted_by_interdiction else 0.05
        else:
            return 0.10

    def update_observation(
        self,
        step: int,
        edge: Tuple[Any, Any],
        observed_state: EdgeState,
        prior_state: Optional[EdgeState] = None,
        edge_robot_count: float = 0.0,
        is_targeted_by_interdiction: bool = False,
    ) -> None:
        """
        Bayesian update upon observing edge at a specific step.
        Ensures each observation is processed at most once per time step.
        """
        if self.frozen:
            return

        c_edge = canonical_edge(edge[0], edge[1])
        obs_key = (step, c_edge)
        if obs_key in self._processed_observations:
            return  # Prevent double-counting evidence
        self._processed_observations.add(obs_key)

        likelihoods = {}
        for t in self.types:
            h = self.get_hazard_under_type(
                t, c_edge, edge_robot_count, is_targeted_by_interdiction
            )

            if prior_state is not None:
                # 2-state Markov transition likelihood
                if prior_state == EdgeState.OPEN:
                    if observed_state == EdgeState.BLOCKED:
                        likelihood = h
                    else:
                        likelihood = 1.0 - h
                else:  # prior was BLOCKED
                    if observed_state == EdgeState.OPEN:
                        likelihood = self.clearance_rate
                    else:
                        likelihood = 1.0 - self.clearance_rate
            else:
                # Steady-state marginal likelihood
                denom = max(1e-5, h + self.clearance_rate)
                pi_blocked = h / denom
                if observed_state == EdgeState.BLOCKED:
                    likelihood = pi_blocked
                else:
                    likelihood = 1.0 - pi_blocked

            likelihoods[t] = max(1e-6, likelihood)

        # Bayes rule
        for t in self.types:
            self.beliefs[t] *= likelihoods[t]
        self._normalize()

    def pool_beliefs(self, neighbor_beliefs: List[np.ndarray], weights: Optional[List[float]] = None) -> None:
        """
        Log-linear belief pooling with communication neighbors:
        ln B_new(theta) = w_self * ln B_self(theta) + sum_s w_s * ln B_s(theta)
        """
        if not neighbor_beliefs:
            return

        all_vectors = [self.get_belief_vector()] + neighbor_beliefs
        if weights is None:
            w = np.ones(len(all_vectors)) / len(all_vectors)
        else:
            w = np.array(weights) / np.sum(weights)

        log_pooled = np.zeros(len(self.types))
        for vec, weight in zip(all_vectors, w):
            vec_safe = np.clip(vec, 1e-6, 1.0)
            log_pooled += weight * np.log(vec_safe)

        pooled = np.exp(log_pooled - np.max(log_pooled))
        self.set_belief_vector(pooled)

    def compute_edge_marginal(
        self,
        edge: Tuple[Any, Any],
        edge_robot_count: float = 0.0,
        is_targeted_by_interdiction: bool = False,
    ) -> float:
        """
        Compute edge blockage marginal probability pi_r(e) = sum_theta B_r(theta) * P(X_e=1 | theta, s).
        """
        c_edge = canonical_edge(edge[0], edge[1])
        pi_e = 0.0
        for t in self.types:
            h = self.get_hazard_under_type(
                t, c_edge, edge_robot_count, is_targeted_by_interdiction
            )
            # Steady-state blockage probability under hazard h and clearance mu
            denom = max(1e-5, h + self.clearance_rate)
            prob_blocked = h / denom
            pi_e += self.beliefs[t] * prob_blocked

        if pi_e < 0.01:
            return 0.01
        elif pi_e > 0.99:
            return 0.99
        return float(pi_e)


def compute_brier_score(
    forecasts: np.ndarray,
    outcomes: np.ndarray,
) -> float:
    """
    Compute multi-class or binary Brier score:
        BS = (1/N) * sum_{i=1}^N sum_{k=1}^K (f_{i,k} - o_{i,k})^2
    Lower score indicates superior probability calibration (0 = perfect, 1 = max error).
    """
    f = np.asarray(forecasts, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    if f.shape != o.shape:
        raise ValueError(f"Shape mismatch: forecasts {f.shape} vs outcomes {o.shape}")
    sq_err = (f - o) ** 2
    if sq_err.ndim > 1:
        return float(np.mean(np.sum(sq_err, axis=-1)))
    return float(np.mean(sq_err))


def compute_reliability_curve(
    predicted_probs: np.ndarray,
    binary_outcomes: np.ndarray,
    n_bins: int = 5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute reliability curve coordinates (predicted bin center vs empirical frequency)
    and sample counts per bin for calibration validation on fresh confirmatory data.
    """
    p = np.asarray(predicted_probs, dtype=float)
    y = np.asarray(binary_outcomes, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    emp_freqs = []
    bin_counts = []

    for low, high in zip(bins[:-1], bins[1:]):
        mask = (p >= low) & (p <= high if high == 1.0 else p < high)
        count = int(np.sum(mask))
        bin_counts.append(count)
        if count > 0:
            emp_freqs.append(float(np.mean(y[mask])))
        else:
            emp_freqs.append(float("nan"))

    return bin_centers, np.array(emp_freqs), np.array(bin_counts)

