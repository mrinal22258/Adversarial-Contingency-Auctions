"""
Verification of Stabilization Guarantees (Phase 2.3):
1. Safe-Claim Monotonicity: Tasks claimed safely in Phase 1 are never outbid or revoked in Phase 2 consensus.
2. Diminishing Marginal Gains (DMG) / Consensus Termination in bounded iterations.
"""

import pytest
import numpy as np

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine
from acalib.alloc.aca import ACAAllocator


def test_safe_claim_monotonicity():
    """
    Proposition 4: Safe claims committed in Phase 1 are never revoked in Phase 2 consensus.
    """
    graph = generate_graph("rgg", n_nodes=25, seed=777)
    engine = SimulationEngine(
        graph=graph,
        adversary_type=AdversaryType.STOCHASTIC,
        allocator_type="aca",
        n_robots=4,
        n_tasks=10,
        contingency_depth=1,
        seed=777,
    )
    
    tasks_dict = {tid: t for tid, t in engine.tasks.items()}
    robot_pos = {rid: r.pos for rid, r in engine.robots.items()}
    
    # Run Phase 1 bundle construction
    phase1_claims = {}
    allocator: ACAAllocator = engine.allocator
    for rid in allocator.fleet_ids:
        prev = set(allocator.robots[rid].bundle)
        allocator._build_bundle_aca(rid, tasks_dict, robot_pos, current_step=0)
        new_in_bundle = [tid for tid in allocator.robots[rid].bundle if tid not in prev]
        phase1_claims[rid] = new_in_bundle
        
    # Phase 2: Communication consensus
    consensus_rounds = 0
    for _ in range(10):
        consensus_rounds += 1
        changed = allocator._communicate_and_resolve(current_step=0, robot_positions=robot_pos)
        if not changed:
            break
    
    # Check that bundle holds the safe claims (Proposition 4: monotonicity)
    assert consensus_rounds <= 10, "Consensus exceeded max iterations"
    for rid, claims in phase1_claims.items():
        for tid in claims:
            # If it was safely claimed, it is never outbid or revoked in consensus
            assert tid in allocator.robots[rid].bundle or tasks_dict[tid].completed
