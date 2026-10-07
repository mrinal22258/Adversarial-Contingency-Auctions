"""
Failing-first regression tests for CBBA Consensus (Choi 2009 compliance):
1. Task Orphaning Test: when an agent releases a task, peers must reset and be able to claim it.
2. Consensus Convergence Test: on a static instance, full agreement on winning agents and bids.
"""

import os
import networkx as nx
import pytest

from acalib.env.graph_families import generate_erdos_renyi
from acalib.agents.robot import RobotAgent
from acalib.env.comm import CommunicationNetwork
from acalib.alloc.cbba import CBBAAllocator
from acalib.alloc.cbba_partial import CBBAPartialReplanAllocator
from acalib.alloc.cc_cbba import ChanceConstrainedCBBAAllocator
from acalib.alloc.cbba_gossip import CBBABeliefGossipAllocator
from acalib.alloc.aca import ACAAllocator
from acalib.alloc.base import Task


def test_cbba_task_orphaning_regression():
    """
    Regression test for Choi 2009 release rule:
    When Robot 0 releases Task 0, Robot 1 must NOT suffer from orphaning lockout.
    Robot 1 must reset its belief of winner for Task 0 to none (-1), and be free to claim it.
    """
    g = generate_erdos_renyi(n_nodes=15, p=0.4, seed=101)
    comm = CommunicationNetwork(comm_range=100.0, p_drop=0.0, seed=101)
    robots = {
        0: RobotAgent(0, 0, g, [0, 1], speed=5.0),
        1: RobotAgent(1, 1, g, [0, 1], speed=5.0),
    }
    alloc = CBBAAllocator(g, robots, comm)

    tasks = {
        0: Task(0, node=4, reward=100.0),
        1: Task(1, node=8, reward=100.0),
    }

    # Step 0: Initial allocation
    pos = {0: robots[0].pos, 1: robots[1].pos}
    alloc.allocate_round(tasks, current_step=0, robot_positions=pos)

    # Verify that one robot won task 0
    winner_t0 = alloc.z[0].get(0)
    assert winner_t0 in (0, 1)
    other_r = 1 if winner_t0 == 0 else 0

    # Ensure other robot also recorded winner_t0
    assert alloc.z[other_r].get(0) == winner_t0

    # Direct test of Choi 2009 release rule in communicate_and_resolve:
    winner_agent = robots[winner_t0]
    winner_agent.bundle.remove(0) if 0 in winner_agent.bundle else None
    alloc.z[winner_t0][0] = -1
    alloc.y[winner_t0][0] = 0.0
    # Run consensus communication
    alloc._communicate_and_resolve(current_step=1, robot_positions=pos)

    # Receiver must reset its belief: z[other_r][0] must be -1, NOT winner_t0!
    assert alloc.z[other_r].get(0) == -1, (
        f"Orphaning defect! Receiver {other_r} failed to reset belief when sender {winner_t0} released Task 0: z={alloc.z[other_r].get(0)}"
    )


def test_static_instance_consensus_convergence():
    """
    Verify consensus convergence across all auction variants on a static instance:
    All reachable agents must converge to identical winning bid and agent tables,
    and no task may be double-assigned.
    """
    allocator_classes = [
        ("CBBA", CBBAAllocator),
        ("CBBA_Partial", CBBAPartialReplanAllocator),
        ("CC_CBBA", ChanceConstrainedCBBAAllocator),
        ("CBBA_Gossip", CBBABeliefGossipAllocator),
        ("ACA", ACAAllocator),
    ]

    for name, AllocClass in allocator_classes:
        g = generate_erdos_renyi(n_nodes=25, p=0.35, seed=202)
        comm = CommunicationNetwork(comm_range=150.0, p_drop=0.0, seed=202)
        fleet_ids = list(range(4))
        robots = {
            i: RobotAgent(i, i * 2, g, fleet_ids, speed=5.0)
            for i in fleet_ids
        }
        alloc = AllocClass(g, robots, comm)

        tasks = {
            tid: Task(tid, node=5 + tid * 2, reward=100.0)
            for tid in range(8)
        }

        pos = {i: robots[i].pos for i in fleet_ids}
        res = alloc.allocate_round(tasks, current_step=0, robot_positions=pos, max_consensus_iterations=10)

        # 1. Zero conflict: no task in multiple bundles
        all_claimed = []
        for r in robots.values():
            all_claimed.extend(r.bundle)
        assert len(all_claimed) == len(set(all_claimed)), (
            f"{name}: Double-assignment conflict in final bundles: {all_claimed}"
        )

        # 2. Table agreement: all robots agree on winners for all tasks
        for tid in tasks:
            winners = set(alloc.z[rid].get(tid, -1) for rid in fleet_ids)
            assert len(winners) == 1, (
                f"{name}: Disagreement on winner for Task {tid}: {winners}"
            )
