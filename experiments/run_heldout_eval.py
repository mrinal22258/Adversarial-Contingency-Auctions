"""
Stage 4 Pre-Registered Held-Out Confirmatory Evaluation.
Evaluates the improved method (aca_adaptive and aca_plus) against standard aca, cbba_lr, and ctp_replan
on strictly held-out disjoint seeds (seeds 51-60) and real topologies (Boston road network and MovingAI warehouse).
"""

import os
import sys
import time
import argparse
import pandas as pd
import numpy as np
from scipy import stats
import concurrent.futures

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial, get_git_commit_hash


def run_heldout_experiments(workers: int = 6, n_seeds: int = 10) -> pd.DataFrame:
    """Execute held-out evaluation across disjoint seeds 51 to 51 + n_seeds - 1."""
    heldout_seeds = list(range(51, 51 + n_seeds))
    environments = [
        {"family": "road_osmnx", "n_nodes": 216},
        {"family": "warehouse_movingai", "n_nodes": 38},
        {"family": "rgg", "n_nodes": 30},
    ]
    adversaries = ["theta_1_stochastic", "theta_2_reactive"]
    methods = ["aca", "aca_adaptive", "aca_plus", "cbba_lr", "ctp_replan"]

    tasks = []
    git_commit = get_git_commit_hash()
    output_dir = os.path.join(REPO_ROOT, "results", "confirmatory")
    os.makedirs(output_dir, exist_ok=True)
    heldout_jsonl = os.path.join(output_dir, "heldout_runs.jsonl")

    for env in environments:
        fam, n_nodes = env["family"], env["n_nodes"]
        for adv in adversaries:
            for seed in heldout_seeds:
                for method in methods:
                    tasks.append((
                        fam,
                        n_nodes,
                        adv,
                        method,
                        "nominal",
                        30.0,
                        0.10,
                        4,
                        15,
                        seed,
                        70,
                        1,
                        None,
                        heldout_jsonl,
                        git_commit,
                    ))

    total_trials = len(tasks)
    print(f"[*] Running {total_trials} held-out confirmatory trials across {len(heldout_seeds)} seeds ({heldout_seeds[0]}-{heldout_seeds[-1]})...")
    start_time = time.time()

    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_single_trial, *t): t for t in tasks}
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            completed += 1
            if completed % 50 == 0 or completed == total_trials:
                print(f"  -> Completed {completed}/{total_trials} trials ({completed*100/total_trials:.0f}%) in {time.time()-start_time:.1f}s")

    elapsed = time.time() - start_time
    print(f"[*] Finished {total_trials} trials in {elapsed:.1f}s ({elapsed/total_trials*1000:.1f}ms/trial)")

    df = pd.DataFrame(results)
    csv_path = os.path.join(output_dir, "heldout_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"[*] Saved raw held-out results to {csv_path}")
    return df


def analyze_heldout_results(df: pd.DataFrame) -> pd.DataFrame:
    """Compute paired statistics on held-out seeds."""
    output_dir = os.path.join(REPO_ROOT, "results", "confirmatory")
    os.makedirs(output_dir, exist_ok=True)

    # Unit of analysis: instance level (graph_family, adversary, seed)
    pairing_cols = ["graph_family", "adversary", "seed"]
    metrics = ["completion_rate_pct", "net_welfare", "total_messages", "total_conflicts"]

    pivot_comp = df.pivot(index=pairing_cols, columns="method", values="completion_rate_pct")
    pivot_welf = df.pivot(index=pairing_cols, columns="method", values="net_welfare")
    pivot_msgs = df.pivot(index=pairing_cols, columns="method", values="total_messages")
    pivot_conf = df.pivot(index=pairing_cols, columns="method", values="total_conflicts")

    comparisons = [
        ("aca_adaptive", "aca", "completion_rate_pct", pivot_comp),
        ("aca_adaptive", "aca", "net_welfare", pivot_welf),
        ("aca_plus", "aca", "completion_rate_pct", pivot_comp),
        ("aca_plus", "cbba_lr", "completion_rate_pct", pivot_comp),
        ("aca_plus", "cbba_lr", "total_conflicts", pivot_conf),
        ("aca_plus", "cbba_lr", "total_messages", pivot_msgs),
    ]

    records = []
    n_instances = len(pivot_comp)
    print(f"\n[*] Confirmatory Paired Analysis on Held-Out Population (N = {n_instances} instances):")
    for m1, m2, metric, p_df in comparisons:
        if m1 not in p_df.columns or m2 not in p_df.columns:
            continue
        diff = p_df[m1] - p_df[m2]
        mean_m1 = float(p_df[m1].mean())
        mean_m2 = float(p_df[m2].mean())
        mean_diff = float(diff.mean())
        std_diff = float(diff.std(ddof=1)) if len(diff) > 1 else 0.0
        cohens_d = mean_diff / max(1e-6, std_diff)

        # Non-parametric Wilcoxon test
        try:
            non_zero_diff = diff[diff != 0.0]
            if len(non_zero_diff) >= 5:
                w_stat, p_val = stats.wilcoxon(diff, alternative="two-sided")
            else:
                p_val = 1.0
        except Exception:
            p_val = 1.0

        records.append({
            "test_comparison": f"{m1}_vs_{m2}",
            "metric": metric,
            "N_instances": n_instances,
            "mean_proposed": round(mean_m1, 2),
            "mean_comparator": round(mean_m2, 2),
            "mean_paired_difference": round(mean_diff, 2),
            "std_paired_difference": round(std_diff, 2),
            "cohens_dz": round(cohens_d, 3),
            "wilcoxon_p_value": f"{p_val:.4f}" if p_val >= 0.001 else "< 0.001",
        })

    summary_df = pd.DataFrame(records)
    summary_path = os.path.join(output_dir, "heldout_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(summary_df.to_string(index=False))
    print(f"\n[*] Saved confirmatory summary to {summary_path}")
    return summary_df


def main():
    parser = argparse.ArgumentParser(description="Run Stage 4 Held-Out Confirmatory Evaluation")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--n-seeds", type=int, default=10, help="Number of held-out seeds (starting from seed 51)")
    args = parser.parse_args()

    df = run_heldout_experiments(workers=args.workers, n_seeds=args.n_seeds)
    analyze_heldout_results(df)


if __name__ == "__main__":
    main()
