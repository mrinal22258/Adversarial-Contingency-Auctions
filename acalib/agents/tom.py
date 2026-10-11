"""
Theory of Mind (ToM) Belief Estimation and Pinsker Claim Margin (Theorem 1).
Computes closed-form belief divergence margins that mathematically guarantee conditional conflict-freedom.
"""

from typing import Dict, List, Optional
import numpy as np

from .belief import compute_kl_divergence


class TheoryOfMindTracker:
    """
    Maintains robot r's internal estimates of peer robots' beliefs B_hat_s^(r).
    Updated via direct message receptions or common-knowledge observation history.
    """

    def __init__(self, robot_id: int, fleet_ids: List[int], n_types: int = 3, eta: float = 0.05):
        self.robot_id = robot_id
        self.fleet_ids = [rid for rid in fleet_ids if rid != robot_id]
        self.n_types = n_types
        self.eta = eta  # Assumed upper bound on ToM TV estimation error

        # Initialize peer belief estimates to uniform prior
        uniform = np.ones(n_types) / n_types
        self.peer_beliefs: Dict[int, np.ndarray] = {
            rid: uniform.copy() for rid in self.fleet_ids
        }
        self.last_update_step: Dict[int, int] = {rid: 0 for rid in self.fleet_ids}

    def update_peer_belief(self, peer_id: int, belief_vector: np.ndarray, step: int) -> None:
        """Update peer belief estimate directly from received message."""
        if peer_id in self.fleet_ids:
            self.peer_beliefs[peer_id] = np.clip(belief_vector.copy(), 1e-6, 1.0)
            self.peer_beliefs[peer_id] /= np.sum(self.peer_beliefs[peer_id])
            self.last_update_step[peer_id] = step

    def get_max_kl(self, my_belief: np.ndarray) -> float:
        """
        Compute pure max KL divergence D'_KL = max_{s != r} D_KL(B_r || B_hat_s^(r)).
        No eta inside KL, preserving correct units for TV bound.
        """
        if not self.fleet_ids:
            return 0.0

        max_kl = 0.0
        for peer_id, p_hat in self.peer_beliefs.items():
            kl = compute_kl_divergence(my_belief, p_hat)
            if kl > max_kl:
                max_kl = kl

        return float(max_kl)

    def get_max_divergence(self, my_belief: np.ndarray) -> float:
        """Legacy helper returning max KL divergence."""
        return self.get_max_kl(my_belief)

    def get_effective_eta(self, current_step: int = 0) -> float:
        """
        Compute effective ToM TV bound eta inflated by belief age / staleness:
        eta_eff = min(0.5, eta + 0.005 * max_staleness).
        """
        if not self.fleet_ids:
            return float(self.eta)
        max_staleness = max(
            (max(0, current_step - self.last_update_step.get(rid, 0)) for rid in self.fleet_ids),
            default=0,
        )
        return float(min(0.5, self.eta + 0.005 * max_staleness))


class PinskerMarginCalculator:
    """
    Computes the unit-consistent Pinsker claim margin (Theorem 1):
    m_{r, j} = Delta_j * ( sqrt(0.5 * D'_hat_r) + eta_eff ) + delta_map
    Derived from: TV(B_r, B_s) <= TV(B_r, B_hat_s) + TV(B_hat_s, B_s)
                               <= sqrt(0.5 * D_KL(B_r || B_hat_s)) + eta.
    """

    def __init__(self, delta_map: float = 0.0, default_delta_j: float = 20.0, eta: float = 0.05):
        self.delta_map = delta_map
        self.default_delta_j = default_delta_j
        self.eta = eta

    def compute_margin(self, delta_j: float, max_kl: float, eta: Optional[float] = None) -> float:
        """
        Compute required margin m_{r, j}.
        m_{r, j} = Delta_j * ( sqrt(0.5 * max_kl) + eta ) + delta_map
        """
        eff_eta = self.eta if eta is None else eta
        pinsker_tv = np.sqrt(0.5 * max(0.0, max_kl)) + eff_eta
        margin = delta_j * pinsker_tv + self.delta_map
        return float(margin)

    def can_claim_safely(
        self,
        my_cost: float,
        min_peer_cost: float,
        margin: float,
    ) -> bool:
        """
        Theorem 1 Conflict-Freedom Condition:
        Robot r claims task j iff my_cost + m_{r, j} < min_{s != r} peer_cost.
        Guarantees that no peer s will simultaneously claim task j under bounded divergence.
        Ties strictly defer (strict inequality).
        """
        return (my_cost + margin) < min_peer_cost
