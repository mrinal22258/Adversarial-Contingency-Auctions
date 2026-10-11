"""Unit tests for CBBA bundle construction and consensus resolution."""


from acalib.env.graph_families import generate_erdos_renyi
from acalib.env.comm import CommunicationNetwork
from acalib.agents.robot import RobotAgent
from acalib.alloc.base import Task
from acalib.alloc.cbba import CBBAAllocator


def test_cbba_consensus_resolves_conflicts():
    """Verify that CBBA builds valid bundles and resolves conflicting claims via consensus."""
    g = generate_erdos_renyi(n_nodes=20, seed=42)
    comm = CommunicationNetwork(comm_range=150.0, p_drop=0.0, seed=1)

    fleet_ids = [0, 1, 2]
    robots = {
        rid: RobotAgent(robot_id=rid, start_node=rid, graph=g, fleet_ids=fleet_ids)
        for rid in fleet_ids
    }

    allocator = CBBAAllocator(graph=g, robots=robots, comm_net=comm, bundle_limit=3)

    # Create 6 tasks
    tasks = {
        tid: Task(task_id=tid, node=tid + 5, reward=100.0)
        for tid in range(6)
    }

    pos_dict = {rid: r.pos for rid, r in robots.items()}
    res = allocator.allocate_round(tasks=tasks, current_step=0, robot_positions=pos_dict)

    assert res["conflicts"] == 0, "CBBA with perfect comm should resolve all conflicts"
    assert res["total_assigned"] > 0, "Tasks should be assigned to robots"

    # Verify no task is duplicated across bundles
    all_assigned = []
    for r in robots.values():
        all_assigned.extend(r.bundle)

    assert len(all_assigned) == len(set(all_assigned)), "No duplicate tasks across bundles"
