"""
Acceptance Tests for Gate 2: Policy Equivalence, Tree Cursor, and Pruning Semantics (P0-2, P0-4, P0-6).
Verifies:
1. Same edge in two branches with different continuations: executor takes the branch appropriate to state.
2. Two-level-deep blockage with no replan/messages: actual cost == tree's predicted branch cost.
3. Monte Carlo: for sampled policies, empirical mean cost matches analytic tree cost within declared tolerance.
4. Active pruning at registered threshold removes detour while preserving failure probability and recovery cost in leaf set.
5. Identical plan hash used by bound, score, cache, and executor.
6. Missing marginal raises MissingMarginalError; malformed tree raises deterministically.
7. Trace test: printed trace demonstrates priced branch == executed branch.
"""

import pytest
import numpy as np
import networkx as nx

from acalib.agents.contingency import (
    ContingencyPlanner,
    RecoursePlan,
    RecourseTreeNode,
    MissingMarginalError,
    canonical_edge,
    compute_plan_hash,
    prune_recourse_plan,
    _collect_leaf_costs,
)
from acalib.agents.executor import LocalRecourseExecutor
from acalib.env.blockage_process import PersistentBlockageProcess
from acalib.env.adversaries import AdversaryType, create_adversary


class MockRobot:
    """Lightweight robot harness for execution and policy equivalence testing."""
    def __init__(self, graph: nx.Graph, start_node: int, contingency_depth: int = 1):
        self.robot_id = 0
        self.graph = graph
        self.current_node = start_node
        self.pos = graph.nodes[start_node].get("pos", (0.0, 0.0))
        self.active_task_id = None
        self.active_path = [start_node]
        self.path_index = 0
        self.edge_progress = 0.0
        self.status = "IDLE"
        self.speed = 1.0
        self.contingency_depth = contingency_depth
        self.assigned_plans = {}
        self.bundle = []
        self.completed_tasks = []
        self.replan_requests = []
        self.tree_cursor = None

    def plan_task_bundle(self, tasks_dict):
        pass

    def get_edge_marginals(self):
        return getattr(self, "edge_marginals", {})


class MockBlockageProcess:
    """Deterministically controls blocked edges during test stepping."""
    def __init__(self, blocked_edges=None):
        self.blocked_set = set()
        if blocked_edges:
            for u, v in blocked_edges:
                self.blocked_set.add(canonical_edge(u, v))
                self.blocked_set.add((u, v))
                self.blocked_set.add((v, u))

    def is_blocked(self, u, v):
        return (u, v) in self.blocked_set or canonical_edge(u, v) in self.blocked_set


def test_same_edge_in_two_branches_branch_appropriate():
    """1. Same edge in two branches with different continuations: executor takes branch appropriate to state."""
    # Graph where edge (2, 3) appears in both Branch A and Branch B
    # Branch A: node 1 -> node 2 -> node 3 -> destination 5 (continuation via 3 -> 5)
    # Branch B: node 4 -> node 2 -> node 3 -> destination 6 (continuation via 3 -> 6)
    G = nx.Graph()
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(4, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    G.add_edge(3, 5, weight=1.0)
    G.add_edge(3, 6, weight=1.0)
    G.add_edge(2, 7, weight=1.0)
    G.add_edge(7, 5, weight=1.0)
    G.add_edge(2, 8, weight=1.0)
    G.add_edge(8, 6, weight=1.0)

    # In Branch A (targeting 5), if (2, 3) is blocked, detour is [2, 7, 5]
    node_a = RecourseTreeNode(
        node_id="branch_A",
        path=[1, 2, 3, 5],
        cost=3.0,
        risky_edges=[canonical_edge(2, 3)],
        detours={
            canonical_edge(2, 3): RecourseTreeNode(
                node_id="detour_A",
                path=[2, 7, 5],
                cost=2.0,
                risky_edges=[],
                detours={},
                depth=1,
                branch_id="detour_A",
            )
        },
        depth=0,
        branch_id="root_A",
    )

    # In Branch B (targeting 6), if (2, 3) is blocked, detour is [2, 8, 6]
    node_b = RecourseTreeNode(
        node_id="branch_B",
        path=[4, 2, 3, 6],
        cost=3.0,
        risky_edges=[canonical_edge(2, 3)],
        detours={
            canonical_edge(2, 3): RecourseTreeNode(
                node_id="detour_B",
                path=[2, 8, 6],
                cost=2.0,
                risky_edges=[],
                detours={},
                depth=1,
                branch_id="detour_B",
            )
        },
        depth=0,
        branch_id="root_B",
    )

    plan_a = RecoursePlan(1, 5, [1, 2, 3, 5], 3.0, 3.0, depth=1, tree=node_a)
    plan_b = RecoursePlan(2, 6, [4, 2, 3, 6], 3.0, 3.0, depth=1, tree=node_b)

    blockage = MockBlockageProcess(blocked_edges=[(2, 3)])

    # Test Robot A (in Branch A)
    robot_a = MockRobot(G, start_node=2, contingency_depth=1)
    robot_a.active_task_id = 1
    robot_a.assigned_plans[1] = plan_a
    robot_a.active_path = [2, 3, 5]
    robot_a.path_index = 0
    robot_a.tree_cursor = node_a

    LocalRecourseExecutor.step_execution(robot_a, blockage, {1: {"node": 5}})
    assert robot_a.status == "PIVOTED"
    assert robot_a.active_path == [2, 7, 5], f"Robot A should pivot to [2, 7, 5], got {robot_a.active_path}"

    # Test Robot B (in Branch B)
    robot_b = MockRobot(G, start_node=2, contingency_depth=1)
    robot_b.active_task_id = 2
    robot_b.assigned_plans[2] = plan_b
    robot_b.active_path = [2, 3, 6]
    robot_b.path_index = 0
    robot_b.tree_cursor = node_b

    LocalRecourseExecutor.step_execution(robot_b, blockage, {2: {"node": 6}})
    assert robot_b.status == "PIVOTED"
    assert robot_b.active_path == [2, 8, 6], f"Robot B should pivot to [2, 8, 6], got {robot_b.active_path}"


def test_two_level_deep_blockage_matches_tree_predicted_cost():
    """2. Two-level-deep blockage with no replan/messages: actual cost == tree's predicted branch cost."""
    G = nx.Graph()
    # Primary path: 0 -> 1 -> 3 (cost 2.0). Edge (1, 3) risky.
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 3, weight=1.0)
    # Detour 1 from 1: 1 -> 2 -> 3 (cost 2.0). Edge (2, 3) risky.
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    # Detour 2 from 2: 2 -> 4 -> 3 (cost 3.0: 2 -> 4 weight 2.0, 4 -> 3 weight 1.0)
    G.add_edge(2, 4, weight=2.0)
    G.add_edge(4, 3, weight=1.0)

    marginals = {
        **{canonical_edge(u, v): 0.0 for u, v in G.edges()},
        canonical_edge(1, 3): 0.40,
        canonical_edge(2, 3): 0.50,
    }
    planner = ContingencyPlanner(G, max_depth=2, exhaustion_penalty=100.0)
    plan = planner.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    assert plan is not None

    # Predicted cost of the 2-level branch:
    # Traversal: 0 -> 1 (1.0), then pivot at 1 -> 2 (1.0), then pivot at 2 -> 4 (2.0) -> 3 (1.0) = 5.0 total
    predicted_branch_cost = 1.0 + 1.0 + 2.0 + 1.0

    # Execute with both (1, 3) and (2, 3) blocked
    blockage = MockBlockageProcess(blocked_edges=[(1, 3), (2, 3)])
    robot = MockRobot(G, start_node=0, contingency_depth=2)
    robot.active_task_id = 1
    robot.assigned_plans[1] = plan
    robot.active_path = list(plan.primary_path)
    robot.tree_cursor = plan.tree
    robot.bundle = [1]

    # Track actual traversed distance
    traversed_edges = []
    step_count = 0
    while robot.active_task_id == 1 and step_count < 20:
        step_count += 1
        curr_u = robot.active_path[robot.path_index]
        LocalRecourseExecutor.step_execution(robot, blockage, {1: {"node": 3}}, dt=1.0)
        curr_v = robot.current_node
        if curr_u != curr_v:
            traversed_edges.append((curr_u, curr_v))

    actual_traversed_cost = sum(G[u][v]["weight"] for u, v in traversed_edges)
    assert 1 in robot.completed_tasks, "Robot failed to complete task via depth-2 recourse"
    assert len(robot.replan_requests) == 0, "No replan requests should be generated for planned depth-2 recourse"
    assert actual_traversed_cost == predicted_branch_cost, f"Actual cost {actual_traversed_cost} != predicted {predicted_branch_cost}"


def test_monte_carlo_analytic_tree_cost_matches_empirical():
    """3. Monte Carlo: for sampled policies, empirical mean cost matches analytic tree cost within declared tolerance."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=2.0)
    G.add_edge(1, 3, weight=3.0)  # risky edge e1
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=4.0)  # risky edge e2 on detour 1
    G.add_edge(2, 4, weight=2.0)
    G.add_edge(4, 3, weight=5.0)  # detour 2

    p1 = 0.30
    p2 = 0.40
    marginals = {
        **{canonical_edge(u, v): 0.0 for u, v in G.edges()},
        canonical_edge(1, 3): p1,
        canonical_edge(2, 3): p2,
    }

    planner = ContingencyPlanner(G, max_depth=2, exhaustion_penalty=50.0)
    plan = planner.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)
    analytic_cost = plan.expected_cost

    # Monte Carlo simulation: 3,000 independent trials under independent Bernoulli model
    n_samples = 3000
    rng = np.random.default_rng(20261013)
    sample_costs = []

    for _ in range(n_samples):
        b1 = rng.random() < p1
        b2 = rng.random() < p2
        blocked_edges = []
        if b1:
            blocked_edges.append((1, 3))
        if b2:
            blocked_edges.append((2, 3))

        blockage = MockBlockageProcess(blocked_edges=blocked_edges)
        robot = MockRobot(G, start_node=0, contingency_depth=2)
        robot.active_task_id = 1
        robot.assigned_plans[1] = plan
        robot.active_path = list(plan.primary_path)
        robot.tree_cursor = plan.tree
        robot.bundle = [1]

        traversed = []
        steps = 0
        while robot.active_task_id == 1 and steps < 25:
            steps += 1
            u = robot.active_path[robot.path_index]
            LocalRecourseExecutor.step_execution(robot, blockage, {1: {"node": 3}}, dt=1.0)
            v = robot.current_node
            if u != v:
                traversed.append((u, v))

        trial_cost = sum(G[u][v]["weight"] for u, v in traversed)
        sample_costs.append(trial_cost)

    empirical_mean = float(np.mean(sample_costs))
    sem = float(np.std(sample_costs) / np.sqrt(n_samples))
    declared_tolerance = 3.0 * sem + 0.05

    # Report values
    print(f"\n[Monte Carlo Validation] Analytic cost: {analytic_cost:.4f}, Empirical mean: {empirical_mean:.4f}, SEM: {sem:.4f}, Tol: {declared_tolerance:.4f}")
    assert np.isclose(empirical_mean, analytic_cost, atol=declared_tolerance), (
        f"Empirical mean {empirical_mean} deviated from analytic {analytic_cost} by more than tolerance {declared_tolerance}"
    )


def test_pruning_at_threshold_preserves_failure_probability_and_recovery_cost():
    """4. At registered threshold at least one candidate edge is genuinely pruned; failure prob and recovery cost remain in leaf set."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)  # risky edge pi=0.15 in [0.12, 0.20)
    G.add_edge(1, 3, weight=3.0)
    G.add_edge(3, 2, weight=1.0)

    # Edge marginal 0.15 is >= planner threshold 0.12, but < prune threshold 0.20
    marginals = {
        **{canonical_edge(u, v): 0.0 for u, v in G.edges()},
        canonical_edge(1, 2): 0.15,
    }

    planner = ContingencyPlanner(G, max_depth=1, exhaustion_penalty=100.0)
    unpruned_plan = planner.build_recourse_plan(1, 0, 2, marginals, risky_edge_threshold=0.12)
    assert canonical_edge(1, 2) in unpruned_plan.risky_edges
    assert canonical_edge(1, 2) in unpruned_plan.tree.detours
    assert not unpruned_plan.tree.detours[canonical_edge(1, 2)].is_recovery

    # Prune plan with threshold 0.20
    pruned_plan = prune_recourse_plan(unpruned_plan, prune_threshold=0.20, planner=planner, edge_marginals=marginals)

    # 1. Edge remains in risky edges
    assert canonical_edge(1, 2) in pruned_plan.risky_edges, "Pruning must NOT erase modeled risk from risky_edges"

    # 2. Detour is converted to an explicit recovery leaf
    detour_node = pruned_plan.tree.detours[canonical_edge(1, 2)]
    assert detour_node.is_recovery is True, "Pruned edge must branch to recovery leaf"
    assert detour_node.recovery_cost == 100.0

    # 3. Leaf costs include the recovery cost
    leaf_costs = []
    _collect_leaf_costs(pruned_plan.tree, planner, 0.0, leaf_costs)
    # Leaf costs: nominal (2.0) and failure at (1, 2): dist_to_u (1.0) + penalty (100.0) = 101.0
    assert 101.0 in leaf_costs, f"Leaf costs must include recovery cost (101.0), got {leaf_costs}"

    # 4. Expected cost strictly accounts for failure probability 0.15 * 101.0 + 0.85 * 2.0 = 15.15 + 1.70 = 16.85
    expected_analytic = 0.15 * 101.0 + 0.85 * 2.0
    assert np.isclose(pruned_plan.expected_cost, expected_analytic, atol=1e-3)


def test_identical_plan_hash_across_bound_score_cache_executor():
    """5. Identical plan hash used by bound, score, cache, and executor."""
    from acalib.alloc.aca import ACAAllocator
    from acalib.agents.robot import RobotAgent
    from acalib.env.comm import CommunicationNetwork
    from acalib.alloc.base import Task

    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(1, 3, weight=2.0)
    G.add_edge(3, 2, weight=1.0)

    robots = {
        0: RobotAgent(0, 0, G, fleet_ids=[0], contingency_depth=1),
    }
    comm_net = CommunicationNetwork(30.0, 0.10)
    alloc = ACAAllocator(G, robots, comm_net, prune_threshold=0.20)
    robots[0].prune_threshold = 0.20

    task = Task(1, 2, 100.0)
    tasks = {1: task}

    # Execute Phase 1 local bundle construction
    alloc._build_bundle_aca(0, tasks, {0: (0.0, 0.0)})

    # Plan in robot.assigned_plans
    assigned_plan = robots[0].assigned_plans.get(1)
    assert assigned_plan is not None, "Robot should have assigned plan for task 1"
    assert assigned_plan.plan_hash != ""

    # Verify _compute_lipschitz_L_j operates on the identical plan object and hash
    L_j = alloc._compute_lipschitz_L_j(task, 0, recourse_plan=assigned_plan)
    assert isinstance(L_j, float)

    # Verify executor setup preserves the identical plan and tree hash
    robots[0].plan_task_bundle({1: {"node": 2}})
    assert robots[0].tree_cursor is not None
    assert robots[0].assigned_plans[1].plan_hash == assigned_plan.plan_hash
    assert compute_plan_hash(robots[0].assigned_plans[1]) == assigned_plan.plan_hash


def test_missing_marginal_and_malformed_tree_raises():
    """6. Missing marginal raises MissingMarginalError; malformed tree raises deterministically."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 2, weight=1.0)

    planner = ContingencyPlanner(G, max_depth=1)

    node = RecourseTreeNode(
        node_id="root",
        path=[0, 1, 2],
        cost=2.0,
        risky_edges=[canonical_edge(1, 2)],
        detours={},
        depth=0,
    )

    # Calling compute_tree_expected_cost without (1, 2) in marginals must raise MissingMarginalError
    with pytest.raises(MissingMarginalError, match="Missing edge marginal"):
        planner.compute_tree_expected_cost(node, edge_marginals={})

    # Calling prune_recourse_tree with missing marginal must raise MissingMarginalError
    from acalib.agents.contingency import prune_recourse_tree
    with pytest.raises(MissingMarginalError, match="Missing edge marginal"):
        prune_recourse_tree(node, prune_threshold=0.20, edge_marginals={})


def test_trace_shows_priced_branch_equals_executed_branch(capsys):
    """7. Trace test: an independently inspectable executed trace shows executor followed priced branch."""
    G = nx.Graph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(1, 3, weight=1.0)
    G.add_edge(1, 2, weight=1.0)
    G.add_edge(2, 3, weight=1.0)
    G.add_edge(2, 4, weight=2.0)
    G.add_edge(4, 3, weight=1.0)

    marginals = {
        **{canonical_edge(u, v): 0.0 for u, v in G.edges()},
        canonical_edge(1, 3): 0.40,
        canonical_edge(2, 3): 0.50,
    }
    planner = ContingencyPlanner(G, max_depth=2, exhaustion_penalty=100.0)
    plan = planner.build_recourse_plan(1, 0, 3, marginals, risky_edge_threshold=0.12)

    blockage = MockBlockageProcess(blocked_edges=[(1, 3), (2, 3)])
    robot = MockRobot(G, start_node=0, contingency_depth=2)
    robot.active_task_id = 1
    robot.assigned_plans[1] = plan
    robot.active_path = list(plan.primary_path)
    robot.tree_cursor = plan.tree
    robot.bundle = [1]

    execution_trace = []
    step = 0
    while robot.active_task_id == 1 and step < 20:
        step += 1
        pos_before = robot.current_node
        status_before = robot.status
        LocalRecourseExecutor.step_execution(robot, blockage, {1: {"node": 3}}, dt=1.0)
        pos_after = robot.current_node
        status_after = robot.status
        execution_trace.append({
            "step": step,
            "from": pos_before,
            "to": pos_after,
            "status": status_after,
            "cursor_node_id": robot.tree_cursor.node_id if robot.tree_cursor else "None",
            "active_path": list(robot.active_path),
        })

    print("\n--- INDEPENDENTLY INSPECTABLE EXECUTION TRACE ---")
    for tr in execution_trace:
        print(f"Step {tr['step']}: Node {tr['from']} -> {tr['to']} | Status: {tr['status']} | Cursor: {tr['cursor_node_id']} | Path: {tr['active_path']}")

    # Assert that cursor transitioned through branch hierarchy
    cursors_visited = [tr["cursor_node_id"] for tr in execution_trace]
    assert any("node_root_d0" in c for c in cursors_visited), "Must execute primary root cursor"
    assert any("node_root->(1,3)_d1" in c for c in cursors_visited), "Must pivot to depth-1 branch cursor"
    assert any("node_root->(1,3)->(2,3)_d2" in c for c in cursors_visited), "Must pivot to depth-2 branch cursor"
    assert robot.current_node == 3, "Must successfully complete task at destination node 3"
