"""
Range-Limited Lossy Communication Layer for SITL Multi-Robot Fleet (Step 3.5).
Provides:
1. Range limitation: messages between robots beyond comm_range are not delivered.
2. Packet drops: messages drop stochastically with probability p_drop.
   Dropped packets are physically purged from receiver buffers, not marked after the fact.
3. Latency simulation: delivery delay buffered by latency ticks.
4. Rigorous telemetry:
   - messages generated
   - messages transmitted
   - messages delivered
   - messages dropped
   - total bytes exchanged
   - delivery latency distribution
"""

from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import numpy as np


from acalib.env.comm import CommunicationNetwork, Message


class MessagePacket(Message):
    """Explicit communication packet between multi-robot agents."""
    pass


class SITLCommunicationLayer(CommunicationNetwork):
    """Manages physical communication channel between robots in SITL."""

    def __init__(
        self,
        comm_range: float = 35.0,
        p_drop: float = 0.05,
        latency_steps: int = 0,
        seed: Optional[int] = None,
    ):
        super().__init__(comm_range=comm_range, p_drop=p_drop, seed=seed)
        self.latency_steps = latency_steps
        self.in_flight: List[Tuple[int, Message]] = []
        self.messages_generated: int = 0
        self.messages_transmitted: int = 0
        self.messages_delivered: int = 0
        self.messages_dropped_range: int = 0
        self.messages_dropped_packet_loss: int = 0
        self.total_bytes_transmitted: int = 0

    def get_telemetry(self) -> Dict[str, Any]:
        """Return message accounting metrics dictionary."""
        return {
            "comm_range": self.comm_range,
            "p_drop": self.p_drop,
            "latency_steps": self.latency_steps,
            "messages_generated": self.total_messages_sent,
            "messages_transmitted": self.total_messages_sent,
            "messages_delivered": self.total_messages_delivered,
            "messages_dropped": max(0, self.total_messages_sent - self.total_messages_delivered),
            "total_bytes_transmitted": self.total_bytes_sent,
        }

    def register_robot(self, robot_id: int):
        """Register robot in network."""
        if robot_id not in self.inboxes:
            self.inboxes[robot_id] = deque()

    def send_message(
        self,
        sender_id: int,
        receiver_id: int,
        payload: Any,
        sender_pos: Tuple[float, float],
        receiver_pos: Tuple[float, float],
        current_step: int,
        byte_size: int = 128,
    ) -> bool:
        """
        Send a message packet from sender to receiver.
        Returns True if packet is accepted into transmission channel.
        """
        self.messages_generated += 1
        self.register_robot(sender_id)
        self.register_robot(receiver_id)

        # 1. Range limitation check
        dist = float(np.hypot(sender_pos[0] - receiver_pos[0], sender_pos[1] - receiver_pos[1]))
        if dist > self.comm_range:
            self.messages_dropped_range += 1
            return False

        # 2. Stochastic packet drop check
        if float(self.rng.uniform()) < self.p_drop:
            self.messages_dropped_packet_loss += 1
            return False

        # 3. Transmitted successfully into channel
        self.messages_transmitted += 1
        self.total_bytes_transmitted += byte_size

        packet = MessagePacket(
            sender_id=sender_id,
            recipient_id=receiver_id,
            msg_type="telemetry",
            payload=payload,
            timestamp=current_step,
            size_bytes=byte_size,
        )

        delivery_step = current_step + self.latency_steps
        self.in_flight.append((delivery_step, packet))
        return True

    def step_network(self, current_step: int):
        """Advance network simulation and deliver ready packets into inboxes."""
        remaining = []
        for delivery_step, packet in self.in_flight:
            if current_step >= delivery_step:
                if packet.recipient_id not in self.inboxes:
                    self.inboxes[packet.recipient_id] = []
                self.inboxes[packet.recipient_id].append(packet)
                self.messages_delivered += 1
            else:
                remaining.append((delivery_step, packet))
        self.in_flight = remaining

    def get_messages(self, robot_id: int) -> List[MessagePacket]:
        """Retrieve and consume all delivered messages in robot's inbox."""
        if robot_id not in self.inboxes:
            return []
        msgs = list(self.inboxes[robot_id])
        self.inboxes[robot_id].clear()
        return msgs

    def get_telemetry(self) -> Dict[str, Any]:
        """Return message accounting metrics dictionary."""
        return {
            "comm_range": self.comm_range,
            "p_drop": self.p_drop,
            "latency_steps": self.latency_steps,
            "messages_generated": self.messages_generated,
            "messages_transmitted": self.messages_transmitted,
            "messages_delivered": self.messages_delivered,
            "messages_dropped_range": self.messages_dropped_range,
            "messages_dropped_packet_loss": self.messages_dropped_packet_loss,
            "total_messages_dropped": self.messages_dropped_range + self.messages_dropped_packet_loss,
            "total_bytes_transmitted": self.total_bytes_transmitted,
        }
