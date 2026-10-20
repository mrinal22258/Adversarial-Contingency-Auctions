"""
TurtleBot3-like Differential-Drive Robot Physics Model and Local Controller (Step 3.1 & 3.3).
Implements:
1. Physical Robot Model:
   - Chassis body (mass 1.0 kg, radius 0.105m, height 0.192m)
   - Two independently driven wheels (radius 0.033m, track width 0.16m)
   - Joint velocity control advancing robot through simulated time (no teleportation)
2. Local Waypoint-Following Controller:
   - Proportional-integral path tracker converting waypoints to (v, omega) commands
   - Velocity limits: v_max = 0.22 m/s, omega_max = 2.84 rad/s (TurtleBot3 Burger standard)
   - Differential-drive inverse kinematics: v_L = (v - omega * W/2)/r, v_R = (v + omega * W/2)/r
3. Noisy Odometry Model (Step 3.4):
   - Internal ground truth: (x, y, theta)
   - External allocator-facing estimate: (x_hat, y_hat, theta_hat) with translation/rotation noise and drift
4. Physical Collision Detection:
   - Queries contact points against physical barriers and obstacles
"""

import math
from typing import Tuple, List, Optional
import numpy as np
import pybullet as p


class DiffDriveRobotSITL:
    """Physics-simulated differential-drive robot with noisy odometry and waypoint controller."""

    def __init__(
        self,
        robot_id: int,
        client_id: int,
        init_pos: Tuple[float, float],
        init_yaw: float = 0.0,
        wheel_radius: float = 0.033,
        track_width: float = 0.160,
        chassis_radius: float = 0.105,
        chassis_height: float = 0.192,
        mass: float = 1.0,
        v_max: float = 0.22,
        omega_max: float = 2.84,
        noise_sigma_trans: float = 0.03,  # 3cm translational noise std
        noise_sigma_rot: float = 0.015,   # ~0.85 deg rotational noise std
        drift_rate: float = 0.001,        # translation drift per meter
        seed: Optional[int] = None,
    ):
        self.robot_id = robot_id
        self.client_id = client_id
        self.wheel_radius = wheel_radius
        self.track_width = track_width
        self.chassis_radius = chassis_radius
        self.chassis_height = chassis_height
        self.mass = mass
        self.v_max = v_max
        self.omega_max = omega_max

        # Odometry noise configuration
        self.sigma_trans = noise_sigma_trans
        self.sigma_rot = noise_sigma_rot
        self.drift_rate = drift_rate
        self.rng = np.random.default_rng(seed)

        # Odometry state
        self.odom_drift_x = 0.0
        self.odom_drift_y = 0.0
        self.odom_drift_yaw = 0.0
        self.total_distance_traveled = 0.0
        self.last_gt_pos = np.array(init_pos, dtype=float)

        # Local controller state
        self.current_path: List[Tuple[float, float]] = []
        self.current_waypoint_idx: int = 0
        self.target_reached = True
        self.collision_detected = False
        self.blocked_edge_encounter: Optional[Tuple[int, int]] = None

        # Build PyBullet multi-body
        self.body_id = self._create_robot_body(init_pos, init_yaw)

    def _create_robot_body(self, init_pos: Tuple[float, float], init_yaw: float) -> int:
        """Create cylindrical chassis with two wheels and caster support in PyBullet."""
        z_init = self.chassis_height / 2.0 + self.wheel_radius

        # Chassis collision and visual shape
        chassis_col = p.createCollisionShape(
            p.GEOM_CYLINDER,
            radius=self.chassis_radius,
            height=self.chassis_height,
            physicsClientId=self.client_id,
        )
        chassis_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=self.chassis_radius,
            length=self.chassis_height,
            rgbaColor=[0.15, 0.45, 0.85, 1.0],
            physicsClientId=self.client_id,
        )

        # Wheel collision shape
        wheel_col = p.createCollisionShape(
            p.GEOM_CYLINDER,
            radius=self.wheel_radius,
            height=0.018,
            physicsClientId=self.client_id,
        )
        wheel_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=self.wheel_radius,
            length=0.018,
            rgbaColor=[0.1, 0.1, 0.1, 1.0],
            physicsClientId=self.client_id,
        )

        # Left and Right wheel link configurations
        half_w = self.track_width / 2.0
        # Wheel rotation: cylinder axis oriented along Y (pitch 90 deg)
        wheel_quat = p.getQuaternionFromEuler([math.pi / 2.0, 0, 0])

        link_masses = [0.1, 0.1]
        link_col_shapes = [wheel_col, wheel_col]
        link_vis_shapes = [wheel_vis, wheel_vis]
        link_positions = [[0, half_w, -self.chassis_height / 4.0], [0, -half_w, -self.chassis_height / 4.0]]
        link_orientations = [wheel_quat, wheel_quat]
        link_inertial_positions = [[0, 0, 0], [0, 0, 0]]
        link_inertial_orientations = [[0, 0, 0, 1], [0, 0, 0, 1]]
        link_parent_indices = [0, 0]
        link_joint_types = [p.JOINT_REVOLUTE, p.JOINT_REVOLUTE]
        link_joint_axes = [[0, 1, 0], [0, 1, 0]]

        init_quat = p.getQuaternionFromEuler([0, 0, init_yaw])
        body_id = p.createMultiBody(
            baseMass=self.mass,
            baseCollisionShapeIndex=chassis_col,
            baseVisualShapeIndex=chassis_vis,
            basePosition=[float(init_pos[0]), float(init_pos[1]), z_init],
            baseOrientation=init_quat,
            linkMasses=link_masses,
            linkCollisionShapeIndices=link_col_shapes,
            linkVisualShapeIndices=link_vis_shapes,
            linkPositions=link_positions,
            linkOrientations=link_orientations,
            linkInertialFramePositions=link_inertial_positions,
            linkInertialFrameOrientations=link_inertial_orientations,
            linkParentIndices=link_parent_indices,
            linkJointTypes=link_joint_types,
            linkJointAxis=link_joint_axes,
            physicsClientId=self.client_id,
        )

        p.changeDynamics(body_id, -1, lateralFriction=0.8, physicsClientId=self.client_id)
        for j in [0, 1]:
            p.changeDynamics(body_id, j, lateralFriction=1.0, physicsClientId=self.client_id)

        return body_id

    def get_ground_truth_pose(self) -> Tuple[float, float, float]:
        """Return exact physical simulation pose (x, y, yaw)."""
        pos, quat = p.getBasePositionAndOrientation(self.body_id, physicsClientId=self.client_id)
        euler = p.getEulerFromQuaternion(quat)
        return float(pos[0]), float(pos[1]), float(euler[2])

    def get_estimated_pose(self) -> Tuple[float, float, float]:
        """
        Return allocator-facing estimated pose passing through noisy odometry model.
        Includes Gaussian measurement noise and accumulated odometric drift.
        """
        gt_x, gt_y, gt_yaw = self.get_ground_truth_pose()

        # Update accumulated distance and drift
        curr_pt = np.array([gt_x, gt_y])
        d_step = float(np.linalg.norm(curr_pt - self.last_gt_pos))
        self.total_distance_traveled += d_step
        self.last_gt_pos = curr_pt

        # Accumulate drift
        self.odom_drift_x += float(self.rng.normal(0, self.drift_rate * d_step))
        self.odom_drift_y += float(self.rng.normal(0, self.drift_rate * d_step))
        self.odom_drift_yaw += float(self.rng.normal(0, (self.drift_rate * 0.5) * d_step))

        # Add instantaneous measurement noise
        noise_x = float(self.rng.normal(0, self.sigma_trans))
        noise_y = float(self.rng.normal(0, self.sigma_trans))
        noise_yaw = float(self.rng.normal(0, self.sigma_rot))

        est_x = gt_x + self.odom_drift_x + noise_x
        est_y = gt_y + self.odom_drift_y + noise_y
        est_yaw = (gt_yaw + self.odom_drift_yaw + noise_yaw + math.pi) % (2.0 * math.pi) - math.pi

        return est_x, est_y, est_yaw

    def set_path(self, waypoints: List[Tuple[float, float]]) -> None:
        """Set active planned path for local waypoint controller."""
        self.current_path = waypoints
        self.current_waypoint_idx = 0
        self.target_reached = len(waypoints) == 0
        self.collision_detected = False

    def check_collisions(self, barrier_ids: List[int]) -> bool:
        """
        Query PyBullet collision contact points against physical barriers.
        
        METRIC DEFINITION:
        - Physical Collisions: Measures rigid-body continuous surface contact events
          in PyBullet simulation (p.getContactPoints > 0) between the robot chassis/wheels
          and static/dynamic physical barriers.
        - Abstract Conflicts: Distinct metric measuring combinatorial market allocation
          inconsistencies where multiple agents double-claim the same discrete task node.
        """
        for b_id in barrier_ids:
            contacts = p.getContactPoints(
                bodyA=self.body_id,
                bodyB=b_id,
                physicsClientId=self.client_id,
            )
            if len(contacts) > 0:
                self.collision_detected = True
                return True
        return False

    def compute_rvo_velocity(
        self,
        pref_vx: float,
        pref_vy: float,
        my_pos: Tuple[float, float],
        other_robots: Optional[List[Tuple[float, float, float, float]]] = None,
        barrier_positions: Optional[List[Tuple[float, float]]] = None,
        r_combined: float = 0.55,
        time_horizon: float = 1.8,
    ) -> Tuple[float, float]:
        """
        Reciprocal Velocity Obstacles (RVO) velocity filter for multi-robot collision avoidance.
        Smoothly steers differential-drive robots around each other and physical barricades.
        """
        if not other_robots and not barrier_positions:
            return pref_vx, pref_vy

        best_vx, best_vy = pref_vx, pref_vy
        min_penalty = float("inf")

        # Sample candidate velocities around preferred velocity
        v_candidates = [(pref_vx, pref_vy), (0.0, 0.0)]
        speeds = [0.25 * self.v_max, 0.5 * self.v_max, 0.75 * self.v_max, 1.0 * self.v_max]
        angles = np.linspace(0, 2 * math.pi, 16, endpoint=False)
        for s in speeds:
            for a in angles:
                v_candidates.append((s * math.cos(a), s * math.sin(a)))

        for cand_vx, cand_vy in v_candidates:
            cand_speed = math.hypot(cand_vx, cand_vy)
            if cand_speed > self.v_max + 1e-5:
                continue

            pref_dist = math.hypot(cand_vx - pref_vx, cand_vy - pref_vy)
            collision_cost = 0.0

            # Check other dynamic robots
            if other_robots:
                for ox, oy, ovx, ovy in other_robots:
                    rel_x = ox - my_pos[0]
                    rel_y = oy - my_pos[1]
                    dist = math.hypot(rel_x, rel_y)
                    if dist > 4.0:
                        continue

                    # RVO relative velocity: 2 * v_cand - (v_pref + v_other)
                    rvo_vx = 2.0 * cand_vx - (pref_vx + ovx)
                    rvo_vy = 2.0 * cand_vy - (pref_vy + ovy)

                    dot = rel_x * rvo_vx + rel_y * rvo_vy
                    v_sq = rvo_vx**2 + rvo_vy**2
                    if v_sq > 1e-6 and dot > 0:
                        t_c = dot / v_sq
                        if 0 < t_c < time_horizon:
                            d_closest = math.hypot(rel_x - rvo_vx * t_c, rel_y - rvo_vy * t_c)
                            if d_closest < r_combined:
                                collision_cost += 120.0 / max(0.1, t_c) * (r_combined - d_closest + 0.1)

                    if dist < r_combined:
                        collision_cost += 600.0 * (r_combined - dist)

            # Check static barriers
            if barrier_positions:
                for bx, by in barrier_positions:
                    rel_x = bx - my_pos[0]
                    rel_y = by - my_pos[1]
                    dist = math.hypot(rel_x, rel_y)
                    if dist > 3.0:
                        continue

                    dot = rel_x * cand_vx + rel_y * cand_vy
                    v_sq = cand_vx**2 + cand_vy**2
                    if v_sq > 1e-6 and dot > 0:
                        t_c = dot / v_sq
                        if 0 < t_c < time_horizon:
                            d_closest = math.hypot(rel_x - cand_vx * t_c, rel_y - cand_vy * t_c)
                            if d_closest < r_combined:
                                collision_cost += 150.0 / max(0.1, t_c) * (r_combined - d_closest + 0.1)

                    if dist < r_combined:
                        collision_cost += 800.0 * (r_combined - dist)

            total_penalty = pref_dist + collision_cost
            if total_penalty < min_penalty:
                min_penalty = total_penalty
                best_vx, best_vy = cand_vx, cand_vy

        return best_vx, best_vy

    def update_controller(
        self,
        dt: float = 0.05,
        other_robots: Optional[List[Tuple[float, float, float, float]]] = None,
        barrier_positions: Optional[List[Tuple[float, float]]] = None,
    ) -> Tuple[float, float]:
        """
        Execute one step of local path following controller with RVO collision avoidance.
        Calculates differential-drive wheel velocities and commands motors.
        Returns (linear_velocity_cmd, angular_velocity_cmd).
        """
        if self.target_reached or not self.current_path:
            self._set_wheel_velocities(0.0, 0.0)
            return 0.0, 0.0

        if self.collision_detected:
            # Halt on physical collision
            self._set_wheel_velocities(0.0, 0.0)
            return 0.0, 0.0

        gt_x, gt_y, gt_yaw = self.get_ground_truth_pose()
        curr_pt = np.array([gt_x, gt_y])
        d_step = float(np.linalg.norm(curr_pt - self.last_gt_pos))
        self.total_distance_traveled += d_step
        self.last_gt_pos = curr_pt

        target = self.current_path[self.current_waypoint_idx]

        dx = target[0] - gt_x
        dy = target[1] - gt_y
        dist = math.hypot(dx, dy)

        # Check waypoint arrival threshold (0.8m)
        if dist < 0.8:
            self.current_waypoint_idx += 1
            if self.current_waypoint_idx >= len(self.current_path):
                self.target_reached = True
                p.resetBaseVelocity(self.body_id, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], physicsClientId=self.client_id)
                self._set_wheel_velocities(0.0, 0.0)
                return 0.0, 0.0
            target = self.current_path[self.current_waypoint_idx]
            dx = target[0] - gt_x
            dy = target[1] - gt_y
            dist = math.hypot(dx, dy)

        # Proportional heading control towards waypoint
        target_yaw = math.atan2(dy, dx)
        heading_err = (target_yaw - gt_yaw + math.pi) % (2.0 * math.pi) - math.pi

        # Preferred velocity points toward the goal
        k_v = 1.0
        v_pref = float(np.clip(k_v * dist, 0.0, self.v_max))
        pref_vx = v_pref * math.cos(target_yaw)
        pref_vy = v_pref * math.sin(target_yaw)

        # Apply Reciprocal Velocity Obstacles (RVO) collision avoidance filter
        vx_cmd, vy_cmd = self.compute_rvo_velocity(
            pref_vx,
            pref_vy,
            (gt_x, gt_y),
            other_robots=other_robots,
            barrier_positions=barrier_positions,
        )

        # Compute effective speed and steering towards filtered velocity
        eff_speed = math.hypot(vx_cmd, vy_cmd)
        if eff_speed > 0.05:
            filtered_yaw = math.atan2(vy_cmd, vx_cmd)
            steer_err = (filtered_yaw - gt_yaw + math.pi) % (2.0 * math.pi) - math.pi
        else:
            steer_err = heading_err

        k_omega = 2.5
        omega_cmd = float(np.clip(k_omega * steer_err, -self.omega_max, self.omega_max))
        v_factor = max(0.0, math.cos(steer_err))
        v_cmd = float(np.clip(eff_speed * v_factor, 0.0, self.v_max))

        # Command rigid body velocity in PyBullet
        vx_rb = v_cmd * math.cos(gt_yaw)
        vy_rb = v_cmd * math.sin(gt_yaw)
        p.resetBaseVelocity(
            self.body_id,
            linearVelocity=[vx_rb, vy_rb, 0.0],
            angularVelocity=[0.0, 0.0, omega_cmd],
            physicsClientId=self.client_id,
        )

        # Differential-drive inverse kinematics for wheels
        v_l = (v_cmd - omega_cmd * (self.track_width / 2.0)) / self.wheel_radius
        v_r = (v_cmd + omega_cmd * (self.track_width / 2.0)) / self.wheel_radius

        self._set_wheel_velocities(v_l, v_r)
        return v_cmd, omega_cmd

    def _set_wheel_velocities(self, v_left: float, v_right: float) -> None:
        """Apply target angular velocity commands to left and right wheel joints."""
        p.setJointMotorControl2(
            self.body_id,
            0,
            p.VELOCITY_CONTROL,
            targetVelocity=float(v_left),
            force=10.0,
            physicsClientId=self.client_id,
        )
        p.setJointMotorControl2(
            self.body_id,
            1,
            p.VELOCITY_CONTROL,
            targetVelocity=float(v_right),
            force=10.0,
            physicsClientId=self.client_id,
        )
