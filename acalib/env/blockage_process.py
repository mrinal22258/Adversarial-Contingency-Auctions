"""
Persistent 2-State Markov Blockage Process for Risky Edges.
Implements onset hazard h_theta(e, s_t), clearance rate mu, and global budget k.
"""

from enum import IntEnum
from typing import Dict, Set, Tuple, Optional, Any
import numpy as np
import networkx as nx

from .adversaries import Adversary, canonical_edge, partition_risky_edges


class EdgeState(IntEnum):
    OPEN = 0
    BLOCKED = 1


class PersistentBlockageProcess:
    """
    Manages the persistent ground-truth blockage state for all risky edges.
    State transitions follow:
    P(0 -> 1) = h_theta(e, s_t)
    P(1 -> 0) = mu (clearance rate)
    P(1 -> 1) = 1 - mu
    P(0 -> 0) = 1 - h_theta(e, s_t)
    Enforces global blockage capacity budget k.
    """

    def __init__(
        self,
        graph: nx.Graph,
        adversary: Adversary,
        risk_fraction: float = 0.25,
        clearance_rate: float = 0.15,
        seed: Optional[int] = None,
        custom_risky_edges: Optional[Set[Tuple[Any, Any]]] = None,
        initial_blocked_edges: Optional[Set[Tuple[Any, Any]]] = None,
        predrawn_clear_uniforms: Optional[Dict[Tuple[Tuple[Any, Any], int], float]] = None,
        predrawn_onset_uniforms: Optional[Dict[Tuple[Tuple[Any, Any], int], float]] = None,
    ):
        self.graph = graph
        self.adversary = adversary
        self.clearance_rate = clearance_rate
        self.rng = np.random.default_rng(seed)
        self.predrawn_clear_uniforms = predrawn_clear_uniforms
        self.predrawn_onset_uniforms = predrawn_onset_uniforms

        # Identify risky edges: high betweenness or custom
        if custom_risky_edges is not None:
            self.risky_edges = {canonical_edge(u, v) for u, v in custom_risky_edges}
        else:
            self.risky_edges = self._select_risky_edges(risk_fraction)

        # Include initial blocked edges in risky edges if specified
        if initial_blocked_edges:
            for u, v in initial_blocked_edges:
                self.risky_edges.add(canonical_edge(u, v))

        # Partition risky edges into structurally distinct topological vulnerability classes
        self.risky_edge_partitions = partition_risky_edges(self.graph, self.risky_edges)

        # Initial blockage state: start all open, or set initially blocked
        self.edge_states: Dict[Tuple[Any, Any], EdgeState] = {
            e: EdgeState.OPEN for e in self.risky_edges
        }
        if initial_blocked_edges:
            for u, v in initial_blocked_edges:
                self.edge_states[canonical_edge(u, v)] = EdgeState.BLOCKED

        self.newly_cleared: Set[Tuple[Any, Any]] = set()
        self.newly_blocked: Set[Tuple[Any, Any]] = set()

    def _select_risky_edges(self, risk_fraction: float) -> Set[Tuple[Any, Any]]:
        """Select top betweenness edges combined with random edges to form E_risk."""
        all_edges = [canonical_edge(u, v) for u, v in self.graph.edges()]
        n_risky = max(1, int(len(all_edges) * risk_fraction))

        edge_bc = nx.edge_betweenness_centrality(self.graph, weight="weight")
        sorted_by_bc = sorted(
            all_edges,
            key=lambda e: edge_bc.get(e, edge_bc.get((e[1], e[0]), 0.0)),
            reverse=True,
        )

        # Take half from top betweenness and half randomly
        n_bc = n_risky // 2
        top_bc = sorted_by_bc[:n_bc]
        remaining = [e for e in sorted_by_bc[n_bc:]]
        self.rng.shuffle(remaining)
        selected = set(top_bc + remaining[: n_risky - n_bc])
        return selected

    def block_edge(self, u: Any, v: Any) -> bool:
        """Explicitly block edge (u, v). Returns True if edge state transitioned to BLOCKED."""
        e = canonical_edge(u, v)
        if not self.graph.has_edge(u, v):
            return False
        self.risky_edges.add(e)
        prev = self.edge_states.get(e, EdgeState.OPEN)
        self.edge_states[e] = EdgeState.BLOCKED
        if prev != EdgeState.BLOCKED:
            self.newly_blocked.add(e)
            self.newly_cleared.discard(e)
            return True
        return False

    def unblock_edge(self, u: Any, v: Any) -> bool:
        """Explicitly unblock edge (u, v). Returns True if edge state transitioned to OPEN."""
        e = canonical_edge(u, v)
        if e not in self.edge_states:
            return False
        prev = self.edge_states[e]
        self.edge_states[e] = EdgeState.OPEN
        if prev != EdgeState.OPEN:
            self.newly_cleared.add(e)
            self.newly_blocked.discard(e)
            return True
        return False

    def set_edge_blocked(self, u: Any, v: Any, blocked: bool) -> bool:
        """Explicitly set whether edge (u, v) is blocked."""
        return self.block_edge(u, v) if blocked else self.unblock_edge(u, v)

    def is_blocked(self, u: Any, v: Any) -> bool:
        """Check if edge (u, v) is currently blocked."""
        e = canonical_edge(u, v)
        if e not in self.risky_edges:
            return False
        return self.edge_states.get(e, EdgeState.OPEN) == EdgeState.BLOCKED

    def get_blocked_edges(self) -> Set[Tuple[Any, Any]]:
        """Return set of currently blocked canonical edges."""
        return {e for e, state in self.edge_states.items() if state == EdgeState.BLOCKED}

    def step(self, fleet_states: Dict[int, Any], current_step: int) -> Dict[Tuple[Any, Any], Tuple[EdgeState, EdgeState]]:
        """
        Advance Markov state by one tick.
        Returns dictionary of transitions: edge -> (old_state, new_state).
        """
        curr_blocked = self.get_blocked_edges()
        hazards = self.adversary.get_onset_hazards(
            self.graph,
            self.risky_edges,
            curr_blocked,
            fleet_states,
            current_step,
        )

        transitions = {}
        candidate_new_blocked = set()

        # Step 1: Process existing blockages (clearance with prob mu)
        for e in sorted(list(curr_blocked)):
            if self.predrawn_clear_uniforms is not None and (e, current_step) in self.predrawn_clear_uniforms:
                u_clear = self.predrawn_clear_uniforms[(e, current_step)]
            else:
                u_clear = float(self.rng.random())

            if u_clear < self.clearance_rate:
                # Cleared
                transitions[e] = (EdgeState.BLOCKED, EdgeState.OPEN)
                self.edge_states[e] = EdgeState.OPEN
            else:
                # Remains blocked
                candidate_new_blocked.add(e)

        # Step 2: Process open edges (onset with prob h(e))
        new_onsets = []
        for e in sorted(list(self.risky_edges)):
            if self.edge_states[e] == EdgeState.OPEN:
                h = hazards.get(e, 0.05)
                if self.predrawn_onset_uniforms is not None and (e, current_step) in self.predrawn_onset_uniforms:
                    u_onset = self.predrawn_onset_uniforms[(e, current_step)]
                else:
                    u_onset = float(self.rng.random())

                if u_onset < h:
                    new_onsets.append((e, h))

        # Step 3: Enforce global budget k
        # Sort new onsets by hazard descending if exceeding budget
        budget_k = self.adversary.budget_k
        space_available = max(0, budget_k - len(candidate_new_blocked))
        new_onsets.sort(key=lambda item: item[1], reverse=True)

        accepted_onsets = {e for e, _ in new_onsets[:space_available]}
        for e in sorted(list(accepted_onsets)):
            transitions[e] = (EdgeState.OPEN, EdgeState.BLOCKED)
            self.edge_states[e] = EdgeState.BLOCKED

        self.newly_cleared = {e for e, (o, n) in transitions.items() if o == EdgeState.BLOCKED and n == EdgeState.OPEN}
        self.newly_blocked = {e for e, (o, n) in transitions.items() if o == EdgeState.OPEN and n == EdgeState.BLOCKED}

        return transitions

    def get_active_blockages(self) -> Set[Tuple[Any, Any]]:
        """Alias for get_blocked_edges for UI and telemetry compatibility."""
        return self.get_blocked_edges()
