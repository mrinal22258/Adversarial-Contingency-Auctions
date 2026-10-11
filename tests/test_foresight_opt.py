"""
Unit tests for ForesightOptAllocator (CP-SAT Exact Benchmark).
"""
from acalib.env.graph_families import generate_erdos_renyi
from acalib.agents.robot import RobotAgent
from acalib.env.comm import CommunicationNetwork
from acalib.env.blockage_process import PersistentBlockageProcess
from acalib.alloc.foresight_opt import ForesightOptAllocator
from acalib.alloc.base import Task


def test_foresight_opt_solves_optimally():
    """Verify that ForesightOptAllocator finds optimal solution with 0 conflicts and 0 optimality gap."""
    g = generate_erdos_renyi(n_nodes=15, p=0.4, seed=42)
    comm = CommunicationNetwork(comm_range=100.0, p_drop=0.0, seed=42)
    from acalib.env.adversaries import create_adversary
    adv = create_adversary("theta_1_stochastic", seed=42)
    bp = PersistentBlockageProcess(g, adversary=adv, clearance_rate=0.15, seed=42)
    robots = {
        0: RobotAgent(0, 0, g, [0, 1], speed=5.0),
        1: RobotAgent(1, 1, g, [0, 1], speed=5.0),
    }
    alloc = ForesightOptAllocator(g, robots, comm, blockage_process=bp, bundle_limit=3)

    tasks = {
        0: Task(0, node=4, reward=100.0),
        1: Task(1, node=8, reward=100.0),
        2: Task(2, node=12, reward=100.0),
    }

    pos = {0: (0.0, 0.0), 1: (1.0, 1.0)}
    res = alloc.allocate_round(tasks, current_step=0, robot_positions=pos)

    assert res["conflicts"] == 0
    assert res["total_assigned"] > 0
    assert res["optimality_gap"] == 0.0
    assert res["solver_status"] in ("OPTIMAL", "FEASIBLE")

    # Ensure no double assignment
    all_assigned = []
    for r in robots.values():
        all_assigned.extend(r.bundle)
    assert len(all_assigned) == len(set(all_assigned))
