"""
Simulation Metrics Accounting.
Tracks completion rate, makespan, net welfare, conflicts, communication, runtimes, and optimality gaps.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class SimulationMetrics:
    total_tasks: int = 0
    total_robots: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    expired_tasks: int = 0

    makespan: int = 0
    total_task_latency: float = 0.0
    task_latencies: List[float] = field(default_factory=list)

    total_reward: float = 0.0
    total_travel_distance: float = 0.0
    net_welfare: float = 0.0

    total_conflicts: int = 0  # Cumulative conflict instances across all rounds
    distinct_conflicts: int = 0  # Number of distinct tasks ever double-assigned
    safe_claim_conflicts: int = 0  # Tasks double-assigned during safe claim phase (Thm 3 verifies 0)
    allocation_rounds: int = 0
    duplicated_distance: float = 0.0

    total_messages_sent: int = 0
    total_bytes_sent: int = 0
    reauction_events: int = 0
    safe_claims: int = 0
    deferred_claims: int = 0

    belief_convergence_step: Optional[int] = None

    per_tick_runtimes_ms: List[float] = field(default_factory=list)
    total_wall_clock_ms: float = 0.0

    @property
    def cumulative_conflicts(self) -> int:
        return self.total_conflicts

    @property
    def total_messages(self) -> int:
        return self.total_messages_sent

    def compute_summary(self) -> Dict[str, Any]:
        """Compute aggregated statistical summary dict."""
        comp_rate = (self.completed_tasks / max(1, self.total_tasks)) * 100.0
        mean_lat = float(np.mean(self.task_latencies)) if self.task_latencies else 0.0
        median_lat = float(np.median(self.task_latencies)) if self.task_latencies else 0.0
        mean_tick_rt = float(np.mean(self.per_tick_runtimes_ms)) if self.per_tick_runtimes_ms else 0.0
        p95_tick_rt = float(np.percentile(self.per_tick_runtimes_ms, 95)) if self.per_tick_runtimes_ms else 0.0
        conf_per_round = self.total_conflicts / max(1, self.allocation_rounds)

        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "completion_rate_pct": comp_rate,
            "makespan": self.makespan,
            "mean_task_latency": mean_lat,
            "median_task_latency": median_lat,
            "net_welfare": self.net_welfare,
            "total_travel_distance": self.total_travel_distance,
            "total_conflicts": self.total_conflicts,
            "distinct_conflicts": self.distinct_conflicts,
            "safe_claim_conflicts": self.safe_claim_conflicts,
            "conflicts_per_round": conf_per_round,
            "duplicated_distance": self.duplicated_distance,
            "total_messages": self.total_messages_sent,
            "total_bytes": self.total_bytes_sent,
            "reauction_events": self.reauction_events,
            "safe_claims": self.safe_claims,
            "deferred_claims": self.deferred_claims,
            "belief_convergence_step": self.belief_convergence_step,
            "mean_tick_runtime_ms": mean_tick_rt,
            "p95_tick_runtime_ms": p95_tick_rt,
            "total_wall_clock_ms": self.total_wall_clock_ms,
        }
