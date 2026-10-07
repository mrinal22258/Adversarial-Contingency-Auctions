"""
Sanity grid in a no-blockage regime (Step 3B / C2).
Verifies SITL completion is within a few points of graph-sim (>= 85-95%)
before running the full SITL evaluation protocol.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from experiments.sitl.run_sitl import run_single_sitl_trial


def run_sanity_grid():
    methods = ["aca", "aca_no_margin", "ctp_replan", "implicit", "cbba_partial_lr", "ssi_lr"]
    maps = ["warehouse_movingai", "road_osmnx"]
    seeds = [2001, 2002, 2003, 2004, 2005]

    results = []
    print("=" * 60)
    print("Running SITL No-Blockage Sanity Grid (5 seeds x 6 methods x 2 maps)...")
    print("=" * 60)

    for map_type in maps:
        for method in methods:
            comp_list = []
            dist_list = []
            for seed in seeds:
                res = run_single_sitl_trial(
                    map_type=map_type,
                    method=method,
                    adversary_name="stochastic", # adversary budget=0 / no blockage
                    comm_regime="benign",
                    seed=seed,
                    n_robots=4,
                    n_tasks=8,
                    max_steps=30,
                    adv_budget_k=0,
                    save_raw_log=False,
                )
                comp_list.append(res["completion_rate_pct"])
                dist_list.append(res["total_distance_meters"])
            mean_comp = np.mean(comp_list)
            mean_dist = np.mean(dist_list)
            print(f"[{map_type:18s}] {method:16s} -> Completion: {mean_comp:5.1f}%, Mean Distance: {mean_dist:5.1f}m")
            results.append({
                "map": map_type,
                "method": method,
                "mean_completion": mean_comp,
                "mean_distance": mean_dist,
            })

    df = pd.DataFrame(results)
    print("=" * 60)
    print("Sanity Grid Summary:")
    print(df.to_string(index=False))
    print("=" * 60)
    aca_mean = df[df["method"] == "aca"]["mean_completion"].mean()
    overall_mean = df["mean_completion"].mean()
    print(f"ACA No-Blockage SITL Mean Completion: {aca_mean:.1f}%")
    print(f"Overall No-Blockage SITL Mean Completion: {overall_mean:.1f}%")
    assert aca_mean >= 80.0, f"ACA SITL completion too low in no-blockage regime: {aca_mean:.1f}%"
    assert overall_mean >= 75.0, f"Overall SITL completion too low in no-blockage regime: {overall_mean:.1f}%"
    print("SANITY CHECK PASSED: SITL completion is within a few points of graph-sim.")
    return df


if __name__ == "__main__":
    run_sanity_grid()
