"""
Adversarial Contingency Auction (ACA) with Pinsker Claim Margins (Theorem 3).
Integrates Exact Recourse Valuation (Theorem 1), Divergence Claim Margins (Theorem 3),
and Rare Bounded Re-auctions (Theorem 4).
"""

import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx

from .base import Task
from .cbba import CBBAAllocator
from ..agents.robot import RobotAgent
from ..agents.contingency import (
    RecoursePlan,
    compute_lipschitz_bound,
    prune_recourse_plan,
    _collect_tree_risky_edges,
    get_marginals_token,
)
from ..agents.belief import MARGINAL_MIN, MARGINAL_MAX
from ..env.comm import CommunicationNetwork
from ..env.adversaries import canonical_edge, get_edge_vulnerability_class


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
        adaptive_margin: bool = False,
        prune_threshold: float = 0.0,
        kappa_hyst: float = 0.5,
        partition_mode: bool = False,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.delta_map = delta_map
        self.enable_margin = enable_margin
        self.contingency_depth = contingency_depth
        self.margin_kappa = margin_kappa
        self.fixed_margin = fixed_margin
        self.adaptive_margin = adaptive_margin
        self.prune_threshold = prune_threshold
        self.kappa_hyst = kappa_hyst
        self.partition_mode = partition_mode

        if partition_mode:
            for r in self.robots.values():
                if hasattr(r, "tom_tracker"):
                    r.tom_tracker.partition_mode = True
                    r.tom_tracker.log_lambda_max = float(np.log(25.0))  # 3.2188758 for Lambda_max=25.0

        # Accounting for deferrals and margins
        self.total_claim_evaluations: int = 0
        self.total_safe_claims: int = 0
        self.total_deferred_tasks: int = 0
        self.logged_tv_observations: List[Tuple[float, float]] = []
        self.per_claim_logs: List[Dict[str, Any]] = []

    def _get_peer_edge_marginals(
        self,
        robot_id: int,
        peer_id: int,
        fleet_states: Optional[Dict[int, Any]] = None,
    ) -> Dict[Tuple[Any, Any], float]:
        """Compute edge blockage marginals under peer s's ToM belief as estimated by robot r."""
        cache_key = (robot_id, peer_id)
        if hasattr(self, "_round_marginal_cache") and self._round_marginal_cache is not None:
            if cache_key in self._round_marginal_cache:
                return self._round_marginal_cache[cache_key]

        robot = self.robots[robot_id]
        if fleet_states is None:
            fleet_states = getattr(self, "_round_fleet_states", None)
            if fleet_states is None:
                fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}

        peer_belief_vec = robot.tom_tracker.peer_beliefs.get(peer_id)
        if peer_belief_vec is None:
            res = robot.get_edge_marginals(fleet_states=fleet_states)
            if hasattr(self, "_round_marginal_cache") and self._round_marginal_cache is not None:
                self._round_marginal_cache[cache_key] = res
            return res

        from ..env.adversaries import compute_fleet_edge_robot_counts, compute_interdiction_cut
        edges = list(self.graph.edges())
        edge_counts = compute_fleet_edge_robot_counts(self.graph, edges, fleet_states)
        risky_set = set(robot.risky_edges) if robot.risky_edges is not None else set(canonical_edge(u, v) for u, v in edges)
        targeted_cuts = compute_interdiction_cut(self.graph, risky_set, fleet_states)

        marginals = {}
        for u, v in self.graph.edges():
            c_e = canonical_edge(u, v)
            if robot.risky_edges is not None and c_e not in robot.risky_edges:
                marginals[c_e] = 0.0
                continue
            erc = edge_counts.get(c_e, 0.0)
            is_tgt = c_e in targeted_cuts
            pi_e = 0.0
            v_class = get_edge_vulnerability_class(self.graph, c_e)
            for i, t in enumerate(robot.type_filter.types):
                h = robot.type_filter.get_hazard_under_type(
                    t,
                    c_e,
                    edge_robot_count=erc,
                    is_targeted_by_interdiction=is_tgt,
                    vulnerability_class=v_class,
                )
                if v_class in (1, 2, 3):
                    prob_blocked = h
                else:
                    denom = max(1e-5, h + robot.type_filter.clearance_rate)
                    prob_blocked = h / denom
                pi_e += float(peer_belief_vec[i]) * prob_blocked
            marginals[c_e] = float(np.clip(pi_e, MARGINAL_MIN, MARGINAL_MAX))

        if hasattr(self, "_round_marginal_cache") and self._round_marginal_cache is not None:
            self._round_marginal_cache[cache_key] = marginals
        return marginals

    def _estimate_peer_cost(
        self,
        peer_id: int,
        task: Task,
        robot_positions: Dict[int, Tuple[float, float]],
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """Estimate peer s's expected recourse cost from robot r's ToM perspective."""
        cache_key = (peer_id, task.task_id, get_marginals_token(edge_marginals))
        if hasattr(self, "_round_peer_cost_cache") and cache_key in self._round_peer_cost_cache:
            return self._round_peer_cost_cache[cache_key]

        peer = self.robots[peer_id]
        peer_node = peer.current_node
        recourse_plan = peer.planner.build_recourse_plan(
            task_id=task.task_id,
            start_node=peer_node,
            target_node=task.node,
            edge_marginals=edge_marginals,
        )
        if recourse_plan is None:
            if hasattr(self, "_round_peer_cost_cache"):
                self._round_peer_cost_cache[cache_key] = float("inf")
            return float("inf")
        if self.prune_threshold > 0.0 and recourse_plan.tree is not None:
            recourse_plan = prune_recourse_plan(
                recourse_plan,
                self.prune_threshold,
                peer.planner,
                edge_marginals,
            )
        cost = recourse_plan.expected_cost
        if hasattr(self, "_round_peer_cost_cache"):
            self._round_peer_cost_cache[cache_key] = cost
        return cost

    def _compute_lipschitz_for_robot(
        self,
        task: Task,
        robot_id: int,
        recourse_plan: Optional[RecoursePlan] = None,
        fleet_states: Optional[Dict[int, Any]] = None,
    ) -> float:
        """Compute Lipschitz bound for a specific robot on task j."""
        cache_key = (task.task_id, robot_id)
        if recourse_plan is None and hasattr(self, "_round_lip_robot_cache") and cache_key in self._round_lip_robot_cache:
            return self._round_lip_robot_cache[cache_key]

        robot = self.robots[robot_id]
        if fleet_states is None:
            fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}

        if recourse_plan is None and hasattr(self, "_round_plan_cache") and cache_key in self._round_plan_cache:
            recourse_plan = self._round_plan_cache[cache_key]

        marginals = robot.get_edge_marginals(fleet_states=fleet_states)
        if recourse_plan is None:
            recourse_plan = robot.planner.build_recourse_plan(
                task_id=task.task_id,
                start_node=robot.current_node,
                target_node=task.node,
                edge_marginals=marginals,
            )
            if recourse_plan is not None and self.prune_threshold > 0.0 and recourse_plan.tree is not None:
                recourse_plan = prune_recourse_plan(
                    recourse_plan,
                    self.prune_threshold,
                    robot.planner,
                    marginals,
                )
            if hasattr(self, "_round_plan_cache"):
                self._round_plan_cache[cache_key] = recourse_plan
        if recourse_plan is None:
            if hasattr(self, "_round_lip_robot_cache"):
                self._round_lip_robot_cache[cache_key] = 0.0
            return 0.0

        active_plan = recourse_plan

        # Collect all active risky edges from the active policy tree and primary path
        all_active_risky: List[Tuple[Any, Any]] = []
        if active_plan.tree is not None:
            _collect_tree_risky_edges(active_plan.tree, all_active_risky, self.graph)
        else:
            for e in (active_plan.risky_edges or []):
                c_e = canonical_edge(e[0], e[1])
                if c_e not in all_active_risky:
                    all_active_risky.append(c_e)

        p_path = active_plan.primary_path or []
        for i in range(len(p_path) - 1):
            c_e = canonical_edge(p_path[i], p_path[i + 1])
            v_class = get_edge_vulnerability_class(self.graph, c_e)
            if v_class in (1, 2, 3) and c_e not in all_active_risky:
                all_active_risky.append(c_e)

        if not all_active_risky:
            if recourse_plan is None and hasattr(self, "_round_lip_robot_cache"):
                self._round_lip_robot_cache[cache_key] = 0.0
            return 0.0

        from ..env.adversaries import compute_fleet_edge_robot_counts, compute_interdiction_cut
        edge_counts = compute_fleet_edge_robot_counts(self.graph, all_active_risky, fleet_states)
        targeted_cuts = compute_interdiction_cut(self.graph, set(all_active_risky), fleet_states)

        hazards_by_type = {}
        for c_e in all_active_risky:
            erc = edge_counts.get(c_e, 0.0)
            is_tgt = c_e in targeted_cuts
            v_class = get_edge_vulnerability_class(self.graph, c_e)
            hazards_by_type[c_e] = [
                robot.type_filter.get_hazard_under_type(
                    t,
                    c_e,
                    edge_robot_count=erc,
                    is_targeted_by_interdiction=is_tgt,
                    vulnerability_class=v_class,
                )
                for t in robot.type_filter.types
            ]

        mu = robot.type_filter.clearance_rate
        val = compute_lipschitz_bound(
            planner=robot.planner,
            recourse_plan=active_plan,
            hazards_by_type=hazards_by_type,
            clearance_rate=mu,
            partition_mode=getattr(self, "partition_mode", False),
        )
        if recourse_plan is None and hasattr(self, "_round_lip_robot_cache"):
            self._round_lip_robot_cache[cache_key] = val
        return val

    def _compute_lipschitz_L_j(
        self,
        task: Task,
        robot_id: int,
        recourse_plan: Optional[RecoursePlan] = None,
        fleet_states: Optional[Dict[int, Any]] = None,
    ) -> float:
        """
        Proposition 2 Analytical Lipschitz Upper Bound Delta_j = max_{s in Fleet} L_{s, j}.
        Covers both own bid sensitivity and peer valuation sensitivity under Theory of Mind.
        """
        if hasattr(self, "_round_lip_L_j_cache") and task.task_id in self._round_lip_L_j_cache:
            return self._round_lip_L_j_cache[task.task_id]

        if fleet_states is None:
            fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}

        l_r = self._compute_lipschitz_for_robot(task, robot_id, recourse_plan=recourse_plan, fleet_states=fleet_states)
        max_l = l_r
        for p_id in self.robots:
            if p_id != robot_id:
                l_p = self._compute_lipschitz_for_robot(task, p_id, recourse_plan=None, fleet_states=fleet_states)
                if l_p > max_l:
                    max_l = l_p
        if hasattr(self, "_round_lip_L_j_cache"):
            self._round_lip_L_j_cache[task.task_id] = max_l
        return max_l

    def _build_bundle_aca(
        self,
        robot_id: int,
        tasks: Dict[int, Task],
        robot_positions: Dict[int, Tuple[float, float]],
        current_step: int = 0,
    ) -> Tuple[int, int, float, float]:
        """
        Phase 1: Local bundle construction with Pinsker Margin Claim Rule.
        Returns (round_safe_claims, round_deferred_tasks, max_tv, eta_eff) for this robot in this round.
        """
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)
        fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}
        edge_marginals = robot.get_edge_marginals(fleet_states=fleet_states)
        round_safe = 0
        eta_eff = robot.tom_tracker.get_effective_eta(current_step)
        max_tv = 0.0

        # Log true TV vs eta_eff for Assumption 1 verification (Hypothesis H7)
        # Observed and logged at most once per robot-peer pair per auction round
        for peer_id in self.fleet_ids:
            if peer_id == robot_id:
                continue
            p_hat = robot.tom_tracker.peer_beliefs.get(peer_id)
            if p_hat is not None:
                p_true = self.robots[peer_id].type_filter.get_belief_vector()
                true_tv = float(0.5 * np.sum(np.abs(p_true - p_hat)))
                self.logged_tv_observations.append((true_tv, eta_eff))
                if true_tv > max_tv:
                    max_tv = true_tv

        robot_plan_cache: Dict[int, Optional[RecoursePlan]] = {}
        peer_cost_cache: Dict[Tuple[int, int], float] = {}
        lipschitz_cache: Dict[int, float] = {}
        deferred_tids: Set[int] = set()

        # Get current divergence bound D_hat_r
        my_belief = robot.type_filter.get_belief_vector()
        max_kl = robot.tom_tracker.get_max_kl(my_belief)

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1
            best_is_safe = False

            for tid, task in tasks.items():
                if tid in bundle or task.completed:
                    continue

                # Check if task is already held by a peer: cannot silently claim without consensus
                existing_holder = self.z[robot_id].get(tid, -1)
                if existing_holder not in (-1, robot_id):
                    deferred_tids.add(tid)
                    continue

                # Expected recourse cost for robot_id
                plan_key = (task.task_id, robot_id)
                if hasattr(self, "_round_plan_cache") and plan_key in self._round_plan_cache:
                    p = self._round_plan_cache[plan_key]
                elif tid not in robot_plan_cache:
                    p = robot.planner.build_recourse_plan(
                        task_id=tid,
                        start_node=robot.current_node,
                        target_node=task.node,
                        edge_marginals=edge_marginals,
                    )
                    if p is not None and self.prune_threshold > 0.0 and p.tree is not None:
                        p = prune_recourse_plan(p, self.prune_threshold, robot.planner, edge_marginals)
                    if hasattr(self, "_round_plan_cache"):
                        self._round_plan_cache[plan_key] = p
                    robot_plan_cache[tid] = p
                else:
                    p = robot_plan_cache[tid]
                recourse_plan = p
                if recourse_plan is None:
                    continue

                my_cost = recourse_plan.expected_cost
                score = max(0.0, task.reward - my_cost)
                current_winner_bid = self.y[robot_id].get(tid, 0.0)

                if score <= current_winner_bid or score <= best_val:
                    continue

                # Theorem 3 Margin Check
                is_safe = False
                if self.enable_margin and len(self.fleet_ids) > 1:
                    self.total_claim_evaluations += 1

                    # Estimate costs of peers under ToM beliefs
                    peer_costs = []
                    for peer_id in self.fleet_ids:
                        if peer_id == robot_id:
                            continue
                        pc_key = (peer_id, tid)
                        if pc_key not in peer_cost_cache:
                            peer_marginals = self._get_peer_edge_marginals(
                                robot_id, peer_id, fleet_states=fleet_states
                            )
                            peer_cost_cache[pc_key] = self._estimate_peer_cost(
                                peer_id, task, robot_positions, peer_marginals
                            )
                        peer_costs.append(peer_cost_cache[pc_key])

                    min_peer_cost = min(peer_costs) if peer_costs else float("inf")
                    if tid not in lipschitz_cache:
                        lipschitz_cache[tid] = self._compute_lipschitz_L_j(
                            task, robot_id, recourse_plan=recourse_plan, fleet_states=fleet_states
                        )
                    L_j = lipschitz_cache[tid]

                    if self.fixed_margin is not None:
                        margin = float(self.fixed_margin)
                    elif self.adaptive_margin:
                        b = robot.type_filter.get_belief_vector()
                        eps = 1e-12
                        entropy = -float(np.sum(b * np.log(b + eps)))
                        max_entropy = float(np.log(len(b))) if len(b) > 1 else 1.0
                        norm_entropy = float(np.clip(entropy / max(eps, max_entropy), 0.0, 1.0))
                        effective_kappa = self.margin_kappa * (1.0 + 0.15 * norm_entropy)
                        margin = float(effective_kappa * robot.pinsker_calc.compute_margin(L_j, max_kl, eta=eta_eff, max_peer_L=L_j))
                    else:
                        margin = float(self.margin_kappa * robot.pinsker_calc.compute_margin(L_j, max_kl, eta=eta_eff, max_peer_L=L_j))

                    # Condition: my_cost + m_{r, j} < min_{s != r} peer_cost
                    if not robot.pinsker_calc.can_claim_safely(my_cost, min_peer_cost, margin):
                        deferred_tids.add(tid)
                        continue
                    else:
                        is_safe = True

                best_val = score
                best_task_id = tid
                best_insert_pos = len(bundle)
                best_is_safe = is_safe

            if best_task_id is not None and best_val > 0.0:
                bundle.insert(best_insert_pos, best_task_id)
                self.y[robot_id][best_task_id] = best_val
                self.z[robot_id][best_task_id] = robot_id
                if best_task_id in robot_plan_cache and robot_plan_cache[best_task_id] is not None:
                    robot.assigned_plans[best_task_id] = robot_plan_cache[best_task_id]
                if best_is_safe:
                    self.total_safe_claims += 1
                    round_safe += 1
            else:
                break

        round_deferred = len(deferred_tids)
        self.total_deferred_tasks += round_deferred
        robot.bundle = bundle
        return round_safe, round_deferred, max_tv, eta_eff

    def _build_bundle(
        self,
        robot_id: int,
        tasks: Dict[int, Task],
    ) -> None:
        """
        Phase 2: Local bundle building for deferred tasks using expected recourse valuation.
        """
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)
        fleet_states = getattr(self, "_round_fleet_states", None)
        if fleet_states is None:
            fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}
        edge_marginals = robot.get_edge_marginals(fleet_states=fleet_states)

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1

            for tid, task in tasks.items():
                if tid in bundle or task.completed:
                    continue

                plan_key = (task.task_id, robot_id)
                if hasattr(self, "_round_plan_cache") and plan_key in self._round_plan_cache:
                    p = self._round_plan_cache[plan_key]
                else:
                    p = robot.planner.build_recourse_plan(
                        task_id=tid,
                        start_node=robot.current_node,
                        target_node=task.node,
                        edge_marginals=edge_marginals,
                    )
                    if p is not None and self.prune_threshold > 0.0 and p.tree is not None:
                        p = prune_recourse_plan(p, self.prune_threshold, robot.planner, edge_marginals)
                    if hasattr(self, "_round_plan_cache"):
                        self._round_plan_cache[plan_key] = p

                if p is None:
                    continue

                my_cost = p.expected_cost
                score = max(0.0, task.reward - my_cost)
                current_winner_bid = self.y[robot_id].get(tid, 0.0)

                if score > current_winner_bid and score > best_val:
                    best_val = score
                    best_task_id = tid
                    best_insert_pos = len(bundle)

            if best_task_id is not None and best_val > 0.0:
                bundle.insert(best_insert_pos, best_task_id)
                self.y[robot_id][best_task_id] = best_val
                self.z[robot_id][best_task_id] = robot_id
                plan_key = (best_task_id, robot_id)
                if hasattr(self, "_round_plan_cache") and plan_key in self._round_plan_cache:
                    robot.assigned_plans[best_task_id] = self._round_plan_cache[plan_key]
            else:
                break

        robot.bundle = bundle

    def _communicate_and_resolve(
        self,
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        tasks: Optional[Dict[int, Task]] = None,
    ) -> bool:
        """
        Phase 2: Consensus communication and conflict resolution with
        Theorem 2 Belief-Consistent Consensus Hysteresis.
        """
        from .consensus import execute_consensus_exchange

        def extra_payload(rid: int) -> Dict[str, Any]:
            return {"belief": list(self.robots[rid].type_filter.get_belief_vector())}

        def handle_extra(rid: int, sender_k: int, k_data: Dict[str, Any]) -> None:
            if "belief" in k_data and hasattr(self.robots[rid], "tom_tracker"):
                self.robots[rid].tom_tracker.update_peer_belief(
                    sender_k, np.array(k_data["belief"], dtype=float), current_step
                )

        def deadband_fn(receiver_id: int, sender_id: int, tid: int) -> float:
            if not self.enable_margin:
                return 0.0
            task = None
            if tasks is not None and tid in tasks:
                task = tasks[tid]
            elif hasattr(self, "_active_tasks") and getattr(self, "_active_tasks") is not None and tid in self._active_tasks:
                task = self._active_tasks[tid]
            if task is None:
                return 0.0

            robot = self.robots[receiver_id]
            L_j = self._compute_lipschitz_L_j(task, receiver_id)
            my_belief = robot.type_filter.get_belief_vector()
            max_kl = robot.tom_tracker.get_max_kl(my_belief)
            eta_eff = robot.tom_tracker.get_effective_eta(current_step)
            base_m = robot.pinsker_calc.compute_margin(L_j, max_kl, eta=eta_eff, max_peer_L=L_j)
            return float(self.kappa_hyst * base_m)

        return execute_consensus_exchange(
            fleet_ids=self.fleet_ids,
            robots=self.robots,
            comm_net=self.comm_net,
            y=self.y,
            z=self.z,
            s=self.s,
            current_step=current_step,
            robot_positions=robot_positions,
            msg_type="CBBA_CONSENSUS",
            extra_payload_fn=extra_payload,
            handle_extra_payload_fn=handle_extra,
            deadband_fn=deadband_fn if self.enable_margin else None,
        )

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
        max_consensus_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute ACA allocation round:
        1. Handle replan requests from robots experiencing unresolvable blockages (Thm 4).
        2. Local bundle construction with Pinsker margin.
        3. Consensus message exchange for any deferred/unresolved items.
        """
        # Handle replan requests from robots experiencing unresolvable blockages
        round_replans = self.handle_replan_requests(tasks, current_step, robot_positions)

        # Initialize invariant caches for this auction round
        self._round_marginal_cache = {}
        self._round_plan_cache = {}
        self._round_lip_robot_cache = {}
        self._round_lip_L_j_cache = {}
        self._round_peer_cost_cache = {}
        self._round_fleet_states = {r_id: r.get_state_summary() for r_id, r in self.robots.items()}

        # Clean up completed tasks from tables and robot bundles
        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]
            for tid, t in tasks.items():
                if t.completed and tid in self.z[rid]:
                    self.z[rid][tid] = -1
                    self.y[rid][tid] = 0.0

        # Phase 1: Local claim with Pinsker margin (safe claims committed directly)
        prev_bundles = {rid: set(self.robots[rid].bundle) for rid in self.fleet_ids}
        phase1_claims: Dict[int, List[int]] = {}
        robot_tv_eta: Dict[int, Tuple[float, float]] = {}
        round_safe_claims = 0
        round_deferred_tasks = 0
        for rid in self.fleet_ids:
            r_safe, r_def, r_tv, r_eta = self._build_bundle_aca(rid, tasks, robot_positions, current_step=current_step)
            round_safe_claims += r_safe
            round_deferred_tasks += r_def
            phase1_claims[rid] = [tid for tid in self.robots[rid].bundle if tid not in prev_bundles[rid]]
            robot_tv_eta[rid] = (r_tv, r_eta)

        # Check safe-claim conflicts against all robots holding tid at end of Phase 1
        claimed_in_phase1 = {tid for claims in phase1_claims.values() for tid in claims}
        safe_claim_holders = {
            tid: [rid for rid in self.fleet_ids if tid in self.robots[rid].bundle]
            for tid in claimed_in_phase1
        }
        safe_claim_conflicts = sum(1 for tid in claimed_in_phase1 if len(safe_claim_holders.get(tid, [])) > 1)

        # Log per-claim evaluations (Theorem 1 verification)
        for rid in self.fleet_ids:
            r_tv, r_eta = robot_tv_eta.get(rid, (0.0, 0.0))
            for tid in phase1_claims[rid]:
                is_conflicted = len(safe_claim_holders.get(tid, [])) > 1
                self.per_claim_logs.append({
                    "step": current_step,
                    "robot_id": rid,
                    "task_id": tid,
                    "tv_at_claim": r_tv,
                    "eta_eff": r_eta,
                    "claimed_safe": bool(self.enable_margin and len(self.fleet_ids) > 1),
                    "tv_le_eta": bool(r_tv <= r_eta),
                    "conflicted": bool(is_conflicted),
                })

        # Phase 2: Communication consensus for deferred/unassigned tasks
        rounds = 0
        if max_consensus_iterations is None or max_consensus_iterations == 5:
            p_drop = getattr(self.comm_net, "p_drop", 0.0) if self.comm_net is not None else 0.0
            eff_max_iter = max(5, min(15, int(math.ceil(2.0 * len(self.fleet_ids) / max(0.25, 1.0 - p_drop)))))
        else:
            eff_max_iter = max_consensus_iterations

        if eff_max_iter > 0:
            for _ in range(eff_max_iter):
                rounds += 1
                bundle_changed = False
                for rid in self.fleet_ids:
                    prev_b = list(self.robots[rid].bundle)
                    self._build_bundle(rid, tasks)
                    if self.robots[rid].bundle != prev_b:
                        bundle_changed = True
                comm_changed = self._communicate_and_resolve(current_step, robot_positions, tasks=tasks)
                if not bundle_changed and not comm_changed:
                    break

        # Update planned bundles
        fleet_states = getattr(self, "_round_fleet_states", None)
        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()}, fleet_states=fleet_states)

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
