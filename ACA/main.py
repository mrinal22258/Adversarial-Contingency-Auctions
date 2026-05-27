"""Discrete event simulation runner for Adversarial Contingency Auctions (ACA).

Orchestrates initialization, dynamic ticks, adversary mutations, peer-to-peer
communication updates, SSI auctions under communication budgets, agent actions,
and consolidated metrics output.
"""

import os
import sys
import yaml
import json
import random
import math
import networkx as nx
from typing import Dict, List, Tuple, Set, Optional, Any

# Framework module imports
from environment.graph_world import GraphWorld
from agents.robot import Robot
from auction.engine import AuctionEngine, Task, Bid


class SimulationEngine:
    """Manages the active discrete-event simulation loop for ACA."""

    def __init__(self, config_path: str) -> None:
        """Loads configuration and instantiates the simulation elements.

        Args:
            config_path: Filepath to the settings.yaml configuration.
        """
        self._config_path: str = config_path
        self._config: Dict[str, Any] = self._load_config()

        # Seed global random generator
        sim_config = self._config.get("simulation", {})
        self._random_seed: int = sim_config.get("random_seed", 42)
        random.seed(self._random_seed)

        # Initialize Environment Ground Truth and Auction Engine
        self._world: GraphWorld = GraphWorld(self._config)
        self._auction_house: AuctionEngine = AuctionEngine(
            bid_epsilon=self._config.get("auction", {}).get("bid_epsilon", 0.01)
        )

        # Dynamic state trackers
        self._robots: List[Robot] = []
        self._active_tasks: List[Task] = []
        self._time_step: int = 0
        self._metrics_log: List[Dict[str, Any]] = []

        # Instantiates the robot fleet
        self._initialize_robot_fleet()

    def _load_config(self) -> Dict[str, Any]:
        """Loads configuration data from YAML settings file.

        Returns:
            Dictionary containing nested configuration blocks.
        """
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"Configuration file not found: {self._config_path}")
        with open(self._config_path, "r") as file:
            return yaml.safe_load(file) or {}

    def _initialize_robot_fleet(self) -> None:
        """Parses configuration fleet types and instantiates private Robot classes."""
        robot_configs = self._config.get("robots", [])
        robot_id_counter = 1

        for spec in robot_configs:
            count = spec.get("count", 1)
            for _ in range(count):
                robot_id = f"robot_{spec.get('type', 'generic')}_{robot_id_counter}"
                # Start robots distributed over the nodes
                initial_node = (robot_id_counter - 1) % len(self._world.nodes)
                
                # Assign capabilities
                capabilities = {"scouting"} if spec.get("type") == "scout" else {"lifting"}
                
                robot_instance = Robot(
                    robot_id=robot_id,
                    robot_type=spec.get("type", "generic"),
                    initial_location=initial_node,
                    battery_capacity=spec.get("battery_capacity", 100.0),
                    battery_drain_rate=spec.get("battery_drain_rate", 1.0),
                    battery_move_cost=spec.get("battery_move_cost", 2.0),
                    comm_budget=spec.get("comm_budget", 50.0),
                    sensing_range=spec.get("sensing_range", 1),
                    speed=spec.get("speed", 1.0),
                    capabilities=capabilities
                )
                self._robots.append(robot_instance)
                robot_id_counter += 1

        print(f"Successfully initialized heterogeneous fleet of {len(self._robots)} robots.")

    def _trigger_task_arrivals(self) -> None:
        """Stochastically spawns new tasks at vertices and registers them with the market.

        Determined by the task_arrival_rate configuration setting.
        """
        sim_config = self._config.get("simulation", {})
        arrival_rate = sim_config.get("task_arrival_rate", 0.2)
        
        if random.random() < arrival_rate:
            task_id = f"task_{self._time_step}_{len(self._active_tasks) + 1}"
            nodes = self._world.nodes or [0]
            location = random.choice(nodes)
            
            # Simple randomized rewards and deadlines
            reward = float(random.randint(60, 180))
            deadline = float(self._time_step + random.randint(20, 50))
            
            new_task = Task(
                task_id=task_id,
                location=location,
                reward=reward,
                deadline=deadline,
                required_capabilities=[]
            )
            self._active_tasks.append(new_task)
            self._auction_house.register_task(new_task)
            print(f"[Tick {self._time_step}] Task arrival: {task_id} at node {location} (Reward: {reward:.1f}, Deadline: {deadline:.1f})")

    def run(self) -> None:
        """Executes the discrete event simulation ticks until termination conditions are met."""
        sim_config = self._config.get("simulation", {})
        time_horizon = sim_config.get("time_horizon", 100)
        
        # Load parameters
        auction_cfg = self._config.get("auction", {})
        kappa = self._config.get("robots", [{}])[0].get("comm_budget", 100.0) # communication limit
        lambda_penalty = 8.0 # lambda parameter weight

        print("\n=== STARTING ADVERSARIAL CONTINGENCY AUCTIONS (ACA) SIMULATION ===")
        print(f"Adversary policy theta^*: {self._world.adversary.policy_type}")
        print(f"Time horizon: {time_horizon} ticks. Fleet size: {len(self._robots)} robots.\n")

        while self._time_step < time_horizon:
            print(f"--- Tick {self._time_step} ---")
            
            # 1. Spontaneous dynamic tasks arrival
            self._trigger_task_arrivals()

            # 2. Extract robot planned navigation paths to pass to adversary blockage mutation
            joint_fleet_actions = {r.robot_id: r.planned_path for r in self._robots}
            
            # 3. Adversary mutates edge risks stochastically
            self._world.update_blockages(joint_fleet_actions)

            # 4. Robots sense the environment within local range and update subjective beliefs
            for robot in self._robots:
                # Query local sensor subgraph observation from GraphWorld (limited radius)
                sensor_data = self._world.get_local_observation(
                    robot_id=robot.robot_id,
                    current_node=robot.current_location,
                    sensing_radius=robot.sensing_range
                )
                # Pass ground-truth risk mapping for Bayes filter evaluation
                sensor_data["is_risk_mapping"] = {
                    (min(u, v), max(u, v)): d.get("is_risk", False)
                    for u, v, d in self._world.graph.edges(data=True)
                }
                robot.update_beliefs_from_sensing(sensor_data)

            # 5. Reset communication budget trackers for the step
            for robot in self._robots:
                robot.reset_comm_budget()

            # 6. Simulate P2P network messaging (robots update their neighbor maps)
            comm_range = auction_cfg.get("comm_range", 3)
            for r1 in self._robots:
                if r1.current_battery <= 0.0:
                    continue
                for r2 in self._robots:
                    if r1.robot_id != r2.robot_id and r2.current_battery > 0.0:
                        try:
                            # Verify direct communication proximity in the graph
                            dist = nx.shortest_path_length(self._world.graph, r1.current_location, r2.current_location)
                            if dist <= comm_range:
                                payload = {
                                    "location": r1.current_location,
                                    "sensing_range": r1.sensing_range,
                                    "planned_path": r1.planned_path,
                                    "belief": r1.belief
                                }
                                r2.receive_message(r1.robot_id, payload)
                        except (nx.NetworkXNoPath, nx.NodeNotFound):
                            pass

            # 7. Robots run cognitive teammate belief predictions
            for robot in self._robots:
                if robot.current_battery > 0.0:
                    robot.predict_teammate_beliefs()

            # 8. Decentralized auction SSI loops
            unassigned_tasks = [
                t for t in self._active_tasks 
                if not t.is_completed and t.task_id not in self._auction_house._assignments
            ]
            if unassigned_tasks:
                self._auction_house.run_ssi_auction(
                    robots=self._robots,
                    unallocated_tasks=unassigned_tasks,
                    comm_budget_kappa=kappa,
                    lambda_penalty=lambda_penalty,
                    current_time=self._time_step
                )

            # 9. Navigation, task execution and energy drainage phase
            for robot in self._robots:
                if robot.current_battery <= 0.0:
                    continue

                assigned_tasks = robot._local_beliefs["assigned_tasks"]
                if assigned_tasks and len(robot.planned_path) > 1:
                    # Move to next node in planned sequence
                    next_node = robot.planned_path[1]
                    
                    if self._world.graph.has_edge(robot.current_location, next_node):
                        weight = self._world.graph[robot.current_location][next_node].get("weight", 1.0)
                        blocked = self._world.is_blocked(robot.current_location, next_node)
                        
                        if not blocked:
                            # Path is clear physically -> Execute move step
                            moved = robot.navigate_step(next_node, weight)
                            if moved:
                                robot.set_planned_path(robot.planned_path[1:])
                                print(f"  [{robot.robot_id}] Moved to node {next_node}. Battery: {robot.current_battery:.1f}")
                        else:
                            # Path is blocked physically in reality!
                            print(f"  [{robot.robot_id}] ALERT: Path {robot.current_location} -> {next_node} is BLOCKED by adversary!")
                            # Force re-sensing/re-planning by halting and clearing plan
                            robot.set_planned_path([robot.current_location])
                            # Sensed immediately upon bump-block (Bayes filter triggers)
                            robot.consume_battery(robot._battery_drain_rate)
                else:
                    # Robot is idle or waiting
                    robot.consume_battery(robot._battery_drain_rate)

                # Check if robot has arrived at any active task location
                for task in self._active_tasks:
                    if not task.is_completed and robot.current_location == task.location:
                        if task.task_id in robot._local_beliefs["assigned_tasks"]:
                            task.mark_completed(robot.robot_id, self._time_step)
                            robot._local_beliefs["assigned_tasks"].remove(task.task_id)
                            print(f"  [SUCCESS] {robot.robot_id} completed {task.task_id} at node {task.location}!")

            # 10. Cache tick metrics
            self._collect_tick_metrics()

            # End simulation early if fleet is fully depleted
            active_energy = sum(r.current_battery for r in self._robots)
            if active_energy <= 0.0:
                print("\nAll fleet batteries fully depleted. Stopping simulation.")
                break

            self._time_step += 1

        print("\n=== SIMULATION SYSTEM LOOP COMPLETED ===")
        self._export_metrics()

    def _collect_tick_metrics(self) -> None:
        """Gathers diagnostic details for the current tick.

        Measures social welfare, remaining battery energy, and statistical
        belief divergence over adversary jamming models.
        """
        # Social welfare: rewards earned minus energy overhead
        completed_rewards = sum(t.reward for t in self._active_tasks if t.is_completed)
        spent_battery_cost = sum(
            r._battery_capacity - r.current_battery for r in self._robots
        )
        welfare = completed_rewards - spent_battery_cost

        # Belief divergence: variance/std of robots' belief estimates for theta_2
        t2_beliefs = [r.belief["theta_2"] for r in self._robots if r.current_battery > 0.0]
        if len(t2_beliefs) > 1:
            mean_b = sum(t2_beliefs) / len(t2_beliefs)
            var_b = sum((x - mean_b) ** 2 for x in t2_beliefs) / (len(t2_beliefs) - 1)
            belief_divergence = math.sqrt(var_b)
        else:
            belief_divergence = 0.0

        tick_record = {
            "tick": self._time_step,
            "active_tasks_count": len([t for t in self._active_tasks if not t.is_completed]),
            "completed_tasks_count": len([t for t in self._active_tasks if t.is_completed]),
            "total_fleet_battery": round(sum(r.current_battery for r in self._robots), 2),
            "social_welfare": round(welfare, 2),
            "belief_divergence": round(belief_divergence, 4),
            "market_state": self._auction_house.get_market_state()
        }
        
        # Log summary states
        print(f"  [Metrics] Completed Tasks: {tick_record['completed_tasks_count']}, Fleet Battery: {tick_record['total_fleet_battery']:.1f}, Belief StdDev: {belief_divergence:.3f}")
        self._metrics_log.append(tick_record)

    def _export_metrics(self) -> None:
        """Saves cached tick records to the designated output log filepath."""
        sim_config = self._config.get("simulation", {})
        export_path = sim_config.get("metrics_export_path", "logs/simulation_metrics.json")
        
        # Enforce folder existence
        folder = os.path.dirname(export_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        with open(export_path, "w") as file:
            json.dump(self._metrics_log, file, indent=2)
        print(f"Simulation metrics exported successfully to: [metrics](file:///{os.path.abspath(export_path)})\n")


if __name__ == "__main__":
    # Standard configuration verification
    default_config_path = "config/settings.yaml"
    
    try:
        engine = SimulationEngine(default_config_path)
        engine.run()
    except Exception as e:
        print(f"Simulation execution failed: {e}")
        sys.exit(1)
