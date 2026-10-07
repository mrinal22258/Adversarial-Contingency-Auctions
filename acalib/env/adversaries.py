"""
Adversary models for strategic and stochastic edge interdiction:
- theta_1: Stochastic (constant onset hazard p_0)
- theta_2: Reactive (traffic-dependent onset hazard p_0 + alpha * N_e)
- theta_3: Budgeted Interdiction / Minimax (periodically cuts k edges maximizing fleet shortest-path increase)
- theta_4: Cyclic Patrol (out-of-model adversary cycling blockages along key bottlenecks)
"""

from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any
import numpy as np
import networkx as nx


class AdversaryType(str, Enum):
    STOCHASTIC = "theta_1_stochastic"
    REACTIVE = "theta_2_reactive"
    BUDGETED_INTERDICTION = "theta_3_budgeted_interdiction"
    CYCLIC_PATROL = "theta_4_cyclic_patrol"
    REAL_TRACE_REPLAY = "theta_5_real_trace_replay"


CanonicalTypeSet = [
    AdversaryType.STOCHASTIC,
    AdversaryType.REACTIVE,
    AdversaryType.BUDGETED_INTERDICTION,
]


def canonical_edge(u: Any, v: Any) -> Tuple[Any, Any]:
    """Return ordered edge tuple (min(u, v), max(u, v)) for undirected graphs."""
    return (u, v) if str(u) <= str(v) else (v, u)


class Adversary:
    """Base adversary interface."""

    def __init__(self, adv_type: AdversaryType, budget_k: int = 4, clearance_rate: float = 0.15):
        self.adv_type = adv_type
        self.budget_k = budget_k
        self.clearance_rate = clearance_rate

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],  # robot_id -> {'pos': (x,y), 'current_node': u, 'next_node': v, 'target_node': t}
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        """
        Compute onset hazard h_theta(e, s_t) for each candidate risky edge.
        Returns mapping canonical_edge -> hazard probability in [0, 1].
        """
        raise NotImplementedError


class StochasticAdversary(Adversary):
    """theta_1: Stochastic i.i.d. onset hazard p_0 across all risky edges."""

    def __init__(self, p0: float = 0.15, budget_k: int = 4, clearance_rate: float = 0.15):
        super().__init__(AdversaryType.STOCHASTIC, budget_k, clearance_rate)
        self.p0 = p0

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        return {e: self.p0 for e in risky_edges}


class ReactiveAdversary(Adversary):
    """
    theta_2: Reactive adversary targeting edges with active robot traffic or proximity.
    h(e) = min(1.0, p0 + alpha * N_e(t))
    where N_e is number of robots currently on or adjacent to edge e.
    """

    def __init__(
        self,
        p0: float = 0.05,
        alpha: float = 0.35,
        budget_k: int = 4,
        clearance_rate: float = 0.15,
    ):
        super().__init__(AdversaryType.REACTIVE, budget_k, clearance_rate)
        self.p0 = p0
        self.alpha = alpha

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        hazards = {}
        # Count robot proximity for each edge
        edge_counts = {e: 0 for e in risky_edges}
        for _, state in fleet_states.items():
            curr = state.get("current_node")
            nxt = state.get("next_node")
            if curr is not None and nxt is not None:
                e_trav = canonical_edge(curr, nxt)
                if e_trav in edge_counts:
                    edge_counts[e_trav] += 1
            elif curr is not None and graph.has_node(curr):
                # Count incident edges
                for nbr in graph.neighbors(curr):
                    e_inc = canonical_edge(curr, nbr)
                    if e_inc in edge_counts:
                        edge_counts[e_inc] += 0.5

        for e in risky_edges:
            count = edge_counts[e]
            h = min(1.0, self.p0 + self.alpha * count)
            hazards[e] = float(h)
        return hazards


class BudgetedInterdictionAdversary(Adversary):
    """
    theta_3: Budgeted Interdiction (Minimax Network Interdiction).
    Evaluates edges every epoch to maximize fleet shortest path delay to their active goals.
    """

    def __init__(
        self,
        p0: float = 0.05,
        p_cut: float = 0.85,
        epoch_length: int = 5,
        budget_k: int = 4,
        clearance_rate: float = 0.15,
    ):
        super().__init__(AdversaryType.BUDGETED_INTERDICTION, budget_k, clearance_rate)
        self.p0 = p0
        self.p_cut = p_cut
        self.epoch_length = epoch_length
        self.targeted_edges: Set[Tuple[Any, Any]] = set()
        self.last_epoch_step: int = -999

    def _compute_interdiction_cut(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
    ) -> Set[Tuple[Any, Any]]:
        """Greedy approximation of max-delay network interdiction under budget k."""
        # Find active origin-destination pairs for the fleet
        od_pairs = []
        for _, state in fleet_states.items():
            curr = state.get("current_node")
            target = state.get("target_node")
            if curr is not None and target is not None and curr != target and nx.has_path(graph, curr, target):
                od_pairs.append((curr, target))

        if not od_pairs:
            # Fallback: pick top betweenness centrality edges among risky edges
            edge_bc = nx.edge_betweenness_centrality(graph, weight="weight")
            sorted_risky = sorted(
                risky_edges,
                key=lambda e: edge_bc.get(e, edge_bc.get((e[1], e[0]), 0.0)),
                reverse=True,
            )
            return set(sorted_risky[: self.budget_k])

        # Baseline total shortest path cost
        def baseline_cost(g_sub: nx.Graph) -> float:
            tot = 0.0
            for u, v in od_pairs:
                try:
                    tot += nx.shortest_path_length(g_sub, u, v, weight="weight")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    tot += 1000.0  # high penalty for disconnected
            return tot

        base_val = baseline_cost(graph)
        selected_cuts = set()
        g_temp = graph.copy()

        # Greedy selection of edges up to budget k
        for _ in range(self.budget_k):
            best_e = None
            best_increase = -1.0
            for e in risky_edges:
                if e in selected_cuts:
                    continue
                u, v = e
                if not g_temp.has_edge(u, v):
                    continue
                w = g_temp[u][v].get("weight", 1.0)
                g_temp.remove_edge(u, v)

                new_cost = baseline_cost(g_temp)
                increase = new_cost - base_val
                if increase > best_increase:
                    best_increase = increase
                    best_e = e

                g_temp.add_edge(u, v, weight=w)

            if best_e is not None and best_increase > 0:
                selected_cuts.add(best_e)
                if g_temp.has_edge(best_e[0], best_e[1]):
                    g_temp.remove_edge(best_e[0], best_e[1])
            else:
                break

        return selected_cuts

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        if step - self.last_epoch_step >= self.epoch_length or not self.targeted_edges:
            self.targeted_edges = self._compute_interdiction_cut(graph, risky_edges, fleet_states)
            self.last_epoch_step = step

        hazards = {}
        for e in risky_edges:
            if e in self.targeted_edges:
                hazards[e] = self.p_cut
            else:
                hazards[e] = self.p0
        return hazards


class CyclicPatrolAdversary(Adversary):
    """
    theta_4: Out-of-model adversary.
    Cycles a rolling set of blockages across ordered bottleneck edges over time.
    """

    def __init__(
        self,
        cycle_period: int = 4,
        budget_k: int = 4,
        clearance_rate: float = 0.2,
    ):
        super().__init__(AdversaryType.CYCLIC_PATROL, budget_k, clearance_rate)
        self.cycle_period = cycle_period
        self._ordered_bottlenecks: Optional[List[Tuple[Any, Any]]] = None

    def _init_bottlenecks(self, graph: nx.Graph, risky_edges: Set[Tuple[Any, Any]]) -> None:
        edge_bc = nx.edge_betweenness_centrality(graph, weight="weight")
        self._ordered_bottlenecks = sorted(
            risky_edges,
            key=lambda e: edge_bc.get(e, edge_bc.get((e[1], e[0]), 0.0)),
            reverse=True,
        )

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        if self._ordered_bottlenecks is None:
            self._init_bottlenecks(graph, risky_edges)

        n = len(self._ordered_bottlenecks)
        if n == 0:
            return {e: 0.1 for e in risky_edges}

        idx_offset = (step // self.cycle_period) % n
        active_window = set(
            self._ordered_bottlenecks[(idx_offset + i) % n]
            for i in range(min(self.budget_k, n))
        )

        hazards = {}
        for e in risky_edges:
            if e in active_window:
                hazards[e] = 0.90
            else:
                hazards[e] = 0.02
        return hazards


class RealTraceReplayAdversary(Adversary):
    """
    Tier E3 Real-Trace Replay Adversary:
    Replays empirical road-closure work zone traces from City of Boston Public Works Active Work Zones
    (data/maps/boston_work_zones.csv, SHA-256: 26b456a6b5857c8380b0d439978ba2fdb3eb2402c3b0bafad6331fca41d663e1).
    Maps street-level construction closures to corresponding graph edges in downtown Boston.
    """

    def __init__(
        self,
        trace_file: Optional[str] = None,
        budget_k: int = 4,
        clearance_rate: float = 0.15,
        base_hazard: float = 0.02,
        closed_hazard: float = 0.95,
    ):
        super().__init__(AdversaryType.REAL_TRACE_REPLAY, budget_k=budget_k, clearance_rate=clearance_rate)
        self.trace_file = trace_file
        self.base_hazard = base_hazard
        self.closed_hazard = closed_hazard
        self._matched_edges: Set[Tuple[Any, Any]] = set()
        self._initialized: bool = False

    def _init_trace(self, graph: nx.Graph):
        if self._initialized:
            return
        self._initialized = True
        import os
        import pandas as pd
        if self.trace_file is None:
            self.trace_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "data", "maps", "boston_work_zones.csv"
            )
        if not os.path.exists(self.trace_file):
            return

        try:
            df = pd.read_csv(self.trace_file)
            wz_streets = set(
                df["Street"].dropna().str.upper().str.replace(" STREET", "").str.replace(" ST", "").str.strip()
            )
            for u, v, d in graph.edges(data=True):
                name = str(d.get("name", "")).upper().replace(" STREET", "").replace(" ST", "").strip()
                if name and name in wz_streets:
                    self._matched_edges.add(canonical_edge(u, v))
        except Exception:
            pass

    def get_onset_hazards(
        self,
        graph: nx.Graph,
        risky_edges: Set[Tuple[Any, Any]],
        current_blockages: Set[Tuple[Any, Any]],
        fleet_states: Dict[int, Any],
        step: int,
    ) -> Dict[Tuple[Any, Any], float]:
        self._init_trace(graph)
        hazards = {}
        for e in risky_edges:
            if e in self._matched_edges:
                hazards[e] = self.closed_hazard
            else:
                hazards[e] = self.base_hazard
        return hazards


def create_adversary(
    adv_type: AdversaryType,
    budget_k: int = 4,
    clearance_rate: float = 0.15,
    **kwargs: Any,
) -> Adversary:
    """Factory for adversaries."""
    if adv_type == AdversaryType.STOCHASTIC:
        p0 = kwargs.get("p0", 0.15)
        return StochasticAdversary(p0=p0, budget_k=budget_k, clearance_rate=clearance_rate)
    elif adv_type == AdversaryType.REACTIVE:
        p0 = kwargs.get("p0", 0.05)
        alpha = kwargs.get("alpha", 0.35)
        return ReactiveAdversary(p0=p0, alpha=alpha, budget_k=budget_k, clearance_rate=clearance_rate)
    elif adv_type == AdversaryType.BUDGETED_INTERDICTION:
        p0 = kwargs.get("p0", 0.05)
        p_cut = kwargs.get("p_cut", 0.85)
        epoch = kwargs.get("epoch_length", 5)
        return BudgetedInterdictionAdversary(
            p0=p0, p_cut=p_cut, epoch_length=epoch, budget_k=budget_k, clearance_rate=clearance_rate
        )
    elif adv_type == AdversaryType.CYCLIC_PATROL:
        period = kwargs.get("cycle_period", 4)
        return CyclicPatrolAdversary(
            cycle_period=period, budget_k=budget_k, clearance_rate=clearance_rate
        )
    elif adv_type == AdversaryType.REAL_TRACE_REPLAY or str(adv_type) in ("theta_5_real_trace_replay", "real_trace_replay"):
        return RealTraceReplayAdversary(
            budget_k=budget_k, clearance_rate=clearance_rate, **kwargs
        )
    else:
        raise ValueError(f"Unknown adversary type: {adv_type}")
