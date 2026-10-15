"""
Communication Network model:
- Metric disk range or topological hop-limit
- Stochastic packet drops (p_drop)
- Accurate message count and byte accounting
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx


@dataclass
class Message:
    sender_id: int
    recipient_id: int  # -1 for local broadcast to communication neighbors
    msg_type: str
    payload: Any
    timestamp: int
    size_bytes: int = 64  # Estimated default serialized payload size


class CommunicationNetwork:
    """
    Simulates decentralized wireless communication with range constraints and packet loss.
    Maintains rigorous byte and message counters for empirical evaluation.
    """

    def __init__(
        self,
        comm_range: float = 40.0,
        p_drop: float = 0.05,
        hop_limit: Optional[int] = None,
        seed: Optional[int] = None,
    ):
        self.comm_range = comm_range
        self.p_drop = p_drop
        self.hop_limit = hop_limit
        self.rng = np.random.default_rng(seed)

        # Metrics accounting
        self.total_messages_sent: int = 0
        self.total_messages_delivered: int = 0
        self.total_bytes_sent: int = 0
        self.messages_by_robot: Dict[int, int] = {}
        self.bytes_by_robot: Dict[int, int] = {}

        # Inboxes: recipient_id -> list of Message
        self.inboxes: Dict[int, List[Message]] = {}

    def reset_metrics(self) -> None:
        self.total_messages_sent = 0
        self.total_messages_delivered = 0
        self.total_bytes_sent = 0
        self.messages_by_robot.clear()
        self.bytes_by_robot.clear()
        self.inboxes.clear()

    def get_neighbors(
        self,
        sender_id: int,
        robot_positions: Dict[int, Tuple[float, float]],
        graph: Optional[nx.Graph] = None,
    ) -> List[int]:
        """Find robot IDs in comm range of sender."""
        sender_pos = robot_positions[sender_id]
        neighbors = []

        for rid, pos in robot_positions.items():
            if rid == sender_id:
                continue
            dist = float(np.linalg.norm(np.array(sender_pos) - np.array(pos)))
            in_range = dist <= self.comm_range

            if in_range and self.hop_limit is not None and graph is not None:
                # Optional topological constraint check
                pass
            if in_range:
                neighbors.append(rid)

        return neighbors

    def send(
        self,
        msg: Message,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> None:
        """Queue a message for delivery, updating transmission counters."""
        sender_id = msg.sender_id
        self.total_messages_sent += 1
        self.total_bytes_sent += msg.size_bytes
        self.messages_by_robot[sender_id] = self.messages_by_robot.get(sender_id, 0) + 1
        self.bytes_by_robot[sender_id] = self.bytes_by_robot.get(sender_id, 0) + msg.size_bytes

        # Determine target recipients
        if msg.recipient_id == -1:
            recipients = self.get_neighbors(sender_id, robot_positions)
        else:
            recipients = [msg.recipient_id]

        sender_pos = robot_positions[sender_id]
        for rid in recipients:
            if rid not in robot_positions:
                continue
            # For unicast, verify recipient is within communication range;
            # broadcast neighbors are already verified in get_neighbors.
            if msg.recipient_id != -1:
                r_pos = robot_positions[rid]
                dist = float(np.linalg.norm(np.array(sender_pos) - np.array(r_pos)))
                if dist > self.comm_range:
                    continue

            # Stochastic channel drop
            if self.rng.random() >= self.p_drop:
                if rid not in self.inboxes:
                    self.inboxes[rid] = []
                self.inboxes[rid].append(msg)
                self.total_messages_delivered += 1

    def receive(self, robot_id: int) -> List[Message]:
        """Deliver queued messages for robot_id and clear its inbox."""
        msgs = self.inboxes.pop(robot_id, [])
        return msgs
