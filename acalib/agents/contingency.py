"""
Contingency Planning and Exact Expected-Recourse Cost Valuation (Theorem 1).
Builds depth-d recourse trees and computes exact expected costs under adversary edge marginals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

from ..env.adversaries import canonical_edge


@dataclass
class RecoursePlan:
    task_id: int
    target_node: Any
    primary_path: List[Any]
    primary_cost: float
    expected_cost: float
    # Detour mapping: edge (u, v) -> alternative path from u to target_node
    detours: Dict[Tuple[Any, Any], List[Any]] = field(default_factory=dict)
    risky_edges: List[Tuple[Any, Any]] = field(default_factory=list)
    depth: int = 1


class ContingencyPlanner:
    """
    Plans primary paths and precomputed depth-d recourse branches around risky edges.
    """

    def __init__(
        self,
        graph: nx.Graph,
        max_depth: int = 1,
        exhaustion_penalty: float = 150.0,
        risk_weight: float = 2.0,
    ):
        self.graph = graph
        self.max_depth = max_depth
        self.exhaustion_penalty = exhaustion_penalty
        self.risk_weight = risk_weight

    def find_risk_aware_path(
        self,
        start_node: Any,
        target_node: Any,
        edge_marginals: Dict[Tuple[Any, Any], float],
        excluded_edges: Optional[Set[Tuple[Any, Any]]] = None,
    ) -> Optional[List[Any]]:
        """
        Compute path minimizing effective risk-weighted travel cost:
        w_eff(e) = w(e) * (1 + risk_weight * pi(e)).
        """
        if start_node == target_node:
            return [start_node]

        if excluded_edges is None:
            excluded_edges = set()

        def edge_weight_fn(u: Any, v: Any, d: Dict[str, Any]) -> float:
            c_e = canonical_edge(u, v)
            if c_e in excluded_edges:
                return 1e9  # impassable
            base_w = d.get("weight", 1.0)
            pi_e = edge_marginals.get(c_e, 0.05)
            return base_w * (1.0 + self.risk_weight * pi_e)

        try:
            path = nx.shortest_path(
                self.graph,
                source=start_node,
                target=target_node,
                weight=edge_weight_fn,
            )
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def compute_path_length(self, path: List[Any]) -> float:
        """Sum of nominal edge weights along path."""
        if not path or len(path) <= 1:
            return 0.0
        tot = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            tot += self.graph[u][v].get("weight", 1.0)
        return tot

    def build_recourse_plan(
        self,
        task_id: int,
        start_node: Any,
        target_node: Any,
        edge_marginals: Dict[Tuple[Any, Any], float],
        risky_edge_threshold: float = 0.12,
    ) -> Optional[RecoursePlan]:
        """
        Construct primary path and depth-d recourse detours for identified risky edges.
        """
        primary_path = self.find_risk_aware_path(start_node, target_node, edge_marginals)
        if primary_path is None:
            return None

        primary_cost = self.compute_path_length(primary_path)

        # Identify risky edges along primary path in path order (upstream -> downstream)
        path_risky_edges: List[Tuple[Any, Any]] = []
        for i in range(len(primary_path) - 1):
            u, v = primary_path[i], primary_path[i + 1]
            c_e = canonical_edge(u, v)
            if edge_marginals.get(c_e, 0.0) >= risky_edge_threshold:
                path_risky_edges.append((u, v))

        detours: Dict[Tuple[Any, Any], List[Any]] = {}

        if self.max_depth > 0:
            for u, v in path_risky_edges:
                c_e = canonical_edge(u, v)
                # Detour must branch from upstream node u avoiding (u, v)
                excluded = {c_e}
                detour = self.find_risk_aware_path(
                    u, target_node, edge_marginals, excluded_edges=excluded
                )
                if detour is not None:
                    detours[(u, v)] = detour
                    detours[c_e] = detour

        # Compute exact expected recourse cost under independent edge marginal model
        expected_cost = self.compute_expected_cost(
            primary_path=primary_path,
            risky_edges=path_risky_edges,
            detours=detours,
            edge_marginals=edge_marginals,
        )

        return RecoursePlan(
            task_id=task_id,
            target_node=target_node,
            primary_path=primary_path,
            primary_cost=primary_cost,
            expected_cost=expected_cost,
            detours=detours,
            risky_edges=path_risky_edges,
            depth=self.max_depth,
        )

    def compute_expected_cost(
        self,
        primary_path: List[Any],
        risky_edges: List[Tuple[Any, Any]],
        detours: Dict[Tuple[Any, Any], List[Any]],
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """
        Theorem 1 Expected Recourse Cost:
        E[C] = sum_{k=1}^m [prod_{i < k} (1 - pi_i)] * pi_k * (c(l -> u_k) + c(D_k))
               + [prod_{i=1}^m (1 - pi_i)] * c(primary)
        Calculated over independent edge marginals for the depth-d policy.
        """
        if not risky_edges:
            return self.compute_path_length(primary_path)

        # Map node to distance from start along primary path
        cost_so_far = 0.0
        node_cum_dist = {primary_path[0]: 0.0}
        for i in range(len(primary_path) - 1):
            u, v = primary_path[i], primary_path[i + 1]
            cost_so_far += self.graph[u][v].get("weight", 1.0)
            node_cum_dist[v] = cost_so_far

        expected_val = 0.0
        prob_all_prior_clear = 1.0

        for edge_item in risky_edges:
            u, v = edge_item
            c_e = canonical_edge(u, v)
            # u is the upstream node from which detour originates
            dist_to_u = node_cum_dist.get(u, 0.0)
            pi_k = edge_marginals.get(c_e, edge_marginals.get(edge_item, 0.15))

            if edge_item in detours:
                branch_cost = dist_to_u + self.compute_path_length(detours[edge_item])
            elif c_e in detours:
                branch_cost = dist_to_u + self.compute_path_length(detours[c_e])
            else:
                branch_cost = dist_to_u + self.exhaustion_penalty

            expected_val += prob_all_prior_clear * pi_k * branch_cost
            prob_all_prior_clear *= (1.0 - pi_k)

        # Add nominal path cost under no blockages
        nominal_cost = self.compute_path_length(primary_path)
        expected_val += prob_all_prior_clear * nominal_cost

        return float(expected_val)


class ExpectedCostValuator:
    """Helper for evaluating bids for all fleet robots across tasks."""

    def __init__(self, planner: ContingencyPlanner):
        self.planner = planner

    def evaluate_task_bid(
        self,
        task_id: int,
        robot_node: Any,
        task_node: Any,
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> Tuple[float, Optional[RecoursePlan]]:
        plan = self.planner.build_recourse_plan(
            task_id=task_id,
            start_node=robot_node,
            target_node=task_node,
            edge_marginals=edge_marginals,
        )
        if plan is None:
            return float("inf"), None
        return plan.expected_cost, plan
