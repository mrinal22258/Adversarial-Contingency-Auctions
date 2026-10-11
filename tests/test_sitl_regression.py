"""
Failing-first regression test suite for SITL (PyBullet) evaluation (Step 3B / C1).
Reproduces:
(a) One robot, one task, no blockage completes
(b) Distance travelled > 0 (meaningful locomotion across waypoints)
(c) All six methods run without exception on both maps (warehouse_movingai and road_osmnx)
"""

import pytest
import os
import sys

pytest.importorskip("pybullet")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.sitl.run_sitl import run_single_sitl_trial


def test_one_robot_one_task_no_blockage():
    """
    (a) One robot, one task, no blockage completes.
    In a benign environment with 1 robot and 1 task, the robot MUST complete the task.
    """
    result = run_single_sitl_trial(
        map_type="warehouse_movingai",
        method="aca",
        adversary_name="stochastic",
        comm_regime="benign",
        seed=2001,
        n_robots=1,
        n_tasks=1,
        max_steps=20,
        save_raw_log=False,
    )
    assert result["status"] == "COMPLETED"
    assert result["completed_tasks"] == 1, (
        f"Failed to complete single task: completed={result['completed_tasks']}/1, "
        f"distance={result['total_distance_meters']:.2f}m"
    )


def test_distance_travelled_positive():
    """
    (b) Distance travelled > 0.
    Robot must physically locomote across waypoints toward its assigned task.
    """
    result = run_single_sitl_trial(
        map_type="road_osmnx",
        method="aca",
        adversary_name="stochastic",
        comm_regime="benign",
        seed=2002,
        n_robots=1,
        n_tasks=1,
        max_steps=20,
        save_raw_log=False,
    )
    # The robot should travel a non-trivial distance (e.g. > 1.0 m)
    assert result["total_distance_meters"] > 1.0, (
        f"Robot barely moved: {result['total_distance_meters']:.3f} meters"
    )


@pytest.mark.parametrize("method", ["aca", "aca_no_margin", "ctp_replan", "implicit", "cbba_partial_lr", "ssi_lr"])
@pytest.mark.parametrize("map_type", ["warehouse_movingai", "road_osmnx"])
def test_all_six_methods_run_without_exception(method, map_type):
    """
    (c) All six methods run without exception on both maps.
    Regression test against crashes like 'RobotAgent' has no attribute 'blocked_edges'.
    """
    result = run_single_sitl_trial(
        map_type=map_type,
        method=method,
        adversary_name="reactive",
        comm_regime="constrained",
        seed=2003,
        n_robots=2,
        n_tasks=2,
        max_steps=5,
        save_raw_log=False,
    )
    assert result["status"] == "COMPLETED"


@pytest.mark.parametrize("method", ["aca", "aca_no_margin", "ctp_replan", "implicit", "cbba_partial_lr", "ssi_lr"])
def test_blocked_edge_handling_no_crash(method):
    """
    (c-crash) Verify that when blocked edges are observed, the allocator adapter does NOT crash with
    'RobotAgent' object has no attribute 'blocked_edges'.
    """
    import networkx as nx
    from acalib.alloc.base import Task
    from experiments.sitl.adapter import SITLAllocatorAdapter

    g = nx.path_graph(5)
    for u, v in g.edges():
        g[u][v]["weight"] = 1.0
        g[u][v]["length"] = 1.0
    for n in g.nodes():
        g.nodes[n]["pos"] = (float(n), 0.0)

    from experiments.sitl.comm import SITLCommunicationLayer

    tasks = {0: Task(0, 4, 100.0, 10, 0)}
    comm_net = SITLCommunicationLayer(comm_range=50.0, p_drop=0.0, latency_steps=0, seed=42)
    adapter = SITLAllocatorAdapter(
        method_name=method,
        graph=g,
        n_robots=2,
        tasks=tasks,
        comm_net=comm_net,
        contingency_depth=1,
    )
    # Provide a non-empty known_blocked_edges set
    bundles = adapter.plan_round(
        current_step=0,
        estimated_robot_poses={0: (0.0, 0.0, 0.0), 1: (1.0, 0.0, 0.0)},
        known_blocked_edges={(1, 2)},
    )
    assert isinstance(bundles, dict)


def test_aruco_orientation_no_flip_ambiguity():
    """
    Verify ArUco synthetic vision heading calculation:
    - Orientation matches ground truth within numerical tolerance (< 0.05 rad)
    - 4x4 binary code breaks 180-degree flip ambiguity across multiple quadrants
    """
    import math
    from experiments.sitl.vision import SyntheticVisionSystem

    vis = SyntheticVisionSystem(pixel_noise_sigma=0.0, occlusion_prob=0.0, detection_drop_prob=0.0, latency_ticks=0)
    test_angles = [0.0, 0.5, 1.0, 1.57, -1.0, 2.5, -2.5]

    for ryaw in test_angles:
        frame, _ = vis.render_overhead_frame({0: (50.0, 50.0, ryaw)})
        poses, _ = vis.detect_and_estimate_poses(frame, {0: (50.0, 50.0, ryaw)}, current_step=0)
        assert 0 in poses, f"Marker 0 missed at yaw {ryaw}"
        est_yaw = poses[0][2]
        err = abs((est_yaw - ryaw + math.pi) % (2.0 * math.pi) - math.pi)
        assert err < 0.05, f"Yaw estimation error too high for ryaw={ryaw}: est={est_yaw}, err={err}"


def test_collision_vs_conflict_metric_separation():
    """
    Verify that physical collisions and abstract conflicts are tracked as distinct metrics.
    """
    result = run_single_sitl_trial(
        map_type="warehouse_movingai",
        method="aca",
        adversary_name="stochastic",
        comm_regime="benign",
        seed=2001,
        n_robots=2,
        n_tasks=2,
        max_steps=5,
        save_raw_log=False,
    )
    assert "physical_collisions" in result
    assert "total_conflicts" in result
    assert isinstance(result["physical_collisions"], int)
    assert isinstance(result["total_conflicts"], int)


def test_simulation_disclaimer_provenance():
    """
    Verify that SITL reports and analysis files carry the strict simulation disclaimer.
    """
    import json
    summary_path = os.path.join(REPO_ROOT, "results", "sitl", "analysis", "sitl_vs_graph_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "SIMULATION ONLY" in data.get("disclaimer", "")


