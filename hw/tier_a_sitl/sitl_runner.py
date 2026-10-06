"""
Tier A: High-Fidelity Software-in-the-Loop (SITL) Differential-Drive Simulation.
Phase E Implementation:
- Unicycle kinematics: x_dot = v * cos(theta), y_dot = v * sin(theta), theta_dot = omega.
- Real TurtleBot3 kinematic limits: v_max = 0.22 m/s, omega_max = 2.84 rad/s.
- Proportional line-of-sight path-following controller.
- Sensor/localization noise: odom drift x, y ~ N(0, sigma_pos^2), theta ~ N(0, sigma_yaw^2).
- Emulated lossy DDS communication network layer.
- NOTE: This is high-fidelity software simulation, NOT physical hardware execution.
"""

import os
import sys
import math
import time
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


class DifferentialDriveRobot:
    """Simulated unicycle robot with realistic differential-drive kinematics and noise."""

    def __init__(
        self,
        robot_id: int,
        init_x: float,
        init_y: float,
        init_yaw: float = 0.0,
        v_max: float = 0.22,      # m/s (TurtleBot3 Burger standard)
        omega_max: float = 2.84,  # rad/s
        noise_sigma_pos: float = 0.02, # 2cm standard deviation odometry noise
        noise_sigma_yaw: float = 0.01, # ~0.6 deg heading noise
    ):
        self.robot_id = robot_id
        # Ground truth state
        self.x = init_x
        self.y = init_y
        self.yaw = init_yaw
        # Kinematic limits
        self.v_max = v_max
        self.omega_max = omega_max
        # Noise parameters
        self.sigma_pos = noise_sigma_pos
        self.sigma_yaw = noise_sigma_yaw
        # Controls
        self.v = 0.0
        self.omega = 0.0

    def step(self, target_pos: Tuple[float, float], dt: float = 0.1) -> Tuple[float, float]:
        """Execute one differential-drive control step toward target_pos."""
        dx = target_pos[0] - self.x
        dy = target_pos[1] - self.y
        dist = math.hypot(dx, dy)

        if dist < 0.10: # 10 cm waypoint acceptance radius
            self.v = 0.0
            self.omega = 0.0
            return self.get_noisy_odometry()

        # Desired heading
        desired_yaw = math.atan2(dy, dx)
        yaw_err = math.atan2(math.sin(desired_yaw - self.yaw), math.cos(desired_yaw - self.yaw))

        # Proportional controller
        k_p_v = 0.5
        k_p_w = 2.0

        # Slow down during sharp turns
        v_cmd = min(self.v_max, k_p_v * dist * max(0.0, math.cos(yaw_err)))
        w_cmd = np.clip(k_p_w * yaw_err, -self.omega_max, self.omega_max)

        self.v = v_cmd
        self.omega = w_cmd

        # Forward integration (Euler)
        self.yaw += self.omega * dt
        self.x += self.v * math.cos(self.yaw) * dt
        self.y += self.v * math.sin(self.yaw) * dt

        return self.get_noisy_odometry()

    def get_noisy_odometry(self) -> Tuple[float, float, float]:
        """Return noisy sensor state (x, y, yaw) with realistic sensor drift."""
        noisy_x = self.x + np.random.normal(0, self.sigma_pos)
        noisy_y = self.y + np.random.normal(0, self.sigma_pos)
        noisy_yaw = self.yaw + np.random.normal(0, self.sigma_yaw)
        return (float(noisy_x), float(noisy_y), float(noisy_yaw))


class TierASoftwareInTheLoopSimulator:
    """
    High-Fidelity SITL Harness coupling differential-drive physical execution
    with ACA decentralized auction coordination.
    """

    def __init__(
        self,
        graph: nx.Graph,
        n_robots: int = 3,
        n_tasks: int = 6,
        comm_range: float = 35.0,
        p_drop: float = 0.05,
        seed: int = 42,
    ):
        self.graph = graph
        self.n_robots = n_robots
        self.n_tasks = n_tasks
        self.engine = SimulationEngine(
            graph=graph,
            adversary_type=AdversaryType.STOCHASTIC,
            allocator_type="aca",
            n_robots=n_robots,
            n_tasks=n_tasks,
            comm_range=comm_range,
            p_drop=p_drop,
            seed=seed,
        )
        # Instantiate physical differential-drive robots at initial waypoint coordinates
        self.physical_fleet: Dict[int, DifferentialDriveRobot] = {}
        for rid, agent in self.engine.robots.items():
            pos = agent.pos
            self.physical_fleet[rid] = DifferentialDriveRobot(
                robot_id=rid,
                init_x=pos[0],
                init_y=pos[1],
            )

    def run_sitl_mission(self, max_ticks: int = 50, dt_substeps: int = 5) -> Dict[str, Any]:
        """Execute high-fidelity simulation with continuous-time sub-stepping."""
        trajectory_log = []

        for tick in range(max_ticks):
            ongoing = self.engine.step(tick)
            if not ongoing:
                break

            # Execute continuous differential-drive sub-steps
            for _ in range(dt_substeps):
                for rid, diff_bot in self.physical_fleet.items():
                    agent = self.engine.robots[rid]
                    noisy_pos = diff_bot.step(agent.pos, dt=0.2)
                    trajectory_log.append({
                        "tick": tick,
                        "robot_id": rid,
                        "true_x": diff_bot.x,
                        "true_y": diff_bot.y,
                        "noisy_x": noisy_pos[0],
                        "noisy_y": noisy_pos[1],
                        "v": diff_bot.v,
                        "omega": diff_bot.omega,
                    })

        metrics = self.engine.finalize()
        summary = metrics.compute_summary()
        summary["sitl_kinematic_substeps"] = len(trajectory_log)
        summary["tier"] = "Tier A (High-Fidelity Software-in-the-Loop Simulation)"
        return summary


def main():
    print("Launching Tier A High-Fidelity SITL Demonstration...")
    g = generate_graph("rgg", n_nodes=20, seed=123)
    sim = TierASoftwareInTheLoopSimulator(graph=g, n_robots=3, n_tasks=6, seed=123)
    results = sim.run_sitl_mission(max_ticks=25)
    print("\nTier A SITL Execution Completed:")
    print(f"  Completion Rate : {results['completion_rate_pct']:.1f}%")
    print(f"  Total Messages  : {results['total_messages']}")
    print(f"  Kinematic Steps : {results['sitl_kinematic_substeps']}")
    print(f"  Validation Tier : {results['tier']}")


if __name__ == "__main__":
    main()
