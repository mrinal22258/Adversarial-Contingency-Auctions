"""
Chance-Constrained CBBA (CC-CBBA - Ponda et al. 2012).
Enforces a probabilistic blockage risk constraint on candidate bundle paths.
"""

from typing import Dict, List, Tuple, Optional, Any
import networkx as nx

from .base import Task
from .cbba import CBBAAllocator
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork
from ..env.adversaries import canonical_edge


class ChanceConstrainedCBBAAllocator(CBBAAllocator):
    """
    Chance-Constrained CBBA (Ponda et al. 2012).
    A task is rejected if the cumulative blockage probability on the path exceeds risk_threshold alpha.
    """

    def __init__(
        self,
        graph: nx.Graph,
        robots: Dict[int, RobotAgent],
        comm_net: CommunicationNetwork,
        bundle_limit: int = 4,
        alpha_risk: float = 0.30,
    ):
        super().__init__(graph, robots, comm_net, bundle_limit)
        self.alpha_risk = alpha_risk

    def _path_blockage_probability(
        self,
        robot: RobotAgent,
        start_node: Any,
        target_node: Any,
    ) -> float:
        """Compute P(at least one edge blocked) along shortest path."""
        try:
            path = nx.shortest_path(self.graph, start_node, target_node, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return 1.0

        edge_marginals = robot.get_edge_marginals()
        prob_all_clear = 1.0
        for i in range(len(path) - 1):
            c_e = canonical_edge(path[i], path[i + 1])
            pi_e = edge_marginals.get(c_e, 0.05)
            prob_all_clear *= (1.0 - pi_e)

        return float(1.0 - prob_all_clear)

    def _build_bundle(self, robot_id: int, tasks: Dict[int, Task]) -> None:
        """Phase 1: Bundle construction with chance constraint filter."""
        robot = self.robots[robot_id]
        bundle = list(robot.bundle)

        while len(bundle) < self.bundle_limit:
            best_task_id = None
            best_val = 0.0
            best_insert_pos = -1

            curr_loc = robot.current_node if not bundle or bundle[-1] not in tasks else tasks[bundle[-1]].node

            for tid, task in tasks.items():
                if tid in bundle or task.completed:
                    continue

                # Chance constraint check: P(blockage) <= alpha_risk
                risk = self._path_blockage_probability(robot, curr_loc, task.node)
                if risk > self.alpha_risk:
                    continue  # Violates chance constraint

                score, ins_idx = self._get_marginal_score(robot, task, bundle, tasks)
                current_winner_bid = self.y[robot_id].get(tid, 0.0)

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
