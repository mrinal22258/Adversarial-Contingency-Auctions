"""
Consensus-Based Bundle Algorithm (CBBA - Choi, Brunet, How 2009).
Rigorous implementation with bundle construction, consensus phase, and release rules.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from .base import BaseAllocator, Task
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message


class CBBAAllocator(BaseAllocator):
    """
    Standard decentralized Consensus-Based Bundle Algorithm.
    Tracks winning agent table z, winning bid table y, and timestamp table s.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.fleet_ids = sorted(list(robots.keys()))

        # CBBA state tables per robot:
        # winning_bids[i][j]: robot i's belief of highest bid on task j
        self.y: Dict[int, Dict[int, float]] = {i: {} for i in self.fleet_ids}
        # winning_agents[i][j]: robot i's belief of winner for task j (-1 for none)
        self.z: Dict[int, Dict[int, int]] = {i: {} for i in self.fleet_ids}
        # timestamps[i][k]: timestamp of most recent info from robot k known by robot i
        self.s: Dict[int, Dict[int, int]] = {
            i: {k: 0 for k in self.fleet_ids} for i in self.fleet_ids
        }

    def _get_marginal_score(
        self,
        robot: RobotAgent,
        task: Task,
        bundle: List[int],
        tasks: Dict[int, Task],
    ) -> Tuple[float, int]:
        """
        Compute marginal score of adding task to bundle.
        Score = Task.reward - (travel cost increment).
        Returns (marginal_score, best_insertion_index).
        """
        curr_loc = robot.current_node

        # Calculate current bundle path cost
        def path_dist(b_list: List[int]) -> float:
            if not b_list:
                return 0.0
            tot = 0.0
            loc = curr_loc
            for tid in b_list:
                if tid not in tasks:
                    continue
                t_node = tasks[tid].node
                try:
                    tot += nx.shortest_path_length(self.graph, loc, t_node, weight="weight")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    tot += 500.0
                loc = t_node
            return tot

        curr_cost = path_dist(bundle)

        best_score = -float("inf")
        best_idx = len(bundle)

        # Test inserting at end of bundle
        for idx in range(len(bundle) + 1):
            cand_bundle = bundle[:idx] + [task.task_id] + bundle[idx:]
            cand_cost = path_dist(cand_bundle)
            cost_increase = cand_cost - curr_cost
            score = task.reward - cost_increase
            if score > best_score:
                best_score = score
                best_idx = idx

        return max(0.0, best_score), best_idx

    def _build_bundle(
        self,
        robot_id: int,
        tasks: Dict[int, Task],
    ) -> None:
        """Phase 1: Local bundle construction for robot_id."""
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1

            for tid, task in tasks.items():
                if tid in bundle or task.completed:
                    continue

                score, ins_idx = self._get_marginal_score(robot, task, bundle, tasks)
                current_winner_bid = self.y[robot_id].get(tid, 0.0)

                # Check if score beats current winning bid
                if score > current_winner_bid and score > best_val:
                    best_val = score
                    best_task_id = tid
                    best_insert_pos = ins_idx

            if best_task_id is not None and best_val > 0.0:
                bundle.insert(best_insert_pos, best_task_id)
                self.y[robot_id][best_task_id] = best_val
                self.z[robot_id][best_task_id] = robot_id
            else:
                break

        robot.bundle = bundle

    def _communicate_and_resolve(
        self,
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> bool:
        """
        Phase 2: Consensus communication and conflict resolution.
        Returns True if tables changed.
        """
        # Step 1: Each robot broadcasts its tables (y_i, z_i, s_i)
        for rid in self.fleet_ids:
            self.s[rid][rid] = current_step
            payload = {
                "y": dict(self.y[rid]),
                "z": dict(self.z[rid]),
                "s": dict(self.s[rid]),
                "belief": list(self.robots[rid].type_filter.get_belief_vector()),
            }
            # Byte size: ~8 bytes per task in table + header + belief floats
            byte_size = 32 + len(self.y[rid]) * 16 + len(payload["belief"]) * 8
            msg = Message(
                sender_id=rid,
                recipient_id=-1,
                msg_type="CBBA_CONSENSUS",
                payload=payload,
                timestamp=current_step,
                size_bytes=byte_size,
            )
            self.comm_net.send(msg, robot_positions)

        # Step 2: Receive and apply consensus resolution rules
        changed = False
        for rid in self.fleet_ids:
            inbox = self.comm_net.receive(rid)
            for msg in inbox:
                if msg.msg_type != "CBBA_CONSENSUS" or not isinstance(msg.payload, dict) or "y" not in msg.payload:
                    continue
                sender_k = msg.sender_id
                k_data = msg.payload
                y_k = k_data["y"]
                z_k = k_data["z"]
                s_k = k_data["s"]

                # Update recipient's Theory of Mind peer belief estimate
                if "belief" in k_data and hasattr(self.robots[rid], "tom_tracker"):
                    self.robots[rid].tom_tracker.update_peer_belief(
                        sender_k, np.array(k_data["belief"], dtype=float), current_step
                    )

                # Update timestamp vector
                for k_id, t_val in s_k.items():
                    if t_val > self.s[rid].get(k_id, 0):
                        self.s[rid][k_id] = t_val

                # Process all task bids
                all_tasks = set(self.y[rid].keys()).union(set(y_k.keys()))
                first_outbid_idx = -1

                for tid in all_tasks:
                    y_i_j = self.y[rid].get(tid, 0.0)
                    z_i_j = self.z[rid].get(tid, -1)
                    y_k_j = y_k.get(tid, 0.0)
                    z_k_j = z_k.get(tid, -1)

                    # Consensus update rules (Choi 2009)
                    if z_k_j == -1:
                        continue
                    elif z_i_j == rid:
                        if z_k_j != rid and y_k_j > y_i_j:
                            # Outbid!
                            self.y[rid][tid] = y_k_j
                            self.z[rid][tid] = z_k_j
                            changed = True
                            if tid in self.robots[rid].bundle:
                                idx = self.robots[rid].bundle.index(tid)
                                if first_outbid_idx == -1 or idx < first_outbid_idx:
                                    first_outbid_idx = idx
                    elif z_i_j == -1:
                        self.y[rid][tid] = y_k_j
                        self.z[rid][tid] = z_k_j
                        changed = True
                    else:
                        # Third-party comparisons
                        if y_k_j > y_i_j or (y_k_j == y_i_j and z_k_j < z_i_j):
                            self.y[rid][tid] = y_k_j
                            self.z[rid][tid] = z_k_j
                            changed = True

                # Bundle truncation rule: if lost task at index idx, release all subsequent tasks
                if first_outbid_idx != -1:
                    released = self.robots[rid].bundle[first_outbid_idx:]
                    self.robots[rid].bundle = self.robots[rid].bundle[:first_outbid_idx]
                    for r_tid in released:
                        if self.z[rid].get(r_tid) == rid:
                            self.z[rid][r_tid] = -1
                            self.y[rid][r_tid] = 0.0

        return changed

    def handle_replan_requests(self, tasks: Dict[int, Task], current_step: int, robot_positions: Dict[int, Tuple[float, float]]) -> int:
        """Standard CBBA: encountering blockage triggers full bundle release and global re-auction."""
        replan_events = 0
        for rid, robot in self.robots.items():
            if robot.replan_requests:
                replan_events += len(robot.replan_requests)
                for tid in list(robot.bundle):
                    self.y[rid][tid] = 0.0
                    self.z[rid][tid] = -1
                robot.bundle.clear()
                robot.replan_requests.clear()
        return replan_events

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        max_consensus_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Run CBBA bundle construction and consensus communication rounds."""
        round_replans = self.handle_replan_requests(tasks, current_step, robot_positions)

        # Clean up finished tasks from tables and robot bundles
        for rid in self.fleet_ids:
            self.robots[rid].bundle = [tid for tid in self.robots[rid].bundle if tid in tasks and not tasks[tid].completed]
            for tid, t in tasks.items():
                if t.completed and tid in self.z[rid]:
                    self.z[rid][tid] = -1
                    self.y[rid][tid] = 0.0

        # Phase 1: Local bundle additions
        for rid in self.fleet_ids:
            self._build_bundle(rid, tasks)

        # Phase 2: Communication consensus iterations
        rounds = 0
        for _ in range(max_consensus_iterations):
            rounds += 1
            changed = self._communicate_and_resolve(current_step, robot_positions)
            if not changed:
                break
            # Re-build bundle for agents that were truncated
            for rid in self.fleet_ids:
                self._build_bundle(rid, tasks)

        # Update robot planned paths
        for rid, robot in self.robots.items():
            robot.plan_task_bundle({tid: {"node": t.node} for tid, t in tasks.items()})

        # Count conflicts: tasks claimed by >= 2 robots
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
