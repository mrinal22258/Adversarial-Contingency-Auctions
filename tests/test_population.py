"""Unit and regression tests for experiments/population.py.

Validates that:
1. get_locked_population locks exact population masks and raises on duplicate cells or missing pairs.
2. Extra irrelevant rows in raw input data do not change the locked population or its computed statistics.
3. Clustered bootstrap / cluster-aware variance estimator accurately estimates cluster n and provides proper coverage.
4. Table caption N and cluster count n are strictly computed from locked data.
"""
import pytest
import numpy as np
import pandas as pd

from experiments.population import (
    get_locked_population,
    compute_population_summary,
    compute_cluster_aware_ci,
    compute_cluster_paired_test,
    LOCKED_POPULATIONS,
)


def create_synthetic_grid(n_clusters=20, n_methods=2, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    methods = ["aca", "cbba_lr"][:n_methods]
    for cluster_id in range(n_clusters):
        cluster_effect = rng.normal(0.0, 5.0)
        for m_idx, m in enumerate(methods):
            # Treatment effect for method 1 vs method 0
            effect = 3.0 if m == "cbba_lr" else 0.0
            error = rng.normal(0.0, 2.0)
            rows.append({
                "graph_family": f"fam_{cluster_id % 3}",
                "seed": 1000 + cluster_id,
                "adversary": "theta_1_stochastic",
                "comm_regime": "nominal",
                "n_robots": 4,
                "n_tasks": 15,
                "method": m,
                "completion_rate_pct": float(np.clip(80.0 + cluster_effect + effect + error, 0.0, 100.0)),
                "net_welfare": float(900.0 + 2.0 * cluster_effect + 5.0 * effect + error),
                "total_conflicts": float(max(0.0, 30.0 + error)),
                "total_messages": float(200.0 + 10.0 * m_idx + error),
                "mean_tick_runtime_ms": float(10.0 + error),
            })
    return pd.DataFrame(rows)


def test_locked_population_isolation():
    df_base = create_synthetic_grid(n_clusters=10, n_methods=2)
    pop_base, meta_base = get_locked_population(df_base, population_id="nominal_balanced_core")
    
    # Add dummy extra rows with different comm_regime or adversary
    df_extra = df_base.copy()
    extra_row = df_base.iloc[0].copy()
    extra_row["comm_regime"] = "ofat_loss_50"
    df_extra = pd.concat([df_extra, pd.DataFrame([extra_row])], ignore_index=True)
    
    pop_extra, meta_extra = get_locked_population(df_extra, population_id="nominal_balanced_core")
    
    assert len(pop_base) == len(pop_extra)
    assert meta_base["n_trials"] == meta_extra["n_trials"]
    assert meta_base["n_clusters"] == meta_extra["n_clusters"]
    pd.testing.assert_frame_equal(pop_base, pop_extra)


def test_duplicate_cell_raises():
    df = create_synthetic_grid(n_clusters=5, n_methods=2)
    # Duplicate first row
    df_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate cells detected"):
        get_locked_population(df_dup, population_id="nominal_balanced_core", strict=True)


def test_missing_method_pair_raises():
    df = create_synthetic_grid(n_clusters=5, n_methods=2)
    # Drop one method row from one cluster
    df_missing = df.iloc[:-1]
    with pytest.raises(ValueError, match="Incomplete pairing"):
        get_locked_population(df_missing, population_id="nominal_balanced_core", strict=True)


def test_cluster_aware_ci_coverage():
    # Verify cluster bootstrap provides near-nominal coverage on synthetic clustered data
    rng = np.random.default_rng(2026)
    true_mean = 85.0
    covered = 0
    n_sims = 50
    for sim in range(n_sims):
        cluster_effects = rng.normal(0.0, 4.0, size=25)
        sim_rows = []
        for c_idx, c_eff in enumerate(cluster_effects):
            for _ in range(4): # 4 observations per cluster
                val = true_mean + c_eff + rng.normal(0.0, 1.0)
                sim_rows.append({"cluster": c_idx, "val": val})
        df_sim = pd.DataFrame(sim_rows)
        mean, ci_low, ci_high = compute_cluster_aware_ci(df_sim, val_col="val", cluster_col="cluster", rng=rng)
        if ci_low <= true_mean <= ci_high:
            covered += 1
    coverage_rate = covered / n_sims
    assert coverage_rate >= 0.84, f"Coverage {coverage_rate} is too low for nominal 95%"


def test_population_summary_metrics():
    df = create_synthetic_grid(n_clusters=15, n_methods=2)
    pop, meta = get_locked_population(df, population_id="nominal_balanced_core")
    summary = compute_population_summary(pop, meta)
    
    assert summary["n_cells_total"] == 30
    assert summary["n_clusters"] == 15
    assert "aca" in summary["methods"]
    assert "cbba_lr" in summary["methods"]
    assert "completion_rate_pct" in summary["metrics"]["aca"]
