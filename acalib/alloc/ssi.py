"""
Sequential Single-Item (SSI) Auction (Koenig et al. 2006).
Classic baseline: tasks are auctioned sequentially one by one based on lowest marginal insertion cost.
"""

from typing import Dict, List, Tuple, Optional, Any
import networkx as nx

from .base import BaseAllocator, Task
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message


class SSIAllocator(BaseAllocator):
    """Sequential Single-Item auction allocator."""

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)

    def _tour_cost(self, robot: RobotAgent, bundle: List[int], tasks: Dict[int, Task]) -> float:
        """Compute shortest path tour cost for bundle from robot's current node."""
        if not bundle:
            return 0.0
        tot = 0.0
        loc = robot.current_node
        for tid in bundle:
            t_node = tasks[tid].node
            try:
                tot += nx.shortest_path_length(self.graph, loc, t_node, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                tot += 500.0
            loc = t_node
        return tot

    def _best_insertion(self, robot: RobotAgent, task: Task, tasks: Dict[int, Task]) -> Tuple[float, int]:
        """Find best insertion position and marginal cost for task into robot bundle."""
        curr_cost = self._tour_cost(robot, robot.bundle, tasks)
        best_inc = float("inf")
        best_pos = len(robot.bundle)
        for idx in range(len(robot.bundle) + 1):
            cand = robot.bundle[:idx] + [task.task_id] + robot.bundle[idx:]
            cost_inc = self._tour_cost(robot, cand, tasks) - curr_cost
            if cost_inc < best_inc:
                best_inc = cost_inc
                best_pos = idx
        return best_inc, best_pos

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> Dict[str, Any]:
        """Auction unassigned tasks sequentially based on minimum marginal insertion cost."""
        # Clean up completed tasks from robot bundles
        for rid, robot in self.robots.items():
            robot.bundle = [tid for tid in robot.bundle if tid in tasks and not tasks[tid].completed]

        # Handle blocked tasks that requested replanning
        round_replans = 0
        for rid, robot in self.robots.items():
            if robot.replan_requests:
                round_replans += len(robot.replan_requests)
                for b_tid in list(robot.replan_requests):
                    if b_tid in robot.bundle:
                        robot.bundle.remove(b_tid)
                robot.replan_requests.clear()

        # Find unassigned tasks
        assigned_tids = {tid for r in self.robots.values() for tid in r.bundle}
        unassigned = [
            t for tid, t in tasks.items()
            if not t.completed and tid not in assigned_tids
        ]

        messages_sent = 0
        for task in unassigned:
            best_bid = float("inf")
            best_robot_id = None
            best_insert_pos = -1

            for rid, robot in self.robots.items():
                if len(robot.bundle) >= self.bundle_limit:
                    continue
                cost_inc, ins_pos = self._best_insertion(robot, task, tasks)

                # Send bid message
                msg = Message(
                    sender_id=rid,
                    recipient_id=-1,
                    msg_type="SSI_BID",
                    payload={"task_id": task.task_id, "cost": cost_inc},
                    timestamp=current_step,
                    size_bytes=32,
                )
                self.comm_net.send(msg, robot_positions)
                messages_sent += 1

                if cost_inc < best_bid:
                    best_bid = cost_inc
                    best_robot_id = rid
                    best_insert_pos = ins_pos

            if best_robot_id is not None and best_bid < 400.0:
                self.robots[best_robot_id].bundle.insert(best_insert_pos, task.task_id)

        # Update planned routes
        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})

        return {"messages_sent": messages_sent, "conflicts": 0, "replan_events": round_replans}
