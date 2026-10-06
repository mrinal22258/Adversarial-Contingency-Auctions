"""
Pilot and Statistical Power Analysis (Phase 1.7 & Phase 4.1).
Executes pilot trials on disjoint pilot seeds (10000-10009),
computes instance-level paired variance estimates,
calculates required sample size n for 80% and 90% statistical power (Wilcoxon ARE-adjusted),
and outputs results/power_analysis.csv.
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import scipy.stats as stats
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acalib.env.adversaries import AdversaryType
from experiments.run_sweep import run_single_trial


def run_pilot(pilot_seeds, methods, environments, adversaries, workers=4):
    """Execute pilot sweep across disjoint seeds."""
    tasks = []
    for env in environments:
        fam, n_nodes = env["family"], env["n_nodes"]
        for adv in adversaries:
            for seed in pilot_seeds:
                for method in methods:
                    tasks.append((
                        fam,
                        n_nodes,
                        adv,
                        method,
                        "constrained",
                        25.0,
                        0.15,
                        4,
                        15,
                        seed,
                        70,
                        1,
                        None,
                        None,
                        "pilot",
                    ))

    print(f"Executing {len(tasks)} pilot simulation runs across {len(pilot_seeds)} seeds...")
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_single_trial, *t): t for t in tasks}
        for f in as_completed(futures):
            results.append(f.result())

    df = pd.DataFrame(results)
    return df


def compute_power_requirements(df_pilot, alpha=0.05, target_powers=(0.80, 0.90)):
    """Compute required sample size n per cell for Wilcoxon paired signed-rank test."""
    # Unit of analysis: instance level (graph_family, seed)
    instance_df = df_pilot.groupby(["graph_family", "seed", "method"])[
        ["completion_rate_pct", "net_welfare", "total_messages", "total_conflicts"]
    ].mean().reset_index()

    pivoted_comp = instance_df.pivot(index=["graph_family", "seed"], columns="method", values="completion_rate_pct")
    pivoted_welfare = instance_df.pivot(index=["graph_family", "seed"], columns="method", values="net_welfare")

    comparisons = [
        ("aca", "aca_depth_0", "completion_rate_pct", pivoted_comp, 5.0), # H1
        ("aca", "cbba_lr", "completion_rate_pct", pivoted_comp, 5.0),      # H2 (vs CBBA+LR)
        ("aca", "ssi_lr", "completion_rate_pct", pivoted_comp, 5.0),       # H2 (vs SSI+LR)
        ("aca", "cbba_lr", "net_welfare", pivoted_welfare, 25.0),          # H3
    ]

    records = []
    for m1, m2, metric_name, p_df, min_effect in comparisons:
        if m1 not in p_df.columns or m2 not in p_df.columns:
            continue
        diff = p_df[m1] - p_df[m2]
        mean_diff = float(diff.mean())
        std_diff = float(diff.std(ddof=1))
        std_diff = max(std_diff, 1.0) # avoid division by zero
        d_z = mean_diff / std_diff

        req_n = {}
        for power in target_powers:
            z_alpha = stats.norm.ppf(1 - alpha / 2.0)
            z_beta = stats.norm.ppf(power)
            # Paired t-test n formula
            n_ttest = ((z_alpha + z_beta) * std_diff / min_effect) ** 2
            # Asymptotic Relative Efficiency adjustment for Wilcoxon signed rank test (Pitman ARE ~ 1.15)
            n_wilcoxon = int(np.ceil(1.15 * n_ttest))
            req_n[int(power * 100)] = max(10, n_wilcoxon)

        records.append({
            "comparison": f"{m1}_vs_{m2}",
            "metric": metric_name,
            "pilot_mean_diff": round(mean_diff, 2),
            "pilot_std_diff": round(std_diff, 2),
            "cohens_dz": round(d_z, 3),
            "min_effect_size": min_effect,
            "required_n_80pct_power": req_n.get(80, 50),
            "required_n_90pct_power": req_n.get(90, 65),
            "recommended_instances": max(50, req_n.get(90, 50)),
        })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=str, default="results/power_analysis.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    pilot_seeds = list(range(10000, 10008)) # 8 disjoint pilot seeds
    environments = [{"family": "rgg", "n_nodes": 30}, {"family": "warehouse", "n_nodes": 25}]
    adversaries = [AdversaryType.STOCHASTIC.value, AdversaryType.REACTIVE.value]
    methods = ["aca", "aca_depth_0", "cbba", "cbba_lr", "ssi", "ssi_lr"]

    df_pilot = run_pilot(pilot_seeds, methods, environments, adversaries, workers=args.workers)
    power_df = compute_power_requirements(df_pilot)
    power_df.to_csv(args.output, index=False)
    print("\nPower Analysis Results:")
    print(power_df.to_string(index=False))
    print(f"\nSaved power analysis to {args.output}")


if __name__ == "__main__":
    main()
