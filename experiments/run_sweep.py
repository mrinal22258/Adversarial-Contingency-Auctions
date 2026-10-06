"""
Parallel Seeded Experiment Runner.
Executes paired experimental trials across graph families, adversary types, and allocation mechanisms.
Outputs granular per-trial results to CSV for statistical post-processing.
"""

import os
import sys
import time
import json
import shutil
import subprocess
import traceback
import argparse
from typing import Dict, List, Any
import concurrent.futures
import yaml
import pandas as pd
import numpy as np

# Ensure acalib is importable from workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash if in a git repository."""
    git_bins = ["git", r"C:\Program Files\Git\cmd\git.exe"]
    for git_bin in git_bins:
        try:
            commit = subprocess.check_output([git_bin, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode("ascii").strip()
            return commit
        except Exception:
            pass
    return "unknown"


def run_single_trial(
    graph_family: str,
    n_nodes: int,
    adversary_type_str: str,
    allocator_name: str,
    n_robots: int,
    n_tasks: int,
    seed: int,
    max_steps: int = 90,
    contingency_depth: int = 1,
) -> Dict[str, Any]:
    """Execute a single trial and return a dictionary of conditions and metrics."""
    # 1. Generate identical graph for this seed
    graph = generate_graph(family=graph_family, n_nodes=n_nodes, seed=seed)

    # 2. Map adversary string to enum
    adv_enum = AdversaryType(adversary_type_str)

    # Contingency depth: ACA, ACA-NoMargin, and Implicit use recourse depth; others depth 0
    if allocator_name in ("aca", "aca_no_margin", "implicit"):
        c_depth = contingency_depth
    else:
        c_depth = 0

    # 3. Instantiate and run simulation
    engine = SimulationEngine(
        graph=graph,
        adversary_type=adv_enum,
        allocator_type=allocator_name,
        n_robots=n_robots,
        n_tasks=n_tasks,
        task_deadline=max_steps,
        max_steps=max_steps,
        contingency_depth=c_depth,
        seed=seed,
    )

    metrics = engine.run(max_steps=max_steps)
    summary = metrics.compute_summary()

    # Prepend condition metadata
    row = {
        "graph_family": graph_family,
        "n_nodes": n_nodes,
        "adversary": adversary_type_str,
        "method": allocator_name,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "seed": seed,
        "contingency_depth": c_depth,
    }
    row.update(summary)
    return row


def _worker_wrapper(args_tuple):
    """Wrapper function for multiprocessing execution."""
    return run_single_trial(*args_tuple)


def main():
    parser = argparse.ArgumentParser(description="Run ACA benchmarks across literature baselines")
    parser.add_argument("--config", type=str, default="experiments/configs/main_benchmark.yaml", help="Path to config YAML")
    parser.add_argument("--seeds", type=int, default=None, help="Number of paired seeds per cell (overrides YAML)")
    parser.add_argument("--output", type=str, default="results/raw_results.csv", help="Path to output CSV")
    parser.add_argument("--fast", action="store_true", help="Run fast verification subset")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel worker processes")
    parser.add_argument("--robots", type=int, default=None, help="Fleet size override")
    parser.add_argument("--tasks", type=int, default=None, help="Task count override")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    yaml_config = {}
    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}

    if args.fast:
        families = [("rgg", 30), ("warehouse", 25)]
        adversaries = [
            AdversaryType.STOCHASTIC.value,
            AdversaryType.REACTIVE.value,
            AdversaryType.BUDGETED_INTERDICTION.value,
            AdversaryType.CYCLIC_PATROL.value,
        ]
        methods = [
            "aca",
            "aca_no_margin",
            "aca_depth_0",
            "cbba",
            "cbba_partial",
            "cc_cbba",
            "implicit",
            "ssi",
            "pessimistic",
            "oracle",
        ]
        n_seeds = args.seeds if args.seeds is not None else 5
        max_steps = 70
        n_robots = args.robots if args.robots is not None else 4
        n_tasks = args.tasks if args.tasks is not None else 15
    else:
        # Load from YAML
        if yaml_config and "environments" in yaml_config:
            families = [(env["family"], env["n_nodes"]) for env in yaml_config["environments"]]
            adversaries = [adv for adv in yaml_config.get("adversaries", [])]
            methods = yaml_config.get("methods", [
                "aca", "aca_no_margin", "aca_depth_0",
                "cbba", "cbba_partial", "cc_cbba", "implicit", "ssi", "pessimistic", "oracle"
            ])
            n_seeds = args.seeds if args.seeds is not None else yaml_config.get("seeds", 10)
            max_steps = yaml_config.get("max_steps", 90)
            n_robots = args.robots if args.robots is not None else yaml_config.get("fleet_sizes", [4])[0]
            n_tasks = args.tasks if args.tasks is not None else yaml_config.get("task_counts", [15])[0]
        else:
            families = [("rgg", 35), ("warehouse", 30), ("er", 35)]
            adversaries = [
                AdversaryType.STOCHASTIC.value,
                AdversaryType.REACTIVE.value,
                AdversaryType.BUDGETED_INTERDICTION.value,
                AdversaryType.CYCLIC_PATROL.value,
            ]
            methods = [
                "aca",
                "aca_no_margin",
                "aca_depth_0",
                "cbba",
                "cbba_partial",
                "cc_cbba",
                "implicit",
                "ssi",
                "pessimistic",
                "oracle",
            ]
            n_seeds = args.seeds if args.seeds is not None else 10
            max_steps = 90
            n_robots = args.robots if args.robots is not None else 4
            n_tasks = args.tasks if args.tasks is not None else 15

    # Assemble task tuples
    task_tuples = []
    for fam, n_nodes in families:
        for adv in adversaries:
            for seed in range(1, n_seeds + 1):
                for method in methods:
                    task_tuples.append((
                        fam,
                        n_nodes,
                        adv,
                        method,
                        n_robots,
                        n_tasks,
                        seed,
                        max_steps,
                    ))

    total_runs = len(task_tuples)
    print(f"Starting parallel experiment sweep: {total_runs} total runs across {n_seeds} paired seeds.")
    print(f"Families: {families}")
    print(f"Adversaries: {adversaries}")
    print(f"Methods: {methods}")
    print(f"Workers: {args.workers}")

    results: List[Dict[str, Any]] = []
    t0 = time.time()

    if args.workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            # Map over task tuples
            future_to_task = {executor.submit(_worker_wrapper, t): t for t in task_tuples}
            completed = 0
            for future in concurrent.futures.as_completed(future_to_task):
                completed += 1
                task = future_to_task[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    print(f"CRITICAL ERROR on task {task}: {e}")
                    traceback.print_exc()
                    raise e

                if completed % 25 == 0 or completed == total_runs:
                    elapsed = time.time() - t0
                    rate = completed / max(0.1, elapsed)
                    print(f"[{completed}/{total_runs}] ({rate:.1f} runs/s) - Latest finished: {task[3]} on {task[0]}/{task[2]} seed {task[6]}")
    else:
        for idx, task in enumerate(task_tuples):
            res = run_single_trial(*task)
            results.append(res)
            if (idx + 1) % 25 == 0 or (idx + 1) == total_runs:
                elapsed = time.time() - t0
                rate = (idx + 1) / max(0.1, elapsed)
                print(f"[{idx + 1}/{total_runs}] ({rate:.1f} runs/s)")

    df = pd.DataFrame(results)
    # Sort deterministically
    df = df.sort_values(["graph_family", "adversary", "seed", "method"]).reset_index(drop=True)
    df.to_csv(args.output, index=False)
    print(f"\nCompleted! Saved {len(df)} rows to {args.output}")

    # Copy config used alongside results
    config_copy_path = os.path.join(os.path.dirname(args.output), "config_used.yaml")
    if os.path.exists(args.config):
        shutil.copyfile(args.config, config_copy_path)

    # Save run metadata alongside results
    meta_path = os.path.join(os.path.dirname(args.output), "run_metadata.json")
    import scipy
    metadata = {
        "commit": get_git_commit_hash(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "total_trials": len(df),
        "families": families,
        "adversaries": adversaries,
        "methods": methods,
        "n_seeds": n_seeds,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "max_steps": max_steps,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved run metadata to {meta_path}")


if __name__ == "__main__":
    main()
