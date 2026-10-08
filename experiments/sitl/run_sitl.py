"""
Physics-Based Software-in-the-Loop (SITL) Evaluation Runner (Step 3).
Executes multi-robot auction algorithms on real map topologies using PyBullet:
- Methods: ACA, ACA-no-margin, CTP replan, Implicit, CBBA-PR+LR, SSI+LR
- Topologies: MovingAI Warehouse (warehouse-10-20-10-2-1), Boston Road Network (OSMnx 2.1.1)
- Adversaries: Stochastic, Reactive, Budgeted, Cyclic, Real-Trace Work Zone Replay
- Communication: Benign, Constrained, Lossy
- Disjoint seeds: seed >= 2000 (disjoint from main 13,800 sweep seeds)

Writes:
- JSONL records to results/sitl/sitl_results.jsonl
- Raw event logs to results/sitl/raw/
- Video telemetry and provenance

DISCLAIMER: Everything produced is SIMULATION.
No physical robots, ROS 2, Gazebo, or hardware were used or claimed.
"""

import os
import sys
import time
import json
import math
import hashlib
import argparse
from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import networkx as nx

# Add repository root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from experiments.plot_style import get_git_commit
from acalib.alloc.base import Task
from acalib.env.adversaries import (
    AdversaryType,
    create_adversary,
    canonical_edge,
)
from acalib.env.blockage_process import PersistentBlockageProcess
from experiments.sitl.world import PhysicsWorld
from experiments.sitl.robot import DiffDriveRobotSITL
from experiments.sitl.comm import SITLCommunicationLayer
from experiments.sitl.adapter import create_sitl_allocator, SITLAllocatorAdapter

RESULTS_SITL_DIR = os.path.join(REPO_ROOT, "results", "sitl")
RESULTS_RAW_DIR = os.path.join(RESULTS_SITL_DIR, "raw")
os.makedirs(RESULTS_SITL_DIR, exist_ok=True)
os.makedirs(RESULTS_RAW_DIR, exist_ok=True)


COMM_REGIME_PARAMS = {
    "nominal": {"comm_range": 45.0, "p_drop": 0.0, "latency": 0},
    "benign": {"comm_range": 45.0, "p_drop": 0.0, "latency": 0},
    "constrained": {"comm_range": 25.0, "p_drop": 0.05, "latency": 1},
    "lossy": {"comm_range": 15.0, "p_drop": 0.20, "latency": 2},
}


def run_single_sitl_trial(
    map_type: str,
    method: str,
    adversary_name: str,
    comm_regime: str,
    seed: int,
    n_robots: int = 4,
    n_tasks: int = 8,
    max_steps: int = 20,
    adv_budget_k: int = 4,
    save_raw_log: bool = True,
    record_history: bool = False,
) -> Dict[str, Any]:
    """Execute a single physical SITL simulation trial in PyBullet."""
    trial_start_wall = time.perf_counter()
    rng = np.random.default_rng(seed)

    # 1. Physics World setup
    world = PhysicsWorld(map_type=map_type, scale=100.0, gui=False)
    graph = world.graph
    nodes = sorted(list(graph.nodes()))
    pos_dict = nx.get_node_attributes(graph, "pos")

    # 2. Communication layer
    comm_params = COMM_REGIME_PARAMS[comm_regime]
    comm_layer = SITLCommunicationLayer(
        comm_range=comm_params["comm_range"],
        p_drop=comm_params["p_drop"],
        latency_steps=comm_params["latency"],
        seed=int(rng.integers(0, 1000000)),
    )

    # 3. Tasks
    starts = rng.choice(nodes, size=n_robots, replace=False).tolist()
    avail = [n for n in nodes if n not in starts]
    task_nodes = rng.choice(avail, size=n_tasks, replace=False).tolist()

    tasks: Dict[int, Task] = {}
    for tid in range(n_tasks):
        tasks[tid] = Task(
            task_id=tid,
            node=task_nodes[tid],
            reward=100.0,
            deadline=max_steps + 10,
            arrival_step=0,
        )

    # 4. Adversary and blockage process
    if adversary_name == "stochastic":
        adv_type = AdversaryType.STOCHASTIC
    elif adversary_name == "reactive":
        adv_type = AdversaryType.REACTIVE
    elif adversary_name == "budgeted":
        adv_type = AdversaryType.BUDGETED
    elif adversary_name == "cyclic":
        adv_type = AdversaryType.CYCLIC_PATROL
    elif adversary_name in ["real_trace", "real_trace_replay"]:
        adv_type = AdversaryType.REAL_TRACE_REPLAY
    else:
        adv_type = AdversaryType.STOCHASTIC

    adversary = create_adversary(adv_type, budget_k=adv_budget_k, clearance_rate=0.15)
    edge_bc = nx.edge_betweenness_centrality(graph)
    sorted_edges = sorted(edge_bc.items(), key=lambda x: x[1], reverse=True)
    risky_edges = {canonical_edge(u, v) for (u, v), _ in sorted_edges[:6]}

    blockage_proc = PersistentBlockageProcess(
        graph=graph,
        adversary=adversary,
        risk_fraction=0.25,
        clearance_rate=0.15,
        custom_risky_edges=risky_edges,
        seed=int(rng.integers(0, 1000000)),
    )

    # 5. Allocator & Adapter
    r_depth = 1 if (method.startswith("aca") or method.endswith("_lr") or method == "implicit") else 0
    adapter = SITLAllocatorAdapter(
        method_name=method,
        graph=graph,
        n_robots=n_robots,
        tasks=tasks,
        comm_net=comm_layer,
        contingency_depth=r_depth,
    )

    # 6. Physical Robots
    robots: Dict[int, DiffDriveRobotSITL] = {}
    for rid in range(n_robots):
        init_pt = pos_dict[starts[rid]]
        robots[rid] = DiffDriveRobotSITL(
            robot_id=rid,
            client_id=world.client_id,
            init_pos=init_pt,
            init_yaw=float(rng.uniform(-math.pi, math.pi)),
            v_max=3.5,
            omega_max=3.0,
            seed=int(rng.integers(0, 1000000)),
        )

    # Telemetry accumulators
    completed_tasks = set()
    total_conflicts = 0
    recourse_detours = 0
    physical_collisions = 0
    total_distance_m = 0.0
    known_blocked_edges: Set[Tuple[int, int]] = set()
    current_robot_targets: Dict[int, Optional[int]] = {rid: None for rid in range(n_robots)}

    event_log = []

    # Simulation loop
    for step in range(max_steps):
        # A. Update blockages
        fleet_states = {rid: {"current_node": starts[rid]} for rid in range(n_robots)}
        blockage_proc.step(fleet_states, step)
        curr_blocked = blockage_proc.get_blocked_edges()

        # Update PyBullet physical barriers
        for e in risky_edges:
            is_b = e in curr_blocked
            world.set_corridor_blockage(e[0], e[1], is_b)

        # B. Sense local blockages (if near edge)
        barrier_ids = list(world.blockage_barriers.values())

        # C. Get estimated poses from noisy odometry
        est_poses = {rid: r.get_estimated_pose() for rid, r in robots.items()}
        gt_poses = {rid: r.get_ground_truth_pose() for rid, r in robots.items()}

        # D. Exchange messages through lossy communication layer
        for r_i in range(n_robots):
            for r_j in range(n_robots):
                if r_i != r_j:
                    comm_layer.send_message(
                        sender_id=r_i,
                        receiver_id=r_j,
                        payload={"step": step, "blocked": list(known_blocked_edges)},
                        sender_pos=est_poses[r_i][:2],
                        receiver_pos=est_poses[r_j][:2],
                        current_step=step,
                    )
        comm_layer.step_network(step)

        # E. Allocator round
        bundles = adapter.plan_round(step, est_poses, known_blocked_edges)

        # Check bundle conflicts (double claims)
        all_claimed = []
        for rid, b in bundles.items():
            all_claimed.extend(b)
        conflicts_step = len(all_claimed) - len(set(all_claimed))
        total_conflicts += max(0, conflicts_step)

        # F. Waypoint path assignment (only replan if target changed, target reached, or collision occurred)
        for rid, r in robots.items():
            assigned_b = bundles.get(rid, [])
            target_t = assigned_b[0] if assigned_b else None
            curr_xy = gt_poses[rid][:2]
            target_changed = (target_t != current_robot_targets.get(rid))
            path_needed = r.target_reached or (len(r.current_path) == 0)

            if target_changed or path_needed or r.collision_detected:
                current_robot_targets[rid] = target_t
                if target_t is not None:
                    waypoints = adapter.compute_waypoint_path(
                        robot_id=rid,
                        target_task_id=target_t,
                        start_pos=curr_xy,
                        blocked_edges=known_blocked_edges,
                    )
                    r.set_path(waypoints)
                else:
                    r.set_path([])

        # Simultaneous physical stepping across all robots
        # 100 sub-steps at 1/60s = 1.67 seconds of physical simulation per auction step
        for _ in range(100):
            for rid, r in robots.items():
                r.update_controller(dt=1.0 / 60.0)
            world.step_simulation(n_steps=1)
            for rid, r in robots.items():
                hit_barrier = r.check_collisions(barrier_ids)
                if hit_barrier:
                    physical_collisions += 1
                    for b_edge in curr_blocked:
                        known_blocked_edges.add(b_edge)
                    if method in ["aca", "aca_no_margin", "cbba_partial_lr", "ssi_lr"]:
                        recourse_detours += 1

            # Check task completion during physical execution
            for rid, r in robots.items():
                assigned_b = bundles.get(rid, [])
                target_t = current_robot_targets.get(rid)
                if target_t is not None and target_t not in completed_tasks:
                    curr_xy = r.get_ground_truth_pose()[:2]
                    t_pos = pos_dict[tasks[target_t].node]
                    dist_to_task = math.hypot(curr_xy[0] - t_pos[0], curr_xy[1] - t_pos[1])
                    if dist_to_task < 3.0:
                        completed_tasks.add(target_t)
                        tasks[target_t].completed = True
                        event_log.append({"step": step, "event": "task_completed", "task_id": target_t, "robot_id": rid})
                        # Advance to next task in bundle if available
                        remaining_b = [t for t in assigned_b if t not in completed_tasks]
                        next_t = remaining_b[0] if remaining_b else None
                        current_robot_targets[rid] = next_t
                        if next_t is not None:
                            wps = adapter.compute_waypoint_path(
                                robot_id=rid,
                                target_task_id=next_t,
                                start_pos=curr_xy,
                                blocked_edges=known_blocked_edges,
                            )
                            r.set_path(wps)
                        else:
                            r.set_path([])

        if record_history:
            step_state = {
                "step": step,
                "sim_time": step * 0.8,
                "robots": {
                    rid: {
                        "ground_truth_pos": list(r.get_ground_truth_pose()[:2]),
                        "ground_truth_theta": float(r.get_ground_truth_pose()[2]),
                        "current_path": [list(p) for p in r.current_path],
                        "state": "MOVING" if len(r.current_path) > 1 else "IDLE",
                    }
                    for rid, r in robots.items()
                },
                "tasks": {
                    tid: {
                        "pos": list(pos_dict[t.node]),
                        "completed": t.completed,
                        "claimed_by": next((rid for rid, b in bundles.items() if tid in b), None),
                    }
                    for tid, t in tasks.items()
                },
                "blockages": [list(e) for e in curr_blocked],
                "completed_tasks": len(completed_tasks),
                "completion_rate_pct": float(len(completed_tasks) / n_tasks) * 100.0,
                "recourse_pivots": recourse_detours,
                "comm_metrics": comm_layer.get_telemetry(),
            }
            event_log.append({"step": step, "type": "step_snapshot", "snapshot": step_state})

        if len(completed_tasks) == n_tasks:
            break

    trial_wall_time = time.perf_counter() - trial_start_wall

    for r in robots.values():
        total_distance_m += r.total_distance_traveled

    comm_telem = comm_layer.get_telemetry()
    completion_rate = float(len(completed_tasks) / n_tasks) * 100.0

    # Net welfare: sum(rewards) - travel_cost
    gross_reward = len(completed_tasks) * 100.0
    net_welfare = float(gross_reward - total_distance_m * 2.0)

    # Cleanup PyBullet world
    world.close()

    result_record = {
        "commit": get_git_commit(),
        "disclaimer": "SIMULATION -- PyBullet SITL -- No Physical Robot",
        "seed": seed,
        "map_type": map_type,
        "method": method,
        "adversary": adversary_name,
        "comm_regime": comm_regime,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "completed_tasks": len(completed_tasks),
        "completion_rate_pct": completion_rate,
        "total_conflicts": total_conflicts,
        "recourse_detours": recourse_detours,
        "physical_collisions": physical_collisions,
        "total_distance_meters": float(total_distance_m),
        "net_welfare": net_welfare,
        "messages_transmitted": comm_telem["messages_transmitted"],
        "messages_delivered": comm_telem["messages_delivered"],
        "messages_dropped": comm_telem["total_messages_dropped"],
        "runtime_seconds": float(trial_wall_time),
        "status": "COMPLETED",
    }

    if record_history:
        result_record["history"] = [e["snapshot"] for e in event_log if e.get("type") == "step_snapshot"]

    if save_raw_log:
        raw_log_file = os.path.join(RESULTS_RAW_DIR, f"sitl_raw_{map_type}_{method}_{adversary_name}_{comm_regime}_{seed}.json")
        with open(raw_log_file, "w", encoding="utf-8") as f:
            json.dump({"result": result_record, "events": event_log}, f, indent=2)

    return result_record


def run_pilot_benchmark():
    """Run short pilot to measure actual execution time per trial and print exact ETA."""
    print("=" * 70)
    print("Running SITL Pilot Benchmark to measure physical simulation execution speed...")
    pilot_seeds = [2001, 2002]
    pilot_times = []

    for s in pilot_seeds:
        t0 = time.perf_counter()
        res = run_single_sitl_trial(
            map_type="warehouse_movingai",
            method="aca",
            adversary_name="reactive",
            comm_regime="constrained",
            seed=s,
            save_raw_log=False,
        )
        elapsed = time.perf_counter() - t0
        pilot_times.append(elapsed)
        print(f"  Pilot trial (seed {s}): completed in {elapsed:.3f} s (completion: {res['completion_rate_pct']}%)")

    mean_trial_time = float(np.mean(pilot_times))
    print(f"Measured mean pilot execution time per trial: {mean_trial_time:.3f} seconds.")
    print("=" * 70)
    return mean_trial_time


def load_sitl_graph(map_type: str) -> nx.Graph:
    """Load graph topology identical to PhysicsWorld."""
    from acalib.env.real_maps import generate_movingai_warehouse, generate_real_road_network, DATA_MAPS_DIR
    if map_type == "warehouse_movingai":
        filepath = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
        return generate_movingai_warehouse(n_nodes=38, filepath=filepath)
    elif map_type == "road_osmnx":
        filepath = os.path.join(DATA_MAPS_DIR, "boston_downtown_drive.graphml")
        return generate_real_road_network(filepath=filepath)
    else:
        filepath = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
        return generate_movingai_warehouse(n_nodes=38, filepath=filepath)


def run_single_graph_sim_trial(
    map_type: str,
    method: str,
    adversary_name: str,
    comm_regime: str,
    seed: int,
    n_robots: int = 4,
    n_tasks: int = 8,
    max_steps: int = 20,
    adv_budget_k: int = 4,
) -> Dict[str, Any]:
    """Execute matched discrete graph simulation on identical instance and random seed."""
    trial_start_wall = time.perf_counter()
    rng = np.random.default_rng(seed)

    # 1. Graph topology (exact match to SITL)
    graph = load_sitl_graph(map_type)
    nodes = sorted(list(graph.nodes()))
    pos_dict = nx.get_node_attributes(graph, "pos")

    # 2. Communication layer
    comm_params = COMM_REGIME_PARAMS[comm_regime]
    comm_layer = SITLCommunicationLayer(
        comm_range=comm_params["comm_range"],
        p_drop=comm_params["p_drop"],
        latency_steps=comm_params["latency"],
        seed=int(rng.integers(0, 1000000)),
    )

    # 3. Tasks and Starts (exact match to SITL)
    starts = rng.choice(nodes, size=n_robots, replace=False).tolist()
    avail = [n for n in nodes if n not in starts]
    task_nodes = rng.choice(avail, size=n_tasks, replace=False).tolist()

    tasks: Dict[int, Task] = {}
    for tid in range(n_tasks):
        tasks[tid] = Task(
            task_id=tid,
            node=task_nodes[tid],
            reward=100.0,
            deadline=max_steps + 10,
            arrival_step=0,
        )

    # 4. Adversary and blockage process (exact match to SITL)
    if adversary_name == "stochastic":
        adv_type = AdversaryType.STOCHASTIC
    elif adversary_name == "reactive":
        adv_type = AdversaryType.REACTIVE
    elif adversary_name == "budgeted":
        adv_type = AdversaryType.BUDGETED
    elif adversary_name == "cyclic":
        adv_type = AdversaryType.CYCLIC_PATROL
    elif adversary_name in ["real_trace", "real_trace_replay"]:
        adv_type = AdversaryType.REAL_TRACE_REPLAY
    else:
        adv_type = AdversaryType.STOCHASTIC

    adversary = create_adversary(adv_type, budget_k=adv_budget_k, clearance_rate=0.15)
    edge_bc = nx.edge_betweenness_centrality(graph)
    sorted_edges = sorted(edge_bc.items(), key=lambda x: x[1], reverse=True)
    risky_edges = {canonical_edge(u, v) for (u, v), _ in sorted_edges[:6]}

    blockage_proc = PersistentBlockageProcess(
        graph=graph,
        adversary=adversary,
        risk_fraction=0.25,
        clearance_rate=0.15,
        custom_risky_edges=risky_edges,
        seed=int(rng.integers(0, 1000000)),
    )

    # 5. Allocator & Adapter
    r_depth = 1 if (method.startswith("aca") or method.endswith("_lr") or method == "implicit") else 0
    adapter = SITLAllocatorAdapter(
        method_name=method,
        graph=graph,
        n_robots=n_robots,
        tasks=tasks,
        comm_net=comm_layer,
        contingency_depth=r_depth,
    )

    robot_nodes = {rid: starts[rid] for rid in range(n_robots)}
    completed_tasks = set()
    total_conflicts = 0
    recourse_detours = 0
    total_distance_m = 0.0
    known_blocked_edges: Set[Tuple[int, int]] = set()

    for step in range(max_steps):
        fleet_states = {rid: {"current_node": robot_nodes[rid]} for rid in range(n_robots)}
        blockage_proc.step(fleet_states, step)
        curr_blocked = blockage_proc.get_blocked_edges()

        # Comm exchange
        est_poses = {rid: (pos_dict[robot_nodes[rid]][0], pos_dict[robot_nodes[rid]][1], 0.0) for rid in range(n_robots)}
        for r_i in range(n_robots):
            for r_j in range(n_robots):
                if r_i != r_j:
                    comm_layer.send_message(
                        sender_id=r_i,
                        receiver_id=r_j,
                        payload={"step": step, "blocked": list(known_blocked_edges)},
                        sender_pos=est_poses[r_i][:2],
                        receiver_pos=est_poses[r_j][:2],
                        current_step=step,
                    )
        comm_layer.step_network(step)

        # Plan round
        bundles = adapter.plan_round(step, est_poses, known_blocked_edges)

        all_claimed = []
        for rid, b in bundles.items():
            all_claimed.extend(b)
        conflicts_step = len(all_claimed) - len(set(all_claimed))
        total_conflicts += max(0, conflicts_step)

        # Step robots along graph shortest paths toward target task
        for rid in range(n_robots):
            assigned_b = bundles.get(rid, [])
            rem_b = [t for t in assigned_b if t not in completed_tasks]
            if not rem_b:
                continue
            target_t = rem_b[0]
            target_node = tasks[target_t].node

            if robot_nodes[rid] == target_node:
                completed_tasks.add(target_t)
                tasks[target_t].completed = True
                continue

            sub_g = graph.copy()
            for u, v in known_blocked_edges:
                if sub_g.has_edge(u, v):
                    sub_g.remove_edge(u, v)

            try:
                if nx.has_path(sub_g, robot_nodes[rid], target_node):
                    path = nx.shortest_path(sub_g, robot_nodes[rid], target_node, weight="weight")
                else:
                    path = nx.shortest_path(graph, robot_nodes[rid], target_node, weight="weight")
            except Exception:
                path = [robot_nodes[rid], target_node]

            if len(path) > 1:
                next_node = path[1]
                edge_cand = canonical_edge(robot_nodes[rid], next_node)
                if edge_cand in curr_blocked:
                    known_blocked_edges.add(edge_cand)
                    if method in ["aca", "aca_no_margin", "cbba_partial_lr", "ssi_lr"]:
                        recourse_detours += 1
                else:
                    d_step = float(np.hypot(
                        pos_dict[next_node][0] - pos_dict[robot_nodes[rid]][0],
                        pos_dict[next_node][1] - pos_dict[robot_nodes[rid]][1]
                    ))
                    total_distance_m += d_step
                    robot_nodes[rid] = next_node
                    if robot_nodes[rid] == target_node:
                        completed_tasks.add(target_t)
                        tasks[target_t].completed = True

        if len(completed_tasks) == n_tasks:
            break

    trial_wall = time.perf_counter() - trial_start_wall
    comm_telem = comm_layer.get_telemetry()
    completion_rate = float(len(completed_tasks) / n_tasks) * 100.0
    net_welfare = float(len(completed_tasks) * 100.0 - total_distance_m * 2.0)

    return {
        "commit": get_git_commit(),
        "disclaimer": "SIMULATION -- Discrete Graph Simulation",
        "seed": seed,
        "map_type": map_type,
        "method": method,
        "adversary": adversary_name,
        "comm_regime": comm_regime,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "completed_tasks": len(completed_tasks),
        "completion_rate_pct": completion_rate,
        "total_conflicts": total_conflicts,
        "recourse_detours": recourse_detours,
        "physical_collisions": 0,
        "total_distance_meters": float(total_distance_m),
        "net_welfare": net_welfare,
        "messages_transmitted": comm_telem["messages_transmitted"],
        "messages_delivered": comm_telem["messages_delivered"],
        "messages_dropped": comm_telem["total_messages_dropped"],
        "runtime_seconds": float(trial_wall),
        "status": "COMPLETED",
    }


def _sitl_worker_task(task_args: Tuple[str, str, str, str, int]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Top-level worker function executing both physical SITL and matched graph simulation."""
    mp, m, adv, cr, seed = task_args
    try:
        sitl_rec = run_single_sitl_trial(
            map_type=mp,
            method=m,
            adversary_name=adv,
            comm_regime=cr,
            seed=seed,
            save_raw_log=True,
        )
    except Exception as e:
        sitl_rec = {
            "commit": get_git_commit(),
            "disclaimer": "SIMULATION -- PyBullet SITL",
            "seed": seed,
            "map_type": mp,
            "method": m,
            "adversary": adv,
            "comm_regime": cr,
            "status": f"FAILED: {str(e)}",
        }

    try:
        graph_rec = run_single_graph_sim_trial(
            map_type=mp,
            method=m,
            adversary_name=adv,
            comm_regime=cr,
            seed=seed,
        )
    except Exception as e:
        graph_rec = {
            "commit": get_git_commit(),
            "disclaimer": "SIMULATION -- Discrete Graph Simulation",
            "seed": seed,
            "map_type": mp,
            "method": m,
            "adversary": adv,
            "comm_regime": cr,
            "status": f"FAILED: {str(e)}",
        }

    return sitl_rec, graph_rec


def main():
    from concurrent.futures import ProcessPoolExecutor, as_completed
    parser = argparse.ArgumentParser(description="PyBullet SITL Benchmark Sweep Runner")
    parser.add_argument("--trials-per-cell", type=int, default=20, help="Number of trials per cell (>= 20)")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4), help="Number of parallel worker processes")
    parser.add_argument("--output-jsonl", type=str, default=os.path.join(RESULTS_SITL_DIR, "sitl_results.jsonl"))
    parser.add_argument("--output-graph-jsonl", type=str, default=os.path.join(RESULTS_SITL_DIR, "graph_results.jsonl"))
    args = parser.parse_args()

    # Pre-registered methods
    methods = [
        "aca",
        "aca_no_margin",
        "ctp_replan",
        "implicit",
        "cbba_partial_lr",
        "ssi_lr",
    ]
    maps = ["warehouse_movingai", "road_osmnx"]
    adversaries = ["reactive", "stochastic", "real_trace"]
    comm_regimes = ["nominal", "constrained", "lossy"]

    total_cells = len(maps) * len(adversaries) * len(comm_regimes)
    total_matched_instances = total_cells * args.trials_per_cell
    total_planned_runs = total_matched_instances * len(methods)

    print(f"SITL Experiment Configuration (Matched Seeds & Discrete Graph Comparison):")
    print(f"  Methods ({len(methods)}): {methods}")
    print(f"  Maps ({len(maps)}): {maps}")
    print(f"  Adversaries ({len(adversaries)}): {adversaries}")
    print(f"  Comm Regimes ({len(comm_regimes)}): {comm_regimes}")
    print(f"  Total Cells: {total_cells}")
    print(f"  Matched Instances per Cell: {args.trials_per_cell}")
    print(f"  Total Matched Instances: {total_matched_instances}")
    print(f"  Total Planned Runs (SITL + Graph-Sim): {total_planned_runs} each")
    print(f"  Parallel Workers: {args.workers}")

    # Measure pilot
    mean_t = run_pilot_benchmark()
    est_total_seconds = (mean_t * total_planned_runs) / max(1, args.workers)
    print(f"Estimated Total Walltime: {est_total_seconds:.1f} s ({est_total_seconds / 60.0:.2f} minutes) across {args.workers} workers.")
    print("=" * 70)

    # Disjoint seeds starting at 20000, perfectly matched across all methods
    base_seed = 20000
    instances = []
    for mp in maps:
        for adv in adversaries:
            for cr in comm_regimes:
                for rep in range(args.trials_per_cell):
                    seed = base_seed + len(instances)
                    instances.append({
                        "map_type": mp,
                        "adversary": adv,
                        "comm_regime": cr,
                        "seed": seed,
                    })

    task_list = []
    for inst in instances:
        for m in methods:
            task_list.append((inst["map_type"], m, inst["adversary"], inst["comm_regime"], inst["seed"]))

    out_file_sitl = args.output_jsonl
    out_file_graph = args.output_graph_jsonl
    completed_sitl = []
    completed_graph = []

    # Write results incrementally as tasks complete
    with open(out_file_sitl, "w", encoding="utf-8") as f_sitl, open(out_file_graph, "w", encoding="utf-8") as f_graph:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_task = {executor.submit(_sitl_worker_task, t): t for t in task_list}
            done_count = 0
            for future in as_completed(future_to_task):
                done_count += 1
                try:
                    s_rec, g_rec = future.result()
                except Exception as exc:
                    t = future_to_task[future]
                    s_rec = {
                        "commit": get_git_commit(),
                        "disclaimer": "SIMULATION -- PyBullet SITL",
                        "seed": t[4],
                        "map_type": t[0],
                        "method": t[1],
                        "adversary": t[2],
                        "comm_regime": t[3],
                        "status": f"FAILED: {str(exc)}",
                    }
                    g_rec = {
                        "commit": get_git_commit(),
                        "disclaimer": "SIMULATION -- Discrete Graph Simulation",
                        "seed": t[4],
                        "map_type": t[0],
                        "method": t[1],
                        "adversary": t[2],
                        "comm_regime": t[3],
                        "status": f"FAILED: {str(exc)}",
                    }
                f_sitl.write(json.dumps(s_rec) + "\n")
                f_sitl.flush()
                f_graph.write(json.dumps(g_rec) + "\n")
                f_graph.flush()
                completed_sitl.append(s_rec)
                completed_graph.append(g_rec)

                if done_count % 100 == 0 or done_count == total_planned_runs:
                    n_succ = len([r for r in completed_sitl if r.get("status") == "COMPLETED"])
                    print(f"  Progress: {done_count}/{total_planned_runs} paired trials completed ({n_succ} successful).")

    print(f"SITL evaluation sweep finished: {len(completed_sitl)} SITL records saved to {out_file_sitl}, {len(completed_graph)} Graph records saved to {out_file_graph}.")


if __name__ == "__main__":
    main()

