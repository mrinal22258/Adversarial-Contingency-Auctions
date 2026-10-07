"""
RobotAgent: Autonomous robotic agent incorporating Bayesian belief updates,
Theory of Mind peer tracking, local contingency recourse pivoting, and task execution.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from ..env.adversaries import canonical_edge
from ..env.blockage_process import EdgeState, PersistentBlockageProcess
from ..env.comm import Message
from .belief import BayesianTypeFilter
from .tom import TheoryOfMindTracker, PinskerMarginCalculator
from .contingency import ContingencyPlanner, RecoursePlan


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

        # Node coordinates
        pos_dict = nx.get_node_attributes(graph, "pos")
        self.pos = pos_dict.get(start_node, (0.0, 0.0))

        # Core reasoning modules
        self.type_filter = BayesianTypeFilter()
        self.tom_tracker = TheoryOfMindTracker(robot_id, fleet_ids, eta=eta)
        self.pinsker_calc = PinskerMarginCalculator(eta=eta)
        self.planner = ContingencyPlanner(graph, max_depth=contingency_depth)

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
        self.type_filter = BayesianTypeFilter()
        self.tom_tracker = TheoryOfMindTracker(self.robot_id, self.fleet_ids, eta=self.eta)
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
        for u, v in self.graph.edges():
            pos_u = np.array(self.graph.nodes[u].get("pos", (0, 0)))
            pos_v = np.array(self.graph.nodes[v].get("pos", (0, 0)))
            midpoint = 0.5 * (pos_u + pos_v)
            dist_to_edge = float(np.linalg.norm(np.array(self.pos) - midpoint))

            if dist_to_edge <= self.sensor_range:
                c_e = canonical_edge(u, v)
                is_blocked = blockage_process.is_blocked(u, v)
                curr_state = EdgeState.BLOCKED if is_blocked else EdgeState.OPEN
                prior_state = self.known_edge_states.get(c_e)

                # Count robots in proximity for reactive model likelihood
                edge_robot_count = sum(
                    1 for _, st in fleet_states.items()
                    if st.get("current_node") in (u, v) or st.get("next_node") in (u, v)
                )

                self.type_filter.update_observation(
                    step=step,
                    edge=c_e,
                    observed_state=curr_state,
                    prior_state=prior_state,
                    edge_robot_count=edge_robot_count,
                )
                self.known_edge_states[c_e] = curr_state

    def get_edge_marginals(self, fleet_states: Optional[Dict[int, Any]] = None) -> Dict[Tuple[Any, Any], float]:
        """Compute all edge blockage marginals under current Bayesian belief."""
        marginals = {}
        for u, v in self.graph.edges():
            c_e = canonical_edge(u, v)
            if self.risky_edges is not None and c_e not in self.risky_edges:
                marginals[c_e] = 0.0
                continue
            edge_robot_count = 0
            if fleet_states:
                edge_robot_count = sum(
                    1 for _, st in fleet_states.items()
                    if st.get("current_node") in (u, v) or st.get("next_node") in (u, v)
                )
            marginals[c_e] = self.type_filter.compute_edge_marginal(c_e, edge_robot_count=edge_robot_count)
        return marginals

    def plan_task_bundle(self, tasks_dict: Dict[int, Any]) -> None:
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

        marginals = self.get_edge_marginals()
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
                new_plans[tid] = plan
                curr_loc = task_node
            else:
                pass

        self.assigned_plans = new_plans

        # Only reset the path if the active task changed or if robot was idle/replan
        new_active = self.bundle[0] if self.bundle and self.bundle[0] in self.assigned_plans else None
        if new_active != self.active_task_id or self.status in ("IDLE", "EXHAUSTED_NEEDS_REPLAN"):
            self.active_task_id = new_active
            if new_active is not None:
                self.active_path = list(self.assigned_plans[new_active].primary_path)
                self.path_index = 0
                self.edge_progress = 0.0
                self.status = "TRANSIT"
            else:
                self.active_path = [self.current_node]
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
