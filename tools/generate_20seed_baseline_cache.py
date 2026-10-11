"""
Pre-compute baseline 20-seed runs (CBBA-PR+LR, CBBA, CTP Replan) for Boston and Warehouse.
Saves exact simulation outputs to results/demo_baseline_20seeds.json.
This ensures 20-seed evaluation in the UI finishes in < 15s on 4 cores.
"""

import os
import sys
import json
import concurrent.futures

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.demo.runner import _evaluate_seed_multi_method, DEFAULT_MAX_STEPS

CACHE_FILE = os.path.join(REPO_ROOT, "results", "demo_baseline_20seeds.json")


def generate_baseline_cache():
    configs = [
        # Boston 216-node
        {
            "graph_family": "road_osmnx",
            "n_nodes": 216,
            "variant": "none",
            "adversary_str": "Reactive (Corridor Interdiction)",
            "methods": ["cbba_partial_lr", "cbba", "ctp_replan"],
            "seed_start": 10001,
            "num_seeds": 20,
            "max_steps": DEFAULT_MAX_STEPS,
            "n_robots": 4,
            "n_tasks": 15,
            "comm_regime": "benign",
            "comm_range": 50.0,
            "p_drop": 0.02,
        },
        # Warehouse 38-node
        {
            "graph_family": "warehouse_movingai",
            "n_nodes": 38,
            "variant": "10-20-10-2-1",
            "adversary_str": "Reactive (Corridor Interdiction)",
            "methods": ["cbba_partial_lr", "cbba", "ctp_replan"],
            "seed_start": 10001,
            "num_seeds": 20,
            "max_steps": DEFAULT_MAX_STEPS,
            "n_robots": 4,
            "n_tasks": 15,
            "comm_regime": "benign",
            "comm_range": 50.0,
            "p_drop": 0.02,
        },
    ]

    all_cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                all_cache = json.load(f)
        except Exception:
            all_cache = {}

    max_workers = min(4, os.cpu_count() or 1)

    for cfg in configs:
        cache_key = f"{cfg['graph_family']}_{cfg['n_nodes']}_{cfg['variant']}_{cfg['adversary_str']}_{cfg['seed_start']}_{cfg['num_seeds']}_{cfg['max_steps']}"
        print(f"Generating baselines for key: {cache_key}...")
        
        task_args = []
        for s_idx in range(cfg["num_seeds"]):
            s = cfg["seed_start"] + s_idx
            task_args.append((
                s,
                cfg["graph_family"],
                cfg["n_nodes"],
                cfg["variant"],
                cfg["adversary_str"],
                cfg["methods"],
                cfg["max_steps"],
                cfg["n_robots"],
                cfg["n_tasks"],
                cfg["comm_regime"],
                cfg["comm_range"],
                cfg["p_drop"],
            ))

        cfg_results = {m: [] for m in cfg["methods"]}
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_evaluate_seed_multi_method, arg) for arg in task_args]
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                for m, s_dict in res["results"].items():
                    # Keep serializable metrics
                    clean_dict = {
                        k: v for k, v in s_dict.items()
                        if isinstance(v, (int, float, str, bool))
                    }
                    cfg_results[m].append(clean_dict)
                done += 1
                print(f"  Completed {done}/{cfg['num_seeds']} seeds")

        all_cache[cache_key] = cfg_results

    with open(CACHE_FILE, "w") as f:
        json.dump(all_cache, f, indent=2)
    print(f"Baseline cache successfully saved to {CACHE_FILE}")


if __name__ == "__main__":
    generate_baseline_cache()
