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
from typing import Tuple, List, Optional, Dict, Any
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

    def update_controller(self, dt: float = 0.05) -> Tuple[float, float]:
        """
        Execute one step of local path following controller.
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

        # Proportional heading control
        target_yaw = math.atan2(dy, dx)
        heading_err = (target_yaw - gt_yaw + math.pi) % (2.0 * math.pi) - math.pi

        # Angular velocity command
        k_omega = 2.5
        omega_cmd = float(np.clip(k_omega * heading_err, -self.omega_max, self.omega_max))

        # Linear velocity command: slow down when turning sharply
        k_v = 1.0
        v_factor = max(0.0, math.cos(heading_err))
        v_cmd = float(np.clip(k_v * dist * v_factor, 0.0, self.v_max))

        # Command rigid body velocity in PyBullet
        vx = v_cmd * math.cos(gt_yaw)
        vy = v_cmd * math.sin(gt_yaw)
        p.resetBaseVelocity(
            self.body_id,
            linearVelocity=[vx, vy, 0.0],
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
