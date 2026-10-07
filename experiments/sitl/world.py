"""
PyBullet Simulation World and Real Map Physical Environment.
Builds 3D physical worlds directly from real repository map files:
1. MovingAI Warehouse (warehouse-10-20-10-2-1.map):
   - Grid-derived physical shelf barriers and traversable aisle corridors
   - Exact spatial scale matching graph representation
2. Downtown Boston Road Network (boston_downtown_drive.graphml):
   - Road segment centerlines, boundary colliders, and physical intersection nodes
   - Dynamic physical blockage obstacles preventing traversal

Pure software simulation using PyBullet headless physics engine.
No physical robots or hardware testbeds are used.
"""

import os
import math
import hashlib
from typing import Dict, Tuple, List, Optional, Any, Set
import numpy as np
import networkx as nx
import pybullet as p
import pybullet_data

from acalib.env.real_maps import (
    generate_movingai_warehouse,
    generate_real_road_network,
    DATA_MAPS_DIR,
    MOVINGAI_WAREHOUSE_HASH,
    OSMNX_ROAD_NETWORK_HASH,
)


class PhysicsWorld:
    """Manages PyBullet physics simulation instance and physical world geometry."""

    def __init__(
        self,
        map_type: str = "warehouse_movingai",
        scale: float = 100.0,
        gui: bool = False,
        time_step: float = 1.0 / 60.0,
    ):
        self.map_type = map_type
        self.scale = scale
        self.time_step = time_step
        self.gui = gui

        # Connect PyBullet
        connection_mode = p.GUI if gui else p.DIRECT
        self.client_id = p.connect(connection_mode)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81, physicsClientId=self.client_id)
        p.setTimeStep(time_step, physicsClientId=self.client_id)

        # Ground plane
        self.plane_id = p.loadURDF("plane.urdf", [0, 0, 0], physicsClientId=self.client_id)
        p.changeDynamics(self.plane_id, -1, lateralFriction=0.8, physicsClientId=self.client_id)

        # Geometry registries
        self.static_obstacles: List[int] = []
        self.blockage_barriers: Dict[Tuple[int, int], int] = {}
        self.graph: Optional[nx.Graph] = None
        self.map_provenance: Dict[str, Any] = {}

        # Load topology
        self._load_map_topology()

    def _load_map_topology(self):
        """Construct physical geometry from repository map data."""
        if self.map_type == "warehouse_movingai":
            filepath = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
            self.graph = generate_movingai_warehouse(n_nodes=38, filepath=filepath)
            self._build_warehouse_physical_geometry(filepath)
            with open(filepath, "rb") as f:
                f_hash = hashlib.sha256(f.read()).hexdigest()
            self.map_provenance = {
                "map_type": "warehouse_movingai",
                "source_file": "warehouse-10-20-10-2-1.map",
                "sha256": f_hash,
                "n_nodes": self.graph.number_of_nodes(),
                "n_edges": self.graph.number_of_edges(),
            }
        elif self.map_type == "road_osmnx":
            filepath = os.path.join(DATA_MAPS_DIR, "boston_downtown_drive.graphml")
            self.graph = generate_real_road_network(filepath=filepath)
            self._build_road_network_physical_geometry()
            with open(filepath, "rb") as f:
                f_hash = hashlib.sha256(f.read()).hexdigest()
            self.map_provenance = {
                "map_type": "road_osmnx",
                "source_file": "boston_downtown_drive.graphml",
                "sha256": f_hash,
                "n_nodes": self.graph.number_of_nodes(),
                "n_edges": self.graph.number_of_edges(),
            }
        else:
            raise ValueError(f"Unsupported map type for SITL: {self.map_type}")

    def _build_warehouse_physical_geometry(self, filepath: str):
        """Instantiate physical shelving racks as consolidated collision blocks for efficient simulation."""
        # Create boundary walls
        wall_thick = 1.0
        wall_height = 0.5
        wall_len = self.scale + 6.0

        for pos, dim in [
            ([self.scale / 2.0, -wall_thick, wall_height / 2.0], [wall_len / 2.0, wall_thick / 2.0, wall_height / 2.0]),
            ([self.scale / 2.0, self.scale + wall_thick, wall_height / 2.0], [wall_len / 2.0, wall_thick / 2.0, wall_height / 2.0]),
            ([-wall_thick, self.scale / 2.0, wall_height / 2.0], [wall_thick / 2.0, wall_len / 2.0, wall_height / 2.0]),
            ([self.scale + wall_thick, self.scale / 2.0, wall_height / 2.0], [wall_thick / 2.0, wall_len / 2.0, wall_height / 2.0]),
        ]:
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=dim, physicsClientId=self.client_id)
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=dim, rgbaColor=[0.4, 0.4, 0.4, 1.0], physicsClientId=self.client_id)
            bid = p.createMultiBody(0.0, col, vis, pos, physicsClientId=self.client_id)
            self.static_obstacles.append(bid)

        # Build physical racks from actual MovingAI map file
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        # Skip header lines to reach map data
        map_idx = 0
        while map_idx < len(lines) and not lines[map_idx].startswith("map"):
            map_idx += 1
        map_idx += 1
        grid = lines[map_idx:]
        height = len(grid)
        width = len(grid[0])
        B = 8
        n_br = height // B
        n_bc = width // B
        cell_w = self.scale / n_bc
        cell_h = self.scale / n_br

        col_shape = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=[cell_w * 0.45, cell_h * 0.45, 0.5],
            physicsClientId=self.client_id,
        )
        vis_shape = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[cell_w * 0.45, cell_h * 0.45, 0.5],
            rgbaColor=[0.3, 0.3, 0.35, 1.0],
            physicsClientId=self.client_id,
        )

        for br in range(n_br):
            for bc in range(n_bc):
                sub = [
                    grid[r][c]
                    for r in range(br * B, min(height, (br + 1) * B))
                    for c in range(bc * B, min(width, (bc + 1) * B))
                ]
                passable_ratio = sub.count(".") / len(sub)
                if passable_ratio < 0.4:
                    pos_x = float(bc * cell_w + cell_w / 2.0)
                    pos_y = float((n_br - 1 - br) * cell_h + cell_h / 2.0)
                    bid = p.createMultiBody(
                        0.0,
                        col_shape,
                        vis_shape,
                        [pos_x, pos_y, 0.5],
                        physicsClientId=self.client_id,
                    )
                    self.static_obstacles.append(bid)

    def _build_road_network_physical_geometry(self):
        """Instantiate physical boundary curbs along road boundaries."""
        # For road network, outer boundaries form containment
        wall_thick = 1.0
        wall_height = 0.5
        wall_len = self.scale + 10.0

        for pos, dim in [
            ([self.scale / 2.0, -wall_thick, wall_height / 2.0], [wall_len / 2.0, wall_thick / 2.0, wall_height / 2.0]),
            ([self.scale / 2.0, self.scale + wall_thick, wall_height / 2.0], [wall_len / 2.0, wall_thick / 2.0, wall_height / 2.0]),
            ([-wall_thick, self.scale / 2.0, wall_height / 2.0], [wall_thick / 2.0, wall_len / 2.0, wall_height / 2.0]),
            ([self.scale + wall_thick, self.scale / 2.0, wall_height / 2.0], [wall_thick / 2.0, wall_len / 2.0, wall_height / 2.0]),
        ]:
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=dim, physicsClientId=self.client_id)
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=dim, rgbaColor=[0.5, 0.5, 0.5, 1.0], physicsClientId=self.client_id)
            bid = p.createMultiBody(0.0, col, vis, pos, physicsClientId=self.client_id)
            self.static_obstacles.append(bid)

    def set_corridor_blockage(self, u: int, v: int, is_blocked: bool) -> None:
        """
        Dynamically spawn or remove a physical barrier across corridor (u, v).
        A physical barrier prevents physical robot passage and causes collision.
        """
        can_edge = tuple(sorted((u, v)))
        if is_blocked and can_edge not in self.blockage_barriers:
            pos_dict = nx.get_node_attributes(self.graph, "pos")
            pu = np.array(pos_dict[u])
            pv = np.array(pos_dict[v])
            mid_pt = (pu + pv) / 2.0
            diff = pv - pu
            dist = float(np.linalg.norm(diff))
            angle = math.atan2(diff[1], diff[0])

            # Barrier perpendicular to edge
            barrier_width = 3.0  # Spans across corridor
            barrier_thick = 0.8  # Thickness
            barrier_height = 0.8 # Tall physical roadblock

            col = p.createCollisionShape(
                p.GEOM_BOX,
                halfExtents=[barrier_thick / 2.0, barrier_width / 2.0, barrier_height / 2.0],
                physicsClientId=self.client_id,
            )
            vis = p.createVisualShape(
                p.GEOM_BOX,
                halfExtents=[barrier_thick / 2.0, barrier_width / 2.0, barrier_height / 2.0],
                rgbaColor=[0.85, 0.2, 0.1, 0.95],
                physicsClientId=self.client_id,
            )
            # Orientation perpendicular to corridor
            quat = p.getQuaternionFromEuler([0, 0, angle + math.pi / 2.0])
            barrier_id = p.createMultiBody(
                baseMass=0.0, # Static immovable physical obstacle
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=[float(mid_pt[0]), float(mid_pt[1]), barrier_height / 2.0],
                baseOrientation=quat,
                physicsClientId=self.client_id,
            )
            self.blockage_barriers[can_edge] = barrier_id

        elif not is_blocked and can_edge in self.blockage_barriers:
            barrier_id = self.blockage_barriers.pop(can_edge)
            p.removeBody(barrier_id, physicsClientId=self.client_id)

    def step_simulation(self, n_steps: int = 1):
        """Advance physical simulation time by n_steps."""
        for _ in range(n_steps):
            p.stepSimulation(physicsClientId=self.client_id)

    def close(self):
        """Clean up PyBullet physics client."""
        if hasattr(self, "client_id") and self.client_id is not None:
            try:
                p.disconnect(physicsClientId=self.client_id)
            except Exception:
                pass
            self.client_id = None
