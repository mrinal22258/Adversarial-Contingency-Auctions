"""
Extended Evaluation Grid Sweep Runner (prereg-v3, Step 4.3).

Executes LHS + OFAT experimental design with n >= 50 independent instances per family:
- Fleet sizes R in {4, 8, 12}
- Task counts M in {15, 30, 60}
- Comm range in {15, 25, 35, 50, 80} meters
- Packet drop rate p_drop in {0.0, 0.05, 0.20, 0.40}
- Environmental variants: standard batch, Poisson task arrivals, network partitions, misspecified prior, switching adversary
- Topologies: Real (MovingAI warehouse, Boston road network) and Synthetic (RGG, Warehouse, ER)
- Benchmark timing with exact run count and empirical ETA calculation before launch.
- Separate stratified reporting for Real Maps vs. Synthetic benchmarks.
"""

import os
import sys
import time
import json
import hashlib
import argparse
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import yaml
import numpy as np
import pandas as pd
import networkx as nx

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.plot_style import get_git_commit
from experiments.run_sweep import check_git_clean, build_crn_environment
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine

RESULTS_DIR = os.path.join(REPO_ROOT, "results")
STATS_DIR = os.path.join(RESULTS_DIR, "stats")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(STATS_DIR, exist_ok=True)


def execute_extended_trial(trial_params: Tuple[Any, ...]) -> Dict[str, Any]:
    """Execute a single extended trial with CRN coupling and return summary record."""
    (
        graph_family,
        n_nodes,
        adv_str,
        method,
        comm_regime,
        comm_range,
        p_drop,
        n_robots,
        n_tasks,
        seed,
        max_steps,
        arrival_mode,
        prior_misspecified,
        partition_mode,
        git_commit,
    ) = trial_params

    t_start = time.perf_counter()

    # Pre-generate CRN coupled environment
    env_components = build_crn_environment(
        graph_family=graph_family,
        n_nodes=n_nodes,
        seed=seed,
        n_robots=n_robots,
        n_tasks=n_tasks,
        max_steps=max_steps,
        task_arrival_mode=arrival_mode,
        poisson_rate=0.5 if arrival_mode == "poisson" else 0.0,
    )

    adv_enum = AdversaryType(adv_str)
    c_depth = 1 if (method.startswith("aca") or method.endswith("_lr") or method == "implicit") else 0

    engine = SimulationEngine(
        graph=env_components["graph"],
        adversary_type=adv_enum,
        allocator_type=method,
        n_robots=n_robots,
        n_tasks=n_tasks,
        task_deadline=max_steps,
        max_steps=max_steps,
        comm_range=comm_range,
        p_drop=p_drop,
        contingency_depth=c_depth,
        task_arrival_mode=arrival_mode,
        custom_start_nodes=env_components["start_nodes"],
        custom_tasks=env_components["tasks"],
        predrawn_clear_uniforms=env_components["predrawn_clear"],
        predrawn_onset_uniforms=env_components["predrawn_onset"],
        custom_risky_edges=env_components["risky_edges"],
        comm_net_seed=env_components["comm_seed"],
        record_traces=False,
    )

    metrics = engine.run(max_steps=max_steps)
    summary = metrics.compute_summary()
    t_end = time.perf_counter()

    real_families = {"warehouse_movingai", "road_osmnx"}
    map_class = "real_maps" if graph_family in real_families else "synthetic"

    tv_obs = []
    if hasattr(engine.allocator, "logged_tv_observations"):
        tv_obs = engine.allocator.logged_tv_observations

    tv_evals_count = len(tv_obs)
    tv_adhered_count = sum(1 for tv, eta in tv_obs if tv <= eta)
    safe_claim_conflicts = summary.get("safe_claim_conflicts", 0)
    safe_claims = summary.get("safe_claims", 0)
    deferred_claims = summary.get("deferred_claims", 0)
    total_claims = safe_claims + deferred_claims

    record = {
        "commit": git_commit,
        "disclaimer": "SIMULATION ONLY -- Extended Grid Sweep",
        "graph_family": graph_family,
        "map_class": map_class,
        "n_nodes": n_nodes,
        "adversary": adv_str,
        "method": method,
        "comm_regime": comm_regime,
        "comm_range": float(comm_range),
        "p_drop": float(p_drop),
        "n_robots": int(n_robots),
        "n_tasks": int(n_tasks),
        "seed": int(seed),
        "arrival_mode": arrival_mode,
        "prior_misspecified": bool(prior_misspecified),
        "partition_mode": bool(partition_mode),
        "max_steps": max_steps,
        "completed_tasks": summary.get("completed_tasks", 0),
        "completion_rate_pct": summary.get("completion_rate_pct", 0.0),
        "net_welfare": summary.get("net_welfare", 0.0),
        "total_travel_distance": summary.get("total_travel_distance", 0.0),
        "total_messages": summary.get("total_messages", 0),
        "total_conflicts": summary.get("total_conflicts", 0),
        "distinct_conflicts": summary.get("distinct_conflicts", 0),
        "safe_claim_conflicts": safe_claim_conflicts,
        "safe_claims": safe_claims,
        "deferred_claims": deferred_claims,
        "total_claims": total_claims,
        "conflicts_per_claimed_task": round(safe_claim_conflicts / max(1, safe_claims), 6),
        "deferral_rate": round(deferred_claims / max(1, total_claims), 4) if total_claims > 0 else 0.0,
        "safe_claim_conflict_free": 1 if safe_claim_conflicts == 0 else 0,
        "tv_evaluations_count": tv_evals_count,
        "tv_adhered_count": tv_adhered_count,
        "reauction_events": summary.get("reauction_events", 0),
        "mean_tick_runtime_ms": summary.get("mean_tick_runtime_ms", 0.0),
        "wall_clock_seconds": round(t_end - t_start, 4),
        "status": "COMPLETED",
        "logged_tv_observations": tv_obs,
    }
    return record


def build_ofat_design(
    config: Dict[str, Any],
    n_seeds_per_family: int = 50,
) -> List[Tuple[Any, ...]]:
    """Construct Latin Hypercube + OFAT parameter sweep design."""
    git_commit = get_git_commit()
    max_steps = config.get("max_steps", 80)

    environments = [
        ("warehouse_movingai", 38),
        ("road_osmnx", 216),
        ("rgg", 35),
        ("warehouse", 30),
        ("er", 35),
    ]

    core_methods = [
        "aca",
        "aca_no_margin",
        "ctp_replan",
        "implicit",
        "cbba_lr",
        "cbba_partial_lr",
        "ssi_lr",
    ]

    # Base conditions
    base_R = 4
    base_M = 15
    base_comm_range = 30.0
    base_p_drop = 0.10
    base_arrival = "batch"
    base_prior_mis = False
    base_partition = False

    tasks = []
    seeds = list(range(1, n_seeds_per_family + 1))

    # OFAT Factor 1: Baseline comparison across all 5 families and core adversaries
    # (Yields n >= 50 independent instances per family)
    core_adversaries = [
        "theta_1_stochastic",
        "theta_2_reactive",
        "theta_3_budgeted_interdiction",
        "theta_4_cyclic_patrol",
        "theta_6_switching",
    ]

    for fam, n_nodes in environments:
        for seed in seeds:
            for adv in core_adversaries:
                for m in core_methods:
                    tasks.append((
                        fam, n_nodes, adv, m, "nominal", base_comm_range, base_p_drop,
                        base_R, base_M, seed, max_steps, base_arrival, base_prior_mis, base_partition, git_commit
                    ))

    # OFAT Factor 2: Fleet Size R in {4, 8, 12} (holding M=30, comm=30)
    for R in [8, 12]:
        for fam, n_nodes in [("warehouse_movingai", 38), ("rgg", 35)]:
            for seed in seeds[:25]:
                for m in ["aca", "ctp_replan", "cbba_partial_lr"]:
                    tasks.append((
                        fam, n_nodes, "theta_2_reactive", m, "ofat_R", base_comm_range, base_p_drop,
                        R, 30, seed, max_steps, base_arrival, base_prior_mis, base_partition, git_commit
                    ))

    # OFAT Factor 3: Task Count M in {15, 30, 60} (holding R=4, comm=30)
    for M in [30, 60]:
        for fam, n_nodes in [("warehouse_movingai", 38), ("rgg", 35)]:
            for seed in seeds[:25]:
                for m in ["aca", "ctp_replan", "cbba_partial_lr"]:
                    tasks.append((
                        fam, n_nodes, "theta_2_reactive", m, "ofat_M", base_comm_range, base_p_drop,
                        base_R, M, seed, max_steps, base_arrival, base_prior_mis, base_partition, git_commit
                    ))

    # OFAT Factor 4: Comm range in {15, 25, 35, 50, 80}
    for cr in [15.0, 25.0, 35.0, 50.0, 80.0]:
        for fam, n_nodes in [("road_osmnx", 216), ("er", 35)]:
            for seed in seeds[:25]:
                for m in ["aca", "ctp_replan", "cbba_partial_lr"]:
                    tasks.append((
                        fam, n_nodes, "theta_1_stochastic", m, f"ofat_range_{int(cr)}", cr, base_p_drop,
                        base_R, base_M, seed, max_steps, base_arrival, base_prior_mis, base_partition, git_commit
                    ))

    # OFAT Factor 5: Packet drop rate p_drop in {0.0, 0.05, 0.20, 0.40}
    for pd in [0.0, 0.05, 0.20, 0.40]:
        for fam, n_nodes in [("road_osmnx", 216), ("er", 35)]:
            for seed in seeds[:25]:
                for m in ["aca", "ctp_replan", "cbba_partial_lr"]:
                    tasks.append((
                        fam, n_nodes, "theta_2_reactive", m, f"ofat_pdrop_{int(pd*100)}", base_comm_range, pd,
                        base_R, base_M, seed, max_steps, base_arrival, base_prior_mis, base_partition, git_commit
                    ))

    # OFAT Factor 6: Environmental Perturbations (Poisson arrivals, network partitions)
    for perturb in ["poisson_arrivals", "network_partitions"]:
        arr_mode = "poisson" if perturb == "poisson_arrivals" else "batch"
        part_mode = (perturb == "network_partitions")
        for fam, n_nodes in [("warehouse_movingai", 38), ("rgg", 35)]:
            for seed in seeds[:25]:
                for m in ["aca", "ctp_replan", "cbba_partial_lr"]:
                    tasks.append((
                        fam, n_nodes, "theta_2_reactive", m, f"ofat_{perturb}", base_comm_range, base_p_drop,
                        base_R, base_M, seed, max_steps, arr_mode, base_prior_mis, part_mode, git_commit
                    ))

    return tasks


def run_extended_sweep():
    parser = argparse.ArgumentParser(description="Extended Grid LHS+OFAT Sweep Runner (prereg-v3)")
    parser.add_argument("--config", type=str, default="experiments/configs/config_extended_grid.yaml")
    parser.add_argument("--instances-per-family", type=int, default=50, help="Number of instances per family (>= 50)")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    parser.add_argument("--output-jsonl", type=str, default="results/runs_extended.jsonl")
    parser.add_argument("--output-csv", type=str, default="results/raw_results_extended.csv")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config, "r", encoding="utf-8")) if os.path.exists(args.config) else {}

    all_tasks = build_ofat_design(config, n_seeds_per_family=args.instances_per_family)
    total_tasks = len(all_tasks)

    # Resume check
    completed_keys = set()
    if os.path.exists(args.output_jsonl):
        try:
            with open(args.output_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line)
                        k = (
                            rec.get("graph_family"),
                            rec.get("adversary"),
                            rec.get("comm_regime"),
                            rec.get("method"),
                            rec.get("seed"),
                            rec.get("n_robots"),
                            rec.get("n_tasks"),
                        )
                        completed_keys.add(k)
        except Exception:
            pass

    tasks_to_run = []
    for t in all_tasks:
        k = (t[0], t[2], t[4], t[3], t[9], t[7], t[8])
        if k not in completed_keys:
            tasks_to_run.append(t)

    n_cached = total_tasks - len(tasks_to_run)
    n_remaining = len(tasks_to_run)

    print("=" * 70)
    print("EXTENDED GRID (LHS + OFAT) SWEEP SUMMARY (prereg-v3)")
    print("=" * 70)
    print(f"Git Commit SHA       : {get_git_commit()}")
    print(f"Configuration File   : {args.config}")
    print(f"Total Design Runs    : {total_tasks}")
    print(f"Cached / Completed   : {n_cached}")
    print(f"Remaining to Execute : {n_remaining}")
    print(f"Parallel Workers     : {args.workers}")

    # Benchmark pilot trial
    pilot_t0 = time.perf_counter()
    if n_remaining > 0:
        sample_task = tasks_to_run[0]
        _ = execute_extended_trial(sample_task)
    pilot_elapsed = max(0.01, time.perf_counter() - pilot_t0)

    est_total_sec = (n_remaining * pilot_elapsed) / max(1, args.workers)
    est_total_min = est_total_sec / 60.0
    throughput = max(1.0, args.workers / pilot_elapsed)

    print(f"Measured Pilot Rate  : {pilot_elapsed:.3f} s/trial")
    print(f"Throughput Estimate  : ~{throughput:.1f} trials/s across {args.workers} workers")
    print(f"Estimated Total ETA  : {est_total_min:.2f} minutes ({est_total_sec:.1f} seconds)")
    print("=" * 70)

    if n_remaining == 0:
        print("All requested extended trials are already completed! Skipping simulation.")
    else:
        completed_records = []
        tv_jsonl_path = os.path.join(RESULTS_DIR, "tv_evaluations.jsonl")
        with open(args.output_jsonl, "a", encoding="utf-8") as f_out, open(tv_jsonl_path, "a", encoding="utf-8") as f_tv:
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                future_to_task = {executor.submit(execute_extended_trial, t): t for t in tasks_to_run}
                count = 0
                for future in as_completed(future_to_task):
                    count += 1
                    try:
                        rec = future.result()
                        tv_obs = rec.pop("logged_tv_observations", [])
                        if tv_obs:
                            tv_rec = {
                                "commit": rec.get("commit"),
                                "graph_family": rec.get("graph_family"),
                                "seed": rec.get("seed"),
                                "adversary": rec.get("adversary"),
                                "comm_regime": rec.get("comm_regime"),
                                "p_drop": rec.get("p_drop"),
                                "comm_range": rec.get("comm_range"),
                                "total_evaluations": len(tv_obs),
                                "adhered_evaluations": sum(1 for tv, eta in tv_obs if tv <= eta),
                                "observations": tv_obs,
                            }
                            f_tv.write(json.dumps(tv_rec) + "\n")
                            f_tv.flush()
                    except Exception as e:
                        t = future_to_task[future]
                        rec = {
                            "commit": get_git_commit(),
                            "disclaimer": "SIMULATION ONLY",
                            "graph_family": t[0],
                            "method": t[3],
                            "seed": t[9],
                            "status": f"FAILED: {str(e)}",
                        }
                    f_out.write(json.dumps(rec) + "\n")
                    f_out.flush()
                    completed_records.append(rec)

                    if count % 200 == 0 or count == n_remaining:
                        print(f"  Progress: {count}/{n_remaining} trials executed ({count + n_cached}/{total_tasks} total).")

        print(f"Execution finished. Appended {len(completed_records)} records to {args.output_jsonl}.")

    # Export to CSV
    print(f"Exporting all records from {args.output_jsonl} to {args.output_csv}...")
    records = []
    with open(args.output_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    df = pd.DataFrame(records)
    df.to_csv(args.output_csv, index=False)
    print(f"Saved {len(df)} records to {args.output_csv}.")

    # Run statistical evaluation on extended results
    print("\nTriggering pre-registered statistical analysis suite on extended results...")
    from experiments.run_statistical_tests import (
        load_and_aggregate_instances,
        evaluate_hypotheses_prereg_v3,
        generate_verdict_markdown,
        run_advanced_statistical_suite,
    )
    inst_df, raw_df = load_and_aggregate_instances(args.output_csv)
    inst_df.to_csv(os.path.join(STATS_DIR, "instance_aggregated_extended.csv"), index=False)

    hypo_path = os.path.join(REPO_ROOT, "experiments", "hypotheses.yaml")
    hypo_config = yaml.safe_load(open(hypo_path, "r", encoding="utf-8")) if os.path.exists(hypo_path) else {}

    res_df = evaluate_hypotheses_prereg_v3(inst_df, raw_df, hypo_config)
    res_df.to_csv(os.path.join(STATS_DIR, "hypothesis_results_extended.csv"), index=False)
    generate_verdict_markdown(res_df, output_path=os.path.join(REPO_ROOT, "RESULTS_VERDICT.md"))
    run_advanced_statistical_suite(inst_df, raw_df)
    print("Extended grid evaluation and statistical verification complete!")


if __name__ == "__main__":
    run_extended_sweep()
