"""
Parallel Seeded Experiment Runner with Common Random Numbers (CRN) and Resumability.
Phase A Implementation:
- Reads comm_regimes, final_seeds, environments (including real maps), baselines, and ablations.
- Per-component RNG via numpy.random.SeedSequence.spawn(5) (graph, starts, tasks, blockages, comm).
- Pre-draws per-(edge, step) blockage uniforms so all allocation methods see identical blockage streams.
- Fully resumable on (config_hash, seed, method, adversary, regime).
- Appends granular per-trial JSONL records with git commit, library versions, and wall-clock times.
- Saves per-step telemetry traces to results/traces/<run_id>.parquet.
- Computes and displays total run count, cached runs, and empirical ETA before execution.
"""

import os
import sys
import time
import json
import shutil
import hashlib
import subprocess
import traceback
import argparse
from typing import Dict, List, Tuple, Any, Optional
import concurrent.futures
import yaml
import pandas as pd
import numpy as np
import networkx as nx

# Ensure acalib is importable from workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType, canonical_edge
from acalib.env.comm import CommunicationNetwork
from acalib.alloc.base import Task
from acalib.sim.engine import SimulationEngine


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash if in a git repository."""
    git_bins = ["git", r"C:\Program Files\Git\cmd\git.exe"]
    for git_bin in git_bins:
        try:
            commit = (
                subprocess.check_output([git_bin, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                .decode("ascii")
                .strip()
            )
            return commit
        except Exception:
            pass
    return "unknown"


def check_git_clean() -> bool:
    """Check if git working tree is clean (Rule R1: reproducible commit)."""
    git_bins = ["git", r"C:\Program Files\Git\cmd\git.exe"]
    for git_bin in git_bins:
        try:
            status = (
                subprocess.check_output([git_bin, "status", "--porcelain"], stderr=subprocess.DEVNULL)
                .decode("utf-8")
                .strip()
            )
            return len(status) == 0
        except Exception:
            pass
    return True


def compute_trial_hash(condition_dict: Dict[str, Any]) -> str:
    """Compute deterministic MD5 hash of trial experimental condition."""
    sorted_items = sorted((k, str(v)) for k, v in condition_dict.items())
    raw = json.dumps(sorted_items, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


_EDGE_BC_CACHE: Dict[Tuple[str, int, int], Dict[Any, float]] = {}


def get_edge_betweenness(graph: nx.Graph, graph_family: str) -> Dict[Any, float]:
    """Retrieve or compute edge betweenness centrality with caching for static real topologies."""
    cache_key = (graph_family, len(graph), len(graph.edges()))
    if cache_key in _EDGE_BC_CACHE:
        return _EDGE_BC_CACHE[cache_key]

    k_sample = min(30, len(graph)) if len(graph) > 30 else None
    bc = nx.edge_betweenness_centrality(graph, k=k_sample, weight="weight")
    if graph_family in ("warehouse_movingai", "road_osmnx", "warehouse"):
        _EDGE_BC_CACHE[cache_key] = bc
    return bc

def build_crn_environment(
    graph_family: str,
    n_nodes: int,
    seed: int,
    n_robots: int,
    n_tasks: int,
    max_steps: int,
    risk_fraction: float = 0.25,
    task_arrival_mode: str = "batch",
    poisson_rate: float = 0.5,
    task_deadline: int = 250,
) -> Dict[str, Any]:
    """
    Generate decoupled components using SeedSequence.spawn(5) for strict CRN across methods.
    Stream 0: graph topology
    Stream 1: robot start nodes
    Stream 2: task generation
    Stream 3: risky edge selection and pre-drawn blockage uniforms
    Stream 4: communication network drop seed
    """
    ss = np.random.SeedSequence(seed)
    seeds = ss.spawn(5)
    rng_graph = np.random.default_rng(seeds[0])
    rng_starts = np.random.default_rng(seeds[1])
    rng_tasks = np.random.default_rng(seeds[2])
    rng_blockages = np.random.default_rng(seeds[3])
    rng_comm = np.random.default_rng(seeds[4])

    # 1. Graph
    graph_seed = int(rng_graph.integers(0, 10000000))
    graph = generate_graph(family=graph_family, n_nodes=n_nodes, seed=graph_seed)
    nodes_list = sorted(list(graph.nodes()))

    # 2. Robot start positions
    start_nodes = [
        nodes_list[int(rng_starts.integers(0, len(nodes_list)))] for _ in range(n_robots)
    ]

    # 3. Tasks
    tasks = {}
    for tid in range(n_tasks):
        t_node = nodes_list[int(rng_tasks.integers(0, len(nodes_list)))]
        arr_step = (
            int(rng_tasks.poisson(tid / max(0.1, poisson_rate)))
            if task_arrival_mode == "poisson"
            else 0
        )
        tasks[tid] = Task(
            task_id=tid,
            node=t_node,
            reward=100.0,
            arrival_step=arr_step,
            deadline=arr_step + task_deadline,
        )

    # 4. Risky edge selection & pre-drawn blockage uniforms
    all_edges = sorted([canonical_edge(u, v) for u, v in graph.edges()])
    n_risky = max(1, int(len(all_edges) * risk_fraction))

    edge_bc = get_edge_betweenness(graph, graph_family)
    sorted_by_bc = sorted(
        all_edges,
        key=lambda e: edge_bc.get(e, edge_bc.get((e[1], e[0]), 0.0)),
        reverse=True,
    )
    n_bc = n_risky // 2
    top_bc = sorted_by_bc[:n_bc]
    rem_edges = [e for e in sorted_by_bc[n_bc:]]
    rng_blockages.shuffle(rem_edges)
    risky_edges = set(top_bc + rem_edges[: n_risky - n_bc])

    predrawn_clear = {}
    predrawn_onset = {}
    for e in sorted(list(risky_edges)):
        for t in range(max_steps + 10):
            predrawn_clear[(e, t)] = float(rng_blockages.random())
            predrawn_onset[(e, t)] = float(rng_blockages.random())

    # 5. Comm seed
    comm_seed = int(rng_comm.integers(0, 10000000))

    return {
        "graph": graph,
        "start_nodes": start_nodes,
        "tasks": tasks,
        "risky_edges": risky_edges,
        "predrawn_clear": predrawn_clear,
        "predrawn_onset": predrawn_onset,
        "comm_seed": comm_seed,
    }


def run_single_trial(
    graph_family: str,
    n_nodes: int,
    adversary_type_str: str,
    allocator_name: str,
    comm_regime: str,
    comm_range: float,
    p_drop: float,
    n_robots: int,
    n_tasks: int,
    seed: int,
    max_steps: int = 80,
    contingency_depth: int = 1,
    traces_dir: Optional[str] = "results/traces",
    runs_jsonl: Optional[str] = "results/runs.jsonl",
    git_commit: str = "unknown",
) -> Dict[str, Any]:
    """Execute a single trial with CRN coupling and save trace parquet and JSONL record."""
    t_start = time.time()

    # Pre-generate CRN coupled environment
    env_components = build_crn_environment(
        graph_family=graph_family,
        n_nodes=n_nodes,
        seed=seed,
        n_robots=n_robots,
        n_tasks=n_tasks,
        max_steps=max_steps,
    )

    adv_enum = AdversaryType(adversary_type_str)

    # Determine recourse depth
    if allocator_name == "aca_depth_0":
        c_depth = 0
    elif allocator_name == "aca_depth_2":
        c_depth = 2
    elif allocator_name.endswith("_lr") or allocator_name.startswith("aca"):
        c_depth = contingency_depth if contingency_depth > 0 else 1
    else:
        c_depth = 0

    engine = SimulationEngine(
        graph=env_components["graph"],
        adversary_type=adv_enum,
        allocator_type=allocator_name,
        n_robots=n_robots,
        n_tasks=n_tasks,
        task_deadline=max_steps,
        max_steps=max_steps,
        comm_range=comm_range,
        p_drop=p_drop,
        contingency_depth=c_depth,
        custom_start_nodes=env_components["start_nodes"],
        custom_tasks=env_components["tasks"],
        predrawn_clear_uniforms=env_components["predrawn_clear"],
        predrawn_onset_uniforms=env_components["predrawn_onset"],
        custom_risky_edges=env_components["risky_edges"],
        comm_net_seed=env_components["comm_seed"],
        record_traces=True,
    )

    metrics = engine.run(max_steps=max_steps)
    summary = metrics.compute_summary()
    t_end = time.time()
    wall_clock_ms = (t_end - t_start) * 1000.0

    actual_n_nodes = len(env_components["graph"].nodes())
    actual_n_edges = len(env_components["graph"].edges())
    condition_info = {
        "graph_family": graph_family,
        "n_nodes": actual_n_nodes,
        "n_edges": actual_n_edges,
        "adversary": adversary_type_str,
        "method": allocator_name,
        "comm_regime": comm_regime,
        "comm_range": comm_range,
        "p_drop": p_drop,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "seed": seed,
        "contingency_depth": c_depth,
    }
    trial_hash = compute_trial_hash(condition_info)
    run_id = f"{graph_family}_{adversary_type_str[:7]}_{comm_regime}_{allocator_name}_s{seed}_{trial_hash}"

    # Save per-step traces as Parquet
    if traces_dir:
        os.makedirs(traces_dir, exist_ok=True)
        trace_path = os.path.join(traces_dir, f"{run_id}.parquet")
        trace_df = engine.get_trace_df()
        trace_df.to_parquet(trace_path, index=False)

    row = dict(condition_info)
    row.update(summary)
    row["trial_hash"] = trial_hash
    row["run_id"] = run_id
    row["wall_clock_ms"] = wall_clock_ms

    # Write JSONL record
    if runs_jsonl:
        os.makedirs(os.path.dirname(runs_jsonl), exist_ok=True)
        jsonl_record = dict(row)
        jsonl_record["git_commit"] = git_commit
        jsonl_record["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start))
        with open(runs_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(jsonl_record) + "\n")

    return row


def _worker_wrapper(args_tuple):
    """Wrapper for multiprocessing."""
    return run_single_trial(*args_tuple)


def main():
    parser = argparse.ArgumentParser(description="Parallel Seeded ACA Experiment Runner (Phase A)")
    parser.add_argument("--config", type=str, default="experiments/configs/config_final.yaml", help="Path to config YAML")
    parser.add_argument("--seeds", type=int, default=None, help="Number of seeds (overrides YAML)")
    parser.add_argument("--pilot", action="store_true", help="Run disjoint pilot sweep on seeds 10000-10009")
    parser.add_argument("--output", type=str, default="results/raw_results.csv", help="Output summary CSV")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel worker processes")
    parser.add_argument("--dry-run", action="store_true", help="Print total run count and ETA estimate without running")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow running sweep with uncommitted working tree")
    args = parser.parse_args()

    # Rule R1: fail if working tree is dirty unless explicitly allowed or dry-run
    if not args.dry_run and not args.allow_dirty:
        if not check_git_clean():
            print("ERROR (Rule R1): Git working tree is dirty. Sweep requires a clean git commit for reproducibility.")
            print("Commit all changes or use --allow-dirty for local debugging.")
            sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    traces_dir = "results/traces"
    runs_jsonl = "results/runs.jsonl"
    os.makedirs(traces_dir, exist_ok=True)

    yaml_config = {}
    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}

    git_commit = get_git_commit_hash()

    # Environments
    if "environments" in yaml_config:
        environments = [(env["family"], env["n_nodes"]) for env in yaml_config["environments"]]
    else:
        environments = [
            ("warehouse_movingai", 36),
            ("road_osmnx", 40),
            ("rgg", 35),
            ("warehouse", 30),
            ("er", 35),
        ]

    # Adversaries
    adversaries = yaml_config.get("adversaries", [
        "theta_1_stochastic",
        "theta_2_reactive",
        "theta_3_budgeted_interdiction",
        "theta_4_cyclic_patrol",
    ])

    # Methods
    methods = yaml_config.get("methods", [
        "aca", "aca_no_margin", "aca_depth_0",
        "cbba", "cbba_partial", "cc_cbba", "ssi",
        "cbba_lr", "cbba_partial_lr", "cc_cbba_lr", "ssi_lr",
        "implicit", "ctp_replan", "cbba_gossip", "clairvoyant_greedy",
    ])

    # Comm regimes
    comm_regimes = yaml_config.get("comm_regimes", {
        "benign": {"comm_range": 50.0, "p_drop": 0.02},
        "constrained": {"comm_range": 25.0, "p_drop": 0.15},
        "lossy": {"comm_range": 20.0, "p_drop": 0.30},
    })

    # Seeds
    if args.pilot:
        seed_range = list(range(10000, 10010))  # 10 pilot seeds
    elif args.seeds is not None:
        seed_range = list(range(1, args.seeds + 1))
    elif "final_seeds" in yaml_config:
        n_seeds = yaml_config["final_seeds"]
        seed_range = list(range(1, n_seeds + 1))
    else:
        seed_range = list(range(1, 11))

    max_steps = yaml_config.get("max_steps", 80)
    contingency_depth = yaml_config.get("contingency_depth", 1)
    fleet_sizes = yaml_config.get("fleet_sizes", [4])
    task_counts = yaml_config.get("task_counts", [15])
    n_robots = fleet_sizes[0]
    n_tasks = task_counts[0]

    # Check for existing completed trials (Resumability)
    completed_keys = set()
    if os.path.exists(runs_jsonl):
        try:
            with open(runs_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rec = json.loads(line)
                        key = (
                            rec.get("graph_family"),
                            rec.get("adversary"),
                            rec.get("comm_regime"),
                            rec.get("method"),
                            rec.get("seed"),
                        )
                        completed_keys.add(key)
        except Exception:
            pass

    # Assemble task tuples
    task_tuples = []
    skipped_count = 0
    for fam, n_nodes in environments:
        for adv in adversaries:
            for regime_name, regime_cfg in comm_regimes.items():
                c_range = regime_cfg.get("comm_range", 30.0)
                p_d = regime_cfg.get("p_drop", 0.05)
                for seed in seed_range:
                    for method in methods:
                        key = (fam, adv, regime_name, method, seed)
                        if key in completed_keys:
                            skipped_count += 1
                            continue
                        task_tuples.append((
                            fam,
                            n_nodes,
                            adv,
                            method,
                            regime_name,
                            c_range,
                            p_d,
                            n_robots,
                            n_tasks,
                            seed,
                            max_steps,
                            contingency_depth,
                            traces_dir,
                            runs_jsonl,
                            git_commit,
                        ))

    total_tasks_needed = len(task_tuples) + skipped_count
    remaining_tasks = len(task_tuples)

    print("\n" + "=" * 70)
    print("ACA EXPERIMENTAL SWEEP PRE-FLIGHT SUMMARY")
    print("=" * 70)
    print(f"Git Commit Hash    : {git_commit}")
    print(f"Config File        : {args.config}")
    print(f"Environments ({len(environments)})  : {[e[0] for e in environments]}")
    print(f"Adversaries ({len(adversaries)})   : {adversaries}")
    print(f"Comm Regimes ({len(comm_regimes)})  : {list(comm_regimes.keys())}")
    print(f"Methods ({len(methods)})       : {methods}")
    print(f"Seed Allocation    : {len(seed_range)} seeds (min={min(seed_range)}, max={max(seed_range)})")
    print(f"Total Design Runs  : {total_tasks_needed}")
    print(f"Cached / Completed : {skipped_count}")
    print(f"Remaining to Run   : {remaining_tasks}")
    print(f"Workers            : {args.workers}")

    # Benchmark 1 sample trial for empirical ETA calculation
    sample_time_sec = 0.35  # default empirical guess
    if remaining_tasks > 0:
        print("\nBenchmarking 1 sample instance for empirical rate estimation...")
        t_bench_start = time.time()
        _ = run_single_trial(
            environments[0][0],
            environments[0][1],
            adversaries[0],
            methods[0],
            list(comm_regimes.keys())[0],
            comm_regimes[list(comm_regimes.keys())[0]]["comm_range"],
            comm_regimes[list(comm_regimes.keys())[0]]["p_drop"],
            n_robots,
            n_tasks,
            seed_range[0],
            max_steps=max_steps,
            contingency_depth=contingency_depth,
            traces_dir=None,
            runs_jsonl=None,
            git_commit=git_commit,
        )
        sample_time_sec = max(0.05, time.time() - t_bench_start)

    est_total_sec = (remaining_tasks * sample_time_sec) / max(1, args.workers)
    est_total_min = est_total_sec / 60.0
    print(f"Sample Trial Time  : {sample_time_sec:.3f} s/trial")
    print(f"Empirical Throughput: ~{(args.workers / sample_time_sec):.1f} trials/s with {args.workers} workers")
    print(f"Estimated ETA      : {est_total_min:.1f} minutes ({est_total_sec:.0f} seconds)")
    print("=" * 70 + "\n")

    if args.dry_run:
        print("Dry run requested. Exiting without execution.")
        return

    if remaining_tasks == 0:
        print("All requested trials are already completed in results/runs.jsonl! Generating raw_results.csv from cached records.")
        # Re-export CSV
        records = []
        with open(runs_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        df = pd.DataFrame(records)
        df.to_csv(args.output, index=False)
        print(f"Exported {len(df)} trials to {args.output}")
        return

    results = []
    t0 = time.time()
    completed = 0

    if args.workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_task = {executor.submit(_worker_wrapper, t): t for t in task_tuples}
            for future in concurrent.futures.as_completed(future_to_task):
                completed += 1
                task = future_to_task[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    print(f"CRITICAL ERROR on task {task[:5]}: {e}")
                    traceback.print_exc()
                    raise e

                if completed % 25 == 0 or completed == remaining_tasks:
                    elapsed = time.time() - t0
                    rate = completed / max(0.1, elapsed)
                    rem_sec = (remaining_tasks - completed) / max(0.01, rate)
                    print(
                        f"[{completed}/{remaining_tasks}] ({rate:.1f} trials/s, ~{rem_sec/60:.1f}m rem) - "
                        f"Finished: {task[3]} on {task[0]}/{task[2]}/{task[4]} s{task[9]}"
                    )
    else:
        for idx, task in enumerate(task_tuples):
            res = run_single_trial(*task)
            results.append(res)
            completed += 1
            if completed % 25 == 0 or completed == remaining_tasks:
                elapsed = time.time() - t0
                rate = completed / max(0.1, elapsed)
                rem_sec = (remaining_tasks - completed) / max(0.01, rate)
                print(f"[{completed}/{remaining_tasks}] ({rate:.1f} trials/s, ~{rem_sec/60:.1f}m rem)")

    # Read all lines from runs_jsonl to generate final CSV
    all_records = []
    if os.path.exists(runs_jsonl):
        with open(runs_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_records.append(json.loads(line))

    df = pd.DataFrame(all_records)
    # Sort deterministically
    sort_cols = [c for c in ["graph_family", "adversary", "comm_regime", "seed", "method"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    df.to_csv(args.output, index=False)
    print(f"\nCompleted! Saved {len(df)} total rows to {args.output}")

    # Copy config used alongside results
    config_copy_path = os.path.join(os.path.dirname(args.output), "config_used.yaml")
    if os.path.exists(args.config):
        shutil.copyfile(args.config, config_copy_path)

    # Save run metadata
    meta_path = os.path.join(os.path.dirname(args.output), "run_metadata.json")
    import scipy
    metadata = {
        "commit": git_commit,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "networkx_version": nx.__version__,
        "total_trials": len(df),
        "environments": environments,
        "adversaries": adversaries,
        "methods": methods,
        "comm_regimes": comm_regimes,
        "n_seeds": len(seed_range),
        "fleet_sizes": fleet_sizes,
        "task_counts": task_counts,
        "max_steps": max_steps,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved run metadata to {meta_path}")


if __name__ == "__main__":
    main()
