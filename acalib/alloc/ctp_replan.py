"""
Canadian Traveller Problem (CTP) Replan-on-Discovery Policy (Phase A.5).
Literature baseline based on Papadimitriou & Yannakakis (1991) and Bnaya et al. (2009).
Robots plan optimistically assuming unobserved edges are open.
Upon discovering an active blockage, the robot updates its local discovered obstacle map
and immediately computes a new shortest path on the updated topology.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import networkx as nx

from .base import BaseAllocator, Task
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message
from ..env.adversaries import canonical_edge


class CTPReplanAllocator(BaseAllocator):
    """
    Canadian Traveller Replan-on-Discovery Allocator.
    Assigns tasks based on shortest paths on current known graph,
    and replans dynamically upon discovering blockages during navigation.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        # Discovered blocked edges per robot
        self.known_blocked_edges: Dict[int, Set[Tuple[Any, Any]]] = {
            rid: set() for rid in self.fleet_ids
        }

    def _get_optimistic_tour_cost(self, robot_id: int, bundle: List[int], tasks: Dict[int, Task]) -> float:
        """Compute tour cost on robot's locally discovered graph."""
        if not bundle:
            return 0.0
        tot = 0.0
        loc = self.robots[robot_id].current_node
        blocked = self.known_blocked_edges[robot_id]

        def weight_fn(u: Any, v: Any, d: Dict[str, Any]) -> float:
            c_e = canonical_edge(u, v)
            if c_e in blocked:
                return 1e6
            return d.get("weight", 1.0)

        for tid in bundle:
            t_node = tasks[tid].node
            try:
                tot += nx.shortest_path_length(self.graph, loc, t_node, weight=weight_fn)
            except Exception:
                tot += 500.0
            loc = t_node
        return tot

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> Dict[str, Any]:
        """Allocate unassigned tasks and handle CTP replan-on-discovery requests."""
        # 1. Clean completed tasks
        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]

        # 2. Process discovered blockages from replan requests
        round_replans = 0
        for rid, robot in self.robots.items():
            if robot.replan_requests:
                round_replans += len(robot.replan_requests)
                # In CTP, the blocked edge is marked in robot's local map
                if robot.path_index < len(robot.active_path) - 1:
                    u = robot.active_path[robot.path_index]
                    v = robot.active_path[robot.path_index + 1]
                    self.known_blocked_edges[rid].add(canonical_edge(u, v))
                # Release blocked task to pool
                for b_tid in list(robot.replan_requests):
                    if b_tid in robot.bundle:
                        robot.bundle.remove(b_tid)
                robot.replan_requests.clear()

        # 3. Sequential greedy auction of unassigned tasks
        assigned_tids = {tid for r in self.robots.values() for tid in r.bundle}
        unassigned = [t for tid, t in tasks.items() if not t.completed and tid not in assigned_tids]

        messages_sent = 0
        for task in unassigned:
            best_cost_inc = float("inf")
            best_rid = None

            for rid in self.fleet_ids:
                robot = self.robots[rid]
                if len(robot.bundle) >= self.bundle_limit:
                    continue
                curr_cost = self._get_optimistic_tour_cost(rid, robot.bundle, tasks)
                cand_bundle = robot.bundle + [task.task_id]
                new_cost = self._get_optimistic_tour_cost(rid, cand_bundle, tasks)
                cost_inc = new_cost - curr_cost

                # Announce & bid messages
                msg = Message(
                    sender_id=rid,
                    recipient_id=-1,
                    msg_type="CTP_BID",
                    payload={"task_id": task.task_id, "cost": cost_inc},
                    timestamp=current_step,
                    size_bytes=32,
                )
                self.comm_net.send(msg, robot_positions)
                messages_sent += 1

                if cost_inc < best_cost_inc and cost_inc < 400.0:
                    best_cost_inc = cost_inc
                    best_rid = rid

            if best_rid is not None:
                self.robots[best_rid].bundle.append(task.task_id)

        # 4. Plan optimistic paths for all robots
        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})

        return {
            "messages_sent": messages_sent,
            "conflicts": 0,
            "replan_events": round_replans,
            "total_assigned": sum(len(r.bundle) for r in self.robots.values()),
        }
