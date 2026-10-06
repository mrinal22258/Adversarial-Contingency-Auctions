"""
Adversarial Contingency Auction (ACA) with Pinsker Claim Margins (Theorem 3).
Integrates Exact Recourse Valuation (Theorem 1), Divergence Claim Margins (Theorem 3),
and Rare Bounded Re-auctions (Theorem 4).
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from .base import BaseAllocator, Task
from .cbba import CBBAAllocator
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message
from ..env.adversaries import canonical_edge


class ACAAllocator(CBBAAllocator):
    """
    ACA-CBBA: Belief-Divergence-Aware Contingency Auction.
    Features:
    1. Type-aware expected recourse cost valuation (Thm 1).
    2. Pinsker belief-divergence claim margin m_{r, j} (Thm 3).
    3. Consensus negotiation fallback only when margin condition fails (Corollary 3.1).
    4. Local recourse pivot with zero messages on blockage (Thm 4).
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
        delta_map: float = 0.0,
        enable_margin: bool = True,
        contingency_depth: int = 1,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.delta_map = delta_map
        self.enable_margin = enable_margin
        self.contingency_depth = contingency_depth

        # Accounting for deferrals and margins
        self.total_claim_evaluations: int = 0
        self.total_safe_claims: int = 0
        self.total_deferred_tasks: int = 0

    def _get_peer_edge_marginals(self, robot_id: int, peer_id: int) -> Dict[Tuple[Any, Any], float]:
        """Compute edge blockage marginals under peer s's ToM belief as estimated by robot r."""
        robot = self.robots[robot_id]
        peer_belief_vec = robot.tom_tracker.peer_beliefs.get(peer_id)
        if peer_belief_vec is None:
            return robot.get_edge_marginals()

        marginals = {}
        for u, v in self.graph.edges():
            c_e = canonical_edge(u, v)
            if robot.risky_edges is not None and c_e not in robot.risky_edges:
                marginals[c_e] = 0.0
                continue
            pi_e = 0.0
            for i, t in enumerate(robot.type_filter.types):
                h = robot.type_filter.get_hazard_under_type(t, c_e)
                denom = max(1e-5, h + robot.type_filter.clearance_rate)
                pi_e += float(peer_belief_vec[i]) * (h / denom)
            marginals[c_e] = float(np.clip(pi_e, 0.01, 0.99))
        return marginals

    def _estimate_peer_cost(
        self,
        peer_id: int,
        task: Task,
        robot_positions: Dict[int, Tuple[float, float]],
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """Estimate peer s's expected recourse cost from robot r's ToM perspective."""
        peer = self.robots[peer_id]
        peer_node = peer.current_node
        recourse_plan = peer.planner.build_recourse_plan(
            task_id=task.task_id,
            start_node=peer_node,
            target_node=task.node,
            edge_marginals=edge_marginals,
        )
        if recourse_plan is None:
            return float("inf")
        return recourse_plan.expected_cost

    def _compute_delta_j(self, task: Task) -> float:
        """
        Theorem 3: Delta_j = max_{s, theta} c_s(j | theta) - min_{s, theta} c_s(j | theta).
        Non-circular, bounded type sensitivity of task j across fleet and adversary types.
        """
        costs = []
        for rid in self.fleet_ids:
            r = self.robots[rid]
            for t in r.type_filter.types:
                pure_marginals = {}
                for u, v in self.graph.edges():
                    c_e = canonical_edge(u, v)
                    if r.risky_edges is not None and c_e not in r.risky_edges:
                        pure_marginals[c_e] = 0.0
                    else:
                        h = r.type_filter.get_hazard_under_type(t, c_e)
                        denom = max(1e-5, h + r.type_filter.clearance_rate)
                        pure_marginals[c_e] = float(np.clip(h / denom, 0.01, 0.99))
                plan = r.planner.build_recourse_plan(
                    task_id=task.task_id,
                    start_node=r.current_node,
                    target_node=task.node,
                    edge_marginals=pure_marginals,
                )
                if plan is not None:
                    costs.append(plan.expected_cost)
                else:
                    costs.append(500.0)

        if not costs:
            return 20.0
        return float(max(1.0, max(costs) - min(costs)))

    def _build_bundle_aca(
        self,
        robot_id: int,
        tasks: Dict[int, Task],
        robot_positions: Dict[int, Tuple[float, float]],
        current_step: int = 0,
    ) -> None:
        """
        Phase 1: Local bundle construction with Pinsker Margin Claim Rule.
        """
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)
        edge_marginals = robot.get_edge_marginals()

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1

            # Get current divergence bound D_hat_r
            my_belief = robot.type_filter.get_belief_vector()
            max_kl = robot.tom_tracker.get_max_kl(my_belief)
            eta_eff = robot.tom_tracker.get_effective_eta(current_step)

            for tid, task in tasks.items():
                if tid in bundle or task.completed:
                    continue

                # Expected recourse cost for robot_id
                recourse_plan = robot.planner.build_recourse_plan(
                    task_id=tid,
                    start_node=robot.current_node,
                    target_node=task.node,
                    edge_marginals=edge_marginals,
                )
                if recourse_plan is None:
                    continue

                my_cost = recourse_plan.expected_cost
                score = max(0.0, task.reward - my_cost)
                current_winner_bid = self.y[robot_id].get(tid, 0.0)

                if score <= current_winner_bid or score <= best_val:
                    continue

                # Theorem 3 Margin Check
                if self.enable_margin and len(self.fleet_ids) > 1:
                    self.total_claim_evaluations += 1

                    # Estimate costs of peers under ToM beliefs
                    peer_costs = []
                    for peer_id in self.fleet_ids:
                        if peer_id == robot_id:
                            continue
                        peer_marginals = self._get_peer_edge_marginals(robot_id, peer_id)
                        c_peer = self._estimate_peer_cost(
                            peer_id, task, robot_positions, peer_marginals
                        )
                        peer_costs.append(c_peer)

                    min_peer_cost = min(peer_costs) if peer_costs else float("inf")
                    delta_j = self._compute_delta_j(task)
                    margin = robot.pinsker_calc.compute_margin(delta_j, max_kl, eta=eta_eff)

                    # Condition: my_cost + m_{r, j} < min_{s != r} peer_cost
                    if not robot.pinsker_calc.can_claim_safely(my_cost, min_peer_cost, margin):
                        # Margin condition not satisfied: task deferred to consensus
                        self.total_deferred_tasks += 1
                        continue
                    else:
                        self.total_safe_claims += 1

                best_val = score
                best_task_id = tid
                best_insert_pos = len(bundle)

            if best_task_id is not None and best_val > 0.0:
                bundle.insert(best_insert_pos, best_task_id)
                self.y[robot_id][best_task_id] = best_val
                self.z[robot_id][best_task_id] = robot_id
            else:
                break

        robot.bundle = bundle

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        max_consensus_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute ACA allocation round:
        1. Local bundle construction with Pinsker margin.
        2. Consensus message exchange for any deferred/unresolved items.
        """
        # Clean up completed tasks from tables and robot bundles
        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]
            for tid, t in tasks.items():
                if t.completed and tid in self.z[rid]:
                    self.z[rid][tid] = -1
                    self.y[rid][tid] = 0.0

        # Phase 1: Local claim with Pinsker margin (safe claims committed directly)
        phase1_claims: Dict[int, List[int]] = {}
        for rid in self.fleet_ids:
            prev_bundle = set(self.robots[rid].bundle)
            self._build_bundle_aca(rid, tasks, robot_positions, current_step=current_step)
            phase1_claims[rid] = [tid for tid in self.robots[rid].bundle if tid not in prev_bundle]

        # Check safe-claim conflicts strictly among Phase 1 simultaneous safe claims
        safe_claim_holders: Dict[int, List[int]] = {}
        for rid in self.fleet_ids:
            for tid in phase1_claims[rid]:
                safe_claim_holders.setdefault(tid, []).append(rid)
        safe_claim_conflicts = sum(1 for holders in safe_claim_holders.values() if len(holders) > 1)

        # Phase 2: Communication consensus for deferred/unassigned tasks
        rounds = 0
        if max_consensus_iterations > 0:
            for rid in self.fleet_ids:
                self._build_bundle(rid, tasks)

            for _ in range(max_consensus_iterations):
                rounds += 1
                changed = self._communicate_and_resolve(current_step, robot_positions)
                if not changed:
                    break
                for rid in self.fleet_ids:
                    self._build_bundle(rid, tasks)

        # Update planned bundles
        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})

        # Count conflicts
        assigned_map: Dict[int, List[int]] = {}
        for rid, robot in self.robots.items():
            for tid in robot.bundle:
                if tid not in assigned_map:
                    assigned_map[tid] = []
                assigned_map[tid].append(rid)

        conflicts = sum(1 for tid, holders in assigned_map.items() if len(holders) > 1)

        return {
            "consensus_rounds": rounds,
            "conflicts": conflicts,
            "safe_claim_conflicts": safe_claim_conflicts,
            "safe_claims": self.total_safe_claims,
            "deferred_tasks": self.total_deferred_tasks,
            "total_assigned": sum(len(r.bundle) for r in self.robots.values()),
        }
