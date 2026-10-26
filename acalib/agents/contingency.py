"""
Contingency Planning and Exact Expected-Recourse Cost Valuation (Theorem 1 & Proposition 2).
Builds true recursive depth-d recourse trees and computes exact expected costs under adversary edge marginals.
Scope: exact under the independent-Bernoulli edge failure model.
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
import networkx as nx

from ..env.adversaries import canonical_edge


class MissingMarginalError(KeyError):
    """Raised when an edge marginal is required but missing from edge_marginals dictionary."""
    pass


def get_edge_marginal_strict(
    edge_marginals: Dict[Tuple[Any, Any], float],
    u: Any,
    v: Any,
) -> float:
    """
    Retrieve edge marginal with fail-closed semantics (no silent default fallback).
    Raises MissingMarginalError if neither (u, v), (v, u), nor canonical_edge is present.
    """
    c_e = canonical_edge(u, v)
    if c_e in edge_marginals:
        return float(edge_marginals[c_e])
    if (u, v) in edge_marginals:
        return float(edge_marginals[(u, v)])
    if (v, u) in edge_marginals:
        return float(edge_marginals[(v, u)])
    raise MissingMarginalError(f"Missing edge marginal for edge {c_e} between nodes {u} and {v}")


@dataclass
class RecourseTreeNode:
    node_id: str
    path: List[Any]
    cost: float
    risky_edges: List[Tuple[Any, Any]] = field(default_factory=list)
    detours: Dict[Tuple[Any, Any], "RecourseTreeNode"] = field(default_factory=dict)
    depth: int = 0
    branch_id: str = "root"
    is_leaf: bool = False
    is_recovery: bool = False
    recovery_cost: float = 0.0


@dataclass
class RecoursePlan:
    task_id: int
    target_node: Any
    primary_path: List[Any]
    primary_cost: float
    expected_cost: float
    # Detour mapping: edge (u, v) -> alternative path from u to target_node (flat lookup for execution compatibility)
    detours: Dict[Tuple[Any, Any], List[Any]] = field(default_factory=dict)
    risky_edges: List[Tuple[Any, Any]] = field(default_factory=list)
    depth: int = 1
    tree: Optional[RecourseTreeNode] = None
    plan_hash: str = ""


def compute_plan_hash(plan: RecoursePlan) -> str:
    """
    Deterministic SHA-256 digest of plan structure:
    primary path, primary cost, expected cost, and recursive tree nodes.
    """
    def serialize_node(node: RecourseTreeNode) -> Dict[str, Any]:
        return {
            "node_id": node.node_id,
            "branch_id": node.branch_id,
            "path": [str(x) for x in node.path],
            "cost": round(float(node.cost), 6),
            "risky_edges": [sorted([str(u), str(v)]) for u, v in node.risky_edges],
            "is_recovery": node.is_recovery,
            "detours": {
                f"{sorted([str(u), str(v)])[0]}_{sorted([str(u), str(v)])[1]}": serialize_node(child)
                for (u, v), child in sorted(
                    node.detours.items(),
                    key=lambda item: str(canonical_edge(item[0][0], item[0][1]))
                )
            },
        }

    tree_dict = serialize_node(plan.tree) if plan.tree is not None else {}
    summary = {
        "task_id": plan.task_id,
        "target_node": str(plan.target_node),
        "primary_path": [str(x) for x in plan.primary_path],
        "primary_cost": round(float(plan.primary_cost), 6),
        "expected_cost": round(float(plan.expected_cost), 6),
        "tree": tree_dict,
    }
    raw = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_marginals_token(edge_marginals: Dict[Tuple[Any, Any], float]) -> int:
    return hash(
        frozenset(
            (canonical_edge(u, v), round(float(prob), 12))
            for (u, v), prob in edge_marginals.items()
        )
    )


class ContingencyPlanner:
    """
    Plans primary paths and precomputed recursive depth-d recourse branches around risky edges.
    Scope: exact under the independent-Bernoulli edge failure model.
    """

    def __init__(
        self,
        graph: nx.Graph,
        max_depth: int = 1,
        exhaustion_penalty: float = 150.0,
        risk_weight: float = 2.0,
        max_deep_branches: Optional[int] = 2,
        prune_threshold: float = 0.0,
    ):
        self.graph = graph
        self.max_depth = max_depth
        self.exhaustion_penalty = exhaustion_penalty
        self.risk_weight = risk_weight
        self.max_deep_branches = max_deep_branches
        self.prune_threshold = prune_threshold
        self._path_cache: Dict[Tuple[Any, Any, Tuple[Tuple[Any, Any], ...], int], Optional[List[Any]]] = {}
        self._plan_cache: Dict[Tuple[int, Any, Any, int, int, float, Optional[int]], Optional[RecoursePlan]] = {}
        self._eff_weight_cache: Dict[int, Dict[Tuple[Any, Any], float]] = {}

    def clear_cache(self) -> None:
        """Clear internal shortest path and plan memoization caches."""
        self._path_cache.clear()
        self._plan_cache.clear()
        self._eff_weight_cache.clear()

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

        canon_key: Tuple[Tuple[Any, Any], ...] = ()
        excluded_lookup = None
        if excluded_edges:
            excluded_lookup = set()
            canon_list = []
            for u, v in excluded_edges:
                excluded_lookup.add((u, v))
                excluded_lookup.add((v, u))
                c_e = canonical_edge(u, v)
                excluded_lookup.add(c_e)
                canon_list.append(c_e)
            canon_key = tuple(sorted(list(set(canon_list))))

        m_token = get_marginals_token(edge_marginals)
        cache_key = (start_node, target_node, canon_key, m_token)
        if cache_key in self._path_cache:
            hit = self._path_cache[cache_key]
            return list(hit) if hit is not None else None

        eff_weights = self._eff_weight_cache.get(m_token)
        if eff_weights is None:
            eff_weights = {}
            risk_w = self.risk_weight
            for u, v, d in self.graph.edges(data=True):
                base_w = d.get("weight", 1.0)
                pi_e = get_edge_marginal_strict(edge_marginals, u, v)
                w = base_w * (1.0 + risk_w * pi_e)
                eff_weights[(u, v)] = w
                eff_weights[(v, u)] = w
            if len(self._eff_weight_cache) > 200:
                self._eff_weight_cache.clear()
            self._eff_weight_cache[m_token] = eff_weights

        if excluded_lookup is not None:
            def edge_weight_fn(u: Any, v: Any, d: Dict[str, Any]) -> Optional[float]:
                if (u, v) in excluded_lookup:
                    return None
                return eff_weights.get((u, v), 1.0)
        else:
            def edge_weight_fn(u: Any, v: Any, d: Dict[str, Any]) -> Optional[float]:
                return eff_weights.get((u, v), 1.0)

        try:
            path = nx.shortest_path(
                self.graph,
                source=start_node,
                target=target_node,
                weight=edge_weight_fn,
            )
            if len(self._path_cache) > 8000:
                self._path_cache.clear()
            self._path_cache[cache_key] = list(path)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            if len(self._path_cache) > 8000:
                self._path_cache.clear()
            self._path_cache[cache_key] = None
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
        branch_id: str = "root",
        max_deep_branches: Optional[int] = 2,
        nominal_cost: Optional[float] = None,
    ) -> Optional[RecourseTreeNode]:
        """
        Recursive helper constructing depth-d branching tree with stable node/branch IDs.
        """
        path = self.find_risk_aware_path(
            start_node,
            target_node,
            edge_marginals,
            excluded_edges=excluded_upstream,
        )
        if path is None:
            return None

        cost = self.compute_path_length(path)
        eff_nominal_cost = cost if nominal_cost is None else nominal_cost
        eff_exhaustion_penalty = max(float(self.exhaustion_penalty), 2.0 * float(eff_nominal_cost))
        node_id = f"node_{branch_id}_d{current_depth}"

        # Identify risky edges along this path (canonicalized)
        risky: List[Tuple[Any, Any]] = []
        detours: Dict[Tuple[Any, Any], RecourseTreeNode] = {}

        if current_depth < max_depth:
            seen_canon = set()
            candidate_risky = []
            for i in range(len(path) - 1):
                u_entry, v_exit = path[i], path[i + 1]
                c_e = canonical_edge(u_entry, v_exit)
                if c_e not in seen_canon:
                    seen_canon.add(c_e)
                    pi_val = get_edge_marginal_strict(edge_marginals, u_entry, v_exit)
                    eff_thresh = max(risky_edge_threshold, getattr(self, "prune_threshold", 0.0))
                    if pi_val >= eff_thresh:
                        candidate_risky.append((i, u_entry, v_exit, c_e, pi_val))

            if max_deep_branches is not None and current_depth >= 1:
                limit = max(1, int(max_deep_branches))
                sorted_by_prob = sorted(candidate_risky, key=lambda item: item[4], reverse=True)
                active_set = {item[3] for item in sorted_by_prob[:limit]}
            else:
                active_set = {item[3] for item in candidate_risky}

            for path_idx, u_entry, v_exit, c_e, pi_val in candidate_risky:
                risky.append(c_e)
                if c_e in active_set:
                    excluded_for_branch = set(excluded_upstream) | {c_e, (u_entry, v_exit), (v_exit, u_entry)}
                    child_branch_id = f"{branch_id}->({c_e[0]},{c_e[1]})"
                    child_start = u_entry
                    child_node = self._build_tree_recursive(
                        start_node=child_start,
                        target_node=target_node,
                        edge_marginals=edge_marginals,
                        current_depth=current_depth + 1,
                        max_depth=max_depth,
                        risky_edge_threshold=risky_edge_threshold,
                        excluded_upstream=excluded_for_branch,
                        branch_id=child_branch_id,
                        max_deep_branches=max_deep_branches,
                        nominal_cost=eff_nominal_cost,
                    )
                    if child_node is not None:
                        detours[c_e] = child_node
                    else:
                        # Explicit recovery leaf on path exhaustion
                        detours[c_e] = RecourseTreeNode(
                            node_id=f"recovery_{node_id}_{c_e}",
                            path=[],
                            cost=eff_exhaustion_penalty,
                            risky_edges=[],
                            detours={},
                            depth=current_depth + 1,
                            branch_id=f"{child_branch_id}_recovery",
                            is_leaf=True,
                            is_recovery=True,
                            recovery_cost=eff_exhaustion_penalty,
                        )
                else:
                    child_branch_id = f"{branch_id}->({c_e[0]},{c_e[1]})_tail"
                    detours[c_e] = RecourseTreeNode(
                        node_id=f"recovery_{node_id}_{c_e}",
                        path=[],
                        cost=eff_exhaustion_penalty,
                        risky_edges=[],
                        detours={},
                        depth=current_depth + 1,
                        branch_id=f"{child_branch_id}_recovery",
                        is_leaf=True,
                        is_recovery=True,
                        recovery_cost=eff_exhaustion_penalty,
                    )
        elif current_depth == 0 and max_depth == 0:
            seen_canon = set()
            for i in range(len(path) - 1):
                u_entry, v_exit = path[i], path[i + 1]
                c_e = canonical_edge(u_entry, v_exit)
                if c_e not in seen_canon:
                    seen_canon.add(c_e)
                    pi_val = get_edge_marginal_strict(edge_marginals, u_entry, v_exit)
                    eff_thresh = max(risky_edge_threshold, getattr(self, "prune_threshold", 0.0))
                    if pi_val >= eff_thresh:
                        risky.append(c_e)
                        child_branch_id = f"{branch_id}->({c_e[0]},{c_e[1]})_d0"
                        detours[c_e] = RecourseTreeNode(
                            node_id=f"recovery_{node_id}_{c_e}",
                            path=[],
                            cost=eff_exhaustion_penalty,
                            risky_edges=[],
                            detours={},
                            depth=1,
                            branch_id=f"{child_branch_id}_recovery",
                            is_leaf=True,
                            is_recovery=True,
                            recovery_cost=eff_exhaustion_penalty,
                        )

        return RecourseTreeNode(
            node_id=node_id,
            path=path,
            cost=cost,
            risky_edges=risky,
            detours=detours,
            depth=current_depth,
            branch_id=branch_id,
            is_leaf=(len(detours) == 0),
        )

    def _collect_flat_detours(
        self,
        node: RecourseTreeNode,
        flat_dict: Dict[Tuple[Any, Any], List[Any]],
        all_risky: List[Tuple[Any, Any]],
    ) -> None:
        """Flatten recursive detours and risky edges into single execution dictionary (read-only view)."""
        for e in node.risky_edges:
            c_e = canonical_edge(e[0], e[1])
            if c_e not in all_risky:
                all_risky.append(c_e)
        for c_e, child in node.detours.items():
            if not child.is_recovery and child.path:
                flat_dict[c_e] = list(child.path)
                flat_dict[(c_e[0], c_e[1])] = list(child.path)
                flat_dict[(c_e[1], c_e[0])] = list(child.path)
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
        Scope: exact under the independent-Bernoulli edge failure model with fixed edge marginals.
        Fails closed with MissingMarginalError if any required edge marginal is missing.
        """
        if node.is_recovery or not node.path:
            return float(node.recovery_cost if node.recovery_cost > 0 else self.exhaustion_penalty)

        if not node.risky_edges:
            return float(node.cost)

        edge_prefix_dist: Dict[Tuple[Any, Any], float] = {}
        edge_order: Dict[Tuple[Any, Any], int] = {}
        cost_so_far = 0.0
        for i in range(len(node.path) - 1):
            u_p, v_p = node.path[i], node.path[i + 1]
            c_e = canonical_edge(u_p, v_p)
            if c_e not in edge_prefix_dist:
                edge_prefix_dist[c_e] = cost_so_far
                edge_order[c_e] = i
            cost_so_far += self.graph[u_p][v_p].get("weight", 1.0)

        # Deduplicate and sort node.risky_edges by traversal order along node.path
        seen_edges = set()
        ordered_risky = []
        for edge_item in node.risky_edges:
            c_e = canonical_edge(*edge_item)
            if c_e not in seen_edges:
                seen_edges.add(c_e)
                ordered_risky.append(c_e)
        ordered_risky.sort(key=lambda c_e: edge_order.get(c_e, float("inf")))

        expected_val = 0.0
        prob_all_prior_clear = 1.0

        for c_e in ordered_risky:
            u, v = c_e
            dist_to_u = edge_prefix_dist.get(c_e, 0.0)
            pi_k = get_edge_marginal_strict(edge_marginals, u, v)

            child_node = node.detours.get(c_e, node.detours.get((u, v), node.detours.get((v, u))))
            if child_node is not None and not child_node.is_recovery and child_node.path:
                child_cost = self.compute_tree_expected_cost(child_node, edge_marginals)
                branch_cost = dist_to_u + child_cost
            elif child_node is not None and child_node.is_recovery:
                branch_cost = dist_to_u + child_node.recovery_cost
            else:
                branch_cost = dist_to_u + max(float(self.exhaustion_penalty), 2.0 * float(node.cost))

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
        risky_edge_threshold: float = 0.35,
        max_deep_branches: Optional[int] = -1,
    ) -> Optional[RecoursePlan]:
        """
        Construct primary path and depth-d recursive recourse detours for identified risky edges.
        """
        eff_deep_branches = self.max_deep_branches if max_deep_branches == -1 else max_deep_branches
        m_token = get_marginals_token(edge_marginals)
        cache_key = (task_id, start_node, target_node, m_token, self.max_depth, risky_edge_threshold, eff_deep_branches)
        if hasattr(self, "_plan_cache") and cache_key in self._plan_cache:
            return self._plan_cache[cache_key]

        tree_root = self._build_tree_recursive(
            start_node=start_node,
            target_node=target_node,
            edge_marginals=edge_marginals,
            current_depth=0,
            max_depth=self.max_depth,
            risky_edge_threshold=risky_edge_threshold,
            excluded_upstream=set(),
            branch_id="root",
            max_deep_branches=eff_deep_branches,
        )
        if tree_root is None:
            if hasattr(self, "_plan_cache"):
                self._plan_cache[cache_key] = None
            return None

        primary_path = tree_root.path
        primary_cost = tree_root.cost

        # Flatten detours for backward-compatible read-only views
        flat_detours: Dict[Tuple[Any, Any], List[Any]] = {}
        all_risky: List[Tuple[Any, Any]] = []
        self._collect_flat_detours(tree_root, flat_detours, all_risky)

        expected_cost = self.compute_tree_expected_cost(tree_root, edge_marginals)

        plan = RecoursePlan(
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
        plan.plan_hash = compute_plan_hash(plan)
        if hasattr(self, "_plan_cache"):
            if len(self._plan_cache) > 2000:
                self._plan_cache.clear()
            self._plan_cache[cache_key] = plan
        return plan

    def compute_expected_cost(
        self,
        primary_path: List[Any],
        risky_edges: List[Tuple[Any, Any]],
        detours: Dict[Tuple[Any, Any], List[Any]],
        edge_marginals: Dict[Tuple[Any, Any], float],
    ) -> float:
        """Backward-compatible flat expected recourse cost with fail-closed marginal lookup."""
        if not risky_edges or not primary_path:
            return self.compute_path_length(primary_path)

        edge_prefix_dist: Dict[Tuple[Any, Any], float] = {}
        edge_order: Dict[Tuple[Any, Any], int] = {}
        cost_so_far = 0.0
        for i in range(len(primary_path) - 1):
            u_p, v_p = primary_path[i], primary_path[i + 1]
            c_e = canonical_edge(u_p, v_p)
            if c_e not in edge_prefix_dist:
                edge_prefix_dist[c_e] = cost_so_far
                edge_order[c_e] = i
            cost_so_far += self.graph[u_p][v_p].get("weight", 1.0)

        seen_edges = set()
        ordered_risky = []
        for edge_item in risky_edges:
            c_e = canonical_edge(*edge_item)
            if c_e not in seen_edges:
                seen_edges.add(c_e)
                ordered_risky.append(c_e)
        ordered_risky.sort(key=lambda c_e: edge_order.get(c_e, float("inf")))

        expected_val = 0.0
        prob_all_prior_clear = 1.0

        for c_e in ordered_risky:
            u, v = c_e
            dist_to_u = edge_prefix_dist.get(c_e, 0.0)
            pi_k = get_edge_marginal_strict(edge_marginals, u, v)

            if c_e in detours:
                branch_cost = dist_to_u + self.compute_path_length(detours[c_e])
            elif (u, v) in detours:
                branch_cost = dist_to_u + self.compute_path_length(detours[(u, v)])
            elif (v, u) in detours:
                branch_cost = dist_to_u + self.compute_path_length(detours[(v, u)])
            else:
                eff_pen = max(float(self.exhaustion_penalty), 2.0 * float(self.compute_path_length(primary_path)))
                branch_cost = dist_to_u + eff_pen

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
    exhaustion_penalty: float = 150.0,
) -> RecourseTreeNode:
    """
    Recursively prune recourse branches beneath prune_threshold.
    Pruning semantics (P0-4):
    - A pruned edge REMAINS in risky_edges (its failure probability is NOT erased).
    - Its precomputed detour branch is replaced by an explicit recovery leaf node with exhaustion cost.
    - If edge marginal >= prune_threshold, the detour is preserved and its children recursively pruned.
    Fails closed with MissingMarginalError if any required edge marginal is missing.
    """
    if node.is_recovery or not node.path:
        return node

    pruned_detours = {}
    for e in node.risky_edges:
        c_e = canonical_edge(e[0], e[1])
        pi_val = get_edge_marginal_strict(edge_marginals, e[0], e[1])

        child = node.detours.get(c_e, node.detours.get(e))
        if pi_val >= prune_threshold and child is not None and not child.is_recovery:
            # Preserve detour and prune deeper children
            pruned_child = prune_recourse_tree(child, prune_threshold, edge_marginals, exhaustion_penalty)
            pruned_detours[c_e] = pruned_child
        else:
            # Prune detour: replace with explicit recovery leaf with exhaustion cost
            pruned_detours[c_e] = RecourseTreeNode(
                node_id=f"pruned_recovery_{node.node_id}_{c_e}",
                path=[],
                cost=exhaustion_penalty,
                risky_edges=[],
                detours={},
                depth=node.depth + 1,
                branch_id=f"{node.branch_id}->pruned_({c_e[0]},{c_e[1]})",
                is_leaf=True,
                is_recovery=True,
                recovery_cost=exhaustion_penalty,
            )

    return RecourseTreeNode(
        node_id=f"pruned_{node.node_id}",
        path=node.path,
        cost=node.cost,
        risky_edges=list(node.risky_edges),
        detours=pruned_detours,
        depth=node.depth,
        branch_id=node.branch_id,
        is_leaf=(len(pruned_detours) == 0),
    )


def prune_recourse_plan(
    recourse_plan: RecoursePlan,
    prune_threshold: float,
    planner: ContingencyPlanner,
    edge_marginals: Dict[Tuple[Any, Any], float],
) -> RecoursePlan:
    """
    Prune recourse plan detours whose edge marginals fall below prune_threshold.
    Returns new immutable RecoursePlan with matching updated expected_cost and plan_hash.
    """
    if recourse_plan.tree is None or prune_threshold <= 0.0:
        return recourse_plan

    pruned_tree = prune_recourse_tree(
        recourse_plan.tree,
        prune_threshold,
        edge_marginals,
        exhaustion_penalty=planner.exhaustion_penalty,
    )
    flat_detours: Dict[Tuple[Any, Any], List[Any]] = {}
    all_risky: List[Tuple[Any, Any]] = []
    planner._collect_flat_detours(pruned_tree, flat_detours, all_risky)
    expected_cost = planner.compute_tree_expected_cost(pruned_tree, edge_marginals)

    new_plan = RecoursePlan(
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
    new_plan.plan_hash = compute_plan_hash(new_plan)
    return new_plan


def _collect_leaf_costs(
    node: RecourseTreeNode,
    planner: ContingencyPlanner,
    prefix_cost: float,
    leaf_costs: List[float],
) -> None:
    if node.is_recovery or not node.path:
        # Invariant: recovery leaf nodes explicitly store exhaustion penalty in recovery_cost upon construction
        rec_val = getattr(node, "recovery_cost", 0.0)
        eff_rec = float(rec_val) if rec_val > 0.0 else float(planner.exhaustion_penalty)
        leaf_costs.append(prefix_cost + eff_rec)
        return

    # Leaf 1: All risky edges on this node's path are clear
    nominal_path_cost = prefix_cost + node.cost
    leaf_costs.append(nominal_path_cost)

    dist_to_u = 0.0
    for i in range(len(node.path) - 1):
        u, v = node.path[i], node.path[i + 1]
        c_e = canonical_edge(u, v)

        # If this edge is risky, it branches to detour or recovery
        if c_e in node.detours or (u, v) in node.detours:
            child = node.detours.get(c_e, node.detours.get((u, v)))
            if child is not None and not child.is_recovery and child.path:
                _collect_leaf_costs(child, planner, prefix_cost + dist_to_u, leaf_costs)
            else:
                eff_rec = child.recovery_cost if child and getattr(child, "recovery_cost", 0.0) > 0 else max(float(planner.exhaustion_penalty), 2.0 * float(node.cost))
                leaf_costs.append(prefix_cost + dist_to_u + eff_rec)
        elif c_e in node.risky_edges or (u, v) in node.risky_edges:
            eff_rec = max(float(planner.exhaustion_penalty), 2.0 * float(node.cost))
            leaf_costs.append(prefix_cost + dist_to_u + eff_rec)

        dist_to_u += planner.graph[u][v].get("weight", 1.0)


def _collect_tree_risky_edges(
    node: RecourseTreeNode,
    result: List[Tuple[Any, Any]],
    graph: Optional[Any] = None,
) -> None:
    for e in node.risky_edges:
        c_e = canonical_edge(e[0], e[1])
        if c_e not in result:
            result.append(c_e)
    if node.path and len(node.path) > 1 and graph is not None:
        from ..env.adversaries import get_edge_vulnerability_class
        for i in range(len(node.path) - 1):
            c_e = canonical_edge(node.path[i], node.path[i + 1])
            if get_edge_vulnerability_class(graph, c_e) in (1, 2, 3) and c_e not in result:
                result.append(c_e)
    for child in node.detours.values():
        if not child.is_recovery:
            _collect_tree_risky_edges(child, result, graph)


def compute_lipschitz_bound(
    planner: ContingencyPlanner,
    recourse_plan: Optional[RecoursePlan],
    hazards_by_type: Dict[Tuple[Any, Any], List[float]],
    clearance_rate: float = 0.15,
    partition_mode: bool = False,
) -> float:
    """
    Proposition 2 Tight Path-Contrast Lipschitz Bound on Tree Recourse Bids:
        |E_B[C(T)] - E_{B'}[C(T)]| <= L_{r, j} * TV(B, B')
    where L_{r, j} = sum_{k=1}^K |c(u_0 -> u_k) + c(D_k) - c(P_j)| * Delta_pi(e_k)
    derived from the actual recourse cost difference |c_{detour,k} - c_{primary}|
    rather than a loose worst-case global tree bound C_max - C_min.
    Raises ValueError on missing hazard terms. Returns 0.0 if no risky edges.
    """
    if recourse_plan is None or not recourse_plan.primary_path:
        return 0.0

    tree_risky_edges: List[Tuple[Any, Any]] = []
    if recourse_plan.tree is not None:
        _collect_tree_risky_edges(recourse_plan.tree, tree_risky_edges, planner.graph)
    else:
        for e in (recourse_plan.risky_edges or []):
            c_e = canonical_edge(e[0], e[1])
            if c_e not in tree_risky_edges:
                tree_risky_edges.append(c_e)

    # Ensure any risky edge along primary_path is in tree_risky_edges
    p_path = recourse_plan.primary_path or []
    for i in range(len(p_path) - 1):
        c_e = canonical_edge(p_path[i], p_path[i + 1])
        if c_e in hazards_by_type and c_e not in tree_risky_edges:
            tree_risky_edges.append(c_e)

    if not tree_risky_edges:
        return 0.0

    if not hazards_by_type:
        raise ValueError("Missing hazard terms dictionary for risky edges!")

    # Verify all hazard terms exist and compute Delta_pi(e)
    edge_spread: Dict[Tuple[Any, Any], float] = {}
    total_spread = 0.0
    for e in tree_risky_edges:
        c_e = canonical_edge(e[0], e[1])
        h_list = hazards_by_type.get(c_e, hazards_by_type.get(e))
        if not h_list:
            raise ValueError(f"Missing hazard term for risky edge {c_e} in recourse plan!")
        if partition_mode or any(h in (0.75, 0.03) for h in h_list):
            delta_pi = 0.72  # Exact partitioned marginal spread: p_target(0.75) - p_bg(0.03) = 0.72
        else:
            probs = [h / max(1e-5, h + clearance_rate) for h in h_list]
            delta_pi = max(probs) - min(probs)
        edge_spread[c_e] = delta_pi
        total_spread += delta_pi

    if total_spread <= 0.0:
        return 0.0

    # Primary path baseline cost
    primary_cost = float(recourse_plan.primary_cost)
    eff_pen = max(float(planner.exhaustion_penalty), 2.0 * primary_cost)

    # Compute prefix costs along primary path
    p_path = recourse_plan.primary_path
    prefix_map: Dict[Any, float] = {}
    cum_cost = 0.0
    prefix_map[p_path[0]] = 0.0
    for i in range(len(p_path) - 1):
        u_node, v_node = p_path[i], p_path[i + 1]
        w = planner.graph[u_node][v_node].get("weight", 1.0)
        cum_cost += w
        prefix_map[v_node] = cum_cost

    # Helper to recursively collect path contrasts: M_k * Delta_pi(e_k) where M_k = max_{m >= k} Delta C_m
    def _collect_tree_contrasts(node: RecourseTreeNode, prefix_cost: float) -> float:
        contr = 0.0
        if node.is_recovery or not node.path:
            return 0.0

        dist_to_u = 0.0
        edge_data: List[Tuple[float, float, Optional[RecourseTreeNode], float]] = []
        for i in range(len(node.path) - 1):
            u_node, v_node = node.path[i], node.path[i + 1]
            c_edge = canonical_edge(u_node, v_node)
            w_edge = planner.graph[u_node][v_node].get("weight", 1.0)
            branch_prefix = prefix_cost + dist_to_u

            if c_edge in edge_spread:
                d_pi = edge_spread[c_edge]
                child = node.detours.get(c_edge, node.detours.get((u_node, v_node)))
                if child is not None:
                    leaves: List[float] = []
                    _collect_leaf_costs(child, planner, branch_prefix, leaves)
                    delta_c = max((abs(lf - primary_cost) for lf in leaves), default=eff_pen)
                    edge_data.append((delta_c, d_pi, child, branch_prefix))
                else:
                    c_branch = branch_prefix + eff_pen
                    delta_c = abs(c_branch - primary_cost)
                    edge_data.append((delta_c, d_pi, None, branch_prefix))

            dist_to_u += w_edge

        # Proposition 2: Apply backward recursion telescoping bound M_k = max_{m >= k} Delta C_m
        for k, (delta_c, d_pi, child, branch_prefix) in enumerate(edge_data):
            M_k = max(item[0] for item in edge_data[k:])
            contr += M_k * d_pi
            if child is not None:
                # Recurse into child detour branch for deeper nested risky edges
                contr += _collect_tree_contrasts(child, branch_prefix)

        return contr

    if recourse_plan.tree is not None:
        L_contrast = _collect_tree_contrasts(recourse_plan.tree, 0.0)
    else:
        seq_items: List[Tuple[float, float]] = []
        for e in tree_risky_edges:
            c_e = canonical_edge(e[0], e[1])
            delta_pi = edge_spread.get(c_e, 0.0)
            if delta_pi <= 0.0:
                continue
            u, v = e
            idx_u = p_path.index(u) if u in p_path else 9999
            idx_v = p_path.index(v) if v in p_path else 9999
            if idx_u < idx_v and u in prefix_map:
                c_prefix = prefix_map[u]
            elif v in prefix_map:
                c_prefix = prefix_map[v]
            else:
                c_prefix = 0.0

            detour = recourse_plan.detours.get(c_e, recourse_plan.detours.get((u, v)))
            if detour:
                if isinstance(detour, list):
                    c_detour = planner.compute_path_length(detour)
                elif hasattr(detour, "cost"):
                    c_detour = float(detour.cost)
                else:
                    c_detour = eff_pen
                c_branch = c_prefix + c_detour
            else:
                c_branch = c_prefix + eff_pen

            delta_c = abs(c_branch - primary_cost)
            seq_items.append((delta_c, delta_pi))

        L_contrast = 0.0
        for k in range(len(seq_items)):
            M_k = max(item[0] for item in seq_items[k:])
            L_contrast += M_k * seq_items[k][1]

    if L_contrast > 0.0:
        return float(L_contrast)

    # Fallback to tree outcome range if path contrast was zero
    leaf_costs: List[float] = []
    if recourse_plan.tree is not None:
        _collect_leaf_costs(recourse_plan.tree, planner, 0.0, leaf_costs)
    else:
        leaf_costs.append(primary_cost)
        for e in recourse_plan.risky_edges:
            detour = recourse_plan.detours.get(e, recourse_plan.detours.get(canonical_edge(e[0], e[1])))
            if detour:
                leaf_costs.append(planner.compute_path_length(detour))
            else:
                leaf_costs.append(primary_cost + eff_pen)

    c_max = max(leaf_costs)
    c_min = min(leaf_costs)
    outcome_range = max(0.0, c_max - c_min)
    return float(outcome_range * total_spread)
