"""
Discrete-Event Multi-Robot Simulation Engine.
Manages realistic time steps, persistent Markov blockages, decentralized auctions,
local recourse branch executions, and wall-clock execution metrics.
"""

import time
from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from ..env.adversaries import (
    AdversaryType,
    create_adversary,
    CanonicalTypeList,
    CanonicalTypeSet,
)
from ..env.blockage_process import PersistentBlockageProcess
from ..env.comm import CommunicationNetwork
from ..agents.robot import RobotAgent
from ..agents.belief import compute_tv_distance
from ..alloc.base import Task, BaseAllocator
from ..alloc.cbba import CBBAAllocator
from ..alloc.aca import ACAAllocator
from ..alloc.ssi import SSIAllocator
from ..alloc.cbba_partial import CBBAPartialReplanAllocator
from ..alloc.cc_cbba import ChanceConstrainedCBBAAllocator
from ..alloc.implicit import ImplicitCoordinationAllocator
from ..alloc.pessimistic import (
    PessimisticRobustAllocator,
    ClairvoyantGreedyAllocator,
)
from ..alloc.ctp_replan import CTPReplanAllocator
from ..alloc.cbba_gossip import CBBABeliefGossipAllocator
from .metrics import SimulationMetrics
import pandas as pd


class SimulationEngine:
    """End-to-end discrete event simulation engine for multi-robot contingency auctions."""

    def __init__(
        self,
        graph: nx.Graph,
        adversary_type: AdversaryType = AdversaryType.STOCHASTIC,
        allocator_type: str = "aca",
        n_robots: int = 4,
        n_tasks: int = 20,
        task_arrival_mode: str = "batch",
        poisson_rate: float = 0.5,
        task_deadline: int = 250,
        max_steps: int = 90,
        comm_range: float = 45.0,
        p_drop: float = 0.05,
        contingency_depth: int = 1,
        risk_fraction: float = 0.25,
        clearance_rate: float = 0.15,
        adversary_budget_k: int = 4,
        seed: Optional[int] = None,
        robot_speeds: Optional[List[float]] = None,
        custom_start_nodes: Optional[List[Any]] = None,
        custom_tasks: Optional[Dict[int, Task]] = None,
        predrawn_clear_uniforms: Optional[Dict[Tuple[Tuple[Any, Any], int], float]] = None,
        predrawn_onset_uniforms: Optional[Dict[Tuple[Tuple[Any, Any], int], float]] = None,
        custom_risky_edges: Optional[Set[Tuple[Any, Any]]] = None,
        comm_net_seed: Optional[int] = None,
        record_traces: bool = False,
        **kwargs: Any,
    ):
        self.graph = graph
        self.adversary_type = adversary_type
        self.allocator_type = allocator_type.lower()
        self.n_robots = n_robots
        self.n_tasks = n_tasks
        self.task_arrival_mode = task_arrival_mode
        self.poisson_rate = poisson_rate
        self.task_deadline = task_deadline
        self.max_steps = max_steps
        self.comm_range = comm_range
        self.p_drop = p_drop
        self.contingency_depth = contingency_depth
        self.risk_fraction = risk_fraction
        self.clearance_rate = clearance_rate
        self.adversary_budget_k = adversary_budget_k
        self.rng = np.random.default_rng(seed)
        self.record_traces = record_traces
        self.traces: List[Dict[str, Any]] = []

        # 1. Adversary and Persistent Blockage Process
        self.adversary = create_adversary(
            adv_type=adversary_type,
            budget_k=adversary_budget_k,
            clearance_rate=clearance_rate,
            **kwargs,
        )
        self.blockage_process = PersistentBlockageProcess(
            graph=graph,
            adversary=self.adversary,
            risk_fraction=risk_fraction,
            clearance_rate=clearance_rate,
            seed=int(self.rng.integers(0, 1000000)) if comm_net_seed is None else comm_net_seed,
            custom_risky_edges=custom_risky_edges,
            predrawn_clear_uniforms=predrawn_clear_uniforms,
            predrawn_onset_uniforms=predrawn_onset_uniforms,
        )

        # 2. Communication Network
        self.comm_net = CommunicationNetwork(
            comm_range=comm_range,
            p_drop=p_drop,
            seed=int(self.rng.integers(0, 1000000)) if comm_net_seed is None else comm_net_seed + 1,
        )

        # 3. Robots
        nodes_list = sorted(list(graph.nodes()))
        self.robots: Dict[int, RobotAgent] = {}
        fleet_ids = list(range(n_robots))

        # Determine level execution depth for robots
        if self.allocator_type == "aca_depth_0":
            r_depth = 0
        elif self.allocator_type == "aca_depth_2":
            r_depth = 2
        elif self.allocator_type.endswith("_lr") or self.allocator_type.startswith("aca"):
            r_depth = contingency_depth if contingency_depth > 0 else 1
        else:
            r_depth = 0

        for rid in range(n_robots):
            if custom_start_nodes is not None and len(custom_start_nodes) > 0:
                start_node = custom_start_nodes[rid % len(custom_start_nodes)]
            else:
                start_node = nodes_list[int(self.rng.integers(0, len(nodes_list)))]
            spd = 5.0 if robot_speeds is None else robot_speeds[rid % len(robot_speeds)]
            self.robots[rid] = RobotAgent(
                robot_id=rid,
                start_node=start_node,
                graph=graph,
                fleet_ids=fleet_ids,
                speed=spd,
                contingency_depth=r_depth,
                risky_edges=self.blockage_process.risky_edges,
            )

        # 4. Allocator
        self.allocator = self._create_allocator(self.allocator_type, kwargs)

        # 5. Tasks
        if custom_tasks is not None:
            import copy
            self.tasks = copy.deepcopy(custom_tasks)
        else:
            self.tasks = self._generate_tasks(nodes_list)

    def _create_allocator(self, alloc_type: str, kwargs: Dict[str, Any]) -> BaseAllocator:
        if alloc_type.startswith("aca_kappa_"):
            try:
                k_val = float(alloc_type.split("aca_kappa_")[1])
            except ValueError:
                k_val = 1.0
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                margin_kappa=k_val,
                enable_margin=True,
            )
        elif alloc_type == "aca_depth_2":
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=2,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=True,
            )
        elif alloc_type == "aca_no_inference":
            alloc = ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=True,
            )
            for r in self.robots.values():
                r.type_filter.frozen = True
            return alloc
        elif alloc_type == "aca_oracle_adv":
            alloc = ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=True,
            )
            for r in self.robots.values():
                r.type_filter.set_oracle(self.adversary_type)
            return alloc
        elif alloc_type in ("aca_adaptive", "aca_adapt"):
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=True,
                adaptive_margin=True,
                prune_threshold=kwargs.get("prune_threshold", 0.0),
                margin_kappa=kwargs.get("margin_kappa", 1.0),
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("aca_plus", "aca_pruned"):
            alloc = ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=True,
                adaptive_margin=True,
                prune_threshold=kwargs.get("prune_threshold", 0.20),
                margin_kappa=kwargs.get("margin_kappa", 1.0),
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
            for r in self.robots.values():
                r.prune_threshold = alloc.prune_threshold
            return alloc
        elif alloc_type in ("aca", "aca_cbba"):
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=kwargs.get("enable_margin", True),
                margin_kappa=kwargs.get("margin_kappa", 1.0),
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("aca_no_margin", "aca_nomargin"):
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=self.contingency_depth,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=False,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("aca_depth_0", "aca_d0"):
            return ACAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                contingency_depth=0,
                delta_map=kwargs.get("delta_map", 0.0),
                enable_margin=kwargs.get("enable_margin", True),
                margin_kappa=kwargs.get("margin_kappa", 1.0),
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("cbba", "cbba_lr"):
            return CBBAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("cbba_partial", "partial_replan", "cbba_partial_lr"):
            return CBBAPartialReplanAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("cc_cbba", "chance_constrained", "cc_cbba_lr"):
            alpha_risk = kwargs.get("alpha_risk", 0.30)
            return ChanceConstrainedCBBAAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                alpha_risk=alpha_risk,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("implicit", "implicit_no_margin", "implicit_lr"):
            return ImplicitCoordinationAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("ssi", "sequential_single_item", "ssi_lr"):
            return SSIAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("ctp_replan", "ctp", "ctp_lr"):
            return CTPReplanAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        elif alloc_type in ("cbba_gossip", "gossip", "cbba_gossip_lr"):
            return CBBABeliefGossipAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
            )
        elif alloc_type in ("pessimistic", "pessimistic_robust"):
            return PessimisticRobustAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
            )
        elif alloc_type in ("oracle", "centralized_oracle", "clairvoyant_greedy"):
            return ClairvoyantGreedyAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                blockage_process=self.blockage_process,
            )
        elif alloc_type in ("foresight_opt", "foresight_optimal"):
            from ..alloc.foresight_opt import ForesightOptAllocator
            return ForesightOptAllocator(
                graph=self.graph,
                robots=self.robots,
                comm_net=self.comm_net,
                blockage_process=self.blockage_process,
                bundle_limit=kwargs.get("bundle_limit", 4),
            )
        else:
            raise ValueError(f"Unknown allocator type: {alloc_type}")

    def _generate_tasks(self, nodes_list: List[Any]) -> Dict[int, Task]:
        tasks = {}
        for tid in range(self.n_tasks):
            t_node = nodes_list[int(self.rng.integers(0, len(nodes_list)))]
            if self.task_arrival_mode == "poisson":
                arr_step = int(self.rng.poisson(tid / max(0.1, self.poisson_rate)))
            else:
                arr_step = 0  # Batch arrival at start

            tasks[tid] = Task(
                task_id=tid,
                node=t_node,
                reward=100.0,
                arrival_step=arr_step,
                deadline=arr_step + self.task_deadline,
            )
        return tasks

    def reset(self, max_steps: Optional[int] = None) -> "SimulationEngine":
        """Initialize or reset simulation state and metrics."""
        if max_steps is not None:
            self.max_steps = max_steps
        self.metrics = SimulationMetrics(total_tasks=self.n_tasks, total_robots=self.n_robots)
        self.start_wall_time = time.perf_counter()
        self.last_pos = {rid: np.array(r.pos) for rid, r in self.robots.items()}
        self.distinct_conflicted_tids = set()
        self.current_step = 0
        return self

    def step(self, step_idx: Optional[int] = None) -> bool:
        """
        Execute a single tick/step of the simulation.
        Returns True if simulation is ongoing, False if terminated.
        """
        if not hasattr(self, "metrics") or self.metrics is None:
            self.reset()

        if step_idx is not None:
            step = step_idx
        else:
            step = self.current_step

        if step >= self.max_steps:
            return False

        tick_start = time.perf_counter()

        # 1. Update active tasks based on arrivals & deadlines
        active_available_tasks = {}
        for tid, t in self.tasks.items():
            if t.completed:
                continue
            if step >= t.deadline:
                self.metrics.expired_tasks += 1
                t.completed = True
                for r in self.robots.values():
                    if tid in r.bundle:
                        r.bundle.remove(tid)
                continue
            if step >= t.arrival_step:
                active_available_tasks[tid] = t

        if not active_available_tasks:
            self.metrics.makespan = step
            return False

        # 2. Advance Markov Blockage Process
        fleet_states = {rid: r.get_state_summary() for rid, r in self.robots.items()}
        self.blockage_process.step(fleet_states, step)

        # 3. Robots Sense Local Environment & Bayesian Update
        for rid, robot in self.robots.items():
            robot.sense_environment(self.blockage_process, fleet_states, step)

        # 4. Check Belief Convergence
        if self.metrics.belief_convergence_step is None and self.adversary_type in CanonicalTypeList:
            true_idx = CanonicalTypeList.index(self.adversary_type)
            all_converged = True
            for r in self.robots.values():
                b_vec = r.type_filter.get_belief_vector()
                if b_vec[true_idx] < 0.85:
                    all_converged = False
                    break
            if all_converged:
                self.metrics.belief_convergence_step = step

        # 5. Task Allocation Phase
        assigned_tids = {t for r in self.robots.values() for t in r.bundle}
        unassigned = any(tid not in assigned_tids for tid in active_available_tasks)
        replans_pending = any(len(r.replan_requests) > 0 for r in self.robots.values())
        robot_pos_dict = {rid: r.pos for rid, r in self.robots.items()}

        if unassigned or replans_pending or step % 10 == 0:
            alloc_res = self.allocator.allocate_round(
                tasks=active_available_tasks,
                current_step=step,
                robot_positions=robot_pos_dict,
            )
            self.metrics.allocation_rounds += 1
            self.metrics.total_conflicts += alloc_res.get("conflicts", 0)
            self.metrics.safe_claim_conflicts += alloc_res.get("safe_claim_conflicts", 0)
            self.metrics.safe_claims += alloc_res.get("safe_claims", 0)
            self.metrics.deferred_claims += alloc_res.get("deferred_tasks", 0)
            self.metrics.reauction_events += alloc_res.get("replan_events", 0)

            task_holders: Dict[int, List[int]] = {}
            for r_id, r_obj in self.robots.items():
                for t_id in r_obj.bundle:
                    task_holders.setdefault(t_id, []).append(r_id)
            for t_id, holders in task_holders.items():
                if len(holders) > 1:
                    self.distinct_conflicted_tids.add(t_id)
            self.metrics.distinct_conflicts = len(self.distinct_conflicted_tids)

        # 6. Physical Execution Step (Movement, Recourse Pivots, Task Completions)
        tasks_info = {tid: {"node": t.node} for tid, t in self.tasks.items()}
        for rid, robot in self.robots.items():
            prev_completed_count = len(robot.completed_tasks)
            robot.step_execution(self.blockage_process, tasks_info, dt=1.0)

            if len(robot.completed_tasks) > prev_completed_count:
                newly_done_tid = robot.completed_tasks[-1]
                if newly_done_tid in self.tasks and not self.tasks[newly_done_tid].completed:
                    self.tasks[newly_done_tid].completed = True
                    self.tasks[newly_done_tid].completed_by = rid
                    self.metrics.completed_tasks += 1
                    latency = step - self.tasks[newly_done_tid].arrival_step
                    self.metrics.task_latencies.append(latency)
                    self.metrics.total_reward += self.tasks[newly_done_tid].reward

        active_counts: Dict[int, int] = {}
        for r in self.robots.values():
            if r.active_task_id is not None:
                active_counts[r.active_task_id] = active_counts.get(r.active_task_id, 0) + 1

        seen_active = set()
        for rid, r in self.robots.items():
            curr_p = np.array(r.pos)
            d = float(np.linalg.norm(curr_p - self.last_pos[rid]))
            self.metrics.total_travel_distance += d
            if r.active_task_id is not None and active_counts.get(r.active_task_id, 0) > 1:
                if r.active_task_id in seen_active:
                    self.metrics.duplicated_distance += d
                else:
                    seen_active.add(r.active_task_id)
            self.last_pos[rid] = curr_p

        tick_elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
        self.metrics.per_tick_runtimes_ms.append(tick_elapsed_ms)

        self.metrics.total_messages_sent = self.comm_net.total_messages_sent
        self.metrics.total_bytes_sent = self.comm_net.total_bytes_sent

        if self.record_traces:
            fleet_b = [r.type_filter.get_belief_vector() for r in self.robots.values()]
            tvs = [
                compute_tv_distance(fleet_b[i], fleet_b[j])
                for i in range(len(fleet_b))
                for j in range(i + 1, len(fleet_b))
            ]
            mean_tv = float(np.mean(tvs)) if tvs else 0.0
            max_tv = float(np.max(tvs)) if tvs else 0.0
            true_idx = CanonicalTypeList.index(self.adversary_type) if self.adversary_type in CanonicalTypeList else -1
            mean_b_true = float(np.mean([b[true_idx] for b in fleet_b])) if (true_idx >= 0 and fleet_b) else 0.0

            # Margin observation
            margin_val = 0.0
            if hasattr(self.allocator, "last_computed_margin"):
                margin_val = float(getattr(self.allocator, "last_computed_margin", 0.0))

            self.traces.append({
                "step": step,
                "mean_pairwise_tv": mean_tv,
                "max_pairwise_tv": max_tv,
                "mean_belief_true": mean_b_true,
                "margin": margin_val,
                "total_messages": self.comm_net.total_messages_sent,
                "total_bytes": self.comm_net.total_bytes_sent,
                "completed_tasks": self.metrics.completed_tasks,
                "active_blockages": len(self.blockage_process.get_blocked_edges()),
                "replan_events": self.metrics.reauction_events,
            })

        self.current_step += 1
        return True

    def finalize(self) -> SimulationMetrics:
        """Finalize simulation summary statistics and returns metrics object."""
        if self.metrics.makespan == 0:
            self.metrics.makespan = self.current_step or self.max_steps

        self.metrics.failed_tasks = self.metrics.total_tasks - self.metrics.completed_tasks
        self.metrics.total_messages_sent = self.comm_net.total_messages_sent
        self.metrics.total_bytes_sent = self.comm_net.total_bytes_sent
        self.metrics.net_welfare = self.metrics.total_reward - self.metrics.total_travel_distance
        self.metrics.total_wall_clock_ms = (time.perf_counter() - self.start_wall_time) * 1000.0
        return self.metrics

    def run(self, max_steps: Optional[int] = None) -> SimulationMetrics:
        """Execute full mission until completion or max_steps."""
        steps_to_run = max_steps if max_steps is not None else self.max_steps
        self.reset(max_steps=steps_to_run)
        for step in range(steps_to_run):
            cont = self.step(step)
            if not cont:
                break
        return self.finalize()

    def get_trace_df(self) -> pd.DataFrame:
        """Return recorded per-step telemetry traces as a pandas DataFrame."""
        return pd.DataFrame(self.traces)


