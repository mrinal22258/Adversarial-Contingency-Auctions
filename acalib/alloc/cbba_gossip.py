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
        """Consensus communication exchanging tables AND full belief vectors via shared consensus."""
        from .consensus import execute_consensus_exchange

        def extra_payload(rid: int) -> Dict[str, Any]:
            belief_vec = list(self.robots[rid].type_filter.get_belief_vector())
            return {
                "belief_vector": belief_vec,
                "known_edges": dict(self.robots[rid].known_edge_states),
            }

        def handle_extra(rid: int, sender_k: int, k_data: Dict[str, Any]) -> None:
            if "belief_vector" in k_data:
                peer_vec = np.array(k_data["belief_vector"], dtype=float)
                self.robots[rid].type_filter.pool_beliefs([peer_vec], weights=[0.7, 0.3])

        return execute_consensus_exchange(
            fleet_ids=self.fleet_ids,
            robots=self.robots,
            comm_net=self.comm_net,
            y=self.y,
            z=self.z,
            s=self.s,
            current_step=current_step,
            robot_positions=robot_positions,
            msg_type="CBBA_GOSSIP",
            extra_payload_fn=extra_payload,
            handle_extra_payload_fn=handle_extra,
        )
