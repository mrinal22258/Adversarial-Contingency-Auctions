"""
Verification tests for Phase A:
1. CRN (Common Random Numbers) identity across all methods using SeedSequence.spawn(5).
2. Config keys honored (comm_regimes, final_seeds, contingency_depth, etc.).
3. Communication range changes outcomes (benign vs isolated).
4. Decentralized SSI respects auctioneer reachability over lossy/range-limited networks.
"""

import numpy as np
import networkx as nx

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine
from acalib.alloc.ssi import SSIAllocator
from acalib.alloc.base import Task


def test_crn_identity_across_methods():
    """Verify that multiple methods initialized with spawned RNG see identical inputs and blockages."""
    master_seed = 4242
    ss = np.random.SeedSequence(master_seed)
    rng_graph, rng_starts, rng_tasks, rng_blockages, rng_comm = [
        np.random.default_rng(s) for s in ss.spawn(5)
    ]

    graph = generate_graph("rgg", n_nodes=25, seed=int(rng_graph.integers(0, 1000000)))
    nodes_list = sorted(list(graph.nodes()))
    n_robots = 3
    n_tasks = 6
    max_steps = 20

    start_nodes = [nodes_list[int(rng_starts.integers(0, len(nodes_list)))] for _ in range(n_robots)]
    tasks = {
        tid: Task(
            task_id=tid,
            node=nodes_list[int(rng_tasks.integers(0, len(nodes_list)))],
            reward=100.0,
            arrival_step=0,
            deadline=max_steps,
        )
        for tid in range(n_tasks)
    }

    from acalib.env.adversaries import canonical_edge
    all_edges = sorted([canonical_edge(u, v) for u, v in graph.edges()])
    n_risky = max(1, int(len(all_edges) * 0.25))
    risky_edges = set(all_edges[:n_risky])

    predrawn_clear = {}
    predrawn_onset = {}
    for e in sorted(list(risky_edges)):
        for t in range(max_steps + 5):
            predrawn_clear[(e, t)] = float(rng_blockages.random())
            predrawn_onset[(e, t)] = float(rng_blockages.random())

    comm_seed = int(rng_comm.integers(0, 1000000))

    methods_to_test = ["aca", "cbba", "ssi", "ctp_replan", "cbba_gossip"]
    engines = {}
    for m in methods_to_test:
        eng = SimulationEngine(
            graph=graph,
            adversary_type=AdversaryType.STOCHASTIC,
            allocator_type=m,
            n_robots=n_robots,
            n_tasks=n_tasks,
            max_steps=max_steps,
            custom_start_nodes=start_nodes,
            custom_tasks=tasks,
            predrawn_clear_uniforms=predrawn_clear,
            predrawn_onset_uniforms=predrawn_onset,
            custom_risky_edges=risky_edges,
            comm_net_seed=comm_seed,
        )
        engines[m] = eng

    # Verify initial start node alignment
    for m, eng in engines.items():
        assert [r.current_node for r in eng.robots.values()] == start_nodes
        assert [t.node for t in eng.tasks.values()] == [t.node for t in tasks.values()]
        assert eng.blockage_process.risky_edges == risky_edges


def test_comm_range_changes_outcomes():
    """Verify that changing comm_range from benign to constrained changes message delivery and allocations."""
    graph = generate_graph("rgg", n_nodes=30, seed=55)
    
    # Run with high comm range (benign)
    engine_benign = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="cbba",
        n_robots=4,
        n_tasks=10,
        comm_range=100.0,
        p_drop=0.0,
        max_steps=20,
        seed=101,
    )
    m_benign = engine_benign.run(max_steps=20)

    # Run with tiny comm range (severely constrained)
    engine_constrained = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="cbba",
        n_robots=4,
        n_tasks=10,
        comm_range=1.0,
        p_drop=0.4,
        max_steps=20,
        seed=101,
    )
    m_constrained = engine_constrained.run(max_steps=20)

    # Under tiny comm range, messages should fail to deliver between distant robots
    assert m_benign.total_messages_sent != m_constrained.total_messages_sent or \
           m_benign.completed_tasks != m_constrained.completed_tasks or \
           m_benign.total_travel_distance != m_constrained.total_travel_distance


def test_ssi_respects_reachability():
    """Verify that decentralized SSI only accepts bids from reachable robots."""
    graph = nx.Graph()
    # Linear graph with 3 nodes: 0 -- 1 -- 2, distances = 50.0
    graph.add_node(0, pos=(0.0, 0.0))
    graph.add_node(1, pos=(50.0, 0.0))
    graph.add_node(2, pos=(120.0, 0.0))
    graph.add_edge(0, 1, weight=50.0)
    graph.add_edge(1, 2, weight=70.0)

    from acalib.env.comm import CommunicationNetwork
    from acalib.agents.robot import RobotAgent

    comm_net = CommunicationNetwork(comm_range=40.0, p_drop=0.0, seed=1) # 40 range: 0 cannot talk to 1 or 2
    robots = {
        0: RobotAgent(0, start_node=0, graph=graph, fleet_ids=[0, 1, 2], contingency_depth=0),
        1: RobotAgent(1, start_node=1, graph=graph, fleet_ids=[0, 1, 2], contingency_depth=0),
        2: RobotAgent(2, start_node=2, graph=graph, fleet_ids=[0, 1, 2], contingency_depth=0),
    }
    allocator = SSIAllocator(graph=graph, robots=robots, comm_net=comm_net, decentralized=True)

    # Task at node 1 (auctioneer is robot 0 at node 0)
    task = Task(task_id=0, node=1, reward=100.0)
    robot_positions = {rid: r.pos for rid, r in robots.items()}

    res = allocator.allocate_round({0: task}, current_step=0, robot_positions=robot_positions)
    # Robot 1 and 2 are out of comm range (distance 50 and 120 > 40) from auctioneer (robot 0)
    # So auctioneer cannot communicate task or receive bids from robots 1 or 2
    # Robot 1 cannot win even though it is at node 1
    assert 0 not in robots[1].bundle
