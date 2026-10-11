"""
Implicit Coordination without Claim Margin (Alighanbari & How 2005/2006).
Ablation / comparison baseline: robots claim tasks implicitly under local beliefs,
with margin m = 0. Isolates the direct impact of Pinsker claim margins on conflict reduction.
"""

from typing import Dict, Tuple, Any
import networkx as nx

from .base import Task
from .aca import ACAAllocator
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork


class ImplicitCoordinationAllocator(ACAAllocator):
    """
    Implicit Coordination baseline (Alighanbari & How 2005).
    Robots claim tasks if their own cost is estimated to be minimum among fleet,
    but without Pinsker margin (margin = 0). Under inconsistent beliefs,
    multiple robots may simultaneously claim the same task, causing conflicts.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
    ):
        super().__init__(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
            bundle_limit=bundle_limit,
            enable_margin=False,  # Margin disabled (m = 0)
        )

    def allocate_round(
        self,
        tasks: Dict[int, Task],
        current_step: int,
        robot_positions: Dict[int, Tuple[float, float]],
        max_consensus_iterations: int = 0,
    ) -> Dict[str, Any]:
        """
        Implicit coordination: robots claim tasks locally under private models without consensus rounds.
        Under divergent beliefs, this leads to simultaneous claims (conflicts).
        """
        return super().allocate_round(
            tasks=tasks,
            current_step=current_step,
            robot_positions=robot_positions,
            max_consensus_iterations=0,
        )
