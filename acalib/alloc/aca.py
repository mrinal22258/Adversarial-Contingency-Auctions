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
    ACA-CBBA: Adversarial Contingency Auction.
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
        margin_kappa: float = 1.0,
        fixed_margin: Optional[float] = None,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.delta_map = delta_map
        self.enable_margin = enable_margin
        self.contingency_depth = contingency_depth
        self.margin_kappa = margin_kappa
        self.fixed_margin = fixed_margin

        # Accounting for deferrals and margins
        self.total_claim_evaluations: int = 0
        self.total_safe_claims: int = 0
        self.total_deferred_tasks: int = 0
        self.logged_tv_observations: List[Tuple[float, float]] = []

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

    def _compute_lipschitz_L_j(self, task: Task, robot_id: int) -> float:
        """
        Theorem 3 Rigorous Lipschitz Constant L_j:
        L_j = sum_{e in path_j} Delta_j^path * Delta_pi(e)
        Derived mathematically from telescoping product inequality over expected recourse valuation.
        """
        robot = self.robots[robot_id]
        recourse_plan = robot.planner.build_recourse_plan(
            task_id=task.task_id,
            start_node=robot.current_node,
            target_node=task.node,
            edge_marginals=robot.get_edge_marginals(),
        )
        if recourse_plan is None or not recourse_plan.risky_edges:
            return 1.0

        # Maximum variation of marginals across adversary types for risky edges on path
        mu = robot.type_filter.clearance_rate
        total_L = 0.0
        nominal_cost = max(1.0, recourse_plan.primary_cost)
        delta_path = max(5.0, nominal_cost * 1.5)

        for e in recourse_plan.risky_edges:
            c_e = canonical_edge(e[0], e[1])
            hazards = [robot.type_filter.get_hazard_under_type(t, c_e) for t in robot.type_filter.types]
            marginals = [h / max(1e-5, h + mu) for h in hazards]
            delta_pi_e = max(marginals) - min(marginals)
            total_L += delta_path * delta_pi_e

        return float(max(1.0, total_L))

    def _build_bundle_aca(
        self,
        robot_id: int,
        tasks: Dict[int, Task],
        robot_positions: Dict[int, Tuple[float, float]],
        current_step: int = 0,
    ) -> Tuple[int, int]:
        """
        Phase 1: Local bundle construction with Pinsker Margin Claim Rule.
        Returns (round_safe_claims, round_deferred_tasks) for this robot in this round.
        """
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)
        edge_marginals = robot.get_edge_marginals()
        round_safe = 0
        round_deferred = 0

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1

            # Get current divergence bound D_hat_r
            my_belief = robot.type_filter.get_belief_vector()
            max_kl = robot.tom_tracker.get_max_kl(my_belief)
            eta_eff = robot.tom_tracker.get_effective_eta(current_step)

            # Log true TV vs eta_eff for Assumption 1 verification (Hypothesis H7)
            for peer_id in self.fleet_ids:
                if peer_id == robot_id:
                    continue
                p_hat = robot.tom_tracker.peer_beliefs.get(peer_id)
                if p_hat is not None:
                    p_true = self.robots[peer_id].type_filter.get_belief_vector()
                    true_tv = float(0.5 * np.sum(np.abs(p_true - p_hat)))
                    self.logged_tv_observations.append((true_tv, eta_eff))

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
                    L_j = self._compute_lipschitz_L_j(task, robot_id)

                    if self.fixed_margin is not None:
                        margin = float(self.fixed_margin)
                    else:
                        margin = float(self.margin_kappa * robot.pinsker_calc.compute_margin(L_j, max_kl, eta=eta_eff))

                    # Condition: my_cost + m_{r, j} < min_{s != r} peer_cost
                    if not robot.pinsker_calc.can_claim_safely(my_cost, min_peer_cost, margin):
                        # Margin condition not satisfied: task deferred to consensus
                        self.total_deferred_tasks += 1
                        round_deferred += 1
                        continue
                    else:
                        self.total_safe_claims += 1
                        round_safe += 1

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
        return round_safe, round_deferred

    def handle_replan_requests(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> int:
        """
        Theorem 4: Bounded partial re-auction on recourse exhaustion.
        Releases the blocked/exhausted task and any dependent downstream bundle tasks,
        clears the robot replan requests, and returns the number of re-auction events.
        """
        replan_events = 0
        for rid, robot in self.robots.items():
            if robot.replan_requests:
                replan_events += len(robot.replan_requests)
                for tid in list(robot.replan_requests):
                    if tid in robot.bundle:
                        idx = robot.bundle.index(tid)
                        released = robot.bundle[idx:]
                        robot.bundle = robot.bundle[:idx]
                        for r_tid in released:
                            self.y[rid][r_tid] = 0.0
                            self.z[rid][r_tid] = -1
                    else:
                        self.y[rid][tid] = 0.0
                        self.z[rid][tid] = -1
                robot.replan_requests.clear()
        return replan_events

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        max_consensus_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute ACA allocation round:
        1. Handle replan requests from robots experiencing unresolvable blockages (Thm 4).
        2. Local bundle construction with Pinsker margin.
        3. Consensus message exchange for any deferred/unresolved items.
        """
        # Handle replan requests from robots experiencing unresolvable blockages
        round_replans = self.handle_replan_requests(tasks, current_step, robot_positions)

        # Clean up completed tasks from tables and robot bundles
        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]
            for tid, t in tasks.items():
                if t.completed and tid in self.z[rid]:
                    self.z[rid][tid] = -1
                    self.y[rid][tid] = 0.0

        # Phase 1: Local claim with Pinsker margin (safe claims committed directly)
        phase1_claims: Dict[int, List[int]] = {}
        round_safe_claims = 0
        round_deferred_tasks = 0
        for rid in self.fleet_ids:
            prev_bundle = set(self.robots[rid].bundle)
            r_safe, r_def = self._build_bundle_aca(rid, tasks, robot_positions, current_step=current_step)
            round_safe_claims += r_safe
            round_deferred_tasks += r_def
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
            "safe_claims": round_safe_claims,
            "deferred_tasks": round_deferred_tasks,
            "replan_events": round_replans,
            "total_assigned": sum(len(r.bundle) for r in self.robots.values()),
        }
