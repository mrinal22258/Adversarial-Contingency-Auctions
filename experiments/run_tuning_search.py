"""
Tuning Search Script (Step 2b) - Seeds 1-30 ONLY.
Executes an empirical 50-trial search budget per method over tuning seeds [1, 30].
Tunes:
  - aca_adaptive: margin_kappa in [0.5, 0.9]
  - aca_plus: prune_threshold in [0.01, 0.08]
  - cbba_lr: bundle_limit in [2, 6]
  - cbba_partial_lr: bundle_limit in [2, 6]
  - ctp_replan: bundle_limit in [2, 6]
  - ssi_lr: bundle_limit in [2, 6]

Saves every trial to results/tuning/trials.csv and reports best configuration per method.
"""

import os
import sys
import time
import json
import argparse
import numpy as np
import pandas as pd
import concurrent.futures
from typing import Dict, Any, List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial, get_git_commit_hash

TUNING_SEEDS = list(range(1, 31))
FAMILIES = ["warehouse_movingai", "road_osmnx", "rgg", "warehouse", "er"]
ADVERSARIES = ["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"]

NODE_COUNTS = {
    "warehouse_movingai": 38,
    "road_osmnx": 216,
    "rgg": 30,
    "warehouse": 36,
    "er": 30,
}

METHODS_TO_TUNE = [
    "aca_adaptive",
    "aca_plus",
    "cbba_lr",
    "cbba_partial_lr",
    "ctp_replan",
    "ssi_lr",
]

def generate_tuning_grid(budget_per_method: int = 50, rng_seed: int = 42) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(rng_seed)
    trials = []

    # 1. aca_adaptive: tune margin_kappa in [0.5, 0.9]
    kappa_candidates = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90]
    for i in range(budget_per_method):
        fam = rng.choice(FAMILIES)
        adv = rng.choice(ADVERSARIES)
        seed = int(rng.choice(TUNING_SEEDS))
        kappa = float(rng.choice(kappa_candidates))
        trials.append({
            "method": "aca_adaptive",
            "family": fam,
            "adversary": adv,
            "seed": seed,
            "param_name": "margin_kappa",
            "param_value": kappa,
            "allocator_kwargs": {"margin_kappa": kappa},
        })

    # 2. aca_plus: tune prune_threshold in [0.01, 0.08]
    prune_candidates = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]
    for i in range(budget_per_method):
        fam = rng.choice(FAMILIES)
        adv = rng.choice(ADVERSARIES)
        seed = int(rng.choice(TUNING_SEEDS))
        prune = float(rng.choice(prune_candidates))
        trials.append({
            "method": "aca_plus",
            "family": fam,
            "adversary": adv,
            "seed": seed,
            "param_name": "prune_threshold",
            "param_value": prune,
            "allocator_kwargs": {"prune_threshold": prune, "margin_kappa": 0.75},
        })

    # 3-6. Baselines: tune bundle_limit in [2, 3, 4, 5, 6]
    bundle_candidates = [2, 3, 4, 5, 6]
    for baseline in ["cbba_lr", "cbba_partial_lr", "ctp_replan", "ssi_lr"]:
        for i in range(budget_per_method):
            fam = rng.choice(FAMILIES)
            adv = rng.choice(ADVERSARIES)
            seed = int(rng.choice(TUNING_SEEDS))
            blim = int(rng.choice(bundle_candidates))
            trials.append({
                "method": baseline,
                "family": fam,
                "adversary": adv,
                "seed": seed,
                "param_name": "bundle_limit",
                "param_value": blim,
                "allocator_kwargs": {"bundle_limit": blim},
            })

    return trials


def run_tuning_trial(trial_spec: Dict[str, Any], git_commit: str) -> Dict[str, Any]:
    fam = trial_spec["family"]
    n_nodes = NODE_COUNTS[fam]
    adv = trial_spec["adversary"]
    method = trial_spec["method"]
    seed = trial_spec["seed"]
    alloc_kwargs = trial_spec["allocator_kwargs"]

    res = run_single_trial(
        graph_family=fam,
        n_nodes=n_nodes,
        adversary_type_str=adv,
        allocator_name=method,
        comm_regime="nominal",
        comm_range=30.0,
        p_drop=0.10,
        n_robots=4,
        n_tasks=15,
        seed=seed,
        max_steps=80,
        contingency_depth=1,
        traces_dir=None,
        runs_jsonl=None,
        git_commit=git_commit,
        allocator_kwargs=alloc_kwargs,
    )

    out = dict(trial_spec)
    out.pop("allocator_kwargs", None)
    out.update({
        "completion_rate_pct": res.get("completion_rate_pct", 0.0),
        "net_welfare": res.get("net_welfare", 0.0),
        "total_messages": res.get("total_messages", 0),
        "total_conflicts": res.get("total_conflicts", 0),
        "wall_clock_ms": res.get("wall_clock_ms", 0.0),
    })
    return out


def main():
    parser = argparse.ArgumentParser(description="Tuning Search on Seeds 1-30")
    parser.add_argument("--budget", type=int, default=50, help="Trial budget per method")
    parser.add_argument("--workers", type=int, default=6, help="Parallel worker processes")
    args = parser.parse_args()

    git_commit = get_git_commit_hash()
    output_dir = os.path.join(REPO_ROOT, "results", "tuning")
    os.makedirs(output_dir, exist_ok=True)
    out_csv = os.path.join(output_dir, "trials.csv")

    trials = generate_tuning_grid(budget_per_method=args.budget, rng_seed=2026)
    total_trials = len(trials)
    print(f"[*] Starting hyperparameter tuning search on seeds 1-30.")
    print(f"[*] Total trials: {total_trials} ({args.budget} per method across {len(METHODS_TO_TUNE)} methods)")
    print(f"[*] Parallel workers: {args.workers}")

    start_time = time.time()
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_tuning_trial, t, git_commit): t for t in trials}
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            completed += 1
            if completed % 25 == 0 or completed == total_trials:
                elapsed = time.time() - start_time
                print(f"  -> Progress: {completed}/{total_trials} ({completed*100/total_trials:.0f}%) in {elapsed:.1f}s")

    df = pd.DataFrame(results)
    df.to_csv(out_csv, index=False)
    print(f"\n[*] All tuning trials saved to: {out_csv}")

    # Summary and Best Configurations
    summary_path = os.path.join(output_dir, "best_hyperparameters.json")
    best_configs = {}
    print("\n" + "="*70)
    print("           HYPERPARAMETER TUNING RESULTS (SEEDS 1-30)")
    print("="*70)

    for method in METHODS_TO_TUNE:
        sub = df[df["method"] == method]
        grouped = sub.groupby("param_value").agg({
            "completion_rate_pct": ["mean", "std", "count"],
            "net_welfare": ["mean", "std"],
            "total_conflicts": ["mean"],
        })
        print(f"\nMethod: {method} ({sub['param_name'].iloc[0]})")
        print(grouped)

        # Objective: Maximize completion rate, tie-break on net welfare
        means = sub.groupby("param_value")[["completion_rate_pct", "net_welfare"]].mean()
        best_val = means.sort_values(by=["completion_rate_pct", "net_welfare"], ascending=[False, False]).index[0]
        best_comp = float(means.loc[best_val, "completion_rate_pct"])
        best_welf = float(means.loc[best_val, "net_welfare"])

        best_configs[method] = {
            "parameter": sub["param_name"].iloc[0],
            "best_value": best_val if not isinstance(best_val, np.generic) else best_val.item(),
            "mean_completion_rate_pct": best_comp,
            "mean_net_welfare": best_welf,
            "budget_trials": len(sub),
        }
        print(f"  => Best {sub['param_name'].iloc[0]}: {best_val} (Completion: {best_comp:.1f}%, Welfare: {best_welf:.1f})")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(best_configs, f, indent=2)
    print(f"\n[*] Best configurations saved to: {summary_path}")


if __name__ == "__main__":
    main()
