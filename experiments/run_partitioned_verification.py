#!/usr/bin/env python3
"""
experiments/run_partitioned_verification.py

Confirmatory verification sweep under structurally partitioned topological vulnerabilities
(E_risk^(1,2,3), partition_mode=True), the analytical Lemma 1 eta_eff(Delta t) drift bound,
and Phase-2 consensus hysteresis across 5 graph topologies and Theta = {theta_1, theta_2, theta_3}.

Compares:
  - aca (Active Bayesian Inference + Pinsker Margin + Consensus Hysteresis)
  - aca_no_inference (Static Uniform Prior)
  - aca_no_margin (No Margin, kappa=0)
  - cbba_lr (Standard CBBA with Level Recourse)

Saves results to: results/confirmatory/partitioned_adversary_eval.csv
"""

import os
import sys
import time
import math
from typing import Dict, Any, List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from experiments.run_sweep import build_crn_environment, compute_trial_hash
from acalib.env.adversaries import AdversaryType, partition_risky_edges, canonical_edge
from acalib.sim.engine import SimulationEngine
from acalib.utils.gitinfo import get_git_commit

ENVIRONMENTS = [
    ("warehouse_movingai", 38),
    ("road_osmnx", 216),
    ("rgg", 35),
    ("warehouse", 30),
    ("er", 35),
]

ADVERSARIES = [
    "theta_1_stochastic",
    "theta_2_reactive",
    "theta_3_budgeted_interdiction",
]

METHODS = [
    "aca",
    "aca_no_inference",
    "aca_no_margin",
    "cbba_lr",
]

EVAL_SEEDS = list(range(1, 21))  # 20 matched seeds: 20 seeds x 5 topols x 3 advs = 300 instances


def run_partitioned_trial(args: Tuple) -> Dict[str, Any]:
    graph_family, n_nodes, adv_str, method, seed, max_steps = args
    t_start = time.perf_counter()

    env_components = build_crn_environment(
        graph_family=graph_family,
        n_nodes=n_nodes,
        seed=seed,
        n_robots=4,
        n_tasks=15,
        max_steps=max_steps,
    )

    graph = env_components["graph"]
    risky_edges = env_components["risky_edges"]

    # Explicitly ensure partition classes E_risk^(1,2,3) are assigned
    partition_risky_edges(graph, risky_edges)

    adv_enum = AdversaryType(adv_str)
    c_depth = 1 if (method.startswith("aca") or method.endswith("_lr")) else 0

    engine = SimulationEngine(
        graph=graph,
        adversary_type=adv_enum,
        allocator_type=method,
        n_robots=4,
        n_tasks=15,
        task_deadline=max_steps,
        max_steps=max_steps,
        comm_range=30.0,
        p_drop=0.10,
        contingency_depth=c_depth,
        custom_start_nodes=env_components["start_nodes"],
        custom_tasks=env_components["tasks"],
        predrawn_clear_uniforms=env_components["predrawn_clear"],
        predrawn_onset_uniforms=env_components["predrawn_onset"],
        custom_risky_edges=risky_edges,
        comm_net_seed=env_components["comm_seed"],
        record_traces=False,
        partition_mode=True,
    )

    metrics = engine.run(max_steps=max_steps)
    summary = metrics.compute_summary()
    t_end = time.perf_counter()

    row = {
        "graph_family": graph_family,
        "n_nodes": n_nodes,
        "adversary": adv_str,
        "method": method,
        "comm_regime": "nominal",
        "comm_range": 30.0,
        "p_drop": 0.10,
        "n_robots": 4,
        "n_tasks": 15,
        "seed": seed,
        "partition_mode": True,
        "max_steps": max_steps,
        "completed_tasks": summary.get("completed_tasks", 0),
        "completion_rate_pct": summary.get("completion_rate_pct", 0.0),
        "net_welfare": summary.get("net_welfare", 0.0),
        "total_travel_distance": summary.get("total_travel_distance", 0.0),
        "total_messages": summary.get("total_messages", 0),
        "total_conflicts": summary.get("total_conflicts", 0),
        "distinct_conflicts": summary.get("distinct_conflicts", 0),
        "safe_claim_conflicts": summary.get("safe_claim_conflicts", 0),
        "safe_claims": summary.get("safe_claims", 0),
        "deferred_claims": summary.get("deferred_claims", 0),
        "mean_tick_runtime_ms": summary.get("mean_tick_runtime_ms", 0.0),
        "wall_clock_seconds": round(t_end - t_start, 4),
        "status": "COMPLETED",
    }
    return row


def main():
    print("=" * 70)
    print("RUNNING PARTITIONED ADVERSARY VERIFICATION SWEEP (partition_mode=True)")
    print(f"Topologies: {len(ENVIRONMENTS)}, Adversaries: {len(ADVERSARIES)}, Seeds: {len(EVAL_SEEDS)}")
    print(f"Total instances: {len(ENVIRONMENTS) * len(ADVERSARIES) * len(EVAL_SEEDS)} x {len(METHODS)} methods = {len(ENVIRONMENTS) * len(ADVERSARIES) * len(EVAL_SEEDS) * len(METHODS)} trials")
    print("=" * 70)

    tasks = []
    max_steps = 80
    for fam, n_nodes in ENVIRONMENTS:
        for adv in ADVERSARIES:
            for seed in EVAL_SEEDS:
                for method in METHODS:
                    tasks.append((fam, n_nodes, adv, method, seed, max_steps))

    results = []
    t0 = time.time()
    n_workers = max(1, os.cpu_count() or 4)
    print(f"Dispatching across {n_workers} workers...")

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(run_partitioned_trial, t): t for t in tasks}
        completed = 0
        total = len(tasks)
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            completed += 1
            if completed % 25 == 0 or completed == total:
                elapsed = time.time() - t0
                rate = completed / max(0.1, elapsed)
                print(f"  [{completed}/{total}] ({completed/total*100:.1f}%) in {elapsed:.1f}s ({rate:.1f} trials/s)", flush=True)

    df = pd.DataFrame(results)
    out_dir = os.path.join(REPO_ROOT, "results", "confirmatory")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "partitioned_v5_adversary_eval.csv")
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {len(df)} trials to: {out_csv}")

    # Compute Statistical Breakdown
    print("\n" + "=" * 70)
    print("PARTITIONED SWEEP SUMMARY METRICS (N = 300 MATCHED INSTANCES)")
    print("=" * 70)

    for adv in ADVERSARIES:
        print(f"\n--- Adversary: {adv} ---")
        sub_adv = df[df["adversary"] == adv]
        aca_comp = sub_adv[sub_adv["method"] == "aca"]["completion_rate_pct"].values
        aca_welf = sub_adv[sub_adv["method"] == "aca"]["net_welfare"].values

        for m in METHODS:
            m_comp = sub_adv[sub_adv["method"] == m]["completion_rate_pct"].values
            m_welf = sub_adv[sub_adv["method"] == m]["net_welfare"].values
            m_safe_conf = sub_adv[sub_adv["method"] == m]["safe_claim_conflicts"].values
            m_tot_conf = sub_adv[sub_adv["method"] == m]["total_conflicts"].values

            diff = m_comp - aca_comp
            mean_d = float(np.mean(diff)) if m != "aca" else 0.0
            p_val = 1.0
            if m != "aca" and not np.all(m_comp == aca_comp):
                res = stats.wilcoxon(aca_comp, m_comp, zero_method="pratt")
                p_val = float(res.pvalue)

            print(f"  {m:18}: Completion = {np.mean(m_comp):.1f}% ± {1.96*np.std(m_comp)/math.sqrt(len(m_comp)):.1f}% | Welfare = {np.mean(m_welf):.0f} | SafeConf = {np.mean(m_safe_conf):.2f} | TotConf = {np.mean(m_tot_conf):.1f} | Diff vs ACA: {mean_d:+.2f} pp (p={p_val:.3e})")

    # Overall
    print("\n--- OVERALL ALL 3 ADVERSARIES COMBINED (N = 300) ---")
    aca_comp_all = df[df["method"] == "aca"]["completion_rate_pct"].values
    for m in METHODS:
        m_comp = df[df["method"] == m]["completion_rate_pct"].values
        m_welf = df[df["method"] == m]["net_welfare"].values
        m_safe_conf = df[df["method"] == m]["safe_claim_conflicts"].values
        m_tot_conf = df[df["method"] == m]["total_conflicts"].values
        diff = m_comp - aca_comp_all
        mean_d = float(np.mean(diff)) if m != "aca" else 0.0
        p_val = 1.0
        if m != "aca" and not np.all(m_comp == aca_comp_all):
            res = stats.wilcoxon(aca_comp_all, m_comp, zero_method="pratt")
            p_val = float(res.pvalue)
        print(f"  {m:18}: Completion = {np.mean(m_comp):.1f}% ± {1.96*np.std(m_comp)/math.sqrt(len(m_comp)):.1f}% | Welfare = {np.mean(m_welf):.0f} | SafeConf = {np.mean(m_safe_conf):.2f} | TotConf = {np.mean(m_tot_conf):.1f} | Diff vs ACA: {mean_d:+.2f} pp (p={p_val:.3e})")


if __name__ == "__main__":
    main()
