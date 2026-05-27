"""Autonomous agent representation for Adversarial Contingency Auctions (ACA).

This module defines the Robot class, encapsulating private local beliefs,
battery constraints, communication limits, a private NetworkX belief graph,
discrete Bayes filter over adversary types, and teammate belief prediction.
"""

from typing import Dict, List, Tuple, Set, Optional, Any
import copy
import networkx as nx


class Robot:
    """Represents a heterogeneous autonomous robot participating in the simulator.

    Strict Rule: To model decentralized operations, robots CANNOT directly read or write
    to another robot's instance variables. All interaction and state sharing must happen
    through structured communication channels or message passing.
    """

    def __init__(
        self,
        robot_id: str,
        robot_type: str,
        initial_location: int,
        battery_capacity: float,
        battery_drain_rate: float,
        battery_move_cost: float,
        comm_budget: float,
        sensing_range: int,
        speed: float,
        capabilities: Optional[Set[str]] = None
    ) -> None:
        """Initializes a heterogeneous robot with private belief states and trackers.

        Args:
            robot_id: Unique string identifier for the robot.
            robot_type: Type classification (e.g., "scout", "heavy_lifter").
            initial_location: Node ID representing starting position.
            battery_capacity: Maximum energy unit capacity.
            battery_drain_rate: Idle energy cost per tick.
            battery_move_cost: Energy cost factor per weight unit traversed.
            comm_budget: Maximum communication bits permitted per tick.
            sensing_range: Visibility radius (hops) for environment verification.
            speed: Traversal speed factor.
            capabilities: Set of capability strings the robot possesses.
        """
        # Static identities
        self._robot_id: str = robot_id
        self._robot_type: str = robot_type
        self._sensing_range: int = sensing_range
        self._speed: float = speed
        self._capabilities: Set[str] = capabilities or set()

        # Private dynamic physical states
        self._current_location: int = initial_location
        self._battery_capacity: float = battery_capacity
        self._current_battery: float = battery_capacity
        self._battery_drain_rate: float = battery_drain_rate
        self._battery_move_cost: float = battery_move_cost
        
        self._comm_budget_limit: float = comm_budget
        self._comm_budget_spent: float = 0.0

        # Plan state
        self._planned_path: List[int] = [initial_location]

        # 1. Local NetworkX belief graph (subjective and dynamic)
        self._local_graph: nx.Graph = nx.Graph()

        # 2. Private belief state over hidden adversary type theta
        # theta_1 = pure_stochastic, theta_2 = reactive_jammer
        self._belief: Dict[str, float] = {
            "theta_1": 0.5,
            "theta_2": 0.5
        }

        # 4. Teammate belief predictions: what this robot *thinks* neighbors believe
        # Maps robot_id -> {"theta_1": float, "theta_2": float}
        self._teammate_beliefs_predictions: Dict[str, Dict[str, float]] = {}

        # General private beliefs dictionary
        self._local_beliefs: Dict[str, Any] = {
            "assigned_tasks": set(),
            "peer_allocations": {},        # robot_id -> assigned task_ids
            "peer_paths": {},              # robot_id -> List[int] planned path
            "last_known_locations": {},    # robot_id -> int location
            "last_known_sensing": {}       # robot_id -> int range
        }

        # Dynamic state trackers for Bayes filter parameters
        self._base_block_prob: float = 0.1
        self._reactive_coefficient: float = 0.25

        # Local event history for auditing decisions
        self._local_history: List[Dict[str, Any]] = []

    # --- Read-Only Properties for Simulation Logging/Auditing ---

    @property
    def robot_id(self) -> str:
        """Gets the unique robot identifier."""
        return self._robot_id

    @property
    def robot_type(self) -> str:
        """Gets the heterogeneous robot type classification."""
        return self._robot_type

    @property
    def capabilities(self) -> Set[str]:
        """Gets the capability set of this robot."""
        return self._capabilities

    @property
    def current_location(self) -> int:
        """Gets the robot's current node location."""
        return self._current_location

    @property
    def current_battery(self) -> float:
        """Gets the remaining battery capacity."""
        return self._current_battery

    @property
    def comm_budget_remaining(self) -> float:
        """Gets the leftover communication budget for the current step."""
        return max(0.0, self._comm_budget_limit - self._comm_budget_spent)

    @property
    def sensing_range(self) -> int:
        """Gets the graph hop sensing limit."""
        return self._sensing_range

    @property
    def planned_path(self) -> List[int]:
        """Gets the current planned navigation path."""
        return self._planned_path

    @property
    def local_graph(self) -> nx.Graph:
        """Gets the robot's local NetworkX belief graph copy."""
        return self._local_graph

    @property
    def belief(self) -> Dict[str, float]:
        """Gets the private belief distribution over the adversary types."""
        return self._belief

    @property
    def teammate_beliefs_predictions(self) -> Dict[str, Dict[str, float]]:
        """Gets the predicted belief states of teammates."""
        return self._teammate_beliefs_predictions

    # --- Public Interaction and Logic Interfaces ---

    def set_planned_path(self, path: List[int]) -> None:
        """Sets the active navigation path planned for the agent.

        Args:
            path: List of node IDs forming a path starting from current_location.
        """
        self._planned_path = path

    def update_beliefs_from_sensing(self, sensor_data: Dict[str, Any]) -> None:
        """Processes raw local sensing measurements to update internal graph copy.

        Also triggers the Bayesian filter update upon observing newly resolved edge states.

        Args:
            sensor_data: Dictionary representing locally discovered graph states:
                         {"nodes": List[int], "edges": Dict[Tuple[int,int], float], "blockages": Dict[Tuple[int,int], Optional[bool]]}
        """
        # Synchronize nodes
        for node in sensor_data.get("nodes", []):
            if not self._local_graph.has_node(node):
                self._local_graph.add_node(node)

        newly_observed_blockages: Dict[Tuple[int, int], bool] = {}

        # Synchronize edges and track newly observed states
        for (u, v), blocked in sensor_data.get("blockages", {}).items():
            edge_key = (min(u, v), max(u, v))
            weight = sensor_data["edges"].get(edge_key, 1.0)
            
            # Determine if this edge block state is a new observation or has changed
            is_new = True
            if self._local_graph.has_edge(u, v):
                prev_blocked = self._local_graph[u][v].get("blocked", None)
                if prev_blocked is not None:
                    is_new = False
            
            # We only perform Bayes updates on risky edges whose state has been resolved (True or False)
            if blocked is not None:
                # Add or update edge
                self._local_graph.add_edge(u, v, weight=weight, blocked=blocked)
                if is_new:
                    # By default, assume risk is designated or discovered if blocked
                    self._local_graph[u][v]["is_risk"] = sensor_data.get("is_risk_mapping", {}).get(edge_key, True)
                    if self._local_graph[u][v]["is_risk"]:
                        newly_observed_blockages[edge_key] = blocked
            else:
                # Outside sensing range -> Add if not present, marked as unobserved (None)
                if not self._local_graph.has_edge(u, v):
                    self._local_graph.add_edge(u, v, weight=weight, blocked=None, is_risk=True)

        # 3. Bayes Filter update for newly observed risky edges
        if newly_observed_blockages:
            self.discrete_bayes_filter_update(newly_observed_blockages)

    # 3. Bayes Filter implementation
    def discrete_bayes_filter_update(self, local_observation: Dict[Tuple[int, int], bool]) -> None:
        """Updates the posterior probability of the adversary type using Bayes' Rule.

        For each observed edge state X_e in local_observation:
            P(theta_j | X_e) = P(X_e | theta_j) * P(theta_j) / Normalizer

        Args:
            local_observation: Dict mapping edge coordinates (u, v) to true block status (bool).
        """
        for edge, blocked in local_observation.items():
            u, v = edge
            
            # 1. Likelihood under theta_1 (Pure Stochastic)
            p_theta1 = self._base_block_prob if blocked else (1.0 - self._base_block_prob)

            # 2. Likelihood under theta_2 (Reactive Jammer)
            # Estimate N_e using local peer path representations
            n_e = 0
            all_paths = [self._planned_path] + list(self._local_beliefs["peer_paths"].values())
            
            for path in all_paths:
                if not path:
                    continue
                # Traverse check
                traverses = False
                for i in range(len(path) - 1):
                    pu, pv = path[i], path[i+1]
                    if (pu == u and pv == v) or (pu == v and pv == u):
                        traverses = True
                        break
                # Near check (adjacent nodes in graph copy)
                is_near = False
                if self._local_graph.has_node(u) and self._local_graph.has_node(v):
                    path_nodes = set(path)
                    neighbors_u = set(self._local_graph.neighbors(u)) if self._local_graph.has_node(u) else set()
                    neighbors_v = set(self._local_graph.neighbors(v)) if self._local_graph.has_node(v) else set()
                    
                    if (path_nodes.intersection(neighbors_u) or 
                        path_nodes.intersection(neighbors_v) or 
                        u in path_nodes or 
                        v in path_nodes):
                        is_near = True

                if traverses or is_near:
                    n_e += 1

            p_base_reactive = min(1.0, self._base_block_prob + self._reactive_coefficient * n_e)
            p_theta2 = p_base_reactive if blocked else (1.0 - p_base_reactive)

            # 3. Bayes Equation calculation
            prior_t1 = self._belief["theta_1"]
            prior_t2 = self._belief["theta_2"]

            num_t1 = p_theta1 * prior_t1
            num_t2 = p_theta2 * prior_t2
            normalizer = num_t1 + num_t2

            # Avoid division by zero in deterministic edge situations
            if normalizer > 0.0:
                self._belief["theta_1"] = num_t1 / normalizer
                self._belief["theta_2"] = num_t2 / normalizer
            
            # Numerical bounds correction
            epsilon = 1e-6
            self._belief["theta_1"] = max(epsilon, min(1.0 - epsilon, self._belief["theta_1"]))
            self._belief["theta_2"] = 1.0 - self._belief["theta_1"]

        self._local_history.append({
            "step": "bayes_update",
            "observation": local_observation,
            "updated_belief": copy.deepcopy(self._belief)
        })

    # 4. Predict Teammate Beliefs implementation
    def predict_teammate_beliefs(self) -> None:
        """Simulates how teammates update their beliefs based on their local perspective.

        Predicts the posterior adversary belief for each neighbor, using their last known
        position, sensor ranges, and visible edges observed by this agent.
        """
        for peer_id, location in self._local_beliefs["last_known_locations"].items():
            peer_range = self._local_beliefs["last_known_sensing"].get(peer_id, 1)
            
            # Initialize or keep track of teammate belief prediction (default 50-50)
            if peer_id not in self._teammate_beliefs_predictions:
                self._teammate_beliefs_predictions[peer_id] = {"theta_1": 0.5, "theta_2": 0.5}

            peer_belief = self._teammate_beliefs_predictions[peer_id]

            # Simulate peer sensing range query on our local graph copy
            if not self._local_graph.has_node(location):
                continue

            visible_nodes = nx.single_source_shortest_path_length(
                self._local_graph,
                location,
                cutoff=peer_range
            )
            visible_node_set = set(visible_nodes.keys())

            # Find all edges visible from peer location
            peer_observations: Dict[Tuple[int, int], bool] = {}
            for u, v, d in self._local_graph.edges(data=True):
                edge_key = (min(u, v), max(u, v))
                blocked = d.get("blocked", None)
                is_risk = d.get("is_risk", True)

                # Peer can see it if it's incident to one of their visible nodes
                if (u in visible_node_set or v in visible_node_set) and blocked is not None and is_risk:
                    peer_observations[edge_key] = blocked

            # Perform a simulated Bayes update on the peer's predicted belief
            for edge, blocked in peer_observations.items():
                u, v = edge
                p_theta1 = self._base_block_prob if blocked else (1.0 - self._base_block_prob)

                # Compute N_e estimate from peer perspective (peer path + peer belief of other paths)
                n_e = 0
                peer_path = self._local_beliefs["peer_paths"].get(peer_id, [location])
                all_paths = [peer_path] + [self._planned_path]
                for p_id, p_path in self._local_beliefs["peer_paths"].items():
                    if p_id != peer_id:
                        all_paths.append(p_path)

                for path in all_paths:
                    if not path:
                        continue
                    traverses = False
                    for i in range(len(path) - 1):
                        pu, pv = path[i], path[i+1]
                        if (pu == u and pv == v) or (pu == v and pv == u):
                            traverses = True
                            break
                    is_near = False
                    if self._local_graph.has_node(u) and self._local_graph.has_node(v):
                        path_nodes = set(path)
                        neighbors_u = set(self._local_graph.neighbors(u))
                        neighbors_v = set(self._local_graph.neighbors(v))
                        if (path_nodes.intersection(neighbors_u) or 
                            path_nodes.intersection(neighbors_v) or 
                            u in path_nodes or 
                            v in path_nodes):
                            is_near = True

                    if traverses or is_near:
                        n_e += 1

                p_base_reactive = min(1.0, self._base_block_prob + self._reactive_coefficient * n_e)
                p_theta2 = p_base_reactive if blocked else (1.0 - p_base_reactive)

                num_t1 = p_theta1 * peer_belief["theta_1"]
                num_t2 = p_theta2 * peer_belief["theta_2"]
                norm = num_t1 + num_t2

                if norm > 0.0:
                    peer_belief["theta_1"] = num_t1 / norm
                    peer_belief["theta_2"] = num_t2 / norm

                # Normalization protection
                epsilon = 1e-6
                peer_belief["theta_1"] = max(epsilon, min(1.0 - epsilon, peer_belief["theta_1"]))
                peer_belief["theta_2"] = 1.0 - peer_belief["theta_1"]

    def receive_message(self, sender_id: str, message_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes structured communications received from peer robots.

        Updates location beliefs, path allocations, and peer status values.

        Args:
            sender_id: ID of the transmitting robot.
            message_payload: Dict containing path plans, location, or auction tables.

        Returns:
            Optional response handshake.
        """
        # Consume communication budget
        self._comm_budget_spent += len(str(message_payload)) / 100.0  # Approx bits/bytes model

        # Update peer tracking
        if "location" in message_payload:
            self._local_beliefs["last_known_locations"][sender_id] = message_payload["location"]
        if "sensing_range" in message_payload:
            self._local_beliefs["last_known_sensing"][sender_id] = message_payload["sensing_range"]
        if "planned_path" in message_payload:
            self._local_beliefs["peer_paths"][sender_id] = message_payload["planned_path"]
        if "belief" in message_payload:
            # Can log what the peer says its actual belief is
            pass

        return None

    def compute_bids_for_tasks(self, available_tasks: List[Any], bid_epsilon: float) -> List[Dict[str, Any]]:
        """Evaluates available tasks and generates bid values for task bundles.

        Calculates utilities using paths computed on the subjective local_graph copy
        modified by the adversary threat probability:
        cost = path_cost * (1 + contingency_premium * belief["theta_2"])

        Args:
            available_tasks: Active tasks list.
            bid_epsilon: Outbidding increment threshold.

        Returns:
            List of bids.
        """
        bids = []
        for task in available_tasks:
            # Find shortest path inside local copy
            if not self._local_graph.has_node(self._current_location) or not self._local_graph.has_node(task.location):
                continue
            
            # Simple fallback check: remove blocked edges to compute feasible paths
            temp_g = nx.Graph()
            for u, v, d in self._local_graph.edges(data=True):
                if d.get("blocked", False) is not True:  # Skip active blockades
                    temp_g.add_edge(u, v, weight=d.get("weight", 1.0))
            
            if not temp_g.has_node(self._current_location) or not temp_g.has_node(task.location):
                continue

            try:
                path = nx.shortest_path(temp_g, source=self._current_location, target=task.location, weight="weight")
                path_cost = nx.shortest_path_length(temp_g, source=self._current_location, target=task.location, weight="weight")
                
                # Risk penalty based on theta_2 belief
                risk_factor = 1.0 + 1.5 * self._belief["theta_2"]
                adjusted_cost = path_cost * risk_factor

                # Feasibility check
                if adjusted_cost * self._battery_move_cost <= self._current_battery:
                    bid_val = task.reward - adjusted_cost
                    bids.append({
                        "task_id": task.task_id,
                        "bidder_id": self._robot_id,
                        "bid_value": round(bid_val, 2),
                        "contingency_cost": round(adjusted_cost - path_cost, 2),
                        "planned_path": path
                    })
            except nx.NetworkXNoPath:
                continue

        return bids

    def generate_contingency_tree(self, target_task: Any, branching_time_t_br: int) -> Dict[str, Any]:
        """Formulates a branching A* contingency tree to reach a target task node.

        If the primary optimal path intersects a risky edge (is_risk = True), the plan 
        branches at branching_time_t_br (as an index in the path) into:
        - Branch A (Optimistic): Assumes the risky edge is clear and traversable.
        - Branch B (Contingency Detour): Assumes the risky edge is blocked, finding an A* detour.

        Args:
            target_task: Task instance (having location attribute) or directly target node ID (int).
            branching_time_t_br: Step index in the planned path where the contingency split occurs.

        Returns:
            A dictionary describing the contingency tree structure:
            {
                "branching_node": int (node ID where split occurs),
                "risky_edge": Tuple[int, int] (the edge causing the split),
                "branch_a": List[int] (optimistic path),
                "branch_b": List[int] (contingency detour path),
                "cost_a": float (optimistic path cost),
                "cost_b": float (detour path cost),
                "expected_cost": float (expected cost based on beliefs theta_1 and theta_2)
            }
        """
        # Resolve target node location
        target_node = getattr(target_task, "location", target_task)

        # Build local search graph (ignoring edges known to be blocked)
        temp_g = nx.Graph()
        for u, v, d in self._local_graph.edges(data=True):
            if d.get("blocked", False) is not True:
                temp_g.add_edge(u, v, weight=d.get("weight", 1.0), is_risk=d.get("is_risk", False))

        if not temp_g.has_node(self._current_location) or not temp_g.has_node(target_node):
            return {
                "branching_node": self._current_location,
                "risky_edge": None,
                "branch_a": [],
                "branch_b": [],
                "cost_a": float("inf"),
                "cost_b": float("inf"),
                "expected_cost": float("inf")
            }

        try:
            # Find primary path using NetworkX A* solver
            primary_path = nx.astar_path(temp_g, self._current_location, target_node, weight="weight")
            primary_cost = nx.astar_path_length(temp_g, self._current_location, target_node, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {
                "branching_node": self._current_location,
                "risky_edge": None,
                "branch_a": [],
                "branch_b": [],
                "cost_a": float("inf"),
                "cost_b": float("inf"),
                "expected_cost": float("inf")
            }

        # Find the risky edge at or near branching_time_t_br index
        risky_edge = None
        branch_idx = min(max(0, branching_time_t_br), len(primary_path) - 2) if len(primary_path) > 1 else 0
        
        # Check if the transition after branch_idx is a risky edge
        if len(primary_path) > 1:
            u = primary_path[branch_idx]
            v = primary_path[branch_idx + 1]
            if temp_g[u][v].get("is_risk", False):
                risky_edge = (u, v)
            else:
                # Search the remaining path for any risky edge
                for i in range(len(primary_path) - 1):
                    pu, pv = primary_path[i], primary_path[i+1]
                    if temp_g[pu][pv].get("is_risk", False):
                        risky_edge = (pu, pv)
                        branch_idx = i
                        break

        # If no risky edge exists on the primary path
        if not risky_edge:
            return {
                "branching_node": self._current_location,
                "risky_edge": None,
                "branch_a": primary_path,
                "branch_b": primary_path,
                "cost_a": primary_cost,
                "cost_b": primary_cost,
                "expected_cost": primary_cost
            }

        # Otherwise, split at branch_idx (node u)
        u, v = risky_edge
        branching_node = u

        # Branch A (Optimistic path is simply primary path)
        branch_a_path = primary_path
        cost_branch_a = primary_cost

        # Calculate cost from start to branching node u
        cost_to_branching_node = 0.0
        for i in range(branch_idx):
            n1, n2 = primary_path[i], primary_path[i+1]
            cost_to_branching_node += temp_g[n1][n2]["weight"]

        # Branch B (Contingency Detour: assumes edge (u, v) is blocked)
        branch_b_g = copy.deepcopy(temp_g)
        if branch_b_g.has_edge(u, v):
            branch_b_g.remove_edge(u, v)

        try:
            # Find detour from branching node u to target_node using A*
            detour_path = nx.astar_path(branch_b_g, branching_node, target_node, weight="weight")
            detour_cost = nx.astar_path_length(branch_b_g, branching_node, target_node, weight="weight")
            
            branch_b_path = primary_path[:branch_idx] + detour_path
            cost_branch_b = cost_to_branching_node + detour_cost
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # No alternative detour exists
            branch_b_path = primary_path[:branch_idx + 1]  # Halts at branching node
            cost_branch_b = float("inf")

        # 3. Calculate expected cost: E[Cost] = P(theta_1)*Cost(Branch A) + P(theta_2)*Cost(Branch B)
        p_t1 = self._belief["theta_1"]
        p_t2 = self._belief["theta_2"]
        
        if cost_branch_b == float("inf"):
            # Penalize highly blocked alternatives
            expected_cost = p_t1 * cost_branch_a + p_t2 * (cost_branch_a + 500.0)
        else:
            expected_cost = p_t1 * cost_branch_a + p_t2 * cost_branch_b

        return {
            "branching_node": branching_node,
            "risky_edge": risky_edge,
            "branch_a": branch_a_path,
            "branch_b": branch_b_path,
            "cost_a": round(cost_branch_a, 2),
            "cost_b": round(cost_branch_b, 2) if cost_branch_b != float("inf") else float("inf"),
            "expected_cost": round(expected_cost, 2)
        }

    def generate_contingency_paths(self, target_node: int, horizon: int) -> Dict[str, Any]:
        """Formulates a branching routing policy considering potential adversary blockages.

        Args:
            target_node: Destination node.
            horizon: Dynamic lookahead depth.

        Returns:
            Dict containing the primary path and branch detours.
        """
        # Primary path computes shortest route skipping known blocked edges
        temp_g = nx.Graph()
        for u, v, d in self._local_graph.edges(data=True):
            if d.get("blocked", False) is not True:
                temp_g.add_edge(u, v, weight=d.get("weight", 1.0))

        if not temp_g.has_node(self._current_location) or not temp_g.has_node(target_node):
            return {"primary_path": [], "contingencies": {}}

        try:
            primary = nx.shortest_path(temp_g, self._current_location, target_node, weight="weight")
            contingencies = {}

            # Generate branch detours for each risky step on the primary path
            for i in range(min(len(primary) - 1, horizon)):
                u, v = primary[i], primary[i+1]
                edge_key = f"{u}->{v}"

                # Calculate path assuming (u, v) is blocked at runtime
                branch_g = copy.deepcopy(temp_g)
                if branch_g.has_edge(u, v):
                    branch_g.remove_edge(u, v)
                
                try:
                    detour = nx.shortest_path(branch_g, u, target_node, weight="weight")
                    contingencies[edge_key] = detour
                except nx.NetworkXNoPath:
                    contingencies[edge_key] = []  # No alternative detour available

            return {
                "primary_path": primary,
                "contingencies": contingencies
            }
        except nx.NetworkXNoPath:
            return {"primary_path": [], "contingencies": {}}

    def navigate_step(self, next_node: int, true_edge_weight: float) -> bool:
        """Executes travel to an adjacent node on the graph.

        Args:
            next_node: The adjacent target node ID.
            true_edge_weight: The cost of the edge.

        Returns:
            True if navigation succeeded.
        """
        # Ensure battery is available
        cost = true_edge_weight * self._battery_move_cost
        if self._current_battery >= cost:
            self._current_battery -= cost
            self._current_location = next_node
            self._local_history.append({
                "step": "navigate",
                "to_node": next_node,
                "spent_battery": cost,
                "remaining_battery": self._current_battery
            })
            return True
        else:
            self.consume_battery(self._current_battery)  # Drain all remaining
            return False

    def consume_battery(self, amount: float) -> None:
        """Deducts energy from the internal battery state."""
        self._current_battery = max(0.0, self._current_battery - amount)
        if self._current_battery <= 0.0:
            self._handle_battery_depletion()

    def reset_comm_budget(self) -> None:
        """Resets the communication tracking spent state."""
        self._comm_budget_spent = 0.0

    def _handle_battery_depletion(self) -> None:
        """Emergency battery depletion handler."""
        self._local_beliefs["assigned_tasks"].clear()
        self._local_history.append({"step": "battery_depleted"})
