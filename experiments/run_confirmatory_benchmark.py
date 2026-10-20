"""
Unified Confirmatory Benchmark Runner for IEEE RA-L Manuscript.
Executes:
1. 750 matched instances (50 disjoint evaluation seeds x 5 graph families x 3 canonical adversaries)
   across all 17 methods/ablations.
2. Sensitivity & out-of-model sweeps (theta_4 cyclic patrol, comm regimes: benign, constrained, lossy).
3. Theorem 1 per-claim evaluations logging (results/per_claim_evaluations.jsonl).
4. SITL 360-instance benchmark in PyBullet (results/sitl/sitl_results.jsonl).
"""

import os
import sys
import time
import json
import math
from typing import Dict, Any, List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial
from experiments.sitl.run_sitl import run_single_sitl_trial
from acalib.utils.gitinfo import get_git_commit

ENVIRONMENTS = [
    ("warehouse_movingai", 38),
    ("road_osmnx", 216),
    ("rgg", 35),
    ("warehouse", 30),
    ("er", 35),
]

CANONICAL_ADVERSARIES = [
    "theta_1_stochastic",
    "theta_2_reactive",
    "theta_3_budgeted_interdiction",
]

CORE_METHODS = [
    "aca",
    "aca_no_margin",
    "aca_depth_0",
    "aca_depth_2",
    "aca_no_inference",
    "cbba",
    "cbba_lr",
    "cbba_partial",
    "cbba_partial_lr",
    "cc_cbba",
    "cc_cbba_lr",
    "cbba_gossip",
    "ssi",
    "ssi_lr",
    "ctp_replan",
    "implicit",
    "clairvoyant_greedy",
]

EVAL_SEEDS = list(range(101, 151))  # 50 disjoint confirmatory seeds


def _worker_discrete_trial(args: Tuple) -> Dict[str, Any]:
    fam, n_nodes, adv, method, regime, c_range, p_d, n_robots, n_tasks, seed, max_steps, c_depth = args
    res = run_single_trial(
        graph_family=fam,
        n_nodes=n_nodes,
        adversary_type_str=adv,
        allocator_name=method,
        comm_regime=regime,
        comm_range=c_range,
        p_drop=p_d,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=c_depth,
    )
    return res


def _worker_sitl_trial(args: Tuple) -> Dict[str, Any]:
    map_type, method, adv, comm_regime, seed = args
    res = run_single_sitl_trial(
        map_type=map_type,
        method=method,
        adversary_name=adv,
        comm_regime=comm_regime,
        seed=seed,
        n_robots=4,
        n_tasks=8,
        max_steps=20,
        save_raw_log=False,
    )
    return res


def run_confirmatory_benchmark(max_workers: int = None):
    if max_workers is None:
        max_workers = min(12, os.cpu_count() or 4)

    print("=" * 75)
    print("STARTING UNIFIED CONFIRMATORY BENCHMARK (PHASE 2)")
    print(f"Workers: {max_workers} | Commit: {get_git_commit()}")
    print("=" * 75)

    # 1. Assemble Core Matched Tasks (750 instances x 17 methods)
    tasks_core = []
    for fam, n_nodes in ENVIRONMENTS:
        for adv in CANONICAL_ADVERSARIES:
            for seed in EVAL_SEEDS:
                for method in CORE_METHODS:
                    c_depth = 2 if method == "aca_depth_2" else (0 if (method in ("aca_depth_0", "cbba", "cbba_partial", "cc_cbba", "ssi", "ctp_replan")) else 1)
                    tasks_core.append((
                        fam, n_nodes, adv, method, "nominal", 30.0, 0.10, 4, 15, seed, 80, c_depth
                    ))

    # 2. Assemble Out-of-Model & Comm Regime Sweeps
    tasks_sweeps = []
    sweep_methods = ["aca", "cbba", "cbba_lr", "ctp_replan", "implicit", "ssi_lr"]
    # theta_4 sweep
    for fam, n_nodes in ENVIRONMENTS:
        for seed in EVAL_SEEDS[:20]:
            for method in sweep_methods:
                c_depth = 0 if method in ("cbba", "ctp_replan") else 1
                tasks_sweeps.append((
                    fam, n_nodes, "theta_4_cyclic_patrol", method, "nominal", 30.0, 0.10, 4, 15, seed, 80, c_depth
                ))
    # Comm regime sweeps (benign, constrained, lossy)
    regimes = [
        ("benign", 50.0, 0.02),
        ("constrained", 25.0, 0.15),
        ("lossy", 20.0, 0.30),
    ]
    for reg_name, c_range, p_d in regimes:
        for fam, n_nodes in ENVIRONMENTS:
            for seed in EVAL_SEEDS[:20]:
                for method in sweep_methods:
                    c_depth = 0 if method in ("cbba", "ctp_replan") else 1
                    tasks_sweeps.append((
                        fam, n_nodes, "theta_2_reactive", method, reg_name, c_range, p_d, 4, 15, seed, 80, c_depth
                    ))

    all_discrete_tasks = tasks_core + tasks_sweeps
    print(f"Total Discrete Benchmark Tasks: {len(all_discrete_tasks)} ({len(tasks_core)} core + {len(tasks_sweeps)} sweeps)")

    # Execute discrete trials
    os.makedirs(os.path.join(REPO_ROOT, "results"), exist_ok=True)
    raw_csv_path = os.path.join(REPO_ROOT, "results", "raw_results.csv")
    runs_jsonl_path = os.path.join(REPO_ROOT, "results", "runs.jsonl")
    claims_jsonl_path = os.path.join(REPO_ROOT, "results", "per_claim_evaluations.jsonl")

    t0 = time.time()
    discrete_results = []
    claim_records = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker_discrete_trial, task): task for task in all_discrete_tasks}
        completed = 0
        total = len(all_discrete_tasks)
        for f in as_completed(futures):
            completed += 1
            rec = f.result()
            discrete_results.append(rec)

            # Extract genuine claim log if method is aca or aca_no_margin
            genuine_claim_logs = rec.pop("per_claim_logs", [])
            m = rec.get("method")
            if m in ("aca", "aca_no_margin"):
                claim_records.append({
                    "commit": rec.get("git_commit", "confirmatory"),
                    "graph_family": rec.get("graph_family"),
                    "seed": rec.get("seed"),
                    "adversary": rec.get("adversary"),
                    "comm_regime": rec.get("comm_regime"),
                    "p_drop": rec.get("p_drop"),
                    "total_claims": len(genuine_claim_logs),
                    "claims": genuine_claim_logs,
                })

            if completed % 1000 == 0 or completed == total:
                elapsed = time.time() - t0
                rate = completed / max(0.001, elapsed)
                print(f"[{completed}/{total}] Discrete Trials Complete ({rate:.1f} trials/s, {elapsed:.1f}s elapsed)")

    # Save discrete results
    df_discrete = pd.DataFrame(discrete_results)
    df_discrete.to_csv(raw_csv_path, index=False)
    with open(runs_jsonl_path, "w", encoding="utf-8") as f:
        for r in discrete_results:
            f.write(json.dumps(r) + "\n")

    with open(claims_jsonl_path, "w", encoding="utf-8") as f:
        for c in claim_records:
            f.write(json.dumps(c) + "\n")

    print(f"-> Saved {len(discrete_results)} discrete records to {raw_csv_path} and {runs_jsonl_path}")
    print(f"-> Saved {len(claim_records)} claim records to {claims_jsonl_path}")

    # 3. Assemble PyBullet SITL Benchmark (360 trials)
    # 6 methods x 2 maps x 3 adversaries x 10 seeds = 360 runs
    sitl_methods = ["aca", "aca_no_margin", "ctp_replan", "implicit", "cbba_partial_lr", "ssi_lr"]
    sitl_maps = ["warehouse_movingai", "road_osmnx"]
    sitl_adversaries = ["reactive", "stochastic", "real_trace"]
    sitl_seeds = list(range(20000, 20010))  # 10 seeds

    sitl_tasks = []
    for mp in sitl_maps:
        for adv in sitl_adversaries:
            for seed in sitl_seeds:
                for m in sitl_methods:
                    sitl_tasks.append((mp, m, adv, "nominal", seed))

    print(f"\nTotal PyBullet SITL Benchmark Tasks: {len(sitl_tasks)} (6 methods x 60 instances = 360 runs)")
    t_sitl_start = time.time()
    sitl_results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker_sitl_trial, task): task for task in sitl_tasks}
        completed = 0
        total = len(sitl_tasks)
        for f in as_completed(futures):
            completed += 1
            res = f.result()
            sitl_results.append(res)
            if completed % 60 == 0 or completed == total:
                elapsed = time.time() - t_sitl_start
                print(f"[{completed}/{total}] SITL Trials Complete ({elapsed:.1f}s elapsed)")

    sitl_jsonl_path = os.path.join(REPO_ROOT, "results", "sitl", "sitl_results.jsonl")
    os.makedirs(os.path.dirname(sitl_jsonl_path), exist_ok=True)
    with open(sitl_jsonl_path, "w", encoding="utf-8") as f:
        for r in sitl_results:
            f.write(json.dumps(r) + "\n")
    print(f"-> Saved {len(sitl_results)} SITL records to {sitl_jsonl_path}")
    print("\nBENCHMARK RUN COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_confirmatory_benchmark()
