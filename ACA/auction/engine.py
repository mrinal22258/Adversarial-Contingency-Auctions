"""Decentralized auction engine for Adversarial Contingency Auctions (ACA).

Defines the dynamic bidding and allocation layers:
- Task: Represents simulation goals requiring allocation.
- Bid: Encapsulates bid parameters including contingency costs and disagreement penalties.
- AuctionEngine: Orchestrates Sequential Single-Item (SSI) auction mechanics under communication limits.
"""

from typing import Dict, List, Tuple, Set, Optional, Any
import math
import copy
from agents.robot import Robot


class Task:
    """Represents a work task generated dynamically during simulation.

    Tasks require robots to navigate to a specific node, satisfy capability demands,
    and execute the objective before a strict deadline.
    """

    def __init__(
        self,
        task_id: str,
        location: int,
        reward: float,
        deadline: float,
        required_capabilities: Optional[List[str]] = None
    ) -> None:
        """Initializes task parameters.

        Args:
            task_id: Unique string identifier for the task.
            location: Graph node ID where the task is located.
            reward: Payoff value earned by completing this task.
            deadline: Absolute simulation time step by which task must complete.
            required_capabilities: Optional list of capabilities required for the task.
        """
        self._task_id: str = task_id
        self._location: int = location
        self._reward: float = reward
        self._deadline: float = deadline
        self._required_capabilities: List[str] = required_capabilities or []
        self._is_completed: bool = False
        self._completed_by: Optional[str] = None
        self._completion_time: Optional[float] = None

    @property
    def task_id(self) -> str:
        """Gets the task unique identifier."""
        return self._task_id

    @property
    def location(self) -> int:
        """Gets the node ID location of the task."""
        return self._location

    @property
    def reward(self) -> float:
        """Gets the completion reward value."""
        return self._reward

    @property
    def deadline(self) -> float:
        """Gets the simulation step deadline."""
        return self._deadline

    @property
    def required_capabilities(self) -> List[str]:
        """Gets the list of capabilities necessary to execute this task."""
        return self._required_capabilities

    @property
    def is_completed(self) -> bool:
        """Checks if the task has been successfully executed."""
        return self._is_completed

    def mark_completed(self, robot_id: str, time_step: float) -> None:
        """Flags the task as completed by an agent at a given step.

        Args:
            robot_id: Identifier of the agent that performed the task.
            time_step: Simulation time step when execution completed.
        """
        self._is_completed = True
        self._completed_by = robot_id
        self._completion_time = time_step


class Bid:
    """Represents a structural bidding offer submitted by an agent.

    Encompasses the valuation of a task bundle, routing contingency costs,
    disagreement penalties, and sequential bundle information.
    """

    def __init__(
        self,
        bidder_id: str,
        task_id: str,
        bid_value: float,
        expected_cost: float,
        disagreement_penalty: float,
        timestamp: float,
        planned_path: List[int]
    ) -> None:
        """Initializes a bid object.

        Args:
            bidder_id: Unique identifier of the robot bidding.
            task_id: Identifier of the target task.
            bid_value: Combined bid metric (Expected_Cost + lambda * Disagreement_Penalty).
            expected_cost: Expected travel cost computed over the contingency tree.
            disagreement_penalty: KL Divergence disagreement calculation.
            timestamp: Simulation time step when the bid was created.
            planned_path: List of node IDs representing the planned optimistic path.
        """
        self._bidder_id: str = bidder_id
        self._task_id: str = task_id
        self._bid_value: float = bid_value
        self._expected_cost: float = expected_cost
        self._disagreement_penalty: float = disagreement_penalty
        self._timestamp: float = timestamp
        self._planned_path: List[int] = planned_path

    @property
    def bidder_id(self) -> str:
        """Gets the bidding robot identifier."""
        return self._bidder_id

    @property
    def task_id(self) -> str:
        """Gets the target task identifier."""
        return self._task_id

    @property
    def bid_value(self) -> float:
        """Gets the combined bidding metric (Expected_Cost + lambda * Disagreement_Penalty)."""
        return self._bid_value

    @property
    def expected_cost(self) -> float:
        """Gets the expected contingency tree cost."""
        return self._expected_cost

    @property
    def disagreement_penalty(self) -> float:
        """Gets the computed Kullback-Leibler belief disagreement penalty."""
        return self._disagreement_penalty

    @property
    def timestamp(self) -> float:
        """Gets the creation simulation step timestamp."""
        return self._timestamp

    @property
    def planned_path(self) -> List[int]:
        """Gets the planned optimistic path for this bid."""
        return self._planned_path


class AuctionEngine:
    """Manages the bidding evaluations and allocation consensus for task bundles.

    Implements Sequential Single-Item (SSI) auction mechanics, belief KL divergence penalization,
    and handles communication-constrained consensus failures.
    """

    def __init__(self, bid_epsilon: float = 0.01) -> None:
        """Initializes the simulation's auction engine.

        Args:
            bid_epsilon: The minimum bidding margin required to capture a task from an assignee.
        """
        self._bid_epsilon: float = bid_epsilon
        self._active_tasks: Dict[str, Task] = {}
        self._assignments: Dict[str, str] = {}  # task_id -> robot_id (Global Ground Truth)
        
        # Local, potentially out-of-sync allocations stored privately by each robot
        # robot_id -> Dict[task_id, robot_id]
        self._local_robot_allocations: Dict[str, Dict[str, str]] = {}
        
        # Track simulated message counts in the current epoch
        self._current_epoch_messages: float = 0.0

    def register_task(self, task: Task) -> None:
        """Registers a new active task into the market ecosystem.

        Args:
            task: Task instance to add.
        """
        self._active_tasks[task.task_id] = task

    @staticmethod
    def calculate_kl_divergence(p: Dict[str, float], q: Dict[str, float]) -> float:
        """Computes the Kullback-Leibler (KL) Divergence between two binary distributions.

        D_KL(P || Q) = Sum_k P(theta_k) * ln( P(theta_k) / Q(theta_k) )

        Args:
            p: The primary robot belief distribution {"theta_1": float, "theta_2": float}.
            q: The target expected belief distribution {"theta_1": float, "theta_2": float}.

        Returns:
            The float divergence value (non-negative).
        """
        eps = 1e-9
        divergence = 0.0
        for k in ["theta_1", "theta_2"]:
            pk = max(p.get(k, 0.5), eps)
            qk = max(q.get(k, 0.5), eps)
            divergence += pk * math.log(pk / qk)
        return max(0.0, divergence)

    def compute_disagreement_penalty(self, robot: Robot) -> float:
        """Calculates the KL divergence between a robot's beliefs and its neighbors.

        Computes the expected neighbor distribution Q by averaging the robot's
        theories of teammate beliefs, then calculates D_KL(P_self || Q).

        Args:
            robot: The Robot agent instance.

        Returns:
            The calculated disagreement penalty scalar.
        """
        predictions = robot.teammate_beliefs_predictions
        if not predictions:
            return 0.0

        # Calculate expectation (average) of neighbors' belief distributions
        avg_q = {"theta_1": 0.0, "theta_2": 0.0}
        for peer_pred in predictions.values():
            avg_q["theta_1"] += peer_pred.get("theta_1", 0.5)
            avg_q["theta_2"] += peer_pred.get("theta_2", 0.5)

        num_peers = len(predictions)
        avg_q["theta_1"] /= num_peers
        avg_q["theta_2"] /= num_peers

        # Return D_KL(P_self || Q_avg)
        return self.calculate_kl_divergence(robot.belief, avg_q)

    def run_ssi_auction(
        self,
        robots: List[Robot],
        unallocated_tasks: List[Task],
        comm_budget_kappa: float,
        lambda_penalty: float,
        current_time: float
    ) -> Dict[str, str]:
        """Runs a Sequential Single-Item (SSI) auction loop across the fleet.

        If message volume exceeds the communication budget kappa, robots are forced
        to complete allocation locally, creating potential out-of-sync allocations.

        Args:
            robots: List of participating Robot instances.
            unallocated_tasks: List of Task objects to allocate during this epoch.
            comm_budget_kappa: Max communication budget units (bits/messages) allowed.
            lambda_penalty: Weighting factor lambda for the disagreement penalty.
            current_time: Current simulation step tick.

        Returns:
            Dict mapping task_id to the winning robot_id.
        """
        self._current_epoch_messages = 0.0
        budget_exceeded = False

        # Initialize local allocations tracker for each robot
        for r in robots:
            if r.robot_id not in self._local_robot_allocations:
                self._local_robot_allocations[r.robot_id] = copy.deepcopy(self._assignments)

        # Allocate tasks sequentially
        for task in unallocated_tasks:
            if task.is_completed:
                continue

            bids: Dict[str, Bid] = {}

            # 1. Robots evaluate the task and compute bids privately
            for robot in robots:
                # Use branching A* contingency tree to estimate expected traversal costs
                # branch at index 0 (immediate path planning)
                tree_data = robot.generate_contingency_tree(task, branching_time_t_br=0)
                expected_cost = tree_data["expected_cost"]

                # If the target is physically unreachable, skip bidding
                if expected_cost == float("inf"):
                    continue

                # Calculate KL divergence disagreement penalty
                penalty = self.compute_disagreement_penalty(robot)

                # 2. Strict equation: Bid = Expected_Cost + lambda * Disagreement_Penalty
                bid_val = expected_cost + lambda_penalty * penalty

                bids[robot.robot_id] = Bid(
                    bidder_id=robot.robot_id,
                    task_id=task.task_id,
                    bid_value=bid_val,
                    expected_cost=expected_cost,
                    disagreement_penalty=penalty,
                    timestamp=current_time,
                    planned_path=tree_data.get("branch_a", [])
                )

            if not bids:
                continue

            # 3. Model communication cost for consensus negotiation
            # Fully decentralized P2P consensus for R robots requires exchanging bid tables
            # We charge 15.0 message units per active bidding agent
            round_comm_cost = len(bids) * 15.0
            
            if not budget_exceeded and (self._current_epoch_messages + round_comm_cost > comm_budget_kappa):
                budget_exceeded = True
                print(f"[Auction] Communication budget exceeded (Spent: {self._current_epoch_messages + round_comm_cost:.1f} / Limit: {comm_budget_kappa}). Entering local out-of-sync fallback mode.")

            if not budget_exceeded:
                # --- CONSENSUS MODE (Normal) ---
                self._current_epoch_messages += round_comm_cost

                # Find robot with the lowest cost bid (minimizing Expected_Cost + penalty)
                winning_robot_id = min(bids.keys(), key=lambda r_id: bids[r_id].bid_value)
                
                # Apply global assignment
                self._assignments[task.task_id] = winning_robot_id
                
                # Broadcast and sync every robot's local allocation records (consuming budget)
                for r in robots:
                    self._local_robot_allocations[r.robot_id][task.task_id] = winning_robot_id
                    # Add task to the winning robot's private list of assignments
                    if r.robot_id == winning_robot_id:
                        r._local_beliefs["assigned_tasks"].add(task.task_id)
                        r.set_planned_path(bids[winning_robot_id].planned_path)
            
            else:
                # --- COMMUNICATION-CONSTRAINED FALLBACK MODE ---
                # Budget is exceeded. Robots must resolve allocations locally using only their
                # own private, out-of-sync bidding information.
                # In this mode, robots cannot communicate. Each robot believes it is choosing
                # the optimal bidder based on its private viewpoint, which may cause overlaps!
                
                for r in robots:
                    # Each robot evaluates the bid list locally
                    if r.robot_id not in bids:
                        continue
                    
                    # Robot chooses its local winner (might disagree due to different beliefs/paths)
                    local_winner_id = min(bids.keys(), key=lambda r_id: bids[r_id].bid_value)
                    
                    # Update private allocation (potentially conflicting with peers)
                    self._local_robot_allocations[r.robot_id][task.task_id] = local_winner_id
                    
                    if r.robot_id == local_winner_id:
                        r._local_beliefs["assigned_tasks"].add(task.task_id)
                        r.set_planned_path(bids[local_winner_id].planned_path)

                # Ground Truth selection defaults to the best physical bid, but we log the disagreement
                ground_winner = min(bids.keys(), key=lambda r_id: bids[r_id].bid_value)
                self._assignments[task.task_id] = ground_winner

        return self._assignments

    def get_market_state(self) -> Dict[str, Any]:
        """Provides the current global allocation layout for simulation monitoring.

        Returns:
            A dictionary of tasks, active assignments, and local discrepancies.
        """
        # Calculate local discrepancies (out-of-sync level)
        discrepancies = {}
        for r_id, loc_alloc in self._local_robot_allocations.items():
            diff = {t_id: val for t_id, val in loc_alloc.items() if self._assignments.get(t_id) != val}
            if diff:
                discrepancies[r_id] = diff

        return {
            "registered_tasks": list(self._active_tasks.keys()),
            "assignments": self._assignments,
            "message_volume_spent": self._current_epoch_messages,
            "out_of_sync_allocations": discrepancies
        }

    # Backward compatibility wrapper for boilerplate call signatures
    def run_consensus_rounds(self, robots: List[Robot], max_rounds: int) -> Dict[str, List[str]]:
        """Simulates decentralized consensus conflict resolution.

        Wraps run_ssi_auction using default bounds.
        """
        # Collect unallocated registered tasks
        unallocated = [
            t for t in self._active_tasks.values() 
            if t.task_id not in self._assignments and not t.is_completed
        ]
        
        # Default limits from standard settings parameters
        kappa = 150.0
        lambda_val = 5.0
        
        self.run_ssi_auction(robots, unallocated, kappa, lambda_val, current_time=0.0)

        # Re-pack into list output
        allocations: Dict[str, List[str]] = {r.robot_id: [] for r in robots}
        for t_id, r_id in self._assignments.items():
            if r_id in allocations:
                allocations[r_id].append(t_id)
        return allocations
