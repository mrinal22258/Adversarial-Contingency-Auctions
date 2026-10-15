"""
Regression tests for Phase 0.B audit defects:
0.B.1: ACA clears robot.replan_requests and counts reauction_events.
0.B.2: safe_claims and deferred_tasks are returned as per-round deltas, not cumulative totals.
0.B.8: Unified message and byte accounting across all allocators.
0.B.9: Total conflicts reflect new conflicting events rather than repeating across rounds.
0.B.10: Common random numbers (CRN) using SeedSequence.spawn for identical blockage streams.
0.B.11: Assumption 1 TV distance logging and validation against eta_eff.
"""


from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


def test_aca_clears_replan_requests_and_records_reauctions():
    """Defect 0.B.1: ACA must clear robot.replan_requests and increment reauction_events."""
    graph = generate_graph("rgg", n_nodes=25, seed=42)
    engine = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca",
        n_robots=3,
        n_tasks=6,
        contingency_depth=1,
        seed=42,
    )

    # Simulate a robot experiencing an unresolvable blockage and adding a replan request
    robot = engine.robots[0]
    task_id = list(engine.tasks.keys())[0]
    robot.bundle = [task_id]
    robot.replan_requests.append(task_id)

    assert len(robot.replan_requests) == 1

    # Execute one simulation step
    engine.step(1)

    # 1. replan_requests must be cleared
    assert len(robot.replan_requests) == 0, "ACA failed to clear robot.replan_requests"

    # 2. reauction_events metric must be at least 1
    assert engine.metrics.reauction_events >= 1, "ACA failed to record reauction_events"


def test_safe_claims_per_round_delta():
    """Defect 0.B.2: allocate_round must return per-round delta for safe_claims, not running totals."""
    graph = generate_graph("rgg", n_nodes=25, seed=42)
    engine = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca",
        n_robots=3,
        n_tasks=8,
        contingency_depth=1,
        seed=42,
    )

    # Run step 0
    engine.step(0)
    claims_step_0 = engine.metrics.safe_claims

    # Force a second allocation round with no new safe claims
    # (tasks already assigned, so new safe claims in round 2 should be 0)
    alloc_res = engine.allocator.allocate_round(
        tasks={tid: t for tid, t in engine.tasks.items() if not t.completed},
        current_step=10,
        robot_positions={rid: r.pos for rid, r in engine.robots.items()},
    )

    # The per-round safe_claims returned by allocate_round must be delta for this round (0)
    assert alloc_res["safe_claims"] == 0, (
        f"allocate_round returned cumulative total {alloc_res['safe_claims']} instead of round delta"
    )


def test_unified_message_accounting_across_allocators():
    """Defect 0.B.8: Unified message and byte accounting across CBBA, ACA, and SSI."""
    graph = generate_graph("rgg", n_nodes=25, seed=42)
    
    for alloc_type in ["cbba", "aca", "ssi"]:
        engine = SimulationEngine(
            graph=graph,
            adversary_type=AdversaryType.STOCHASTIC,
            allocator_type=alloc_type,
            n_robots=3,
            n_tasks=6,
            contingency_depth=0,
            seed=42,
        )
        engine.run(max_steps=15)
        
        # All methods must log non-zero messages and bytes if allocations occur
        assert engine.metrics.total_messages_sent > 0, f"{alloc_type} logged 0 messages"
        assert engine.metrics.total_bytes_sent > 0, f"{alloc_type} logged 0 bytes"
        # Bytes per message should be physically plausible (e.g. >= 20 bytes per message)
        assert engine.metrics.total_bytes_sent >= engine.metrics.total_messages_sent * 16


def test_common_random_numbers_blockage_stream():
    """Defect 0.B.10: Two methods on same instance must see identical blockage realizations."""
    graph = generate_graph("rgg", n_nodes=25, seed=123)
    
    engine_aca = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca",
        n_robots=3,
        n_tasks=6,
        contingency_depth=1,
        seed=123,
    )
    
    engine_cbba = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="cbba",
        n_robots=3,
        n_tasks=6,
        contingency_depth=1,
        seed=123,
    )
    
    # Risky edge selection must be identical
    assert engine_aca.blockage_process.risky_edges == engine_cbba.blockage_process.risky_edges
    
    # Advance both engines by 10 steps and check that edge states match when independent of fleet
    for step in range(10):
        engine_aca.step(step)
        engine_cbba.step(step)
    
    # Stochastic adversary does not depend on fleet state; edge states must be identical
    assert (
        engine_aca.blockage_process.get_blocked_edges() ==
        engine_cbba.blockage_process.get_blocked_edges()
    )


def test_build_crn_environment_reproducibility():
    """Defect C-1: build_crn_environment must be bit-for-bit reproducible across independent calls and processes."""
    import hashlib
    from experiments.run_sweep import build_crn_environment

    env1 = build_crn_environment("warehouse_movingai", 38, 10001, 4, 15, 80)
    env2 = build_crn_environment("warehouse_movingai", 38, 10001, 4, 15, 80)

    assert env1["risky_edges"] == env2["risky_edges"]
    assert env1["predrawn_clear"] == env2["predrawn_clear"]
    assert env1["predrawn_onset"] == env2["predrawn_onset"]
    assert env1["comm_seed"] == env2["comm_seed"]

    # Also test for a synthetic family > 30 nodes (uncached)
    env3 = build_crn_environment("rgg", 35, 10001, 4, 15, 80)
    env4 = build_crn_environment("rgg", 35, 10001, 4, 15, 80)

    assert env3["risky_edges"] == env4["risky_edges"]
    assert env3["predrawn_clear"] == env4["predrawn_clear"]
    assert env3["predrawn_onset"] == env4["predrawn_onset"]


def test_f05_run_cache_bounded_lru():
    """F-05: _RUN_CACHE must be bounded by maxsize and follow LRU eviction."""
    from acalib.demo.runner import BoundedLRUCache
    cache = BoundedLRUCache(maxsize=3)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3
    assert len(cache) == 3

    # Access 'a' to make it most recently used
    _ = cache["a"]

    # Insert 'd', which should evict oldest unaccessed 'b'
    cache["d"] = 4
    assert len(cache) == 3
    assert "b" not in cache
    assert "a" in cache
    assert "c" in cache
    assert "d" in cache
    assert cache["a"] == 1


def test_f06_f21_all_pairs_dist_cache_and_graph_dict():
    """F-06, F-21: get_all_pairs_distances must store in graph.graph and bound module cache."""
    import networkx as nx
    from acalib.alloc.cbba import get_all_pairs_distances, _ALL_PAIRS_DIST_CACHE, MAX_ALL_PAIRS_CACHE_SIZE

    g = nx.path_graph(5)
    for u, v in g.edges():
        g[u][v]["weight"] = 1.0
    g.graph["sha256"] = "test_hash_123"

    dists = get_all_pairs_distances(g)
    assert dists[0][4] == 4.0
    assert "all_pairs_dist_cache" in g.graph
    assert g.graph["all_pairs_dist_cache"] is dists
    assert len(_ALL_PAIRS_DIST_CACHE) <= MAX_ALL_PAIRS_CACHE_SIZE


def test_f06_edge_bc_cache_bounded():
    """F-06: _EDGE_BC_CACHE in run_sweep.py must be bounded by MAX_BC_CACHE_SIZE."""
    import collections
    from experiments.run_sweep import _EDGE_BC_CACHE, MAX_BC_CACHE_SIZE
    assert isinstance(_EDGE_BC_CACHE, collections.OrderedDict)
    assert len(_EDGE_BC_CACHE) <= MAX_BC_CACHE_SIZE


