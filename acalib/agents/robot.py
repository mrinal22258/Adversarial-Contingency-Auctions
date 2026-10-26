"""
RobotAgent: Autonomous robotic agent incorporating Bayesian belief updates,
Theory of Mind peer tracking, local contingency recourse pivoting, and task execution.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import logging
import math
import networkx as nx

from ..env.adversaries import canonical_edge, get_edge_vulnerability_class
from ..env.blockage_process import EdgeState, PersistentBlockageProcess
from .belief import BayesianTypeFilter
from .tom import TheoryOfMindTracker, PinskerMarginCalculator
from .contingency import ContingencyPlanner, RecoursePlan

logger = logging.getLogger(__name__)


class RobotAgent:
    """
    Decentralized multi-robot agent.
    Maintains Bayesian belief filter, ToM peer divergence estimates,
    and executes contingency recourse paths locally upon encountering blockages.
    """

    def __init__(
        self,
        robot_id: int,
        start_node: Any,
        graph: nx.Graph,
        fleet_ids: List[int],
        speed: float = 5.0,
        sensor_range: float = 25.0,
        contingency_depth: int = 1,
        eta: float = 0.05,
        risky_edges: Optional[Set[Tuple[Any, Any]]] = None,
        max_deep_branches: Optional[int] = 2,
        partition_mode: bool = False,
        enforce_analytical_bounds: bool = False,
        gamma_obs: float = 0.35,
    ):
        self.robot_id = robot_id
        self.current_node = start_node
        self.graph = graph
        self.fleet_ids = fleet_ids
        self.speed = speed
        self.sensor_range = sensor_range
        self.contingency_depth = contingency_depth
        self.eta = eta
        self.risky_edges = risky_edges
        self.max_deep_branches = max_deep_branches
        self.partition_mode = partition_mode
        self.enforce_analytical_bounds = enforce_analytical_bounds
        self.gamma_obs = gamma_obs

        # Node coordinates
        pos_dict = nx.get_node_attributes(graph, "pos")
        self.pos = pos_dict.get(start_node, (0.0, 0.0))

        # Core reasoning modules
        self.type_filter = BayesianTypeFilter(enforce_analytical_bounds=enforce_analytical_bounds)
        self.tom_tracker = TheoryOfMindTracker(
            robot_id,
            fleet_ids,
            eta=eta,
            gamma_obs=gamma_obs,
            partition_mode=partition_mode,
            enforce_analytical_bounds=enforce_analytical_bounds,
        )
        self.pinsker_calc = PinskerMarginCalculator(eta=eta)
        self.planner = ContingencyPlanner(
            graph,
            max_depth=contingency_depth,
            max_deep_branches=max_deep_branches,
        )

        # Local task allocation and execution state
        self.bundle: List[int] = []  # Ordered list of task IDs
        self.assigned_plans: Dict[int, RecoursePlan] = {}  # task_id -> RecoursePlan
        self.active_task_id: Optional[int] = None
        self.active_path: List[Any] = [start_node]
        self.path_index: int = 0
        self.edge_progress: float = 0.0  # distance traveled on current edge

        # Local edge observation memory
        self.known_edge_states: Dict[Tuple[Any, Any], EdgeState] = {}
        self.blocked_edges: Set[Tuple[Any, Any]] = set()

        # Execution flags
        self.status: str = "IDLE"  # IDLE, TRANSIT, PIVOTED, EXHAUSTED_NEEDS_REPLAN
        self.completed_tasks: List[int] = []
        self.failed_tasks: List[int] = []
        self.replan_requests: List[int] = []  # tasks needing partial re-auction

    def reset_for_run(self, start_node: Any) -> None:
        """Reset internal execution state for a new experiment seed."""
        self.current_node = start_node
        pos_dict = nx.get_node_attributes(self.graph, "pos")
        self.pos = pos_dict.get(start_node, (0.0, 0.0))
        self.type_filter = BayesianTypeFilter(
            enforce_analytical_bounds=self.enforce_analytical_bounds
        )
        self.tom_tracker = TheoryOfMindTracker(
            self.robot_id,
            self.fleet_ids,
            eta=self.eta,
            gamma_obs=self.gamma_obs,
            partition_mode=self.partition_mode,
            enforce_analytical_bounds=self.enforce_analytical_bounds,
        )
        self.bundle.clear()
        self.assigned_plans.clear()
        self.active_task_id = None
        self.active_path = [start_node]
        self.path_index = 0
        self.edge_progress = 0.0
        self.known_edge_states.clear()
        self.blocked_edges.clear()
        self.status = "IDLE"
        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.replan_requests.clear()

    def get_state_summary(self) -> Dict[str, Any]:
        """Export state dictionary for environment tracking."""
        next_node = None
        if self.path_index + 1 < len(self.active_path):
            next_node = self.active_path[self.path_index + 1]

        target_node = None
        if self.active_task_id is not None and self.active_task_id in self.assigned_plans:
            target_node = self.assigned_plans[self.active_task_id].target_node

        return {
            "robot_id": self.robot_id,
            "pos": self.pos,
            "current_node": self.current_node,
            "next_node": next_node,
            "target_node": target_node,
            "bundle": list(self.bundle),
            "status": self.status,
            "speed": self.speed,
        }

    def sense_environment(
        self,
        blockage_process: PersistentBlockageProcess,
        fleet_states: Dict[int, Any],
        step: int,
    ) -> None:
        """
        Scan edges within sensor range and update Bayesian type filter.
        Ensures observations are only updated once per tick.
        """
        edge_midpoints = self.graph.graph.get("_cached_edge_midpoints")
        if edge_midpoints is None:
            pos_dict = nx.get_node_attributes(self.graph, "pos")
            edge_midpoints = {
                (u, v): (
                    0.5 * (pos_dict.get(u, (0.0, 0.0))[0] + pos_dict.get(v, (0.0, 0.0))[0]),
                    0.5 * (pos_dict.get(u, (0.0, 0.0))[1] + pos_dict.get(v, (0.0, 0.0))[1]),
                )
                for u, v in self.graph.edges()
            }
            self.graph.graph["_cached_edge_midpoints"] = edge_midpoints

        rx, ry = self.pos
        sr_sq = self.sensor_range * self.sensor_range

        from ..env.adversaries import compute_edge_robot_count, compute_interdiction_cut
        all_known = set(self.known_edge_states.keys()) or set(canonical_edge(x, y) for x, y in self.graph.edges())
        targeted_cut = compute_interdiction_cut(self.graph, all_known, fleet_states)

        obs_count = 0
        max_obs = max(1, int(math.floor(self.tom_tracker.gamma_obs * 1.0))) if self.enforce_analytical_bounds else None

        for (u, v), (mx, my) in edge_midpoints.items():
            dx = rx - mx
            dy = ry - my
            if dx * dx + dy * dy <= sr_sq:
                c_e = canonical_edge(u, v)
                is_blocked = blockage_process.is_blocked(u, v)
                curr_state = EdgeState.BLOCKED if is_blocked else EdgeState.OPEN
                prior_state = self.known_edge_states.get(c_e)

                edge_robot_count = compute_edge_robot_count(self.graph, c_e, fleet_states)
                is_targeted = c_e in targeted_cut
                v_class = get_edge_vulnerability_class(self.graph, c_e)

                if not self.enforce_analytical_bounds or (max_obs is not None and obs_count < max_obs):
                    self.type_filter.update_observation(
                        step=step,
                        edge=c_e,
                        observed_state=curr_state,
                        prior_state=prior_state,
                        edge_robot_count=edge_robot_count,
                        is_targeted_by_interdiction=is_targeted,
                        vulnerability_class=v_class,
                        enforce_analytical_bounds=self.enforce_analytical_bounds,
                    )
                    obs_count += 1
                self.known_edge_states[c_e] = curr_state

    def get_edge_marginals(self, fleet_states: Optional[Dict[int, Any]] = None) -> Dict[Tuple[Any, Any], float]:
        """Compute all edge blockage marginals under current Bayesian belief with explicit fleet state."""
        if fleet_states is None:
            fleet_states = {self.robot_id: self.get_state_summary()}

        from ..env.adversaries import compute_fleet_edge_robot_counts, compute_interdiction_cut
        edges = self.graph.graph.get("_canonical_edges")
        if edges is None:
            edges = [canonical_edge(u, v) for u, v in self.graph.edges()]
            self.graph.graph["_canonical_edges"] = edges

        edge_counts = compute_fleet_edge_robot_counts(self.graph, edges, fleet_states)
        risky_set = set(self.risky_edges) if self.risky_edges is not None else set(edges)
        targeted_cuts = compute_interdiction_cut(self.graph, risky_set, fleet_states)

        marginals = {}
        for c_e in edges:
            if self.risky_edges is not None and c_e not in self.risky_edges:
                marginals[c_e] = 0.0
                continue
            count = edge_counts.get(c_e, 0.0)
            is_tgt = c_e in targeted_cuts
            v_class = get_edge_vulnerability_class(self.graph, c_e)
            marginals[c_e] = self.type_filter.compute_edge_marginal(
                c_e,
                edge_robot_count=count,
                is_targeted_by_interdiction=is_tgt,
                vulnerability_class=v_class,
            )

        return marginals

    def plan_task_bundle(self, tasks_dict: Dict[int, Any], fleet_states: Optional[Dict[int, Any]] = None) -> None:
        """
        Re-plan sequential paths for all tasks currently in bundle.
        Preserves bundle ordering and constructs contingency recourse plans.
        Never resets mid-edge progress if current active task remains unchanged.
        """
        if not self.bundle:
            self.active_task_id = None
            self.active_path = [self.current_node]
            self.path_index = 0
            self.edge_progress = 0.0
            self.status = "IDLE"
            self.assigned_plans.clear()
            return

        if fleet_states is None:
            fleet_states = {self.robot_id: self.get_state_summary()}
        marginals = self.get_edge_marginals(fleet_states=fleet_states)
        curr_loc = self.current_node
        new_plans = {}

        for tid in self.bundle:
            if tid not in tasks_dict:
                continue
            task_node = tasks_dict[tid]["node"]
            plan = self.planner.build_recourse_plan(
                task_id=tid,
                start_node=curr_loc,
                target_node=task_node,
                edge_marginals=marginals,
            )
            if plan is not None:
                if getattr(self, "prune_threshold", 0.0) > 0.0 and plan.tree is not None:
                    from .contingency import prune_recourse_plan
                    plan = prune_recourse_plan(plan, self.prune_threshold, self.planner, marginals)
                new_plans[tid] = plan
                curr_loc = task_node
            else:
                logger.debug(
                    "Robot %s failed to build recourse plan for task %s from location %s",
                    self.robot_id, tid, curr_loc,
                )

        self.assigned_plans = new_plans

        # Only reset the path if the active task changed or if robot was idle/replan
        new_active = self.bundle[0] if self.bundle and self.bundle[0] in self.assigned_plans else None
        if new_active != self.active_task_id or self.status in ("IDLE", "EXHAUSTED_NEEDS_REPLAN"):
            self.active_task_id = new_active
            if new_active is not None:
                self.active_path = list(self.assigned_plans[new_active].primary_path)
                self.tree_cursor = self.assigned_plans[new_active].tree
                self.path_index = 0
                self.edge_progress = 0.0
                self.status = "TRANSIT"
            else:
                self.active_path = [self.current_node]
                self.tree_cursor = None
                self.path_index = 0
                self.edge_progress = 0.0
                self.status = "IDLE"
        # else: keep executing the current path/edge without resetting progress!

    def step_execution(
        self,
        blockage_process: PersistentBlockageProcess,
        tasks_dict: Dict[int, Any],
        dt: float = 1.0,
    ) -> None:
        """
        Execute movement along active path at designated speed.
        Delegates to shared LocalRecourseExecutor ensuring identical execution physics and pivot semantics across all allocators.
        """
        from .executor import LocalRecourseExecutor
        LocalRecourseExecutor.step_execution(self, blockage_process, tasks_dict, dt=dt)
