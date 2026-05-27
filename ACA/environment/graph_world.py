"""Environment representation for Adversarial Contingency Auctions (ACA).

This module models the global "ground truth" environment using NetworkX:
- GraphWorld: Manages actual node and edge connectivity, costs, and current blockages.
- Adversary: Models the strategic agent (theta^*) blockading edges to impede robot progress.
"""

from typing import Dict, List, Tuple, Set, Optional, Any
import random
import networkx as nx


class Adversary:
    """Represents a strategic adversary (theta^*) operating on the graph world.

    The adversary selectively blockades edges based on its policy type (theta):
    - theta_1 (Pure Stochastic): Blockages occur based on a state-independent baseline probability.
    - theta_2 (Reactive Jammer): Jamming probability increases proportionally to robot path plans
      running through or near risky edges.
    """

    def __init__(
        self,
        policy_type: str,
        base_block_prob: float = 0.1,
        reactive_coefficient: float = 0.25,
        max_blockages: int = 5,
        seed: Optional[int] = None
    ) -> None:
        """Initializes the strategic adversary.

        Args:
            policy_type: The behavioral type ("pure_stochastic" or "reactive_jammer").
            base_block_prob: Baseline probability of an edge becoming blocked.
            reactive_coefficient: Multiplier alpha for reactive jammer probability scaling.
            max_blockages: Maximum concurrent blockades allowed globally.
            seed: Random seed for stochastic blocker mutations.
        """
        # Normalize policy type to allow flexible names
        self._policy_type: str = "reactive_jammer" if "reactive" in policy_type.lower() else "pure_stochastic"
        self._base_block_prob: float = base_block_prob
        self._reactive_coefficient: float = reactive_coefficient
        self._max_blockages: int = max_blockages
        self._random_generator: random.Random = random.Random(seed)
        self._active_blockages: Set[Tuple[int, int]] = set()

    @property
    def policy_type(self) -> str:
        """Gets the strategic policy type (theta) of the adversary."""
        return self._policy_type

    @property
    def active_blockages(self) -> Set[Tuple[int, int]]:
        """Gets the set of currently blockaded edges as sorted (u, v) tuples."""
        return self._active_blockages

    def compute_blockage_decisions(
        self,
        graph: nx.Graph,
        joint_fleet_actions: Dict[str, Any]
    ) -> Set[Tuple[int, int]]:
        """Determines which edges to blockade during the current simulation step.

        For theta_1 (Pure Stochastic):
            P(blocked | e) = P_base
        For theta_2 (Reactive Jammer):
            P(blocked | e) = P_base + alpha * N_e
            where N_e is the number of robots planning paths through or near (1-hop of) edge e.

        Args:
            graph: The ground-truth NetworkX environment graph G = (V, E).
            joint_fleet_actions: Map of robot ID to their dynamic planned actions/paths.
                                 Can be a list of node IDs `List[int]` representing their intended path,
                                 or a dictionary containing `{"planned_path": List[int], "current_node": int}`.

        Returns:
            A set of (u, v) edge tuples representing the newly designated blockages.
        """
        new_blockages: Set[Tuple[int, int]] = set()
        risky_edges = [
            (u, v) for u, v, d in graph.edges(data=True) if d.get("is_risk", False)
        ]

        if not risky_edges:
            return new_blockages

        # Extract plans for all robots
        robot_paths: List[List[int]] = []
        for action in joint_fleet_actions.values():
            if isinstance(action, list):
                robot_paths.append(action)
            elif isinstance(action, dict) and "planned_path" in action:
                robot_paths.append(action["planned_path"])

        # Evaluate each risky edge
        for u, v in risky_edges:
            edge_key = (min(u, v), max(u, v))
            
            if self._policy_type == "pure_stochastic":
                prob = self._base_block_prob
            else:  # reactive_jammer
                # Count robots planning paths through or near (1-hop) of edge (u, v)
                n_e = 0
                for path in robot_paths:
                    if not path:
                        continue
                    
                    # 1. Check if path directly traverses the edge
                    traverses = False
                    for i in range(len(path) - 1):
                        pu, pv = path[i], path[i+1]
                        if (pu == u and pv == v) or (pu == v and pv == u):
                            traverses = True
                            break
                    
                    # 2. Check if path is near the edge (within 1-hop of u or v)
                    is_near = False
                    path_nodes = set(path)
                    neighbors_u = set(graph.neighbors(u))
                    neighbors_v = set(graph.neighbors(v))
                    
                    # If path contains u, v, or any neighbor of u/v
                    if (path_nodes.intersection(neighbors_u) or 
                        path_nodes.intersection(neighbors_v) or 
                        u in path_nodes or 
                        v in path_nodes):
                        is_near = True

                    if traverses or is_near:
                        n_e += 1

                # Reactive scaling: P = P_base + alpha * N_e
                prob = min(1.0, self._base_block_prob + self._reactive_coefficient * n_e)

            # Sample blockage outcome
            if self._random_generator.random() < prob:
                new_blockages.add(edge_key)
                if len(new_blockages) >= self._max_blockages:
                    break

        self._active_blockages = new_blockages
        return self._active_blockages


class GraphWorld:
    """Manages the true physical state of the environment graph using NetworkX.

    Maintains ground truth connectivity, traversal weights, and blockages, 
    and handles dynamic environmental mutations driven by the active Adversary.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initializes the GraphWorld environment using configurations.

        Args:
            config: Dict containing configuration keys for graph size, connectivity, and adversary settings.
        """
        self._config: Dict[str, Any] = config
        
        # Instantiate empty NetworkX Graph G = (V, E)
        self._graph: nx.Graph = nx.Graph()
        
        # Parse adversary configuration
        adv_config = config.get("adversary", {})
        self._adversary: Adversary = Adversary(
            policy_type=adv_config.get("type", "reactive_blocker"),
            base_block_prob=adv_config.get("mutation_probability", 0.1),
            reactive_coefficient=adv_config.get("reactive_coefficient", 0.25),
            max_blockages=adv_config.get("max_active_blockages", 5),
            seed=adv_config.get("seed", 42)
        )

        self._initialize_graph()

    def _initialize_graph(self) -> None:
        """Builds the base graph topology based on configuration parameters.

        Creates nodes, establishes connectivity (Erdős-Rényi layout), 
        assigns traversal costs, and designates risky edges (E_risk).
        """
        graph_config = self._config.get("graph", {})
        num_nodes = graph_config.get("num_nodes", 15)
        conn_prob = graph_config.get("connection_probability", 0.3)
        weight_range = graph_config.get("edge_weight_range", [1.0, 10.0])
        seed = graph_config.get("seed", 42)

        # Generate base Erdős-Rényi graph
        temp_g = nx.erdos_renyi_graph(num_nodes, conn_prob, seed=seed)
        
        # Ensure the graph is fully connected (add bridges between components if disconnected)
        if not nx.is_connected(temp_g):
            components = list(nx.connected_components(temp_g))
            for i in range(len(components) - 1):
                u = random.choice(list(components[i]))
                v = random.choice(list(components[i+1]))
                temp_g.add_edge(u, v)

        # Build true self._graph attributes
        self._graph.add_nodes_from(temp_g.nodes())
        
        rng = random.Random(seed)
        for u, v in temp_g.edges():
            # Generate random traversal cost/weight
            weight = rng.uniform(weight_range[0], weight_range[1])
            # Designate ~30% of edges as part of E_risk
            is_risk = rng.random() < 0.3
            
            self._graph.add_edge(
                u, v,
                weight=round(weight, 2),
                is_risk=is_risk,
                blocked=False  # Initial physical state is clear
            )

    @property
    def graph(self) -> nx.Graph:
        """Gets the underlying ground-truth NetworkX graph."""
        return self._graph

    @property
    def nodes(self) -> List[int]:
        """Gets all node identifiers in the graph."""
        return list(self._graph.nodes())

    @property
    def edges(self) -> List[Tuple[int, int]]:
        """Gets all edge coordinate tuples in the graph."""
        return list(self._graph.edges())

    @property
    def adversary(self) -> Adversary:
        """Gets the true adversary instance currently active in the world."""
        return self._adversary

    def is_blocked(self, u: int, v: int) -> bool:
        """Checks if a specific edge is physically blocked under the true state.

        Args:
            u: Start node.
            v: End node.

        Returns:
            True if the path is physically impassable, False otherwise.
        """
        if not self._graph.has_edge(u, v):
            return True  # Non-existent edge is impassable
        return self._graph[u][v].get("blocked", False)

    def update_blockages(self, joint_fleet_actions: Dict[str, Any]) -> None:
        """Mutates the physical graph state by invoking the active Adversary.

        Evaluates fleet trajectories/plans to compute blockage risks and applies mutations.

        Args:
            joint_fleet_actions: Map of robot ID to their dynamic planned actions/paths.
        """
        # Reset all edge blockages first
        for u, v in self._graph.edges():
            self._graph[u][v]["blocked"] = False

        # Compute new blockage layout
        active_blockages = self._adversary.compute_blockage_decisions(
            self._graph,
            joint_fleet_actions
        )

        # Apply blockages to true graph attributes
        for u, v in active_blockages:
            if self._graph.has_edge(u, v):
                self._graph[u][v]["blocked"] = True

    def get_local_observation(
        self,
        robot_id: str,
        current_node: int,
        sensing_radius: int
    ) -> Dict[str, Any]:
        """Exposes local observation data within a sensing radius (hops).

        Returns true edge states only within a limited radius, leaving the rest
        of the graph uncertain (returns None for blockages outside range).

        Args:
            robot_id: Identifier of the query robot.
            current_node: The query origin node ID.
            sensing_radius: Sensing hop limit.

        Returns:
            A dictionary containing the local subjective view:
            {
                "nodes": List of nodes within sensing range,
                "edges": Dict of edge tuples mapped to weight,
                "blockages": Dict of edge tuples mapped to blockage status (bool or None)
            }
        """
        # Perform breadth-first search up to sensing_radius to find visible nodes
        visible_nodes = nx.single_source_shortest_path_length(
            self._graph,
            current_node,
            cutoff=sensing_radius
        )
        visible_node_set = set(visible_nodes.keys())

        local_edges: Dict[Tuple[int, int], float] = {}
        local_blockages: Dict[Tuple[int, int], Optional[bool]] = {}

        # Scan all edges in the graph
        for u, v, d in self._graph.edges(data=True):
            edge_key = (min(u, v), max(u, v))
            weight = d.get("weight", 1.0)
            
            # An edge is visible if BOTH of its endpoints are in visible_nodes
            # Or if it is incident to a visible node (1-hop sensor boundary lookup)
            if u in visible_node_set or v in visible_node_set:
                local_edges[edge_key] = weight
                local_blockages[edge_key] = d.get("blocked", False)
            else:
                # Outside sensing range -> state is uncertain (None)
                local_edges[edge_key] = weight
                local_blockages[edge_key] = None

        return {
            "nodes": list(self._graph.nodes()),  # Graph structure is known
            "edges": local_edges,
            "blockages": local_blockages
        }

    # Backward compatibility wrapper for boilerplate call signatures
    def mutate_edges(self, robot_positions: Dict[str, int]) -> None:
        """Wrapper around update_blockages mapping current robot locations.

        Args:
            robot_positions: Map of robot ID to node locations.
        """
        # Treat current locations as 1-node trivial paths for blockage calculations
        joint_actions = {rid: [node] for rid, node in robot_positions.items()}
        self.update_blockages(joint_actions)

    # Backward compatibility wrapper for boilerplate call signatures
    def get_local_subgraph(self, location: int, radius: int) -> Dict[str, Any]:
        """Wrapper around get_local_observation.

        Args:
            location: Query node ID.
            radius: Hop limit.
        """
        return self.get_local_observation("generic_robot", location, radius)

    def get_true_world_state(self) -> Dict[str, Any]:
        """Returns the full ground-truth physical state of the simulation.

        Returns:
            A dict containing global nodes, edge details, true blockages, and active adversary state.
        """
        true_blockages = {
            (min(u, v), max(u, v)): d.get("blocked", False)
            for u, v, d in self._graph.edges(data=True)
        }
        return {
            "nodes": list(self._graph.nodes()),
            "edges": {(u, v): d.get("weight", 1.0) for u, v, d in self._graph.edges(data=True)},
            "true_blockages": true_blockages,
            "adversary_policy": self._adversary.policy_type
        }
