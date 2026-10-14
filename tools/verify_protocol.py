#!/usr/bin/env python3
"""
Protocol Verification Tool for ACA Benchmark Runs (Gate 5 / Section 1b / Gate 1).
Validates configuration integrity, cryptographic seed schedules, preregistration cross-checks,
hyperparameter bounds, environment manifest integrity, and output directory isolation.

Usage:
    python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml --strict
"""

import os
import sys
import re
import ast
import json
import yaml
import hashlib
import argparse
import subprocess
from typing import Dict, Any, List, Set, Tuple
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Historical frozen seed sets
V1_V4_SEEDS = set(range(1, 31))
V5_HELDOUT_SEEDS = set(range(101, 131))
STAGE4_PILOT_SEEDS = set(range(1000, 1061))
SITL_SEEDS = set(range(20000, 20360))
DEMO_SEEDS = set(range(10001, 10011))
ALL_HISTORICAL_SEEDS = V1_V4_SEEDS | V5_HELDOUT_SEEDS | STAGE4_PILOT_SEEDS | SITL_SEEDS | DEMO_SEEDS

EXPECTED_V6_SHA256 = "09638b69b6d331eb3738023b4ad7502116e7d4768405235cf396d76bc3eea5cb"
EXPECTED_DEV_SHA256 = "19a8aabd61d3f15800164feae865f285ec0d8b4ccc13619534a940d57d63417c"


def compute_sha256_of_list(items: List[Any]) -> str:
    return hashlib.sha256(str(sorted(items)).encode("utf-8")).hexdigest()


def compute_file_sha256(filepath: str) -> str:
    if not os.path.exists(filepath):
        return "MISSING"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_v6_seeds(n_seeds: int = 50, rng_seed: int = 20261013) -> List[int]:
    rng = np.random.default_rng(rng_seed)
    candidates = rng.choice(np.arange(50000, 60000), size=n_seeds * 2, replace=False)
    v6_seeds = []
    for s in candidates:
        int_s = int(s)
        if int_s not in ALL_HISTORICAL_SEEDS:
            v6_seeds.append(int_s)
        if len(v6_seeds) == n_seeds:
            break
    return sorted(v6_seeds)


def generate_dev_seeds(n_seeds: int = 15, rng_seed: int = 9992026) -> List[int]:
    dev_rng = np.random.default_rng(rng_seed)
    candidates = dev_rng.choice(np.arange(40000, 45000), size=n_seeds * 2, replace=False)
    dev_seeds = []
    for s in candidates:
        int_s = int(s)
        if int_s not in ALL_HISTORICAL_SEEDS:
            dev_seeds.append(int_s)
        if len(dev_seeds) == n_seeds:
            break
    return sorted(dev_seeds)


def parse_seeds_from_prereg(filepath: str) -> Tuple[List[int], List[int]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Preregistration file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    conf_match = re.search(r"Confirmatory Seeds.*?`(\[[0-9,\s]+\])`", content, re.DOTALL)
    if not conf_match:
        raise ValueError(f"Could not find confirmatory seeds list in {filepath}")
    conf_seeds = sorted(ast.literal_eval(conf_match.group(1)))

    dev_match = re.search(r"Development.*?Seeds.*?`(\[[0-9,\s]+\])`", content, re.DOTALL)
    if not dev_match:
        raise ValueError(f"Could not find development seeds list in {filepath}")
    dev_seeds = sorted(ast.literal_eval(dev_match.group(1)))

    return conf_seeds, dev_seeds


FROZEN_DEV_SEEDS = [40484, 40506, 40601, 40685, 40827, 41625, 41883, 41904, 42246, 42740, 43213, 44518, 44544, 44637, 44867]


def check_git_status() -> Tuple[bool, str, str]:
    git_bins = ["git", r"C:\Program Files\Git\cmd\git.exe"]
    commit = "unknown"
    for git_bin in git_bins:
        try:
            commit = subprocess.check_output([git_bin, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode("ascii").strip()
            if commit:
                break
        except Exception:
            pass

    for git_bin in git_bins:
        try:
            status = subprocess.check_output([git_bin, "status", "--porcelain"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
            lines = [l for l in status.splitlines() if not l.startswith("?? results/test_logs") and not l.startswith("?? ACA_End_to_End_Audit")]
            is_clean = len(lines) == 0
            return is_clean, commit, status
        except Exception as e:
            pass
    return False, commit, "git_uninspectable"


def verify_protocol(config_path: str, prereg_path: str = "protocols/prereg-v6.md", strict: bool = False) -> Dict[str, Any]:
    full_config_path = os.path.join(REPO_ROOT, config_path) if not os.path.isabs(config_path) else config_path
    full_prereg_path = os.path.join(REPO_ROOT, prereg_path) if not os.path.isabs(prereg_path) else prereg_path

    if not os.path.exists(full_config_path):
        raise FileNotFoundError(f"Protocol config not found: {full_config_path}")

    with open(full_config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    errors = []
    warnings = []

    # 1. Version and Status
    version = cfg.get("version")
    if version != "6.1.0":
        errors.append(f"Expected version '6.1.0', got '{version}'")
    status = cfg.get("status")
    if status != "REGISTERED_FROZEN":
        errors.append(f"Expected status 'REGISTERED_FROZEN', got '{status}'")

    # 2. Confirmatory Seeds
    eval_design = cfg.get("evaluation_design", {})
    conf_phase = eval_design.get("confirmatory_phase", {})
    conf_seeds = conf_phase.get("seeds", [])
    expected_conf = generate_v6_seeds(50)
    if sorted(conf_seeds) != expected_conf:
        errors.append(f"Confirmatory seeds do not match algorithmic generator output")
    conf_sha = compute_sha256_of_list(conf_seeds)
    if conf_sha != EXPECTED_V6_SHA256:
        errors.append(f"Confirmatory seeds SHA mismatch: got {conf_sha}, expected {EXPECTED_V6_SHA256}")
    if conf_phase.get("seeds_sha256") != EXPECTED_V6_SHA256:
        errors.append(f"Config declared seeds_sha256 does not match authoritative hash")
    conf_overlap = set(conf_seeds) & ALL_HISTORICAL_SEEDS
    if conf_overlap:
        errors.append(f"Confirmatory seeds overlap with historical seeds: {conf_overlap}")

    # 3. Development Seeds
    dev_phase = eval_design.get("development_phase", {})
    dev_seeds = dev_phase.get("seeds", [])
    if sorted(dev_seeds) != FROZEN_DEV_SEEDS:
        errors.append(f"Development seeds do not match frozen development seed list")
    dev_sha = compute_sha256_of_list(dev_seeds)
    if dev_sha != EXPECTED_DEV_SHA256:
        errors.append(f"Development seeds SHA mismatch: got {dev_sha}, expected {EXPECTED_DEV_SHA256}")
    dev_overlap = (set(dev_seeds) & ALL_HISTORICAL_SEEDS) | (set(dev_seeds) & set(conf_seeds))
    if dev_overlap:
        errors.append(f"Development seeds overlap with historical or confirmatory seeds: {dev_overlap}")

    # 4. Preregistration Cross-Check
    if os.path.exists(full_prereg_path):
        prereg_conf, prereg_dev = parse_seeds_from_prereg(full_prereg_path)
        if prereg_conf != sorted(conf_seeds):
            errors.append("Preregistration confirmatory seeds do not match config seeds")
        if prereg_dev != sorted(dev_seeds):
            errors.append("Preregistration development seeds do not match config seeds")
        with open(full_prereg_path, "r", encoding="utf-8") as f:
            prereg_txt = f.read()
        if "v6.1 pre-execution correction" not in prereg_txt:
            errors.append("Preregistration lacks required amendment note regarding seed list correction")
    else:
        errors.append(f"Preregistration file missing: {full_prereg_path}")

    # 5. Environments and Real Maps
    universe = cfg.get("benchmark_universe", {})
    environments = universe.get("environments", [])
    families = [e.get("family") for e in environments]
    expected_fams = ["warehouse_movingai", "road_osmnx", "rgg", "grid", "er"]
    if sorted(families) != sorted(expected_fams):
        errors.append(f"Environments mismatch: got {families}, expected {expected_fams}")

    manifest_path = os.path.join(REPO_ROOT, "data", "maps", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        warehouse_map = os.path.join(REPO_ROOT, "data", "maps", "warehouse-10-20-10-2-1.map")
        if not os.path.exists(warehouse_map):
            errors.append("MovingAI map file missing")
        elif compute_file_sha256(warehouse_map) != manifest.get("movingai", {}).get("warehouse-10-20-10-2-1.map", {}).get("sha256"):
            errors.append("MovingAI map file hash mismatch with manifest")

        boston_map = os.path.join(REPO_ROOT, "data", "maps", "boston_downtown_drive.graphml")
        if not os.path.exists(boston_map):
            errors.append("OSMnx road graphml file missing")
        elif compute_file_sha256(boston_map) != manifest.get("osmnx", {}).get("sha256"):
            errors.append("OSMnx road graphml file hash mismatch with manifest")
    else:
        errors.append("data/maps/manifest.json missing")

    # 6. Adversaries
    adversaries = universe.get("adversaries", [])
    expected_adv = ["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"]
    if sorted(adversaries) != sorted(expected_adv):
        errors.append(f"Adversaries mismatch: got {adversaries}, expected {expected_adv}")

    # 7. Methods and Hyperparameters
    eval_methods = cfg.get("evaluated_methods", {})
    expected_methods = [
        "aca", "aca_plus", "aca_adaptive", "aca_no_margin", "aca_depth_0",
        "cbba_lr", "cbba_partial_lr", "ctp_replan", "ssi_lr"
    ]
    for m in expected_methods:
        if m not in eval_methods:
            errors.append(f"Required evaluated method '{m}' missing in config")

    # Numerical pruning threshold for aca_plus
    aca_plus_kw = eval_methods.get("aca_plus", {}).get("allocator_kwargs", {})
    prune_thresh = aca_plus_kw.get("prune_threshold")
    if not isinstance(prune_thresh, (int, float)):
        errors.append(f"aca_plus prune_threshold must be numeric, got {type(prune_thresh)}")
    elif prune_thresh <= 0.12:
        errors.append(f"aca_plus prune_threshold must be strictly > 0.12 (planner threshold), got {prune_thresh}")

    # 8. Output Isolation
    out_cfg = cfg.get("output", {})
    out_dir = out_cfg.get("dir", "")
    if not out_dir or out_dir in ["results", "results/sweep", "."]:
        errors.append(f"Protocol output dir must be strictly isolated, got '{out_dir}'")

    # 9. Statistical Estimand Specification
    stats_cfg = cfg.get("statistical_testing", {})
    primary_est = stats_cfg.get("primary_estimand", {})
    if primary_est.get("unit") != "graph_family x seed":
        errors.append(f"Primary estimand unit must be 'graph_family x seed', got '{primary_est.get('unit')}'")
    if primary_est.get("correction") != "holm_bonferroni":
        errors.append(f"Primary estimand correction must be 'holm_bonferroni', got '{primary_est.get('correction')}'")

    # 10. Strict Git Verification
    is_clean, commit_sha, git_out = check_git_status()
    if strict:
        if not is_clean:
            errors.append(f"Strict verification failed: Git working tree is dirty: {git_out}")
        if commit_sha == "unknown":
            errors.append("Strict verification failed: Git commit SHA is unknown")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "version": version,
        "status": status,
        "conf_seeds_count": len(conf_seeds),
        "conf_seeds_sha256": conf_sha,
        "dev_seeds_count": len(dev_seeds),
        "dev_seeds_sha256": dev_sha,
        "git_commit": commit_sha,
        "git_clean": is_clean,
    }


def main():
    parser = argparse.ArgumentParser(description="ACA Benchmark Protocol Verifier")
    parser.add_argument("--config", default="experiments/configs/protocol_v6.yaml", help="Path to protocol YAML")
    parser.add_argument("--prereg", default="protocols/prereg-v6.md", help="Path to preregistration Markdown")
    parser.add_argument("--strict", action="store_true", help="Fail closed on dirty git or any discrepancy")
    args = parser.parse_args()

    results = verify_protocol(args.config, args.prereg, strict=args.strict)

    print("==================================================================")
    print("                 PROTOCOL VERIFICATION REPORT                     ")
    print("==================================================================")
    print(f"Config:                  {args.config}")
    print(f"Prereg:                  {args.prereg}")
    print(f"Protocol Version:        {results['version']}")
    print(f"Protocol Status:         {results['status']}")
    print(f"Confirmatory Seeds:      {results['conf_seeds_count']} seeds (SHA: {results['conf_seeds_sha256'][:16]}...)")
    print(f"Development Seeds:       {results['dev_seeds_count']} seeds (SHA: {results['dev_seeds_sha256'][:16]}...)")
    print(f"Git Commit:              {results['git_commit']}")
    print(f"Git Clean:               {results['git_clean']}")
    print("------------------------------------------------------------------")

    if not results["valid"]:
        print("STATUS: PROTOCOL VERIFICATION FAILED:")
        for err in results["errors"]:
            print(f"  [ERROR] {err}")
        sys.exit(1)
    else:
        print("STATUS: PROTOCOL VERIFIED 100% VALID AND FROZEN (PASS)")
        sys.exit(0)


if __name__ == "__main__":
    main()
