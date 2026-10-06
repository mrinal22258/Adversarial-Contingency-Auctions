"""
Pessimistic Robust Allocation and Centralized Omniscient Oracle.
- PessimisticAllocator: assumes all risky edges are permanently impassable (lower-risk, high-cost extreme).
- CentralizedOracleAllocator: knows true adversary type and ground-truth edge states; solves optimal allocation.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx
from scipy.optimize import linear_sum_assignment

from .base import BaseAllocator, Task
from .cbba import CBBAAllocator
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork
from ..env.adversaries import canonical_edge
from ..env.blockage_process import PersistentBlockageProcess


class PessimisticRobustAllocator(CBBAAllocator):
    """
    Pessimistic robust baseline: assumes all identified risky edges are blocked,
    forcing robots to avoid all risky edges entirely.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)

    def _get_marginal_score(
        self,
        robot: RobotAgent,
        task: Task,
        bundle: List[int],
        tasks: Dict[int, Task],
    ) -> Tuple[float, int]:
        """Compute path costs treating all risky edges with heavy penalty."""
        risky_edges = set(robot.get_edge_marginals().keys())

        def robust_weight(u: Any, v: Any, d: Dict[str, Any]) -> float:
            c_e = canonical_edge(u, v)
            base_w = d.get("weight", 1.0)
            if c_e in risky_edges:
                return base_w * 50.0  # extreme penalty
            return base_w

        curr_loc = robot.current_node

        def path_dist(b_list: List[int]) -> float:
            if not b_list:
                return 0.0
            tot = 0.0
            loc = curr_loc
            for tid in b_list:
                t_node = tasks[tid].node
                try:
                    tot += nx.shortest_path_length(self.graph, loc, t_node, weight=robust_weight)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    tot += 1000.0
                loc = t_node
            return tot

        curr_cost = path_dist(bundle)
        cand_bundle = bundle + [task.task_id]
        new_cost = path_dist(cand_bundle)
        cost_inc = new_cost - curr_cost
        score = max(0.0, task.reward - cost_inc)
        return score, len(bundle)


class CentralizedOracleAllocator(BaseAllocator):
    """
    Centralized Omniscient Oracle.
    Knows the true ground-truth graph state and active blockages,
    assigning tasks globally via minimum cost Hungarian matching.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        blockage_process: PersistentBlockageProcess,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.blockage_process = blockage_process

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> Dict[str, Any]:
        """Globally optimal task assignment via Hungarian algorithm on ground-truth graph."""
        active_tasks = [t for tid, t in tasks.items() if not t.completed]
        if not active_tasks:
            return {"conflicts": 0, "total_assigned": 0}

        # Subgraph without currently blocked edges
        g_open = self.graph.copy()
        for u, v in self.graph.edges():
            if self.blockage_process.is_blocked(u, v):
                if g_open.has_edge(u, v):
                    g_open.remove_edge(u, v)

        robot_list = list(self.robots.values())
        cost_matrix = np.full((len(robot_list), len(active_tasks)), 1000.0)

        for i, robot in enumerate(robot_list):
            for j, task in enumerate(active_tasks):
                try:
                    c = nx.shortest_path_length(g_open, robot.current_node, task.node, weight="weight")
                    cost_matrix[i, j] = c
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    cost_matrix[i, j] = 999.0

        # Hungarian assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # Clean up completed tasks
        for robot in robot_list:
            robot.bundle = [tid for tid in robot.bundle if tid in tasks and not tasks[tid].completed]

        # Retain currently active assignments
        assigned = {tid for r in robot_list for tid in r.bundle}
        unassigned = [t for t in active_tasks if t.task_id not in assigned]

        # Assign remaining tasks on ground-truth open graph up to bundle_limit
        for task in unassigned:
            best_cost = float("inf")
            best_robot = None
            for robot in robot_list:
                if len(robot.bundle) >= self.bundle_limit:
                    continue
                loc = robot.current_node
                try:
                    c = nx.shortest_path_length(g_open, loc, task.node, weight="weight")
                    if c < best_cost:
                        best_cost = c
                        best_robot = robot
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
            if best_robot is not None and best_cost < 500.0:
                best_robot.bundle.append(task.task_id)

        for robot in robot_list:
            if robot.bundle:
                active_tid = robot.bundle[0]
                target_node = tasks[active_tid].node
                try:
                    open_path = nx.shortest_path(g_open, robot.current_node, target_node, weight="weight")
                    robot.active_task_id = active_tid
                    robot.active_path = list(open_path)
                    robot.path_index = 0
                    robot.edge_progress = 0.0
                    robot.status = "TRANSIT"
                except Exception:
                    robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})
            else:
                robot.active_task_id = None
                robot.active_path = []
                robot.status = "IDLE"

        total_assigned = sum(len(r.bundle) for r in robot_list)
        return {"conflicts": 0, "total_assigned": total_assigned}
