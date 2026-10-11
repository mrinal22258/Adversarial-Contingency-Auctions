"""
Base classes and data structures for task allocation mechanisms.
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import abc
import networkx as nx

from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork


@dataclass
class Task:
    task_id: int
    node: Any
    reward: float = 100.0
    arrival_step: int = 0
    deadline: int = 300
    completed: bool = False
    assigned_robot: Optional[int] = None
    completed_by: Optional[int] = None

    @property
    def destination(self) -> Any:
        return self.node


class BaseAllocator(abc.ABC):
    """Abstract base allocator interface for multi-robot task allocation."""

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 5,
    ):
        self.graph = graph
        self.robots = robots
        self.comm_net = comm_net
        self.bundle_limit = bundle_limit
        self.fleet_ids = list(self.robots.keys())

    @abc.abstractmethod
    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
    ) -> Dict[str, Any]:
        """
        Execute one or more communication/bidding phases of the auction mechanism.
        Returns round metrics dict (e.g. messages_sent, conflicts_detected, etc.).
        """
        pass
