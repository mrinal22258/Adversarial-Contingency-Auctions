"""
Parallel Seeded Experiment Runner with Common Random Numbers (CRN), Protocol Isolation, and Strict Resumability.
Phase A & Protocol v6 Implementation:
- Reads comm_regimes, seed list/schedule, environments, baselines, and ablations from authoritative config.
- Per-component RNG via numpy.random.SeedSequence.spawn(5) (graph, starts, tasks, blockages, comm).
- Pre-draws per-(edge, step) blockage uniforms so all allocation methods see identical blockage streams.
- Full trial identity: SHA-256 over normalized resolved config including all physical/network factors, depth, allocator_kwargs, commit, and protocol hash.
- Strict resumability on full trial identity.
- Protocol-isolated output directories (no cross-contamination with global results/runs.jsonl).
- Atomic logging with canonical per-record SHA-256 digests.
- Strict Git reproducibility enforcement in confirmatory mode.
- Explicit --dry-run (0 simulator steps) and --smoke-test support.
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
import collections
from typing import Dict, Tuple, Any, Optional, List
import concurrent.futures
import yaml
import pandas as pd
import numpy as np
import networkx as nx

# Ensure acalib is importable from workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType, canonical_edge
from acalib.alloc.base import Task
from acalib.sim.engine import SimulationEngine
from acalib.data.logger import AtomicJsonlWriter, compute_record_hash


from acalib.utils.gitinfo import get_git_info, get_git_commit, check_git_clean

get_git_commit_hash = get_git_commit


def compute_trial_hash(condition_dict: Dict[str, Any]) -> str:
    """
    Compute full deterministic SHA-256 hash of normalized trial experimental condition.
    Includes all factors: graph, robots, tasks, comm, max_steps, depth, allocator kwargs, commit, protocol hash.
    """
    normalized = {}
    for k, v in sorted(condition_dict.items()):
        if isinstance(v, dict):
            normalized[k] = json.dumps(sorted((dk, str(dv)) for dk, dv in v.items()))
        elif isinstance(v, (list, tuple)):
            normalized[k] = json.dumps(sorted([str(x) for x in v]))
        else:
            normalized[k] = str(v)
    raw = json.dumps(sorted(normalized.items()), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_EDGE_BC_CACHE: collections.OrderedDict = collections.OrderedDict()
MAX_BC_CACHE_SIZE = 64


def compute_graph_hash(graph: nx.Graph) -> str:
    """Deterministic hash of graph topology (nodes + canonical edges)."""
    nodes = sorted(list(graph.nodes()))
    edges = sorted([canonical_edge(u, v) for u, v in graph.edges()])
    data = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def get_edge_betweenness(
    graph: nx.Graph, graph_family: str, seed: Optional[int] = None
) -> Dict[Any, float]:
    """Retrieve or compute edge betweenness centrality with caching for static real topologies."""
    g_hash = compute_graph_hash(graph)
    cache_key = (graph_family, len(graph), len(graph.edges()), g_hash, seed)
    if cache_key in _EDGE_BC_CACHE:
        _EDGE_BC_CACHE.move_to_end(cache_key)
        return _EDGE_BC_CACHE[cache_key]

    k_sample = min(30, len(graph)) if len(graph) > 30 else None
    bc = nx.edge_betweenness_centrality(graph, k=k_sample, weight="weight", seed=seed)
    if graph_family in ("warehouse_movingai", "road_osmnx", "warehouse"):
        _EDGE_BC_CACHE[cache_key] = bc
        if len(_EDGE_BC_CACHE) > MAX_BC_CACHE_SIZE:
            _EDGE_BC_CACHE.popitem(last=False)
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
    **kwargs: Any,
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
    graph = generate_graph(family=graph_family, n_nodes=n_nodes, seed=graph_seed, **kwargs)
    nodes_list = sorted(list(graph.nodes()))

    # 2. Robot start positions
    start_nodes = [
        nodes_list[int(rng_starts.integers(0, len(nodes_list)))] for _ in range(n_robots)
    ]

    # 3. Tasks
    tasks = {}
    if task_arrival_mode == "poisson":
        # Standard homogeneous Poisson process: cumulative exponential inter-arrival intervals
        rate = max(0.1, float(poisson_rate))
        inter_arrivals = rng_tasks.exponential(1.0 / rate, size=n_tasks)
        arr_steps = np.floor(np.cumsum(inter_arrivals)).astype(int)
        arr_steps[0] = 0  # Task 0 arrives at step 0; remaining tasks arrive non-decreasingly
    else:
        arr_steps = np.zeros(n_tasks, dtype=int)

    for tid in range(n_tasks):
        t_node = nodes_list[int(rng_tasks.integers(0, len(nodes_list)))]
        arr_step = int(arr_steps[tid])
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

    bc_seed = int(seeds[3].generate_state(1)[0])
    edge_bc = get_edge_betweenness(graph, graph_family, seed=bc_seed)
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
    traces_dir: Optional[str] = None,
    runs_jsonl: Optional[str] = None,
    git_commit: str = "unknown",
    protocol_hash: str = "unknown",
    allocator_kwargs: Optional[Dict[str, Any]] = None,
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
    alloc_kw = dict(allocator_kwargs) if allocator_kwargs else {}
    if "contingency_depth" in alloc_kw:
        c_depth = alloc_kw["contingency_depth"]
    elif allocator_name == "aca_depth_0":
        c_depth = 0
    elif allocator_name == "aca_depth_2":
        c_depth = 2
    elif allocator_name.endswith("_lr") or allocator_name.startswith("aca"):
        c_depth = contingency_depth if contingency_depth > 0 else 1
    else:
        c_depth = 0

    engine_kwargs = dict(alloc_kw)
    engine_kwargs.pop("contingency_depth", None)
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
        record_traces=(traces_dir is not None),
        **engine_kwargs,
    )

    metrics = engine.run(max_steps=max_steps)
    summary = metrics.compute_summary()
    t_end = time.time()
    wall_clock_ms = (t_end - t_start) * 1000.0

    actual_n_nodes = len(env_components["graph"].nodes())
    actual_n_edges = len(env_components["graph"].edges())
    condition_info = {
        "graph_family": graph_family,
        "n_nodes": n_nodes,
        "adversary": adversary_type_str,
        "method": allocator_name,
        "comm_regime": comm_regime,
        "comm_range": comm_range,
        "p_drop": p_drop,
        "n_robots": n_robots,
        "n_tasks": n_tasks,
        "seed": seed,
        "max_steps": max_steps,
        "contingency_depth": c_depth,
        "allocator_kwargs": alloc_kw,
        "git_commit": git_commit,
        "protocol_hash": protocol_hash,
    }
    trial_hash = compute_trial_hash(condition_info)
    run_id = f"{graph_family}_{adversary_type_str[:7]}_{comm_regime}_{allocator_name}_s{seed}_{trial_hash[:16]}"

    # Save per-step traces as Parquet
    if traces_dir:
        os.makedirs(traces_dir, exist_ok=True)
        trace_path = os.path.join(traces_dir, f"{run_id}.parquet")
        trace_df = engine.get_trace_df()
        trace_df.to_parquet(trace_path, index=False)

    row = dict(condition_info)
    row.update(summary)
    if "status" not in row:
        row["status"] = "COMPLETED"
    row["actual_n_nodes"] = actual_n_nodes
    row["actual_n_edges"] = actual_n_edges
    row["trial_hash"] = trial_hash
    row["run_id"] = run_id
    row["wall_clock_ms"] = wall_clock_ms
    row["per_claim_logs"] = list(getattr(engine.allocator, "per_claim_logs", []))
    row["tv_obs_total"] = len(getattr(engine.allocator, "logged_tv_observations", []))
    row["tv_obs_adhered"] = sum(1 for tv, eta in getattr(engine.allocator, "logged_tv_observations", []) if tv <= eta)

    # Write JSONL record atomically with per-record SHA-256
    if runs_jsonl:
        os.makedirs(os.path.dirname(runs_jsonl), exist_ok=True)
        writer = AtomicJsonlWriter(runs_jsonl)
        rec_hash = writer.append(row)
        row["record_sha256"] = rec_hash

    return row


def get_default_workers() -> int:
    """Determine default worker count based on physical CPU cores."""
    try:
        import psutil
        cores = psutil.cpu_count(logical=False)
        if cores and cores > 0:
            return cores
    except Exception:
        pass
    logical = os.cpu_count() or 4
    return max(1, logical // 2)


def _worker_wrapper(args_tuple):
    """Wrapper for multiprocessing with single-threaded BLAS to prevent oversubscription."""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    return run_single_trial(*args_tuple)


def resolve_seeds(args, yaml_config: Dict[str, Any]) -> Tuple[List[int], str]:
    """Resolve exact seed list and compute its SHA-256 digest."""
    if args.seed_list:
        if args.seed_list in ("v6", "protocol_v6"):
            from tests.test_prereg_v6_seeds import generate_v6_seeds
            seeds = generate_v6_seeds(50)
        elif args.seed_list in ("dev", "development"):
            from tests.test_prereg_v6_seeds import generate_dev_seeds
            seeds = generate_dev_seeds(15)
        elif os.path.exists(args.seed_list):
            with open(args.seed_list, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if args.seed_list.endswith(".yaml") or args.seed_list.endswith(".yml"):
                    cfg = yaml.safe_load(content)
                    seeds = cfg.get("seeds") or cfg.get("evaluation_design", {}).get("confirmatory_phase", {}).get("seeds", [])
                elif args.seed_list.endswith(".json"):
                    seeds = json.loads(content)
                else:
                    seeds = [int(x.strip()) for x in content.replace(",", " ").split() if x.strip()]
        else:
            raise ValueError(f"Unknown seed-list option or file not found: {args.seed_list}")
    elif args.pilot:
        seeds = list(range(10000, 10010))
    elif args.seeds is not None:
        seeds = list(range(1, args.seeds + 1))
    elif "evaluation_design" in yaml_config and "confirmatory_phase" in yaml_config["evaluation_design"]:
        seeds = yaml_config["evaluation_design"]["confirmatory_phase"]["seeds"]
    elif "evaluation_design" in yaml_config and "development_phase" in yaml_config["evaluation_design"]:
        seeds = yaml_config["evaluation_design"]["development_phase"]["seeds"]
    elif "final_seeds" in yaml_config:
        n_seeds = yaml_config["final_seeds"]
        seeds = list(range(1, n_seeds + 1))
    else:
        seeds = list(range(1, 11))

    seed_hash = hashlib.sha256(str(seeds).encode("utf-8")).hexdigest()
    return seeds, seed_hash


def main():
    parser = argparse.ArgumentParser(description="Parallel Seeded ACA Experiment Runner (Phase A & Protocol v6)")
    parser.add_argument("--config", type=str, default="experiments/configs/config_final.yaml", help="Path to config YAML")
    parser.add_argument("--protocol", type=str, default=None, help="Protocol ID (e.g. v6)")
    parser.add_argument("--seeds", type=int, default=None, help="Number of seeds (overrides YAML)")
    parser.add_argument("--seed-list", type=str, default=None, help="Path to seed list file or 'v6' or 'dev'")
    parser.add_argument("--pilot", action="store_true", help="Run disjoint pilot sweep on seeds 10000-10009")
    parser.add_argument("--output", type=str, default=None, help="Output summary CSV")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory for all run outputs (CSV, JSONL, traces)")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel worker processes (defaults to physical cores)")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and validate config, print planned workload, run NO simulator")
    parser.add_argument("--smoke-test", action="store_true", help="Run single tiny trial to verify end-to-end pipeline")
    parser.add_argument("--strict", action="store_true", help="Fail closed on any malformed record, hash mismatch, or dirty git")
    parser.add_argument("--confirmatory", action="store_true", help="Enforce confirmatory reproducibility (clean git, strict cache)")
    args = parser.parse_args()

    if args.workers is None:
        args.workers = get_default_workers()

    # Protocol selection override
    if args.protocol == "v6":
        args.config = "experiments/configs/protocol_v6.yaml"
        args.confirmatory = True

    # Load YAML config
    yaml_config = {}
    protocol_hash = "unknown"
    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            raw_content = f.read()
            protocol_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            yaml_config = yaml.safe_load(raw_content) or {}

    is_confirmatory = (
        args.confirmatory
        or (args.protocol == "v6")
        or ("confirmatory_phase" in yaml_config.get("evaluation_design", {}))
    )

    # Git cleanliness check (fail-closed in confirmatory mode)
    git_clean, git_msg = check_git_clean()
    git_commit = get_git_commit_hash()
    git_info = get_git_info()

    if is_confirmatory or args.strict:
        if not git_clean:
            raise RuntimeError(f"Confirmatory/strict mode failure: Git working tree is dirty ({git_msg}).")
        if git_commit == "unknown":
            raise RuntimeError("Confirmatory/strict mode failure: Git commit hash is unknown.")
        if git_info.source != "git":
            raise RuntimeError(f"Confirmatory/strict mode failure: Must run within a live Git repository (got source '{git_info.source}').")

    # Output directory isolation
    out_cfg = yaml_config.get("output", {})
    if args.output_dir:
        out_dir = args.output_dir
    elif args.output:
        out_dir = os.path.dirname(args.output) or "."
    elif "dir" in out_cfg:
        out_dir = out_cfg["dir"]
    else:
        out_dir = "results/sweep"

    os.makedirs(out_dir, exist_ok=True)
    results_csv = args.output or os.path.join(out_dir, "results.csv")
    runs_jsonl = os.path.join(out_dir, "runs.jsonl")
    traces_dir = os.path.join(out_dir, "traces")
    os.makedirs(traces_dir, exist_ok=True)

    # Benchmark universe extraction (support both top-level and nested benchmark_universe)
    bu = yaml_config.get("benchmark_universe", {})

    # Environments
    if "environments" in yaml_config:
        environments = [(env["family"], env["n_nodes"]) for env in yaml_config["environments"]]
    elif "environments" in bu:
        environments = [(env["family"], env["n_nodes"]) for env in bu["environments"]]
    else:
        environments = [
            ("warehouse_movingai", 36),
            ("road_osmnx", 40),
            ("rgg", 35),
            ("warehouse", 30),
            ("er", 35),
        ]

    # Adversaries
    adversaries = yaml_config.get("adversaries") or bu.get("adversaries", [
        "theta_1_stochastic",
        "theta_2_reactive",
        "theta_3_budgeted_interdiction",
        "theta_4_cyclic_patrol",
    ])

    # Methods & per-method allocator kwargs
    method_specs = {}
    if "evaluated_methods" in yaml_config and isinstance(yaml_config["evaluated_methods"], dict):
        for m_name, m_cfg in yaml_config["evaluated_methods"].items():
            if isinstance(m_cfg, dict):
                a_type = m_cfg.get("allocator_type", m_name)
                a_kw = m_cfg.get("allocator_kwargs", {})
            else:
                a_type = m_name
                a_kw = {}
            method_specs[m_name] = (a_type, a_kw)
    elif "methods" in yaml_config:
        for m in yaml_config["methods"]:
            method_specs[m] = (m, {})
    else:
        default_methods = [
            "aca", "aca_no_margin", "aca_depth_0",
            "cbba", "cbba_partial", "cc_cbba", "ssi",
            "cbba_lr", "cbba_partial_lr", "cc_cbba_lr", "ssi_lr",
            "implicit", "ctp_replan", "cbba_gossip", "clairvoyant_greedy",
        ]
        for m in default_methods:
            method_specs[m] = (m, {})

    # Comm regimes
    comm_regimes = yaml_config.get("comm_regimes") or bu.get("comm_regimes", {
        "benign": {"comm_range": 50.0, "p_drop": 0.02},
        "constrained": {"comm_range": 25.0, "p_drop": 0.15},
        "lossy": {"comm_range": 20.0, "p_drop": 0.30},
    })

    # Seeds
    seed_range, seed_hash = resolve_seeds(args, yaml_config)

    # Fleet sizes and task counts handling (grid iteration or rejection in single-cell)
    fleet_sizes = yaml_config.get("fleet_sizes") or bu.get("fleet_sizes", [4])
    task_counts = yaml_config.get("task_counts") or bu.get("task_counts", [15])
    if not isinstance(fleet_sizes, list):
        fleet_sizes = [fleet_sizes]
    if not isinstance(task_counts, list):
        task_counts = [task_counts]

    single_cell_mode = is_confirmatory or yaml_config.get("single_cell", False)
    if single_cell_mode and (len(fleet_sizes) > 1 or len(task_counts) > 1):
        raise ValueError(
            f"Confirmatory/single-cell mode requires exactly 1 fleet size and 1 task count, "
            f"got fleet_sizes={fleet_sizes}, task_counts={task_counts}. "
            f"To evaluate a grid, disable single_cell mode."
        )

    max_steps = yaml_config.get("max_steps") or bu.get("max_steps", 80)
    contingency_depth = yaml_config.get("contingency_depth") or bu.get("contingency_depth", 1)

    # Strict cache loading and trial identity tracking
    completed_trial_hashes = set()
    if os.path.exists(runs_jsonl):
        with open(runs_jsonl, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    if args.strict or is_confirmatory:
                        raise ValueError(f"Strict verification failed: Empty line at {runs_jsonl}:{line_idx}")
                    continue
                try:
                    rec = json.loads(line_str)
                except Exception as e:
                    if args.strict or is_confirmatory:
                        raise ValueError(f"Strict verification failed: Malformed JSON at {runs_jsonl}:{line_idx}: {e}")
                    continue

                if (args.strict or is_confirmatory) and "record_sha256" in rec:
                    recomputed = compute_record_hash(rec)
                    if rec["record_sha256"] != recomputed:
                        raise ValueError(
                            f"Strict verification failed: Record SHA-256 mismatch at {runs_jsonl}:{line_idx}: "
                            f"{rec['record_sha256']} != {recomputed}"
                        )

                th = rec.get("trial_hash")
                if th:
                    completed_trial_hashes.add(th)

    # Assemble task tuples
    task_tuples = []
    skipped_count = 0
    all_planned_trial_hashes = set()

    for fam, n_nodes in environments:
        for adv in adversaries:
            for regime_name, regime_cfg in comm_regimes.items():
                c_range = regime_cfg.get("comm_range", 30.0)
                p_d = regime_cfg.get("p_drop", 0.05)
                for n_robots in fleet_sizes:
                    for n_tasks in task_counts:
                        for seed in seed_range:
                            for m_name, (alloc_type, alloc_kw) in method_specs.items():
                                # Compute deterministic trial identity
                                c_depth = alloc_kw.get("contingency_depth", contingency_depth if contingency_depth > 0 else 1)
                                cond = {
                                    "graph_family": fam,
                                    "n_nodes": n_nodes,
                                    "adversary": adv,
                                    "method": alloc_type,
                                    "comm_regime": regime_name,
                                    "comm_range": c_range,
                                    "p_drop": p_d,
                                    "n_robots": n_robots,
                                    "n_tasks": n_tasks,
                                    "seed": seed,
                                    "max_steps": max_steps,
                                    "contingency_depth": c_depth,
                                    "allocator_kwargs": alloc_kw,
                                    "git_commit": git_commit,
                                    "protocol_hash": protocol_hash,
                                }
                                t_hash = compute_trial_hash(cond)
                                all_planned_trial_hashes.add(t_hash)

                                if t_hash in completed_trial_hashes:
                                    skipped_count += 1
                                    continue

                                task_tuples.append((
                                    fam,
                                    n_nodes,
                                    adv,
                                    alloc_type,
                                    regime_name,
                                    c_range,
                                    p_d,
                                    n_robots,
                                    n_tasks,
                                    seed,
                                    max_steps,
                                    c_depth,
                                    traces_dir,
                                    runs_jsonl,
                                    git_commit,
                                    protocol_hash,
                                    alloc_kw,
                                ))

    total_tasks_needed = len(task_tuples) + skipped_count
    remaining_tasks = len(task_tuples)

    print("\n" + "=" * 70)
    print("ACA EXPERIMENTAL SWEEP PRE-FLIGHT SUMMARY")
    print("=" * 70)
    print(f"Git Commit Hash    : {git_commit}")
    print(f"Protocol Hash      : {protocol_hash}")
    print(f"Config File        : {args.config}")
    print(f"Output Directory   : {out_dir}")
    print(f"Environments ({len(environments)})  : {[e[0] for e in environments]}")
    print(f"Adversaries ({len(adversaries)})   : {adversaries}")
    print(f"Comm Regimes ({len(comm_regimes)})  : {list(comm_regimes.keys())}")
    print(f"Methods ({len(method_specs)})       : {list(method_specs.keys())}")
    print(f"Seed Allocation    : {len(seed_range)} seeds (hash={seed_hash[:16]}...)")
    print(f"Total Design Runs  : {total_tasks_needed}")
    print(f"Cached / Completed : {skipped_count}")
    print(f"Remaining to Run   : {remaining_tasks}")
    print(f"Workers            : {args.workers}")
    print("=" * 70 + "\n")

    # Gate 1 / Acceptance Test 7: --dry-run must run zero simulator steps
    if args.dry_run:
        print("Dry run requested. Configuration validated. Exiting without execution (0 steps run).")
        return

    # Gate 5 Smoke Test mode: run exactly 1 small trial and exit
    if args.smoke_test:
        print("Running single smoke test trial...")
        if task_tuples:
            smoke_task = task_tuples[0]
        else:
            # Reconstruct 1 trial
            first_m = list(method_specs.keys())[0]
            smoke_task = (
                environments[0][0],
                environments[0][1],
                adversaries[0],
                method_specs[first_m][0],
                list(comm_regimes.keys())[0],
                comm_regimes[list(comm_regimes.keys())[0]].get("comm_range", 30.0),
                comm_regimes[list(comm_regimes.keys())[0]].get("p_drop", 0.10),
                fleet_sizes[0],
                task_counts[0],
                seed_range[0],
                10,  # small max steps for smoke
                1,
                traces_dir,
                runs_jsonl,
                git_commit,
                protocol_hash,
                method_specs[first_m][1],
            )
        res = run_single_trial(*smoke_task)
        df = pd.DataFrame([res])
        df.to_csv(results_csv, index=False)
        print(f"Smoke test successful! Saved record to {runs_jsonl} and {results_csv}")
        return

    if remaining_tasks == 0:
        print("All requested trials are already completed in runs.jsonl! Generating summary CSV.")
        records = []
        with open(runs_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    rec = json.loads(line_str)
                    if rec.get("trial_hash") in all_planned_trial_hashes:
                        records.append(rec)
        df = pd.DataFrame(records)
        df.to_csv(results_csv, index=False)
        print(f"Exported {len(df)} trials to {results_csv}")
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

    # Read records strictly matching this experiment from isolated runs_jsonl
    all_records = []
    if os.path.exists(runs_jsonl):
        with open(runs_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    rec = json.loads(line_str)
                    if rec.get("trial_hash") in all_planned_trial_hashes:
                        all_records.append(rec)

    df = pd.DataFrame(all_records)
    sort_cols = [c for c in ["graph_family", "adversary", "comm_regime", "seed", "method"] if c in df.columns]
    if sort_cols and not df.empty:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    df.to_csv(results_csv, index=False)
    print(f"\nCompleted! Saved {len(df)} total rows to {results_csv}")

    # Copy config used alongside results
    config_copy_path = os.path.join(out_dir, "config_used.yaml")
    if os.path.exists(args.config):
        shutil.copyfile(args.config, config_copy_path)

    # Save run metadata
    meta_path = os.path.join(out_dir, "run_metadata.json")
    import scipy
    metadata = {
        "commit": git_commit,
        "protocol_hash": protocol_hash,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "networkx_version": nx.__version__,
        "total_trials": len(df),
        "environments": environments,
        "adversaries": adversaries,
        "methods": list(method_specs.keys()),
        "comm_regimes": comm_regimes,
        "seed_list": seed_range,
        "seed_list_hash": seed_hash,
        "fleet_sizes": fleet_sizes,
        "task_counts": task_counts,
        "max_steps": max_steps,
        "contingency_depth": contingency_depth,
        "resolved_hyperparameters": {m: specs[1] for m, specs in method_specs.items()},
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved run metadata to {meta_path}")


if __name__ == "__main__":
    main()
