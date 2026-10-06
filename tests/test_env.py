"""Unit tests for environment modules: graphs, blockages, adversaries, comm."""

import pytest
import networkx as nx
import numpy as np

from acalib.env.graph_families import (
    generate_graph,
    generate_erdos_renyi,
    generate_random_geometric,
    generate_warehouse_grid,
)
from acalib.env.adversaries import (
    AdversaryType,
    create_adversary,
    StochasticAdversary,
    ReactiveAdversary,
    BudgetedInterdictionAdversary,
    CyclicPatrolAdversary,
)
from acalib.env.blockage_process import PersistentBlockageProcess, EdgeState
from acalib.env.comm import CommunicationNetwork, Message


def test_graph_generators_connected():
    """Verify all graph families generate connected graphs with 2D positions and weights."""
    for fam in ["er", "rgg", "warehouse"]:
        g = generate_graph(family=fam, n_nodes=30, seed=42)
        assert nx.is_connected(g), f"{fam} graph is not connected"
        assert g.number_of_nodes() >= 25
        # Check node attributes
        for n in g.nodes():
            assert "pos" in g.nodes[n]
            pos = g.nodes[n]["pos"]
            assert len(pos) == 2
        # Check edge weights
        for u, v in g.edges():
            assert "weight" in g[u][v]
            assert g[u][v]["weight"] > 0


def test_blockage_process_markov_and_budget():
    """Verify persistent 2-state Markov dynamics and budget k constraint."""
    g = generate_erdos_renyi(n_nodes=25, seed=123)
    adv = StochasticAdversary(p0=0.5, budget_k=3, clearance_rate=0.2)
    bp = PersistentBlockageProcess(g, adversary=adv, risk_fraction=0.4, seed=42)

    # Initial state should be all open
    assert len(bp.get_blocked_edges()) == 0
    assert len(bp.risky_edges) > 0

    fleet_states = {0: {"current_node": list(g.nodes())[0]}}

    # Step multiple times and check budget k is strictly respected
    for step in range(20):
        bp.step(fleet_states, step)
        blocked = bp.get_blocked_edges()
        assert len(blocked) <= adv.budget_k, f"Blocked count {len(blocked)} exceeded budget {adv.budget_k}"


def test_adversary_behaviors():
    """Verify hazard models for reactive and interdiction adversaries."""
    g = generate_erdos_renyi(n_nodes=20, seed=1)
    risky = {tuple(sorted(e)) for e in list(g.edges())[:5]}

    # Reactive adversary: hazard increases on traffic
    react_adv = ReactiveAdversary(p0=0.05, alpha=0.4, budget_k=3)
    fleet_idle = {0: {"current_node": 999}}
    h_idle = react_adv.get_onset_hazards(g, risky, set(), fleet_idle, 0)

    # Put robot on first risky edge
    e0 = list(risky)[0]
    fleet_active = {0: {"current_node": e0[0], "next_node": e0[1]}}
    h_active = react_adv.get_onset_hazards(g, risky, set(), fleet_active, 0)
    assert h_active[e0] > h_idle[e0]

    # Interdiction adversary
    interdict_adv = BudgetedInterdictionAdversary(p0=0.05, p_cut=0.8, budget_k=2)
    h_interdict = interdict_adv.get_onset_hazards(g, risky, set(), fleet_idle, 0)
    assert len([h for h in h_interdict.values() if h > 0.5]) <= 2


def test_communication_network_metrics():
    """Verify comm network range filtering, packet drops, and byte counters."""
    comm = CommunicationNetwork(comm_range=30.0, p_drop=0.0, seed=42)
    pos = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (100.0, 100.0)}

    # Send broadcast from robot 0
    msg = Message(sender_id=0, recipient_id=-1, msg_type="TEST", payload="hello", timestamp=0, size_bytes=64)
    comm.send(msg, pos)

    assert comm.total_messages_sent == 1
    assert comm.total_bytes_sent == 64

    # Robot 1 is within 30m, Robot 2 is not
    inbox1 = comm.receive(1)
    inbox2 = comm.receive(2)
    assert len(inbox1) == 1
    assert len(inbox2) == 0
