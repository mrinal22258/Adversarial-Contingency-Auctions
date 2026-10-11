"""
CBBA with Partial Replanning (Buckman, Choi, How 2019).
Strong literature competitor replacing Greedy DRA.
Re-auctions only the blocked task locally rather than clearing the entire bundle.
"""

from typing import Dict, List, Tuple, Any
import networkx as nx

from .base import Task
from .cbba import CBBAAllocator
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message


class CBBAPartialReplanAllocator(CBBAAllocator):
    """
    CBBA with Partial Replanning on blockage events.
    When a robot encounters a blockage on task j, only task j is released
    and re-auctioned, retaining all subsequent valid bundle tasks.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.replan_events: int = 0

    def handle_robot_replan_requests(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> int:
        """Process robots that encountered blockages and requested partial re-auction."""
        round_replans = 0
        for rid, robot in self.robots.items():
            if robot.replan_requests:
                for blocked_tid in list(robot.replan_requests):
                    round_replans += 1
                    self.replan_events += 1
                    # Broadcast release message for blocked_tid
                    msg = Message(
                        sender_id=rid,
                        recipient_id=-1,
                        msg_type="PARTIAL_RELEASE",
                        payload={"task_id": blocked_tid},
                        timestamp=current_step,
                        size_bytes=32,
                    )
                    self.comm_net.send(msg, robot_positions)

                    # Reset local table for blocked_tid only (retaining remaining bundle)
                    self.y[rid][blocked_tid] = 0.0
                    self.z[rid][blocked_tid] = -1

                robot.replan_requests.clear()
                # Re-plan remaining bundle
                robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})
        return round_replans

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        max_consensus_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Handle partial replan requests then run consensus rounds."""
        round_replans = self.handle_robot_replan_requests(tasks, current_step, robot_positions)

        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]
            for tid, t in tasks.items():
                if t.completed and tid in self.z[rid]:
                    self.z[rid][tid] = -1
                    self.y[rid][tid] = 0.0

        for rid in self.fleet_ids:
            self._build_bundle(rid, tasks)

        rounds = 0
        for _ in range(max_consensus_iterations):
            rounds += 1
            changed = self._communicate_and_resolve(current_step, robot_positions)
            if not changed:
                break
            for rid in self.fleet_ids:
                self._build_bundle(rid, tasks)

        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})

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
            "replan_events": round_replans,
            "total_assigned": sum(len(r.bundle) for r in self.robots.values()),
        }
