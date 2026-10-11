"""
High-Fidelity Simulation Runner and Paired Benchmark Evaluator for ACA Demo.
Coupled with experiments/run_sweep.py common random number streams (CRN) and
results/stats/instance_aggregated.csv empirical archives.
"""

import os
import json
import time
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
import networkx as nx
import concurrent.futures

from experiments.run_sweep import build_crn_environment
from experiments.stats import bootstrap_ci
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine

# Universal shared simulation horizon
DEFAULT_MAX_STEPS = 80

# In-memory execution cache for fast interactive scrubbing and comparison
_RUN_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPER_STATS_CSV = os.path.join(REPO_ROOT, "results", "stats", "instance_aggregated.csv")

METHOD_NAME_MAP = {
    "aca": "ACA (Ours)",
    "aca_adaptive": "ACA-Adaptive (Entropy Calibrated)",
    "aca_plus": "ACA+ (Adaptive + Corridor Pruning)",
    "aca_no_margin": "ACA (No Margin Ablation)",
    "aca_depth_0": "ACA (Depth-0 Ablation)",
    "aca_depth_2": "ACA (Depth-2)",
    "aca_no_inference": "ACA (No Inference)",
    "cbba": "CBBA [Choi '09]",
    "cbba_lr": "CBBA (+LR)",
    "cbba_partial": "CBBA-PR (Adapted) [Buckman '19]",
    "cbba_partial_lr": "CBBA-PR (+LR)",
    "ssi": "SSI [Koenig '06]",
    "ssi_lr": "SSI (+LR)",
    "ctp_replan": "CTP Replan",
    "implicit": "Implicit (No Consensus) [Alighanbari '05]",
    "clairvoyant_greedy": "Clairvoyant greedy (reference, not a bound)",
    "foresight_opt": "Foresight Optimal (CP-SAT benchmark)",
}

REV_METHOD_MAP = {v: k for k, v in METHOD_NAME_MAP.items()}
REV_METHOD_MAP["ACA (Ours)"] = "aca"
REV_METHOD_MAP["ACA-v1"] = "aca"
REV_METHOD_MAP["ACA-v1 (Ours)"] = "aca"
REV_METHOD_MAP["ACA-Adaptive"] = "aca_adaptive"
REV_METHOD_MAP["ACA-Adaptive (Entropy Calibrated)"] = "aca_adaptive"
REV_METHOD_MAP["ACA+"] = "aca_plus"
REV_METHOD_MAP["ACA+ (Adaptive + Corridor Pruning)"] = "aca_plus"
REV_METHOD_MAP["ACA (No Margin)"] = "aca_no_margin"
REV_METHOD_MAP["ACA (No Margin Ablation)"] = "aca_no_margin"
REV_METHOD_MAP["ACA (Depth-0)"] = "aca_depth_0"
REV_METHOD_MAP["ACA (Depth-0 Ablation)"] = "aca_depth_0"
REV_METHOD_MAP["ACA (Depth-2)"] = "aca_depth_2"
REV_METHOD_MAP["ACA (No Inference)"] = "aca_no_inference"
REV_METHOD_MAP["CBBA"] = "cbba"
REV_METHOD_MAP["CBBA (+LR)"] = "cbba_lr"
REV_METHOD_MAP["CBBA-PR (+LR)"] = "cbba_partial_lr"
REV_METHOD_MAP["CBBA-Partial"] = "cbba_partial"
REV_METHOD_MAP["CC-CBBA"] = "cc_cbba"
REV_METHOD_MAP["Implicit (No Margin)"] = "implicit"
REV_METHOD_MAP["Implicit"] = "implicit"
REV_METHOD_MAP["Sequential Single-Item (SSI)"] = "ssi"
REV_METHOD_MAP["SSI"] = "ssi"
REV_METHOD_MAP["Pessimistic Robust"] = "pessimistic"
REV_METHOD_MAP["Centralized Oracle"] = "clairvoyant_greedy"
REV_METHOD_MAP["Oracle"] = "clairvoyant_greedy"

ADVERSARY_NAME_MAP = {
    "theta_1_stochastic": "Stochastic (Static/Poisson)",
    "theta_2_reactive": "Reactive (Corridor Interdiction)",
    "theta_3_budgeted_interdiction": "Budgeted Interdiction",
    "theta_4_cyclic_patrol": "Cyclic Patrol",
}

REV_ADV_MAP = {v: k for k, v in ADVERSARY_NAME_MAP.items()}
REV_ADV_MAP["Stochastic"] = "theta_1_stochastic"
REV_ADV_MAP["Reactive"] = "theta_2_reactive"
REV_ADV_MAP["Budgeted Interdiction"] = "theta_3_budgeted_interdiction"
REV_ADV_MAP["Cyclic Patrol"] = "theta_4_cyclic_patrol"


def parse_allocator_name(alloc_input: str) -> str:
    """Normalize user-facing or internal allocator name."""
    if alloc_input in METHOD_NAME_MAP:
        return alloc_input
    if alloc_input in REV_METHOD_MAP:
        return REV_METHOD_MAP[alloc_input]
    cleaned = (
        alloc_input.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
    )
    if cleaned in REV_METHOD_MAP:
        return REV_METHOD_MAP[cleaned]
    return cleaned


def parse_adversary_name(adv_input: str) -> str:
    """Normalize user-facing or internal adversary name."""
    if adv_input in ADVERSARY_NAME_MAP:
        return adv_input
    if adv_input in REV_ADV_MAP:
        return REV_ADV_MAP[adv_input]
    return "theta_2_reactive"


def run_single_simulation(
    graph_family: str,
    n_nodes: int,
    adversary_str: str,
    allocator_str: str,
    comm_regime: str = "benign",
    comm_range: float = 50.0,
    p_drop: float = 0.02,
    n_robots: int = 4,
    n_tasks: int = 15,
    seed: int = 10001,
    max_steps: int = DEFAULT_MAX_STEPS,
    contingency_depth: int = 1,
    risk_fraction: float = 0.25,
    clearance_rate: float = 0.15,
    adversary_budget_k: int = 4,
    variant: str = "10-20-10-2-1",
    prebuilt_env: Optional[Dict[str, Any]] = None,
    record_history: bool = True,
    record_traces: bool = True,
) -> Dict[str, Any]:
    """
    Execute discrete simulation stepping identical to sweep harness.
    Records tick-by-tick state history when record_history=True.
    When record_history=False, runs pure headless simulation with minimal overhead.
    """
    alloc_type = parse_allocator_name(allocator_str)
    adv_type_str = parse_adversary_name(adversary_str)
    adv_enum = AdversaryType(adv_type_str)

    # 1. Build or use CRN coupled environment
    if prebuilt_env is not None:
        env_components = prebuilt_env
    else:
        env_components = build_crn_environment(
            graph_family=graph_family,
            n_nodes=n_nodes,
            seed=seed,
            n_robots=n_robots,
            n_tasks=n_tasks,
            max_steps=max_steps,
            risk_fraction=risk_fraction,
            task_arrival_mode="batch",
            task_deadline=max_steps,
            variant=variant,
        )

    # Contingency depth resolution
    if alloc_type == "aca_depth_0":
        c_depth = 0
    elif alloc_type == "aca_depth_2":
        c_depth = 2
    elif alloc_type.endswith("_lr") or alloc_type.startswith("aca"):
        c_depth = contingency_depth if contingency_depth > 0 else 1
    else:
        c_depth = 0

    engine = SimulationEngine(
        graph=env_components["graph"],
        adversary_type=adv_enum,
        allocator_type=alloc_type,
        n_robots=n_robots,
        n_tasks=n_tasks,
        task_deadline=max_steps,
        max_steps=max_steps,
        comm_range=comm_range,
        p_drop=p_drop,
        contingency_depth=c_depth,
        risk_fraction=risk_fraction,
        clearance_rate=clearance_rate,
        adversary_budget_k=adversary_budget_k,
        custom_start_nodes=env_components["start_nodes"],
        custom_tasks=env_components["tasks"],
        predrawn_clear_uniforms=env_components["predrawn_clear"],
        predrawn_onset_uniforms=env_components["predrawn_onset"],
        custom_risky_edges=env_components["risky_edges"],
        comm_net_seed=env_components["comm_seed"],
        record_traces=record_traces,
    )

    history = []
    prev_blocked = set()
    prev_conflicts = 0
    prev_deferred = 0

    engine.reset(max_steps=max_steps)

    for step in range(max_steps):
        cont = engine.step(step)

        if record_history:
            blocked_edges = list(engine.blockage_process.get_active_blockages())
            curr_blocked_set = set(tuple(sorted(e)) for e in blocked_edges)
            newly_blocked = list(curr_blocked_set - prev_blocked)

            robot_snaps = []
            active_detour_edges = set()
            for r in engine.robots.values():
                loc = r.current_node
                took_detour = (r.status == "PIVOTED")
                if took_detour and len(r.active_path) > 1:
                    for idx in range(max(0, r.path_index - 1), min(len(r.active_path) - 1, r.path_index + 2)):
                        active_detour_edges.add((r.active_path[idx], r.active_path[idx + 1]))

                planned_route = list(r.active_path) if hasattr(r, "active_path") else []
                robot_snaps.append({
                    "id": r.robot_id,
                    "location": loc,
                    "pos": list(r.pos),
                    "status": r.status,
                    "active_task": r.active_task_id,
                    "bundle": list(r.bundle),
                    "planned_route": planned_route,
                    "took_local_detour": took_detour,
                })

            task_snaps = []
            for tid, t in engine.tasks.items():
                task_snaps.append({
                    "id": tid,
                    "location": t.node,
                    "reward": t.reward,
                    "is_completed": t.completed,
                    "completed_by": t.completed_by,
                    "claimed_by": getattr(t, "claimed_by", None),
                })

            conflicts_this_tick = engine.metrics.cumulative_conflicts - prev_conflicts
            deferred_this_tick = engine.metrics.deferred_claims - prev_deferred
            total_msgs = engine.comm_net.total_messages_sent
            welfare = engine.metrics.total_reward - engine.metrics.total_travel_distance

            history.append({
                "tick": step + 1,
                "robots": robot_snaps,
                "tasks": task_snaps,
                "blocked_edges": blocked_edges,
                "newly_blocked": newly_blocked,
                "active_detours": list(active_detour_edges),
                "completed_tasks": engine.metrics.completed_tasks,
                "conflicts": engine.metrics.cumulative_conflicts,
                "conflicts_this_tick": conflicts_this_tick,
                "messages": total_msgs,
                "travel": float(engine.metrics.total_travel_distance),
                "welfare": float(welfare),
                "safe_claims": engine.metrics.safe_claims,
                "deferred_claims": engine.metrics.deferred_claims,
                "deferred_claims_this_tick": deferred_this_tick,
                "reauction_events": engine.metrics.reauction_events,
            })

            prev_blocked = curr_blocked_set
            prev_conflicts = engine.metrics.cumulative_conflicts
            prev_deferred = engine.metrics.deferred_claims

        if not cont:
            break

    # Finalize
    final_metrics = engine.finalize()
    summary = final_metrics.compute_summary()
    summary["completed_tasks"] = final_metrics.completed_tasks
    summary["total_tasks"] = final_metrics.total_tasks
    summary["completion_rate_pct"] = (final_metrics.completed_tasks / max(1, final_metrics.total_tasks)) * 100.0
    summary["total_messages"] = final_metrics.total_messages_sent
    summary["total_messages_sent"] = final_metrics.total_messages_sent
    summary["total_conflicts"] = final_metrics.total_conflicts
    summary["distinct_conflicts"] = final_metrics.distinct_conflicts
    summary["safe_claim_conflicts"] = final_metrics.safe_claim_conflicts
    summary["safe_claims"] = final_metrics.safe_claims
    summary["deferred_claims"] = final_metrics.deferred_claims
    summary["reauction_events"] = final_metrics.reauction_events
    summary["net_welfare"] = final_metrics.net_welfare
    summary["total_travel_distance"] = final_metrics.total_travel_distance
    summary["makespan"] = final_metrics.makespan
    summary["total_robots"] = final_metrics.total_robots

    graph = env_components["graph"]
    pos = nx.get_node_attributes(graph, "pos")
    if not pos:
        pos = {n: (0.0, 0.0) for n in graph.nodes()}

    return {
        "history": history,
        "summary": summary,
        "graph": graph,
        "pos": pos,
        "env_components": env_components,
    }


def get_cached_run(
    graph_family: str,
    n_nodes: int,
    adversary_str: str,
    allocator_str: str,
    comm_regime: str = "benign",
    comm_range: float = 50.0,
    p_drop: float = 0.02,
    n_robots: int = 4,
    n_tasks: int = 15,
    seed: int = 10001,
    max_steps: int = DEFAULT_MAX_STEPS,
    contingency_depth: int = 1,
    variant: str = "10-20-10-2-1",
) -> Dict[str, Any]:
    """Retrieve run from cache or execute and populate."""
    cache_key = (
        graph_family,
        n_nodes,
        adversary_str,
        allocator_str,
        comm_regime,
        comm_range,
        p_drop,
        n_robots,
        n_tasks,
        seed,
        max_steps,
        contingency_depth,
        variant,
    )
    if cache_key in _RUN_CACHE:
        return _RUN_CACHE[cache_key]

    res = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str=adversary_str,
        allocator_str=allocator_str,
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=contingency_depth,
        variant=variant,
        record_history=True,
    )
    _RUN_CACHE[cache_key] = res
    return res


def run_paired_comparison(
    graph_family: str,
    n_nodes: int,
    adversary_str: str,
    selected_allocator_str: str,
    comm_regime: str = "benign",
    comm_range: float = 50.0,
    p_drop: float = 0.02,
    n_robots: int = 4,
    n_tasks: int = 15,
    seed: int = 10001,
    max_steps: int = DEFAULT_MAX_STEPS,
    contingency_depth: int = 1,
    variant: str = "10-20-10-2-1",
) -> Dict[str, Any]:
    """
    Run selected method alongside CBBA, CBBA-PR (+LR), and CTP Replan on identical CRN environment.
    """
    main_run = get_cached_run(
        graph_family, n_nodes, adversary_str, selected_allocator_str,
        comm_regime, comm_range, p_drop, n_robots, n_tasks, seed, max_steps,
        contingency_depth, variant,
    )
    env_components = main_run["env_components"]

    # 1. CBBA-PR (+LR)
    cbba_lr_run = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str=adversary_str,
        allocator_str="cbba_partial_lr",
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=1,
        variant=variant,
        prebuilt_env=env_components,
        record_history=False,
    )

    # 2. CBBA Plain
    cbba_run = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str=adversary_str,
        allocator_str="cbba",
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=0,
        variant=variant,
        prebuilt_env=env_components,
        record_history=False,
    )

    # 3. CTP Replan
    ctp_run = run_single_simulation(
        graph_family=graph_family,
        n_nodes=n_nodes,
        adversary_str=adversary_str,
        allocator_str="ctp_replan",
        comm_regime=comm_regime,
        comm_range=comm_range,
        p_drop=p_drop,
        n_robots=n_robots,
        n_tasks=n_tasks,
        seed=seed,
        max_steps=max_steps,
        contingency_depth=0,
        variant=variant,
        prebuilt_env=env_components,
        record_history=False,
    )

    return {
        "selected": main_run,
        "cbba_partial_lr": cbba_lr_run,
        "cbba": cbba_run,
        "ctp_replan": ctp_run,
    }


def get_paper_aggregate_comparison(graph_family: str, variant: str = "10-20-10-2-1") -> Optional[pd.DataFrame]:
    """
    Load pre-registered aggregate empirical benchmarks from results/stats/instance_aggregated.csv.
    MovingAI 20-40 has no pre-registered aggregate; returns None in that case.
    """
    if "20-40" in variant:
        return None

    if not os.path.exists(PAPER_STATS_CSV):
        return None

    try:
        df = pd.read_csv(PAPER_STATS_CSV)
        fam_df = df[df["graph_family"] == graph_family]
        if fam_df.empty:
            return None

        records = []
        for method, group in fam_df.groupby("method"):
            n_inst = len(group)
            comp_mean = group["completion_rate_pct"].mean()
            comp_ci = bootstrap_ci(group["completion_rate_pct"].values)
            welfare_mean = group["net_welfare"].mean()
            welfare_ci = bootstrap_ci(group["net_welfare"].values)
            msg_mean = group["total_messages"].mean()
            msg_ci = bootstrap_ci(group["total_messages"].values)
            conf_mean = group["total_conflicts"].mean()
            conf_ci = bootstrap_ci(group["total_conflicts"].values)

            records.append({
                "Method": METHOD_NAME_MAP.get(method, method),
                "Instances": n_inst,
                "Completion (%)": f"{comp_mean:.1f} ± {comp_ci[1] - comp_mean:.1f}",
                "Net Welfare": f"{welfare_mean:.0f} ± {welfare_ci[1] - welfare_mean:.0f}",
                "Total Messages": f"{msg_mean:.0f} ± {msg_ci[1] - msg_mean:.0f}",
                "Total Conflicts": f"{conf_mean:.1f} ± {conf_ci[1] - conf_mean:.1f}",
            })
        return pd.DataFrame(records)
    except Exception:
        return None


def _evaluate_seed_multi_method(args: Tuple) -> Dict[str, Any]:
    """Top-level picklable parallel worker for multi-seed CRN evaluation."""
    (
        seed,
        graph_family,
        n_nodes,
        variant,
        adversary_str,
        methods_to_run,
        max_steps,
        n_robots,
        n_tasks,
        comm_regime,
        comm_range,
        p_drop,
    ) = args

    env = build_crn_environment(
        graph_family=graph_family,
        n_nodes=n_nodes,
        seed=seed,
        n_robots=n_robots,
        n_tasks=n_tasks,
        max_steps=max_steps,
        variant=variant,
    )

    seed_results = {}
    for m in methods_to_run:
        res = run_single_simulation(
            graph_family=graph_family,
            n_nodes=n_nodes,
            adversary_str=adversary_str,
            allocator_str=m,
            comm_regime=comm_regime,
            comm_range=comm_range,
            p_drop=p_drop,
            n_robots=n_robots,
            n_tasks=n_tasks,
            seed=seed,
            max_steps=max_steps,
            variant=variant,
            prebuilt_env=env,
            record_history=False,
            record_traces=False,
        )
        seed_results[m] = res["summary"]

    return {"seed": seed, "results": seed_results}


def run_20_seeds_paired(
    graph_family: str,
    n_nodes: int,
    adversary_str: str,
    allocator_str: str = "aca",
    baseline_str: str = "cbba_partial_lr",  # Fair, execution-matched default baseline
    comm_regime: str = "benign",
    comm_range: float = 50.0,
    p_drop: float = 0.02,
    n_robots: int = 4,
    n_tasks: int = 15,
    max_steps: int = DEFAULT_MAX_STEPS,
    variant: str = "10-20-10-2-1",
    seed_start: int = 10001,
    num_seeds: int = 20,
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run 20 independent seeds evaluating selected method against:
    1. CBBA-PR (+LR) (default execution-matched baseline)
    2. CBBA (plain)
    3. CTP Replan
    Streams progress 'seed k/20' and parallelizes across up to 4 worker processes.
    Target: Boston 20 seeds < 15s on 4 cores.
    """
    alloc_main = parse_allocator_name(allocator_str)
    methods = [alloc_main, "cbba_partial_lr", "cbba", "ctp_replan"]
    # De-duplicate while preserving order
    unique_methods = []
    for m in methods:
        if m not in unique_methods:
            unique_methods.append(m)

    # Load pre-computed baseline runs from results/demo_baseline_20seeds.json if available
    baseline_cache_file = os.path.join(REPO_ROOT, "results", "demo_baseline_20seeds.json")
    cache_key = f"{graph_family}_{n_nodes}_{variant}_{adversary_str}_{seed_start}_{num_seeds}_{max_steps}"
    results_by_method: Dict[str, List[Dict[str, Any]]] = {m: [] for m in unique_methods}

    if os.path.exists(baseline_cache_file):
        try:
            with open(baseline_cache_file, "r") as f:
                cached_data = json.load(f)
            if cache_key in cached_data:
                for bm, b_runs in cached_data[cache_key].items():
                    if bm in results_by_method and len(b_runs) >= num_seeds:
                        results_by_method[bm] = list(b_runs[:num_seeds])
        except Exception:
            pass

    methods_to_run = [m for m in unique_methods if len(results_by_method[m]) < num_seeds]

    if methods_to_run:
        task_args = []
        for s_idx in range(num_seeds):
            s = seed_start + s_idx
            task_args.append((
                s,
                graph_family,
                n_nodes,
                variant,
                adversary_str,
                methods_to_run,
                max_steps,
                n_robots,
                n_tasks,
                comm_regime,
                comm_range,
                p_drop,
            ))

        max_workers = min(4, os.cpu_count() or 1)
        completed_seeds = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_evaluate_seed_multi_method, arg) for arg in task_args]
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                for m, s_dict in res["results"].items():
                    results_by_method[m].append(s_dict)
                completed_seeds += 1
                if progress is not None:
                    progress(completed_seeds / num_seeds, desc=f"Evaluating seed {completed_seeds}/{num_seeds}")
    elif progress is not None:
        progress(1.0, desc="Evaluation complete")

    # Build comparative statistics for each method
    stats_table = []
    for m in ["cbba_partial_lr", "cbba", "ctp_replan"]:
        if m not in results_by_method:
            continue
        m_list = results_by_method[m]
        main_list = results_by_method[alloc_main]

        m_comps = np.array([x["completion_rate_pct"] for x in m_list])
        main_comps = np.array([x["completion_rate_pct"] for x in main_list])

        ci_m_comp = bootstrap_ci(m_comps)
        m_mean_comp = float(np.mean(m_comps))

        # Paired win / tie / loss vs ACA
        w, t, l = 0, 0, 0
        for i in range(len(main_comps)):
            if main_comps[i] > m_comps[i] + 0.01:
                w += 1
            elif m_comps[i] > main_comps[i] + 0.01:
                l += 1
            else:
                # Tie-breaker on net welfare
                m_wel = m_list[i].get("net_welfare", 0.0)
                main_wel = main_list[i].get("net_welfare", 0.0)
                if main_wel > m_wel + 0.01:
                    w += 1
                elif m_wel > main_wel + 0.01:
                    l += 1
                else:
                    t += 1

        stats_table.append({
            "Baseline": METHOD_NAME_MAP.get(m, m),
            "Completion (%)": f"{m_mean_comp:.1f}% ± {ci_m_comp[1] - m_mean_comp:.1f}%",
            "Paired W/T/L (ACA vs Baseline)": f"{w}W / {t}T / {l}L",
        })

    main_comps = np.array([x["completion_rate_pct"] for x in results_by_method[alloc_main]])
    ci_main = bootstrap_ci(main_comps)
    main_mean = float(np.mean(main_comps))

    # Construct scientifically honest verdict
    cbba_lr_mean = float(np.mean([x["completion_rate_pct"] for x in results_by_method.get("cbba_partial_lr", [])]))
    ctp_mean = float(np.mean([x["completion_rate_pct"] for x in results_by_method.get("ctp_replan", [])]))

    if ctp_mean > main_mean + 1.0 and abs(main_mean - cbba_lr_mean) < 4.0:
        verdict = f"ACA is statistically level with CBBA-PR+LR on this map ({main_mean:.1f}% vs {cbba_lr_mean:.1f}%); CTP Replan completes more tasks ({ctp_mean:.1f}%)."
    elif main_mean > cbba_lr_mean + 2.0:
        verdict = f"ACA outperforms CBBA-PR+LR by {main_mean - cbba_lr_mean:+.1f}% on average across {num_seeds} paired seeds."
    else:
        verdict = f"ACA achieves {main_mean:.1f}% completion rate across {num_seeds} paired seeds."

    return {
        "n_seeds": num_seeds,
        "main_method": METHOD_NAME_MAP.get(alloc_main, alloc_main),
        "main_completion": f"{main_mean:.1f}% ± {ci_main[1] - main_mean:.1f}%",
        "comparisons_table": pd.DataFrame(stats_table),
        "verdict": verdict,
    }


def diagnose_task_failures(run_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Compute structured failure reasons for uncompleted tasks from simulation trace:
    - unreachable under current blockages
    - deadline
    - lost claim
    - never claimed
    """
    if not run_data or "history" not in run_data or not run_data["history"]:
        return pd.DataFrame()

    last_frame = run_data["history"][-1]
    graph = run_data.get("graph")
    tasks = last_frame.get("tasks", [])
    blocked = set(tuple(sorted(e)) for e in last_frame.get("blocked_edges", []))

    # Graph without active blockages
    open_graph = graph.copy()
    for u, v in blocked:
        if open_graph.has_edge(u, v):
            open_graph.remove_edge(u, v)

    robot_locs = [r["location"] for r in last_frame.get("robots", []) if "location" in r]

    records = []
    for t in tasks:
        if t.get("is_completed", False):
            continue

        tid = t["id"]
        tloc = t["location"]
        rew = t.get("reward", 100)

        # Check reachability from any robot location
        is_reachable = False
        for rloc in robot_locs:
            if nx.has_path(open_graph, rloc, tloc):
                is_reachable = True
                break

        # Check if ever claimed
        ever_claimed = False
        for frame in run_data["history"]:
            for r in frame.get("robots", []):
                if tid in r.get("bundle", []):
                    ever_claimed = True
                    break
            if ever_claimed:
                break

        if not is_reachable:
            reason = "unreachable under current blockages"
            detail = f"Adversary interdictions severed all active paths to node {tloc}"
        elif not ever_claimed:
            reason = "never claimed"
            detail = "Fleet capacity or cost horizon saturated before bid acceptance"
        elif t.get("claimed_by") is None:
            reason = "lost claim"
            detail = "Initial claim was outbid or dropped during dynamic market re-auction"
        else:
            reason = "deadline"
            detail = f"Assigned to robot {t.get('claimed_by')}, but mission horizon reached step limit"

        records.append({
            "Task ID": f"T{tid}",
            "Node": tloc,
            "Reward": rew,
            "Primary Failure Cause": reason,
            "Diagnostic Detail": detail,
        })

    if not records:
        return pd.DataFrame([{"Status": "All tasks completed successfully."}])

    return pd.DataFrame(records)
