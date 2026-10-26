"""
Regression tests for High and Medium severity bugs (Bugs 1 through 8).
Guarantees permanent immunity against regressions across:
- Bug 1: RobotAgent.reset_for_run() drops analytical bounds & partition flags
- Bug 2: runner.py 19-tuple vs 16-tuple cache key mismatch
- Bug 3: Undefined Set annotation and implicit fleet_ids in aca.py
- Bug 4: CTPReplanAllocator misses blocked edge on path exhaustion
- Bug 5: sense_environment() NameError: np is not defined
- Bug 6: CyclicPatrolAdversary direction-sensitive edge hazard lookup
- Bug 7: consensus.py string vs integer key mismatch on deserialized payloads
- Bug 8: ForesightOptAllocator CP-SAT first-task travel cost evasion
"""

import json
import math
import networkx as nx
import numpy as np
import pytest

from acalib.agents.belief import compute_reliability_curve
from acalib.agents.robot import RobotAgent
from acalib.alloc.base import Task
from acalib.alloc.aca import ACAAllocator
from acalib.alloc.ctp_replan import CTPReplanAllocator
from acalib.alloc.consensus import execute_consensus_exchange
from acalib.alloc.foresight_opt import ForesightOptAllocator
from acalib.demo.runner import _RUN_CACHE, run_single_simulation, get_cached_run, _build_simulation_cache_key
from acalib.env.adversaries import CyclicPatrolAdversary, StochasticAdversary
from acalib.env.blockage_process import PersistentBlockageProcess
from acalib.env.comm import CommunicationNetwork, Message


def test_bug1_and_bug5_robot_reset_preserves_flags_and_sense_executes():
    """Bug 1 & Bug 5: reset_for_run preserves flags and sense_environment does not crash with np NameError."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    nx.set_node_attributes(G, {0: (0.0, 0.0), 1: (1.0, 1.0)}, "pos")

    robot = RobotAgent(
        robot_id=0,
        start_node=0,
        graph=G,
        fleet_ids=[0, 1],
        partition_mode=True,
        enforce_analytical_bounds=True,
        gamma_obs=0.45,
    )
    assert robot.type_filter.enforce_analytical_bounds is True
    assert robot.tom_tracker.partition_mode is True
    assert robot.tom_tracker.enforce_analytical_bounds is True
    assert robot.tom_tracker.gamma_obs == 0.45

    # Test Bug 1: reset_for_run must not wipe configuration flags
    robot.reset_for_run(start_node=0)
    assert robot.type_filter.enforce_analytical_bounds is True
    assert robot.tom_tracker.partition_mode is True
    assert robot.tom_tracker.enforce_analytical_bounds is True
    assert robot.tom_tracker.gamma_obs == 0.45

    # Test Bug 5: sense_environment must execute cleanly without NameError: np is not defined
    bp = PersistentBlockageProcess(G, adversary=StochasticAdversary(), clearance_rate=0.0)
    robot.sense_environment(bp, fleet_states={0: robot.get_state_summary()}, step=0)


def test_bug2_cache_key_unification_and_hit():
    """Bug 2: get_cached_run hits _RUN_CACHE populated by run_single_simulation."""
    _RUN_CACHE._cache.clear()

    res1 = run_single_simulation(
        graph_family="er",
        n_nodes=12,
        adversary_str="theta_1_stochastic",
        allocator_str="aca",
        comm_regime="unconstrained",
        comm_range=100.0,
        p_drop=0.0,
        n_robots=2,
        n_tasks=2,
        seed=42,
        max_steps=5,
        contingency_depth=1,
    )
    cache_len_after_first = len(_RUN_CACHE)
    assert cache_len_after_first == 1

    res2 = get_cached_run(
        graph_family="er",
        n_nodes=12,
        adversary_str="theta_1_stochastic",
        allocator_str="aca",
        comm_regime="unconstrained",
        comm_range=100.0,
        p_drop=0.0,
        n_robots=2,
        n_tasks=2,
        seed=42,
        max_steps=5,
        contingency_depth=1,
    )
    assert len(_RUN_CACHE) == 1, "Cache length increased; get_cached_run missed cache!"
    assert res1 is res2, "get_cached_run should return the exact cached object reference"


def test_bug3_aca_set_imported_and_fleet_ids():
    """Bug 3: ACA module imports Set and initializes fleet_ids explicitly."""
    import acalib.alloc.aca as aca_mod
    assert hasattr(aca_mod, "Set"), "Set must be imported in acalib.alloc.aca"

    G = nx.Graph()
    G.add_node(0, pos=(0.0, 0.0))
    G.add_node(1, pos=(1.0, 1.0))
    comm = CommunicationNetwork()
    robots = {0: RobotAgent(0, 0, G, [0, 1]), 1: RobotAgent(1, 1, G, [0, 1])}
    alloc = ACAAllocator(G, robots, comm)
    assert hasattr(alloc, "fleet_ids")
    assert alloc.fleet_ids == [0, 1]


def test_bug4_ctp_replan_records_last_blocked_edge_on_exhaustion():
    """Bug 4: CTPReplanAllocator consumes robot.last_blocked_edge upon replan request."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    nx.set_node_attributes(G, {0: (0.0, 0.0), 1: (1.0, 0.0), 2: (2.0, 0.0)}, "pos")

    comm = CommunicationNetwork()
    robot = RobotAgent(0, 0, G, [0])
    alloc = CTPReplanAllocator(G, {0: robot}, comm)

    # Robot active path exhausted at terminal index
    robot.last_blocked_edge = (1, 2)
    robot.active_path = [1]
    robot.path_index = 0
    robot.replan_requests = [10]
    robot.bundle = [10]
    tasks = {10: Task(10, 2, 10.0)}

    alloc.allocate_round(tasks, current_step=0, robot_positions={0: (1.0, 0.0)})
    assert (1, 2) in alloc.known_blocked_edges[0]
    assert robot.last_blocked_edge is None


def test_bug6_cyclic_patrol_adversary_direction_invariant_lookup():
    """Bug 6: CyclicPatrolAdversary hazards are direction-invariant for undirected edges."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)

    adv = CyclicPatrolAdversary(cycle_period=10, budget_k=1)
    # Forward query
    h_fwd = adv.get_onset_hazards(G, risky_edges={(0, 1)}, current_blockages=set(), fleet_states={}, step=0)
    # Reverse query
    h_rev = adv.get_onset_hazards(G, risky_edges={(1, 0)}, current_blockages=set(), fleet_states={}, step=0)

    assert h_fwd.get((0, 1)) == 0.90
    assert h_rev.get((1, 0)) == 0.90


def test_bug7_consensus_deserialized_string_keys():
    """Bug 7: execute_consensus_exchange correctly parses JSON-deserialized string keys."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    comm = CommunicationNetwork(p_drop=0.0)
    robots = {0: RobotAgent(0, 0, G, [0, 1]), 1: RobotAgent(1, 1, G, [0, 1])}

    y = {0: {1: 5.0}, 1: {1: 10.0}}
    z = {0: {1: 0}, 1: {1: 1}}
    s = {0: {0: 1, 1: 0}, 1: {0: 0, 1: 1}}

    # Payload with string keys simulating JSON roundtrip
    raw_payload = json.loads(json.dumps({
        "y": {"1": 10.0},
        "z": {"1": 1},
        "s": {"0": 0, "1": 2},
    }))

    msg = Message(sender_id=1, recipient_id=0, msg_type="CBBA_CONSENSUS", payload=raw_payload, timestamp=2)
    comm.send(msg, {0: (0.0, 0.0), 1: (0.0, 0.0)})

    execute_consensus_exchange([0], robots, comm, y, z, s, current_step=2, robot_positions={0: (0.0, 0.0), 1: (0.0, 0.0)})

    assert y[0] == {1: 10.0}
    assert z[0] == {1: 1}
    assert s[0][1] == 2
    assert "1" not in y[0]
    assert "1" not in s[0]


def test_bug8_foresight_opt_deducts_first_task_travel_penalty():
    """Bug 8: ForesightOptAllocator properly penalizes initial travel distance via bidirectional channeling."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(0, 2, weight=10.0)
    nx.set_node_attributes(G, {0: (0.0, 0.0), 1: (1.0, 0.0), 2: (10.0, 0.0)}, "pos")

    comm = CommunicationNetwork()
    bp = PersistentBlockageProcess(G, StochasticAdversary())
    r0 = RobotAgent(0, 0, G, [0])
    alloc = ForesightOptAllocator(G, {0: r0}, comm, bp, bundle_limit=1)

    # Task 1: reward=5, distance=1 -> net welfare = 4
    # Task 2: reward=6, distance=10 -> net welfare = -4
    # If distance is penalized, solver must pick Task 1.
    t1 = Task(1, 1, 5.0)
    t2 = Task(2, 2, 6.0)

    alloc.allocate_round({1: t1, 2: t2}, current_step=0, robot_positions={0: (0.0, 0.0)})
    assert r0.bundle == [1], f"Expected task [1] (closer), got {r0.bundle}"


def test_bug10_compute_reliability_curve_bin_boundaries():
    """Verify [low, high) interior bins and [low, 1.0] inclusive final bin without dropping or double-counting."""
    # Exact boundary values for 10 bins: 0.0, interior edges (0.1, 0.2, 0.5, 0.9), and 1.0
    p = np.array([0.0, 0.1, 0.2, 0.5, 0.9, 1.0], dtype=float)
    outcomes = np.array([0, 0, 1, 1, 1, 1], dtype=float)

    curve = compute_reliability_curve(p, outcomes, n_bins=10)

    # Extract bin counts depending on return schema (dict vs list of dicts vs tuple)
    if isinstance(curve, dict) and "bin_counts" in curve:
        counts = list(curve["bin_counts"])
    elif isinstance(curve, dict) and "counts" in curve:
        counts = list(curve["counts"])
    elif isinstance(curve, dict) and "bins" in curve:
        counts = [b["count"] for b in curve["bins"]]
    elif isinstance(curve, list):
        counts = [b["count"] for b in curve]
    elif isinstance(curve, tuple) and len(curve) == 3:
        counts = list(curve[2])
    else:
        raise AssertionError(f"Unexpected return format from compute_reliability_curve: {type(curve)}")

    # 1. Total counted samples must equal len(p) (no dropped p=1.0, no double-counted interior edges)
    assert sum(counts) == len(p), f"Expected {len(p)} total binned samples, got {sum(counts)}: {counts}"

    # 2. Each of the 6 boundary points should land in its respective single bin:
    #    0.0 -> bin 0 [0.0, 0.1)
    #    0.1 -> bin 1 [0.1, 0.2)
    #    0.2 -> bin 2 [0.2, 0.3)
    #    0.5 -> bin 5 [0.5, 0.6)
    #    0.9 -> bin 9 [0.9, 1.0]
    #    1.0 -> bin 9 [0.9, 1.0]  (2 items in final bin)
    assert counts[0] == 1
    assert counts[1] == 1
    assert counts[2] == 1
    assert counts[5] == 1
    assert counts[9] == 2
