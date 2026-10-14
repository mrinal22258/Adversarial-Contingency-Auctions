"""
Golden Trace Acceptance Test: Protects bit-for-bit determinism of simulation outcomes.
Verifies that 2 development seeds x all 9 evaluated methods produce byte-identical
simulation records matching tests/golden/smoke_records.sha256.
"""

import os
import sys
import json
import hashlib
import yaml
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.run_sweep import run_single_trial

EXCLUDE_TIMING_AND_TRANSIENT_FIELDS = {
    "mean_tick_runtime_ms",
    "p95_tick_runtime_ms",
    "total_wall_clock_ms",
    "wall_clock_ms",
    "record_sha256",
    "git_commit",
    "trial_hash",
    "run_id",
}


@pytest.mark.core
def test_golden_trace_records_integrity():
    """Verify simulation records across 2 dev seeds and all 9 methods match golden hash."""
    golden_sha_path = os.path.join(REPO_ROOT, "tests", "golden", "smoke_records.sha256")
    assert os.path.exists(golden_sha_path), "Golden hash file missing: tests/golden/smoke_records.sha256"

    with open(golden_sha_path, "r", encoding="utf-8") as f:
        expected_hash = f.read().strip()

    # Load protocol v6 config for all 9 evaluated methods
    protocol_cfg_path = os.path.join(REPO_ROOT, "experiments", "configs", "protocol_v6.yaml")
    with open(protocol_cfg_path, "r", encoding="utf-8") as f:
        p6_cfg = yaml.safe_load(f)

    # Load smoke config for developmental benchmark universe
    smoke_cfg_path = os.path.join(REPO_ROOT, "experiments", "configs", "smoke_config.yaml")
    with open(smoke_cfg_path, "r", encoding="utf-8") as f:
        smoke_cfg = yaml.safe_load(f)

    eval_methods = p6_cfg["evaluated_methods"]
    methods = list(eval_methods.keys())
    dev_seeds = [40484, 40506]

    assert len(methods) == 9, f"Expected 9 methods, got {len(methods)}"
    assert len(dev_seeds) == 2, f"Expected 2 dev seeds, got {len(dev_seeds)}"

    records = []
    for seed in dev_seeds:
        for method_name in methods:
            m_spec = eval_methods[method_name]
            alloc_kw = m_spec.get("allocator_kwargs", {})
            c_depth = alloc_kw.get("contingency_depth", smoke_cfg["benchmark_universe"]["contingency_depth"])

            rec = run_single_trial(
                graph_family="grid",
                n_nodes=16,
                adversary_type_str="theta_1_stochastic",
                allocator_name=method_name,
                comm_regime="nominal",
                comm_range=30.0,
                p_drop=0.10,
                n_robots=2,
                n_tasks=4,
                seed=seed,
                max_steps=20,
                contingency_depth=c_depth,
                allocator_kwargs=alloc_kw,
                git_commit="golden_trace_commit",
                protocol_hash="golden_protocol_hash",
                traces_dir=None,
                runs_jsonl=None,
            )
            records.append(rec)

    assert len(records) == 18, f"Expected 18 trial records, got {len(records)}"

    cleaned = []
    for r in records:
        c = {k: v for k, v in r.items() if k not in EXCLUDE_TIMING_AND_TRANSIENT_FIELDS}
        cleaned.append(c)

    canonical_bytes = json.dumps(cleaned, sort_keys=True, indent=2).encode("utf-8")
    actual_hash = hashlib.sha256(canonical_bytes).hexdigest()

    assert actual_hash == expected_hash, (
        f"Golden trace hash mismatch!\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}\n"
        f"An optimization has altered simulation or algorithmic outcomes!"
    )
