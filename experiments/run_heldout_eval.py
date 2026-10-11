"""
Stage 4 Protocol v5 Pre-Registered Held-Out Confirmatory Evaluation.
Evaluates the 8 methods across all 5 benchmark families and 3 adversaries
on strictly held-out seeds (seeds 101-130, N=450 paired instances).
Applies family-wide Holm-Bonferroni correction, bootstrap 95% CIs,
Hodges-Lehmann median estimators, and Cohen's d_z effect sizes.
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd
from scipy import stats
import concurrent.futures
from typing import Dict, Any, List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial, get_git_commit_hash
from experiments.stats import (
    paired_cohens_dz,
    hodges_lehmann_difference,
    holm_bonferroni_correction,
    paired_wilcoxon_test,
    bootstrap_ci,
)

BENCHMARK_FAMILIES = [
    {"family": "warehouse_movingai", "n_nodes": 38},
    {"family": "road_osmnx", "n_nodes": 216},
    {"family": "rgg", "n_nodes": 30},
    {"family": "warehouse", "n_nodes": 36},
    {"family": "er", "n_nodes": 30},
]

ADVERSARIES = [
    "theta_1_stochastic",
    "theta_2_reactive",
    "theta_4_cyclic_patrol",
]

EVAL_METHODS = [
    "aca",
    "aca_adaptive",
    "aca_plus",
    "aca_no_margin",
    "cbba_lr",
    "cbba_partial_lr",
    "ctp_replan",
    "ssi_lr",
]

# Tuned hyperparameter configs from Step 2b (Tuning on Seeds 1-30)
METHOD_KWARGS = {
    "aca": {"margin_kappa": 1.0, "bundle_limit": 4},
    "aca_adaptive": {"margin_kappa": 0.5, "bundle_limit": 4},
    "aca_plus": {"prune_threshold": 0.06, "margin_kappa": 0.75, "bundle_limit": 4},
    "aca_no_margin": {"bundle_limit": 4},
    "cbba_lr": {"bundle_limit": 2},
    "cbba_partial_lr": {"bundle_limit": 3},
    "ctp_replan": {"bundle_limit": 2},
    "ssi_lr": {"bundle_limit": 6},
}


def run_heldout_v5_experiments(
    workers: int = 6,
    start_seed: int = 101,
    n_seeds: int = 30,
) -> pd.DataFrame:
    """Execute held-out evaluation across disjoint seeds [start_seed, start_seed + n_seeds - 1]."""
    heldout_seeds = list(range(start_seed, start_seed + n_seeds))
    tasks = []
    git_commit = get_git_commit_hash()
    output_dir = os.path.join(REPO_ROOT, "results", "confirmatory")
    os.makedirs(output_dir, exist_ok=True)
    heldout_jsonl = os.path.join(output_dir, "heldout_v5_runs.jsonl")

    for env in BENCHMARK_FAMILIES:
        fam, n_nodes = env["family"], env["n_nodes"]
        for adv in ADVERSARIES:
            for seed in heldout_seeds:
                for method in EVAL_METHODS:
                    kw = METHOD_KWARGS.get(method, {})
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
                        80,
                        1,
                        None,
                        heldout_jsonl,
                        git_commit,
                        kw,
                    ))

    total_trials = len(tasks)
    print(f"[*] Starting Protocol v5 Held-Out Confirmatory Evaluation:")
    print(f"    - Families ({len(BENCHMARK_FAMILIES)}): {[f['family'] for f in BENCHMARK_FAMILIES]}")
    print(f"    - Adversaries ({len(ADVERSARIES)}): {ADVERSARIES}")
    print(f"    - Seeds ({len(heldout_seeds)}): {heldout_seeds[0]} to {heldout_seeds[-1]}")
    print(f"    - Methods ({len(EVAL_METHODS)}): {EVAL_METHODS}")
    print(f"    - Total paired trials: {total_trials}")
    start_time = time.time()

    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_single_trial, *t): t for t in tasks}
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            completed += 1
            if completed % 100 == 0 or completed == total_trials:
                elapsed = time.time() - start_time
                print(f"  -> Completed {completed}/{total_trials} trials ({completed*100/total_trials:.0f}%) in {elapsed:.1f}s")

    elapsed = time.time() - start_time
    print(f"[*] Finished {total_trials} held-out trials in {elapsed:.1f}s ({elapsed/total_trials*1000:.1f}ms/trial)")

    df = pd.DataFrame(results)
    csv_path = os.path.join(output_dir, "heldout_v5_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"[*] Saved raw Protocol v5 held-out results to: {csv_path}")
    return df


def analyze_heldout_v5_results(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Compute pre-registered hypothesis test suite on held-out seeds with Holm-Bonferroni correction."""
    output_dir = os.path.join(REPO_ROOT, "results", "confirmatory")
    os.makedirs(output_dir, exist_ok=True)

    # Unit of analysis: instance level (graph_family, adversary, seed)
    pairing_cols = ["graph_family", "adversary", "seed"]

    pivot_comp = df.pivot(index=pairing_cols, columns="method", values="completion_rate_pct")
    pivot_welf = df.pivot(index=pairing_cols, columns="method", values="net_welfare")
    pivot_msgs = df.pivot(index=pairing_cols, columns="method", values="total_messages")
    pivot_conf = df.pivot(index=pairing_cols, columns="method", values="total_conflicts")

    pivots = {
        "completion_rate_pct": pivot_comp,
        "net_welfare": pivot_welf,
        "total_messages": pivot_msgs,
        "total_conflicts": pivot_conf,
    }

    # Pre-registered Hypothesis Suite
    hypotheses = [
        ("H1_aca_plus_comp", "aca_plus", "aca", "completion_rate_pct", "greater"),
        ("H1_aca_plus_welf", "aca_plus", "aca", "net_welfare", "greater"),
        ("H2_aca_adapt_comp", "aca_adaptive", "aca", "completion_rate_pct", "greater"),
        ("H2_aca_adapt_welf", "aca_adaptive", "aca", "net_welfare", "greater"),
        ("H3_aca_plus_vs_cbba_comp", "aca_plus", "cbba_lr", "completion_rate_pct", "greater"),
        ("H3_aca_plus_vs_cbba_conf", "aca_plus", "cbba_lr", "total_conflicts", "less"),
        ("H4_aca_plus_vs_cbbapr_comp", "aca_plus", "cbba_partial_lr", "completion_rate_pct", "greater"),
        ("H4_aca_plus_vs_cbbapr_conf", "aca_plus", "cbba_partial_lr", "total_conflicts", "less"),
        ("H5_aca_plus_vs_ctp_comp", "aca_plus", "ctp_replan", "completion_rate_pct", "two-sided"),
        ("H5_aca_plus_vs_ctp_msgs", "aca_plus", "ctp_replan", "total_messages", "two-sided"),
        ("H6_aca_plus_vs_ssi_comp", "aca_plus", "ssi_lr", "completion_rate_pct", "greater"),
        ("H6_aca_plus_vs_ssi_conf", "aca_plus", "ssi_lr", "total_conflicts", "less"),
        ("H7_aca_nomargin_conf", "aca", "aca_no_margin", "total_conflicts", "less"),
        ("H7_aca_nomargin_comp", "aca", "aca_no_margin", "completion_rate_pct", "two-sided"),
    ]

    raw_p_values = []
    test_data_records = []
    n_instances = len(pivot_comp)

    for h_id, m1, m2, metric, alt in hypotheses:
        p_df = pivots[metric]
        s1 = p_df[m1]
        s2 = p_df[m2]
        diff = s1 - s2

        mean_1 = float(s1.mean())
        mean_2 = float(s2.mean())
        mean_d = float(diff.mean())
        std_d = float(diff.std(ddof=1)) if len(diff) > 1 else 0.0
        dz = paired_cohens_dz(s1.tolist(), s2.tolist())
        hl_est, hl_lo, hl_hi = hodges_lehmann_difference(s1.tolist(), s2.tolist())

        # Bootstrap 95% CI of mean diff
        _, boot_lo, boot_hi = bootstrap_ci(diff.tolist(), n_resamples=1000, ci=0.95)

        # Wilcoxon signed-rank test
        w_stat, p_val = paired_wilcoxon_test(s1.tolist(), s2.tolist(), alternative=alt)
        raw_p_values.append(p_val)

        test_data_records.append({
            "hypothesis_id": h_id,
            "m1": m1,
            "m2": m2,
            "metric": metric,
            "alternative": alt,
            "n_instances": n_instances,
            "mean_m1": mean_1,
            "mean_m2": mean_2,
            "mean_diff": mean_d,
            "std_diff": std_d,
            "cohens_dz": dz,
            "hl_median_diff": hl_est,
            "hl_ci_95": [hl_lo, hl_hi],
            "boot_ci_95": [boot_lo, boot_hi],
            "wilcoxon_stat": w_stat,
            "raw_p_value": p_val,
        })

    # Apply family-wide Holm-Bonferroni correction
    holm_results = holm_bonferroni_correction(raw_p_values, alpha=0.05)

    summary_rows = []
    detailed_dict = {}

    print("\n" + "="*85)
    print("      PROTOCOL V5 CONFIRMATORY HYPOTHESIS TESTING (SEEDS 101-130, N=450)")
    print("="*85)

    for i, rec in enumerate(test_data_records):
        adj_p, is_sig = holm_results[i]
        rec["holm_p_value"] = adj_p
        rec["significant_holm_05"] = is_sig

        h_id = rec["hypothesis_id"]
        detailed_dict[h_id] = rec

        summary_rows.append({
            "Hypothesis": h_id,
            "Comparison": f"{rec['m1']} vs {rec['m2']}",
            "Metric": rec["metric"],
            "Mean Proposed": round(rec["mean_m1"], 2),
            "Mean Comparator": round(rec["mean_m2"], 2),
            "Mean Paired Diff": round(rec["mean_diff"], 2),
            "95% CI (Boot)": f"[{rec['boot_ci_95'][0]:.2f}, {rec['boot_ci_95'][1]:.2f}]",
            "Cohen's dz": round(rec["cohens_dz"], 3),
            "Raw p": f"{rec['raw_p_value']:.4e}",
            "Holm p": f"{adj_p:.4e}",
            "Sig (alpha=0.05)": is_sig,
        })

    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))

    summary_path = os.path.join(output_dir, "heldout_v5_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    json_path = os.path.join(output_dir, "heldout_v5_statistical_tests.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(detailed_dict, f, indent=2)

    print(f"\n[*] Summary table saved to: {summary_path}")
    print(f"[*] Detailed test JSON saved to: {json_path}")
    return summary_df, detailed_dict


def main():
    parser = argparse.ArgumentParser(description="Protocol v5 Held-Out Confirmatory Evaluation")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel worker processes")
    parser.add_argument("--start-seed", type=int, default=101, help="Start seed for held-out evaluation")
    parser.add_argument("--n-seeds", type=int, default=30, help="Number of held-out seeds")
    parser.add_argument("--analyze-only", action="store_true", help="Analyze existing heldout_v5_results.csv")
    args = parser.parse_args()

    csv_path = os.path.join(REPO_ROOT, "results", "confirmatory", "heldout_v5_results.csv")
    if args.analyze_only and os.path.exists(csv_path):
        print(f"[*] Loading existing held-out results from: {csv_path}")
        df = pd.read_csv(csv_path)
    else:
        df = run_heldout_v5_experiments(
            workers=args.workers,
            start_seed=args.start_seed,
            n_seeds=args.n_seeds,
        )
    analyze_heldout_v5_results(df)


if __name__ == "__main__":
    main()
