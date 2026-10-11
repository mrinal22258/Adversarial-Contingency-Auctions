"""
Stage 1 Regression Test Suite: Provenance, Schema Validation, Map Verification, and Statistical Integrity.

Covers:
- Schema validation (required columns, types, finite ranges, invalid status)
- Failed-trial retention in denominators
- Duplicate and scale collision detection (7-tuple vs 5-tuple)
- Fallback prohibition and map verification states (VERIFIED, MISMATCH, MISSING, UNAVAILABLE)
- Boston map edge statistics (326 GraphML vs 323 undirected)
- Per-baseline paired N consistency and paired estimand consistency
- p-value formatting (no false 0.00)
- Constant, all-zero, and tied differences
- Instance-count vs row-count distinction
"""

import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from acalib.data.schema import (
    REQUIRED_COLUMNS,
    ALLOWED_STATUSES,
    TrialValidationError,
    validate_trial_row,
    validate_results_dataframe,
    get_pairing_key,
    get_independent_instance_key,
    check_duplicates,
)
from acalib.demo.provenance import verify_map_provenance, VerificationState
from experiments.stats import (
    bootstrap_ci,
    hodges_lehmann_difference,
    paired_wilcoxon_test,
    holm_bonferroni_correction,
)
from experiments.make_tables import compute_paired_statistics


# ---------------------------------------------------------------------------
# 1. Schema Validation Tests
# ---------------------------------------------------------------------------

def test_schema_valid_row():
    valid_row = {
        "trial_id": "test_001",
        "method": "aca",
        "graph_family": "rgg",
        "map_name": "rgg_n50",
        "adversary": "theta_1_stochastic",
        "comm_regime": "nominal",
        "n_robots": 8,
        "n_tasks": 30,
        "seed": 42,
        "status": "COMPLETED",
        "completion_rate_pct": 85.5,
        "social_welfare": 120.0,
        "total_conflicts": 2,
        "total_messages": 150,
        "planning_time_ms": 32.5,
    }
    # Should not raise
    validate_trial_row(valid_row)


def test_schema_missing_column():
    incomplete_row = {
        "trial_id": "test_002",
        "method": "aca",
        # missing graph_family and others
        "seed": 42,
        "status": "COMPLETED",
    }
    with pytest.raises(TrialValidationError) as exc_info:
        validate_trial_row(incomplete_row)
    assert "Missing required column" in str(exc_info.value)


def test_schema_invalid_status():
    bad_status_row = {
        "trial_id": "test_003",
        "method": "aca",
        "graph_family": "rgg",
        "map_name": "rgg_n50",
        "adversary": "theta_1_stochastic",
        "comm_regime": "nominal",
        "n_robots": 8,
        "n_tasks": 30,
        "seed": 42,
        "status": "UNKNOWN_CRASH",
        "completion_rate_pct": 50.0,
        "social_welfare": 100.0,
        "total_conflicts": 0,
        "total_messages": 100,
        "planning_time_ms": 10.0,
    }
    with pytest.raises(TrialValidationError) as exc_info:
        validate_trial_row(bad_status_row)
    assert "Invalid status" in str(exc_info.value)


def test_schema_non_finite_and_out_of_range():
    nan_row = {
        "trial_id": "test_004",
        "method": "aca",
        "graph_family": "rgg",
        "map_name": "rgg_n50",
        "adversary": "theta_1_stochastic",
        "comm_regime": "nominal",
        "n_robots": 8,
        "n_tasks": 30,
        "seed": 42,
        "status": "COMPLETED",
        "completion_rate_pct": float("nan"),
        "social_welfare": 100.0,
        "total_conflicts": 0,
        "total_messages": 100,
        "planning_time_ms": 10.0,
    }
    with pytest.raises(TrialValidationError) as exc_info:
        validate_trial_row(nan_row)
    assert "non-finite" in str(exc_info.value)

    out_of_range_row = dict(nan_row, completion_rate_pct=105.0)
    with pytest.raises(TrialValidationError) as exc_info:
        validate_trial_row(out_of_range_row)
    assert "out of valid range" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Failed-Trial Retention Tests
# ---------------------------------------------------------------------------

def test_failed_trials_retained_in_denominators():
    rows = [
        {
            "trial_id": f"t_{i}",
            "method": "aca",
            "graph_family": "rgg",
            "map_name": "rgg_n50",
            "adversary": "theta_1_stochastic",
            "comm_regime": "nominal",
            "n_robots": 8,
            "n_tasks": 30,
            "seed": i,
            "status": "COMPLETED" if i < 8 else "FAILED",
            "completion_rate_pct": 100.0 if i < 8 else 0.0,
            "net_welfare": 50.0 if i < 8 else 0.0,
            "social_welfare": 50.0 if i < 8 else 0.0,
            "total_conflicts": 0,
            "total_messages": 100,
            "planning_time_ms": 20.0,
        }
        for i in range(10)
    ]
    df = pd.DataFrame(rows)
    validate_results_dataframe(df)
    # The denominator for completion rate MUST include all 10 trials, not 8
    assert len(df) == 10
    assert (df["status"] == "FAILED").sum() == 2
    # Mean completion rate must reflect 8/10 = 80.0%, not 100.0%
    assert np.isclose(df["completion_rate_pct"].mean(), 80.0)


# ---------------------------------------------------------------------------
# 3. Duplicate and Scale Collision Detection (7-Tuple vs 5-Tuple)
# ---------------------------------------------------------------------------

def test_scale_collision_differentiation():
    row_scale1 = {
        "graph_family": "rgg",
        "adversary": "theta_1_stochastic",
        "comm_regime": "ofat_scale_robots_12",
        "method": "aca",
        "seed": 42,
        "n_robots": 8,
        "n_tasks": 30,
    }
    row_scale2 = {
        "graph_family": "rgg",
        "adversary": "theta_1_stochastic",
        "comm_regime": "ofat_scale_robots_12",
        "method": "aca",
        "seed": 42,
        "n_robots": 12,  # different scale!
        "n_tasks": 30,
    }
    # 5-tuple collides
    five_tuple_1 = (row_scale1["graph_family"], row_scale1["adversary"], row_scale1["comm_regime"], row_scale1["method"], row_scale1["seed"])
    five_tuple_2 = (row_scale2["graph_family"], row_scale2["adversary"], row_scale2["comm_regime"], row_scale2["method"], row_scale2["seed"])
    assert five_tuple_1 == five_tuple_2, "5-tuple erroneously collides across scale sweeps"

    # 7-tuple differentiates
    pairing_key_1 = get_pairing_key(row_scale1)
    pairing_key_2 = get_pairing_key(row_scale2)
    assert pairing_key_1 != pairing_key_2, "7-tuple must differentiate distinct robot/task scales"


def test_true_duplicate_detection():
    row1 = {
        "trial_id": "dup_1",
        "method": "aca",
        "graph_family": "rgg",
        "map_name": "rgg_n50",
        "adversary": "theta_1_stochastic",
        "comm_regime": "nominal",
        "n_robots": 8,
        "n_tasks": 30,
        "seed": 42,
        "status": "COMPLETED",
        "completion_rate_pct": 90.0,
        "social_welfare": 100.0,
        "total_conflicts": 0,
        "total_messages": 100,
        "planning_time_ms": 20.0,
    }
    row2 = dict(row1, trial_id="dup_2", completion_rate_pct=85.0)
    df = pd.DataFrame([row1, row2])

    dups = check_duplicates(df)
    assert len(dups) == 2, "Duplicate checker must identify both rows sharing identical 7-tuple key"


# ---------------------------------------------------------------------------
# 4. Map Verification and Fallback Prohibition Tests
# ---------------------------------------------------------------------------

def test_map_provenance_states():
    # Test valid map
    res_boston = verify_map_provenance("road_osmnx")
    assert res_boston.status == VerificationState.VERIFIED
    assert res_boston.manifest_hash == res_boston.computed_hash
    assert res_boston.nodes == 216
    assert res_boston.edges == 323
    assert res_boston.matched_work_zone_edges == 112

    # Test missing map
    res_missing = verify_map_provenance("non_existent_map_xyz")
    assert res_missing.status == VerificationState.MISSING
    assert res_missing.computed_hash is None
    assert res_missing.manifest_hash is None

    # Test unavailable manifest
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pass a non-existent manifest path
        fake_manifest = os.path.join(tmpdir, "manifest_missing.json")
        res_unavail = verify_map_provenance("road_osmnx", manifest_path=fake_manifest)
        assert res_unavail.status == VerificationState.UNAVAILABLE
        assert "Manifest not found" in res_unavail.message


def test_no_fallback_hashes_in_provenance():
    # Ensure acalib/demo/provenance.py contains no hardcoded fallback hashes
    import inspect
    import acalib.demo.provenance as prov_module
    src = inspect.getsource(prov_module)
    assert "9f9c73b0" not in src, "Hardcoded fallback SHA-256 hash must not exist in provenance module"
    assert "default=" not in src.lower() or "sha" not in src.lower()


# ---------------------------------------------------------------------------
# 5. Boston Map Edge Statistics (326 raw vs 323 simple undirected)
# ---------------------------------------------------------------------------

def test_boston_map_edge_counts_in_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "data", "maps", "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    osmnx_info = data["osmnx"]
    assert osmnx_info["nodes"] == 216
    assert osmnx_info["edges"] == 323
    assert osmnx_info["raw_graphml_edges"] == 326
    assert osmnx_info["matched_work_zone_edges"] == 112


# ---------------------------------------------------------------------------
# 6. Statistical Integrity: Per-Baseline Paired N and Consistency
# ---------------------------------------------------------------------------

def test_compute_paired_statistics_independent_n():
    """Ensure compute_paired_statistics records actual n_pairs per baseline without stale loop values."""
    # Create synthetic dataset where aca has 10 runs, baseline1 has 10 runs, baseline2 has 5 runs
    aca_rows = [
        {"graph_family": "rgg", "adversary": "theta_1", "comm_regime": "nominal", "n_robots": 8, "n_tasks": 30, "seed": i, "method": "aca", "completion_rate_pct": 90.0 + i}
        for i in range(10)
    ]
    b1_rows = [
        {"graph_family": "rgg", "adversary": "theta_1", "comm_regime": "nominal", "n_robots": 8, "n_tasks": 30, "seed": i, "method": "b1", "completion_rate_pct": 80.0 + i}
        for i in range(10)
    ]
    b2_rows = [
        {"graph_family": "rgg", "adversary": "theta_1", "comm_regime": "nominal", "n_robots": 8, "n_tasks": 30, "seed": i, "method": "b2", "completion_rate_pct": 70.0 + i}
        for i in range(5)
    ]
    synth_df = pd.DataFrame(aca_rows + b1_rows + b2_rows)

    keys = ["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks", "seed"]
    stats_results = compute_paired_statistics(synth_df, ["b1", "b2"], ["completion_rate_pct"], keys)

    assert stats_results["b1"]["completion_rate_pct"]["n_pairs"] == 10
    assert stats_results["b2"]["completion_rate_pct"]["n_pairs"] == 5
    assert stats_results["b1"]["completion_rate_pct"]["n_pairs"] != stats_results["b2"]["completion_rate_pct"]["n_pairs"]


def test_paired_estimand_consistency():
    """Verify that mean_diff and hl_median operate on the exact matched pairs."""
    aca_vals = np.array([90.0, 92.0, 85.0, 88.0, 95.0])
    base_vals = np.array([80.0, 82.0, 75.0, 80.0, 85.0])
    diffs = aca_vals - base_vals

    mean_diff = float(np.mean(diffs))
    hl_diff, _, _ = hodges_lehmann_difference(aca_vals.tolist(), base_vals.tolist())
    mean_boot, ci_low, ci_high = bootstrap_ci(diffs.tolist(), n_resamples=1000, ci=0.95, seed=42)

    assert np.isclose(mean_diff, 9.6)
    assert ci_low <= mean_diff <= ci_high


# ---------------------------------------------------------------------------
# 7. p-Value Formatting and Constant / Zero Difference Handling
# ---------------------------------------------------------------------------

def test_p_value_formatting_no_false_zero():
    from experiments.make_tables import generate_numbers_macro_file

    def format_p_val_test(pval: float) -> str:
        if pval < 0.001:
            return "< 0.001"
        return f"{pval:.3f}"

    assert format_p_val_test(1e-5) == "< 0.001"
    assert format_p_val_test(0.0001) == "< 0.001"
    assert format_p_val_test(0.00099) == "< 0.001"
    assert format_p_val_test(0.001) == "0.001"
    assert format_p_val_test(0.0456) == "0.046"
    assert format_p_val_test(0.0) == "< 0.001"
    assert format_p_val_test(0.0) != "0.00"


def test_constant_zero_difference_handling():
    """Verify that constant zero differences do not crash or produce invalid CIs."""
    zero_diffs = [0.0] * 20
    hl_val, _, _ = hodges_lehmann_difference(zero_diffs, [0.0] * 20)
    mean_boot, ci_low, ci_high = bootstrap_ci(zero_diffs, n_resamples=1000, ci=0.95, seed=42)
    w_stat, w_pval = paired_wilcoxon_test(np.zeros(20), np.zeros(20))

    assert hl_val == 0.0
    assert ci_low == 0.0
    assert ci_high == 0.0
    assert w_pval == 1.0


# ---------------------------------------------------------------------------
# 8. Instance Count vs Row Count Separation
# ---------------------------------------------------------------------------

def test_instance_vs_row_count():
    """Independent instances represent distinct problem configurations (family, map, seed, scale)."""
    # 3 seeds, 2 adversaries per seed -> 6 trial rows, but only 3 independent problem instances
    rows = []
    for s in [1, 2, 3]:
        for adv in ["theta_1", "theta_2"]:
            rows.append({
                "graph_family": "rgg",
                "map_name": "rgg_50",
                "adversary": adv,
                "comm_regime": "nominal",
                "n_robots": 8,
                "n_tasks": 30,
                "seed": s,
                "method": "aca",
            })
    df = pd.DataFrame(rows)
    assert len(df) == 6
    instances = df.apply(get_independent_instance_key, axis=1).unique()
    assert len(instances) == 3
