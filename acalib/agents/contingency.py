"""
Contingency Planning and Exact Expected-Recourse Cost Valuation (Theorem 1 & Proposition 2).
Builds true recursive depth-d recourse trees and computes exact expected costs under adversary edge marginals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
import networkx as nx

from ..env.adversaries import canonical_edge


@dataclass
class RecourseTreeNode:
    path: List[Any]
    cost: float
    risky_edges: List[Tuple[Any, Any]] = field(default_factory=list)
    detours: Dict[Tuple[Any, Any], "RecourseTreeNode"] = field(default_factory=dict)
    depth: int = 0


@dataclass
class RecoursePlan:
    task_id: int
    target_node: Any
    primary_path: List[Any]
    primary_cost: float
    expected_cost: float
    # Detour mapping: edge (u, v) -> alternative path from u to target_node (flat lookup for execution)
    detours: Dict[Tuple[Any, Any], List[Any]] = field(default_factory=dict)
    risky_edges: List[Tuple[Any, Any]] = field(default_factory=list)
    depth: int = 1
    tree: Optional[RecourseTreeNode] = None


class ContingencyPlanner:
    """
    Plans primary paths and precomputed recursive depth-d recourse branches around risky edges.
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
        Returns None if no path exists avoiding excluded_edges (never traverses excluded edges).
        """
        if start_node == target_node:
            return [start_node]

        # Use subgraph view or filtered copy excluding impassable edges
        if excluded_edges:
            excluded_canon = {canonical_edge(u, v) if not (isinstance(u, int) and isinstance(v, int) and u <= v) else (u, v) for u, v in excluded_edges}
            # Add reverse for undirected lookup
            excluded_canon.update({(v, u) for u, v in list(excluded_canon)})
            
            def edge_filter(u: Any, v: Any) -> bool:
                c_e = canonical_edge(u, v)
                return (u, v) not in excluded_canon and c_e not in excluded_canon
            
            sub_g = nx.subgraph_view(self.graph, filter_edge=edge_filter)
        else:
            sub_g = self.graph

        def edge_weight_fn(u: Any, v: Any, d: Dict[str, Any]) -> float:
            c_e = canonical_edge(u, v)
            base_w = d.get("weight", 1.0)
            pi_e = edge_marginals.get(c_e, edge_marginals.get((u, v), 0.05))
            return base_w * (1.0 + self.risk_weight * pi_e)

        try:
            path = nx.shortest_path(
                sub_g,
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

    def _build_tree_recursive(
        self,
        start_node: Any,
        target_node: Any,
        edge_marginals: Dict[Tuple[Any, Any], float],
        current_depth: int,
        max_depth: int,
        risky_edge_threshold: float,
        excluded_upstream: Set[Tuple[Any, Any]],
    ) -> Optional[RecourseTreeNode]:
        """Recursive helper constructing depth-d branching tree."""
        path = self.find_risk_aware_path(
            start_node,
            target_node,
            edge_marginals,
            excluded_edges=excluded_upstream,
        )
        if path is None:
            return None

        cost = self.compute_path_length(path)

        # Identify risky edges along this path (only if recursion depth allows recourse)
        risky: List[Tuple[Any, Any]] = []
        detours: Dict[Tuple[Any, Any], RecourseTreeNode] = {}

        if current_depth < max_depth:
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                c_e = canonical_edge(u, v)
                if edge_marginals.get(c_e, edge_marginals.get((u, v), 0.0)) >= risky_edge_threshold:
                    risky.append((u, v))

            for u, v in risky:
                c_e = canonical_edge(u, v)
                excluded_for_branch = set(excluded_upstream) | {c_e, (u, v)}
                child_node = self._build_tree_recursive(
                    start_node=u,
                    target_node=target_node,
                    edge_marginals=edge_marginals,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    risky_edge_threshold=risky_edge_threshold,
                    excluded_upstream=excluded_for_branch,
                )
                if child_node is not None:
                    detours[(u, v)] = child_node
                    detours[c_e] = child_node

        return RecourseTreeNode(
            path=path,
            cost=cost,
            risky_edges=risky,
            detours=detours,
            depth=current_depth,
        )

    def _collect_flat_detours(
        self,
        node: RecourseTreeNode,
        flat_dict: Dict[Tuple[Any, Any], List[Any]],
        all_risky: List[Tuple[Any, Any]],
    ) -> None:
        """Flatten recursive detours and risky edges into single execution dictionary."""
        for e in node.risky_edges:
            if e not in all_risky:
                all_risky.append(e)
        for e, child in node.detours.items():
            flat_dict[e] = list(child.path)
            c_e = canonical_edge(e[0], e[1])
            flat_dict[c_e] = list(child.path)
            self._collect_flat_detours(child, flat_dict, all_risky)

    def compute_tree_expected_cost(
        self,
        node: RecourseTreeNode,
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """
        Exact recursive expected cost calculation:
        E[C] = sum_{k=1}^m [prod_{i < k} (1 - pi_i)] * pi_k * (c(u_0 -> u_k) + E[Cost(D_k)])
               + [prod_{i=1}^m (1 - pi_i)] * c(primary)
        """
        if not node.risky_edges:
            return node.cost

        cost_so_far = 0.0
        node_cum_dist = {node.path[0]: 0.0}
        for i in range(len(node.path) - 1):
            u, v = node.path[i], node.path[i + 1]
            cost_so_far += self.graph[u][v].get("weight", 1.0)
            node_cum_dist[v] = cost_so_far

        expected_val = 0.0
        prob_all_prior_clear = 1.0

        for edge_item in node.risky_edges:
            u, v = edge_item
            c_e = canonical_edge(u, v)
            dist_to_u = node_cum_dist.get(u, 0.0)
            pi_k = edge_marginals.get(c_e, edge_marginals.get(edge_item, 0.15))

            child_node = node.detours.get(edge_item, node.detours.get(c_e))
            if child_node is not None:
                child_cost = self.compute_tree_expected_cost(child_node, edge_marginals)
                branch_cost = dist_to_u + child_cost
            else:
                branch_cost = dist_to_u + self.exhaustion_penalty

            expected_val += prob_all_prior_clear * pi_k * branch_cost
            prob_all_prior_clear *= (1.0 - pi_k)

        nominal_cost = node.cost
        expected_val += prob_all_prior_clear * nominal_cost
        return float(expected_val)

    def compute_expected_cost_for_plan(
        self,
        recourse_plan: RecoursePlan,
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """Compute expected cost for a pre-built plan under given edge marginals."""
        if recourse_plan.tree is not None:
            return self.compute_tree_expected_cost(recourse_plan.tree, edge_marginals)
        return self.compute_expected_cost(
            primary_path=recourse_plan.primary_path,
            risky_edges=recourse_plan.risky_edges,
            detours=recourse_plan.detours,
            edge_marginals=edge_marginals,
        )

    def build_recourse_plan(
        self,
        task_id: int,
        start_node: Any,
        target_node: Any,
        edge_marginals: Dict[Tuple[Any, Any], float],
        risky_edge_threshold: float = 0.12,
    ) -> Optional[RecoursePlan]:
        """
        Construct primary path and depth-d recursive recourse detours for identified risky edges.
        """
        tree_root = self._build_tree_recursive(
            start_node=start_node,
            target_node=target_node,
            edge_marginals=edge_marginals,
            current_depth=0,
            max_depth=self.max_depth,
            risky_edge_threshold=risky_edge_threshold,
            excluded_upstream=set(),
        )
        if tree_root is None:
            return None

        primary_path = tree_root.path
        primary_cost = tree_root.cost

        # Flatten detours and collect all risky edges
        flat_detours: Dict[Tuple[Any, Any], List[Any]] = {}
        all_risky: List[Tuple[Any, Any]] = []
        self._collect_flat_detours(tree_root, flat_detours, all_risky)

        expected_cost = self.compute_tree_expected_cost(tree_root, edge_marginals)

        return RecoursePlan(
            task_id=task_id,
            target_node=target_node,
            primary_path=primary_path,
            primary_cost=primary_cost,
            expected_cost=expected_cost,
            detours=flat_detours,
            risky_edges=list(tree_root.risky_edges),
            depth=self.max_depth,
            tree=tree_root,
        )

    def compute_expected_cost(
        self,
        primary_path: List[Any],
        risky_edges: List[Tuple[Any, Any]],
        detours: Dict[Tuple[Any, Any], List[Any]],
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """Backward-compatible flat 1-level expected recourse cost."""
        if not risky_edges:
            return self.compute_path_length(primary_path)

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


def prune_recourse_tree(
    node: RecourseTreeNode,
    prune_threshold: float,
    edge_marginals: Dict[Tuple[Any, Any], float],
) -> RecourseTreeNode:
    """Recursively prune risky edges and their detours if marginal is below prune_threshold."""
    pruned_risky = []
    pruned_detours = {}
    for e in node.risky_edges:
        c_e = canonical_edge(e[0], e[1])
        if edge_marginals.get(c_e, edge_marginals.get(e, 0.0)) >= prune_threshold:
            pruned_risky.append(e)
            if e in node.detours or c_e in node.detours:
                child = node.detours.get(e, node.detours.get(c_e))
                if child is not None:
                    pruned_child = prune_recourse_tree(child, prune_threshold, edge_marginals)
                    pruned_detours[e] = pruned_child
                    pruned_detours[c_e] = pruned_child
    return RecourseTreeNode(
        path=node.path,
        cost=node.cost,
        risky_edges=pruned_risky,
        detours=pruned_detours,
        depth=node.depth,
    )


def prune_recourse_plan(
    recourse_plan: RecoursePlan,
    prune_threshold: float,
    planner: ContingencyPlanner,
    edge_marginals: Dict[Tuple[Any, Any], float],
) -> RecoursePlan:
    """Prune recourse plan detours whose edge marginals fall below prune_threshold."""
    if recourse_plan.tree is None or prune_threshold <= 0.0:
        return recourse_plan

    pruned_tree = prune_recourse_tree(recourse_plan.tree, prune_threshold, edge_marginals)
    flat_detours: Dict[Tuple[Any, Any], List[Any]] = {}
    all_risky: List[Tuple[Any, Any]] = []
    planner._collect_flat_detours(pruned_tree, flat_detours, all_risky)
    expected_cost = planner.compute_tree_expected_cost(pruned_tree, edge_marginals)

    return RecoursePlan(
        task_id=recourse_plan.task_id,
        target_node=recourse_plan.target_node,
        primary_path=recourse_plan.primary_path,
        primary_cost=recourse_plan.primary_cost,
        expected_cost=expected_cost,
        detours=flat_detours,
        risky_edges=list(pruned_tree.risky_edges),
        depth=recourse_plan.depth,
        tree=pruned_tree,
    )


def _collect_leaf_costs(
    node: RecourseTreeNode,
    planner: ContingencyPlanner,
    prefix_cost: float,
    leaf_costs: List[float],
) -> None:
    """Collect all terminal realized path costs along tree branches."""
    # Leaf 1: All risky edges on this node's path are clear
    nominal_path_cost = prefix_cost + node.cost
    leaf_costs.append(nominal_path_cost)

    dist_to_u = 0.0
    for i in range(len(node.path) - 1):
        u, v = node.path[i], node.path[i + 1]
        c_e = canonical_edge(u, v)

        # If this edge is risky, it can branch to detour or exhaustion
        if (u, v) in node.detours or c_e in node.detours:
            child = node.detours.get((u, v), node.detours.get(c_e))
            if child is not None:
                _collect_leaf_costs(child, planner, prefix_cost + dist_to_u, leaf_costs)
        elif (u, v) in node.risky_edges or c_e in node.risky_edges:
            # Recourse exhausted at this risky edge
            leaf_costs.append(prefix_cost + dist_to_u + planner.exhaustion_penalty)

        dist_to_u += planner.graph[u][v].get("weight", 1.0)


def _collect_tree_risky_edges(node: RecourseTreeNode, result: List[Tuple[Any, Any]]) -> None:
    for e in node.risky_edges:
        c_e = canonical_edge(e[0], e[1])
        if c_e not in result:
            result.append(c_e)
    for child in node.detours.values():
        _collect_tree_risky_edges(child, result)


def compute_lipschitz_bound(
    planner: ContingencyPlanner,
    recourse_plan: Optional[RecoursePlan],
    hazards_by_type: Dict[Tuple[Any, Any], List[float]],
    clearance_rate: float = 0.15,
) -> float:
    """
    Proposition 2 Analytical Lipschitz Upper Bound on Tree Recourse Bids:
        |E_B[C(T)] - E_{B'}[C(T)]| <= L_j * TV(B, B')
    where L_j = (C_max(T) - C_min(T)) * sum_{e in risky} Delta_pi(e).
    Derived via multivariable mean value theorem on the recursive branching tree.
    Raises ValueError on missing hazard terms. Returns 0.0 if no risky edges.
    """
    if recourse_plan is None or not recourse_plan.primary_path:
        return 0.0

    tree_risky_edges: List[Tuple[Any, Any]] = []
    if recourse_plan.tree is not None:
        _collect_tree_risky_edges(recourse_plan.tree, tree_risky_edges)
    else:
        for e in (recourse_plan.risky_edges or []):
            c_e = canonical_edge(e[0], e[1])
            if c_e not in tree_risky_edges:
                tree_risky_edges.append(c_e)

    if not tree_risky_edges:
        return 0.0

    if not hazards_by_type:
        raise ValueError("Missing hazard terms dictionary for risky edges!")

    # Verify that every risky edge has an entry in hazards_by_type
    total_spread = 0.0
    for e in tree_risky_edges:
        c_e = canonical_edge(e[0], e[1])
        h_list = hazards_by_type.get(c_e, hazards_by_type.get(e))
        if not h_list:
            raise ValueError(f"Missing hazard term for risky edge {c_e} in recourse plan!")
        probs = [h / max(1e-5, h + clearance_rate) for h in h_list]
        delta_pi = max(probs) - min(probs)
        total_spread += delta_pi

    if total_spread <= 0.0:
        return 0.0

    # Collect leaf realized costs across the tree
    leaf_costs: List[float] = []
    if recourse_plan.tree is not None:
        _collect_leaf_costs(recourse_plan.tree, planner, 0.0, leaf_costs)
    else:
        leaf_costs.append(recourse_plan.primary_cost)
        for e in recourse_plan.risky_edges:
            detour = recourse_plan.detours.get(e, recourse_plan.detours.get(canonical_edge(e[0], e[1])))
            if detour:
                leaf_costs.append(planner.compute_path_length(detour))
            else:
                leaf_costs.append(recourse_plan.primary_cost + planner.exhaustion_penalty)

    c_max = max(leaf_costs)
    c_min = min(leaf_costs)
    outcome_range = max(0.0, c_max - c_min)

    L = outcome_range * total_spread
    return float(L)
