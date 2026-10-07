"""
Thin Allocator Adapter for SITL Robotics Simulation (Step 3.7).
Connects existing acalib allocators unchanged to the PyBullet physics simulator:
- Allocator decision -> graph-level path / task assignment -> local waypoint trajectory
- Simulator state / observations (noisy odometry, sensed blockages) -> allocator input

Supported algorithms (identical parameterization across all methods):
1. ACA (Pinsker margin + local recourse)
2. ACA-no-margin (consensus only)
3. CTP replan (Canadian Traveller Problem replan-on-discovery)
4. Implicit (margin-free implicit coordination)
5. CBBA-PR+LR (best +LR CBBA baseline)
6. SSI+LR (Sequential Single-Item auction with local recourse)

All acalib allocators run UNCHANGED without favorable hand-tuning.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from acalib.alloc.base import Task, BaseAllocator
from acalib.alloc.aca import ACAAllocator
from acalib.alloc.cbba import CBBAAllocator
from acalib.alloc.cbba_partial import CBBAPartialReplanAllocator
from acalib.alloc.ctp_replan import CTPReplanAllocator
from acalib.alloc.implicit import ImplicitCoordinationAllocator
from acalib.alloc.ssi import SSIAllocator
from acalib.agents.robot import RobotAgent
from acalib.env.adversaries import canonical_edge


from acalib.env.comm import CommunicationNetwork


def create_sitl_allocator(
    method_name: str,
    graph: nx.Graph,
    robots: Dict[int, RobotAgent],
    comm_net: Any,
    contingency_depth: int = 1,
) -> Tuple[BaseAllocator, int]:
    """
    Instantiate standard acalib allocator for SITL trial.
    Returns (allocator_instance, robot_recourse_depth).
    """
    method = method_name.lower()
    
    if method == "aca":
        allocator = ACAAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
            contingency_depth=contingency_depth,
            enable_margin=True,
        )
        recourse_depth = contingency_depth
    elif method == "aca_no_margin":
        allocator = ACAAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
            contingency_depth=contingency_depth,
            enable_margin=False,
        )
        recourse_depth = contingency_depth
    elif method == "ctp_replan":
        allocator = CTPReplanAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
        )
        recourse_depth = 0
    elif method == "implicit":
        allocator = ImplicitCoordinationAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
        )
        recourse_depth = contingency_depth
    elif method in ["cbba_partial_lr", "cbba_pr_lr", "best_lr_cbba"]:
        allocator = CBBAPartialReplanAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
        )
        recourse_depth = contingency_depth
    elif method == "ssi_lr":
        allocator = SSIAllocator(
            graph=graph,
            robots=robots,
            comm_net=comm_net,
        )
        recourse_depth = contingency_depth
    else:
        raise ValueError(f"Unknown allocator for SITL adapter: {method_name}")

    return allocator, recourse_depth


class SITLAllocatorAdapter:
    """Thin adapter interfacing graph-level auction algorithms with physics simulation."""

    def __init__(
        self,
        method_name: str,
        graph: nx.Graph,
        n_robots: int,
        tasks: Dict[int, Task],
        comm_net: Any,
        contingency_depth: int = 1,
    ):
        self.graph = graph
        self.n_robots = n_robots
        self.tasks = tasks
        self.recourse_depth = contingency_depth

        # Create RobotAgent wrappers for acalib algorithm logic
        fleet_ids = list(range(n_robots))
        self.robot_agents: Dict[int, RobotAgent] = {}
        for rid in range(n_robots):
            self.robot_agents[rid] = RobotAgent(
                robot_id=rid,
                start_node=0,
                graph=graph,
                fleet_ids=fleet_ids,
                contingency_depth=contingency_depth,
            )

        self.allocator, self.recourse_depth = create_sitl_allocator(
            method_name=method_name,
            graph=graph,
            robots=self.robot_agents,
            comm_net=comm_net,
            contingency_depth=contingency_depth,
        )
        self.last_alloc_result: Dict[str, Any] = {}

    def plan_round(
        self,
        current_step: int,
        estimated_robot_poses: Dict[int, Tuple[float, float, float]],
        known_blocked_edges: Set[Tuple[int, int]],
    ) -> Dict[int, List[int]]:
        """
        Execute auction allocation round passing estimated states into acalib allocator.
        Returns robot bundles: {robot_id -> [task_id, ...]}.
        """
        # Map estimated continuous poses to nearest graph nodes
        pos_dict = nx.get_node_attributes(self.graph, "pos")
        for rid, (est_x, est_y, est_yaw) in estimated_robot_poses.items():
            best_node = None
            best_dist = float("inf")
            for node, n_pos in pos_dict.items():
                d = float(np.hypot(est_x - n_pos[0], est_y - n_pos[1]))
                if d < best_dist:
                    best_dist = d
                    best_node = node
            if best_node is not None:
                self.robot_agents[rid].current_node = best_node
                self.robot_agents[rid].pos = (est_x, est_y)

        # Update known blocked edges in robot agents
        for rid, agent in self.robot_agents.items():
            for e in known_blocked_edges:
                agent.blocked_edges.add(canonical_edge(e[0], e[1]))

        # Run allocator.allocate_round
        robot_pos_dict = {rid: (est_x, est_y) for rid, (est_x, est_y, _) in estimated_robot_poses.items()}
        active_tasks = {tid: t for tid, t in self.tasks.items() if not t.completed}
        try:
            alloc_res = self.allocator.allocate_round(
                tasks=active_tasks,
                current_step=current_step,
                robot_positions=robot_pos_dict,
            )
        except TypeError:
            alloc_res = self.allocator.allocate_round(
                tasks=active_tasks,
                current_step=current_step,
            )
        self.last_alloc_result = alloc_res if isinstance(alloc_res, dict) else {}

        # Extract bundles
        bundles = {rid: list(r.bundle) for rid, r in self.robot_agents.items()}
        return bundles

    def compute_waypoint_path(
        self,
        robot_id: int,
        target_task_id: Optional[int],
        start_pos: Tuple[float, float],
        blocked_edges: Set[Tuple[int, int]],
    ) -> List[Tuple[float, float]]:
        """
        Convert task assignment into physical waypoint coordinates in the world.
        Excludes known blocked edges from graph planning.
        """
        if target_task_id is None or target_task_id not in self.tasks:
            return []

        task = self.tasks[target_task_id]
        dest_node = task.node
        pos_dict = nx.get_node_attributes(self.graph, "pos")

        # Find closest start node to robot start_pos
        start_node = min(
            self.graph.nodes(),
            key=lambda n: np.hypot(start_pos[0] - pos_dict[n][0], start_pos[1] - pos_dict[n][1]),
        )

        # Plan on traversable subgraph (excluding blocked edges)
        sub_g = self.graph.copy()
        for u, v in blocked_edges:
            if sub_g.has_edge(u, v):
                sub_g.remove_edge(u, v)

        try:
            if nx.has_path(sub_g, start_node, dest_node):
                node_path = nx.shortest_path(sub_g, start_node, dest_node, weight="weight")
            else:
                # Path blocked; fallback shortest path or detour
                node_path = nx.shortest_path(self.graph, start_node, dest_node, weight="weight")
        except Exception:
            node_path = [start_node, dest_node]

        waypoints = [pos_dict[n] for n in node_path]
        if len(waypoints) > 1:
            d_first = float(np.hypot(start_pos[0] - waypoints[0][0], start_pos[1] - waypoints[0][1]))
            if d_first < 1.0:
                waypoints = waypoints[1:]
        return waypoints
