"""
Decentralized Auction with Explicit Belief Exchange / Gossip (Phase A.5).
Robots explicitly gossip full belief vectors B_r and edge observation sets over the communication network.
Enables direct empirical comparison of ACA's 'no belief exchange' claim against explicit gossip.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx

from .cbba import CBBAAllocator
from .base import Task
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message


class CBBABeliefGossipAllocator(CBBAAllocator):
    """
    CBBA with Explicit Belief Vector Gossip.
    Every consensus broadcast includes full belief distribution B_r and edge observations,
    increasing payload size but accelerating belief pooling across reachable peers.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)

    def _communicate_and_resolve(
        self,
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> bool:
        """Consensus communication exchanging tables AND full belief vectors."""
        # Step 1: Broadcast tables + belief distribution (larger payload size)
        for rid in self.fleet_ids:
            self.s[rid][rid] = current_step
            belief_vec = list(self.robots[rid].type_filter.get_belief_vector())
            payload = {
                "y": dict(self.y[rid]),
                "z": dict(self.z[rid]),
                "s": dict(self.s[rid]),
                "belief_vector": belief_vec,
                "known_edges": dict(self.robots[rid].known_edge_states),
            }
            # Byte size: tables + 64 bytes header + full belief floats + edge observations
            byte_size = 48 + len(self.y[rid]) * 16 + len(belief_vec) * 8 + len(payload["known_edges"]) * 4
            msg = Message(
                sender_id=rid,
                recipient_id=-1,
                msg_type="CBBA_GOSSIP",
                payload=payload,
                timestamp=current_step,
                size_bytes=byte_size,
            )
            self.comm_net.send(msg, robot_positions)

        # Step 2: Receive and apply consensus resolution and belief pooling
        changed = False
        for rid in self.fleet_ids:
            inbox = self.comm_net.receive(rid)
            for msg in inbox:
                if msg.msg_type != "CBBA_GOSSIP" or not isinstance(msg.payload, dict):
                    continue
                sender_k = msg.sender_id
                k_data = msg.payload

                # Explicit belief pooling from gossiped belief vector
                if "belief_vector" in k_data:
                    peer_vec = np.array(k_data["belief_vector"], dtype=float)
                    # Pool beliefs: weighted geometric/linear average
                    self.robots[rid].type_filter.pool_beliefs([peer_vec], weights=[0.7, 0.3])

                # Standard CBBA table resolution
                y_k = k_data.get("y", {})
                z_k = k_data.get("z", {})
                s_k = k_data.get("s", {})

                for k_id, t_val in s_k.items():
                    if t_val > self.s[rid].get(k_id, 0):
                        self.s[rid][k_id] = t_val

                all_tasks = set(self.y[rid].keys()).union(set(y_k.keys()))
                first_outbid_idx = -1

                for tid in all_tasks:
                    y_i_j = self.y[rid].get(tid, 0.0)
                    z_i_j = self.z[rid].get(tid, -1)
                    y_k_j = y_k.get(tid, 0.0)
                    z_k_j = z_k.get(tid, -1)

                    if z_k_j == -1:
                        continue
                    elif z_i_j == rid:
                        if z_k_j != rid and y_k_j > y_i_j:
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
                        if y_k_j > y_i_j or (y_k_j == y_i_j and z_k_j < z_i_j):
                            self.y[rid][tid] = y_k_j
                            self.z[rid][tid] = z_k_j
                            changed = True

                if first_outbid_idx != -1:
                    released = self.robots[rid].bundle[first_outbid_idx:]
                    self.robots[rid].bundle = self.robots[rid].bundle[:first_outbid_idx]
                    for r_tid in released:
                        if self.z[rid].get(r_tid) == rid:
                            self.z[rid][r_tid] = -1
                            self.y[rid][r_tid] = 0.0

        return changed
