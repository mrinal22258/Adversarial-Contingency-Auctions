#!/usr/bin/env python3
"""
Empirical Pruning Threshold Tuning on Development Seeds (Protocol v6).
Evaluates candidate pruning thresholds {0.15, 0.20, 0.25} for aca_plus
exclusively on the 15 pre-registered development seeds across the benchmark universe.

Decision D-09 Rule:
- Primary selection criterion: Mean task completion rate (%).
- Tie-breaking: If within 0.5 percentage points (pp), choose smaller threshold (parsimony).
- Confirmatory seeds are strictly held out.
"""

import os
import sys
import json
import time
import argparse
import yaml
import pandas as pd
import numpy as np
import concurrent.futures

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial, get_default_workers, get_git_commit_hash


def _tuning_worker(t):
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    return run_single_trial(*t)


def main():
    parser = argparse.ArgumentParser(description="Tune aca_plus pruning threshold on dev seeds")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--config", type=str, default="experiments/configs/protocol_v6.yaml", help="Protocol config")
    args = parser.parse_args()

    workers = args.workers or get_default_workers()
    print("=" * 70)
    print("      ACA+ PRUNING THRESHOLD TUNING ON DEVELOPMENT SEEDS (v6)       ")
    print("=" * 70)

    # 1. Load authoritative Protocol v6 configuration
    cfg_path = os.path.join(REPO_ROOT, args.config)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    dev_seeds = cfg["evaluation_design"]["development_phase"]["seeds"]
    print(f"Development Seeds ({len(dev_seeds)}) : {dev_seeds}")

    # Benchmark Universe
    bu = cfg["benchmark_universe"]
    environments = [(e["family"], e["n_nodes"]) for e in bu["environments"]]
    adversaries = bu["adversaries"]
    comm_cfg = bu["comm_regimes"]["nominal"]
    comm_range = comm_cfg["comm_range"]
    p_drop = comm_cfg["p_drop"]
    n_robots = bu["n_robots"]
    n_tasks = bu["n_tasks"]
    max_steps = bu["max_steps"]
    bundle_capacity = bu["bundle_capacity"]
    sensor_range = bu["sensor_range"]

    candidate_thresholds = [0.15, 0.20, 0.25]
    print(f"Candidate Thresholds: {candidate_thresholds}")
    print(f"Environments ({len(environments)})  : {[e[0] for e in environments]}")
    print(f"Adversaries ({len(adversaries)})   : {adversaries}")
    print(f"Parallel Workers   : {workers}")

    # Assemble task tuples
    task_tuples = []
    git_commit = get_git_commit_hash()
    protocol_hash = "prune_dev_tuning"

    for tau in candidate_thresholds:
        alloc_kw = {
            "kappa": 1.0,
            "contingency_depth": 1,
            "prune_threshold": tau,
        }
        for fam, n_nodes in environments:
            for adv in adversaries:
                for seed in dev_seeds:
                    task_tuples.append((
                        fam,
                        n_nodes,
                        adv,
                        "aca_plus",
                        "nominal",
                        comm_range,
                        p_drop,
                        n_robots,
                        n_tasks,
                        seed,
                        max_steps,
                        1,
                        None,  # traces_dir
                        None,  # runs_jsonl
                        git_commit,
                        protocol_hash,
                        alloc_kw,
                    ))

    total_tasks = len(task_tuples)
    print(f"Total Sweep Trials : {total_tasks} ({len(candidate_thresholds)} thresholds x {total_tasks // len(candidate_thresholds)} instances)")
    print("-" * 70)

    # 2. Execute parallel sweep
    t0 = time.time()
    results = []
    completed = 0

    if workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_task = {executor.submit(_tuning_worker, t): t for t in task_tuples}
            for future in concurrent.futures.as_completed(future_to_task):
                completed += 1
                task = future_to_task[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    print(f"[ERROR] Task failed: {e}")
                    raise e

                if completed % 50 == 0 or completed == total_tasks:
                    elapsed = time.time() - t0
                    rate = completed / max(0.1, elapsed)
                    rem_sec = (total_tasks - completed) / max(0.01, rate)
                    print(f"[{completed}/{total_tasks}] ({rate:.1f} trials/s, ~{rem_sec/60:.1f}m rem)")
    else:
        for t in task_tuples:
            res = _tuning_worker(t)
            results.append(res)
            completed += 1
            if completed % 50 == 0 or completed == total_tasks:
                elapsed = time.time() - t0
                rate = completed / max(0.1, elapsed)
                print(f"[{completed}/{total_tasks}] ({rate:.1f} trials/s)")

    # 3. Analyze Results
    df = pd.DataFrame(results)
    # Extract prune_threshold column
    df["prune_threshold"] = df["allocator_kwargs"].apply(lambda kw: kw.get("prune_threshold"))

    out_dir = os.path.join(REPO_ROOT, "results", "tuning")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "prune_dev_v6.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nSaved raw tuning results to: {csv_path}")

    # Group by threshold
    summary_df = df.groupby("prune_threshold").agg(
        mean_completion_pct=("completion_rate_pct", "mean"),
        std_completion_pct=("completion_rate_pct", "std"),
        mean_net_welfare=("net_welfare", "mean"),
        mean_conflicts=("total_conflicts", "mean"),
        total_trials=("trial_hash", "count"),
    ).reset_index()

    print("\n" + "=" * 70)
    print("              PRUNING THRESHOLD EVALUATION SUMMARY                 ")
    print("=" * 70)
    print(summary_df.to_string(index=False))
    print("-" * 70)

    # 4. Apply Decision D-09 Selection Rule
    # Primary: mean completion rate
    # Tie within 0.5 pp: smaller threshold wins
    best_row = None
    sorted_candidates = summary_df.sort_values(by="mean_completion_pct", ascending=False).to_dict(orient="records")
    top_candidate = sorted_candidates[0]

    # Check for ties within 0.5 pp
    tied_candidates = [
        c for c in sorted_candidates
        if (top_candidate["mean_completion_pct"] - c["mean_completion_pct"]) <= 0.50
    ]
    # Smallest threshold among tied candidates wins
    winning_candidate = min(tied_candidates, key=lambda c: c["prune_threshold"])
    winner_tau = winning_candidate["prune_threshold"]

    print(f"\nSelection Analysis (Decision D-09 Rule):")
    print(f"  Top candidate by completion: tau = {top_candidate['prune_threshold']} ({top_candidate['mean_completion_pct']:.2f}%)")
    if len(tied_candidates) > 1:
        print(f"  Tied candidates within 0.5 pp: {[c['prune_threshold'] for c in tied_candidates]}")
        print(f"  Tie-breaker applied (parsimony): tau = {winner_tau}")
    else:
        print(f"  Clear winner: tau = {winner_tau}")

    # 5. Write Summary JSON
    summary_json_path = os.path.join(out_dir, "prune_dev_v6_summary.json")
    summary_data = {
        "protocol": "v6",
        "evaluation_phase": "development_seeds_only",
        "code_commit": git_commit,
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_seeds": len(dev_seeds),
        "seeds": dev_seeds,
        "selection_rule": "Primary = mean completion rate (%); ties within 0.5 pp choose smaller threshold for parsimony.",
        "candidate_results": summary_df.to_dict(orient="records"),
        "winning_prune_threshold": winner_tau,
        "winning_mean_completion_pct": winning_candidate["mean_completion_pct"],
        "winning_mean_net_welfare": winning_candidate["mean_net_welfare"],
        "winning_mean_conflicts": winning_candidate["mean_conflicts"],
        "status": "DETERMINED",
    }

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved tuning summary JSON to: {summary_json_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
