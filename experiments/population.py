"""Locked Population Definitions and Cluster-Aware Statistical Inference.

Single source of truth for:
1. Population filters, expected cell counts, and pairing keys.
2. Cell-level and cluster-aware bootstrap confidence intervals.
3. Paired non-parametric and cluster-robust hypothesis testing.
4. Estimand consistency enforcement across tables, macros, and claim verification.
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from scipy import stats

LOCKED_POPULATIONS = {
    "nominal_balanced_core": {
        "description": "Balanced nominal grid (4 robots, 15 tasks, nominal comm, 3 canonical adversaries)",
        "comm_regime": "nominal",
        "adversaries": ["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"],
        "pairing_keys": ["graph_family", "adversary", "n_robots", "n_tasks", "seed"],
        "cluster_keys": ["graph_family", "seed"],
        "expected_instances": 250,
        "expected_methods": ["aca", "aca_no_margin", "cbba", "ctp_replan", "implicit", "ssi", "cbba_partial"],
    },
    "protocol_v5_confirmatory": {
        "description": "Protocol v5 Held-Out Confirmatory Benchmark (450 matched instances per method, 8 methods)",
        "comm_regime": "nominal",
        "adversaries": ["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"],
        "pairing_keys": ["graph_family", "adversary", "seed"],
        "cluster_keys": ["graph_family", "seed"],
        "expected_instances": 450,
        "expected_methods": ["aca", "aca_plus", "aca_adaptive", "aca_no_margin", "cbba_lr", "cbba_partial_lr", "ctp_replan", "ssi_lr"],
    },
}


def get_locked_population(
    df: pd.DataFrame,
    population_id: str = "nominal_balanced_core",
    strict: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Extract and validate a locked population from a raw or confirmatory dataframe.
    
    Fails closed on empty result, duplicate cells, or incomplete pairings when strict=True.
    """
    if population_id not in LOCKED_POPULATIONS:
        raise ValueError(f"Unknown population_id: {population_id}. Expected one of {list(LOCKED_POPULATIONS.keys())}")
    
    spec = LOCKED_POPULATIONS[population_id]
    mask = pd.Series(True, index=df.index)
    
    if "comm_regime" in df.columns and "comm_regime" in spec:
        mask &= (df["comm_regime"] == spec["comm_regime"])
    if "adversary" in df.columns and "adversaries" in spec:
        mask &= (df["adversary"].isin(spec["adversaries"]))
        
    pop_df = df[mask].copy()
    if len(pop_df) == 0:
        raise ValueError(f"Population '{population_id}' is empty after applying registered filters!")
        
    # Determine valid pairing keys
    pairing_cols = [k for k in spec["pairing_keys"] if k in pop_df.columns]
    if not pairing_cols:
        pairing_cols = ["graph_family", "seed"] if "graph_family" in pop_df.columns and "seed" in pop_df.columns else ["seed"]
        
    pop_df["pairing_key"] = pop_df[pairing_cols].astype(str).agg("_".join, axis=1)
    
    # Cluster unit: family x seed
    cluster_cols = [k for k in spec["cluster_keys"] if k in pop_df.columns]
    if not cluster_cols:
        cluster_cols = pairing_cols
    pop_df["cluster_id"] = pop_df[cluster_cols].astype(str).agg("_".join, axis=1)
    
    # Validation
    methods = sorted(pop_df["method"].unique())
    clusters = sorted(pop_df["cluster_id"].unique())
    pairs = sorted(pop_df["pairing_key"].unique())
    
    # Check duplicate cells: (pairing_key, method)
    dups = pop_df.duplicated(subset=["pairing_key", "method"], keep=False)
    if dups.any():
        dup_count = dups.sum()
        if strict:
            raise ValueError(f"Duplicate cells detected in population '{population_id}': {dup_count} duplicate rows.")
            
    # Check incomplete pairs
    pair_counts = pop_df.groupby("pairing_key")["method"].nunique()
    expected_m_count = len(methods)
    incomplete = pair_counts[pair_counts < expected_m_count]
    if len(incomplete) > 0 and strict:
        raise ValueError(f"Incomplete pairing in population '{population_id}': {len(incomplete)} pairs have < {expected_m_count} methods.")
        
    meta = {
        "population_id": population_id,
        "n_cells_total": len(pop_df),
        "n_pairs": len(pairs),
        "n_clusters": len(clusters),
        "n_trials": len(pop_df[pop_df["method"] == methods[0]]) if methods else 0,
        "methods": methods,
        "pairing_cols": pairing_cols,
        "cluster_cols": cluster_cols,
    }
    
    return pop_df, meta


def compute_cluster_aware_ci(
    df: pd.DataFrame,
    val_col: str,
    cluster_col: str = "cluster_id",
    n_boot: int = 2000,
    ci: float = 0.95,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[float, float, float]:
    """
    Cluster bootstrap confidence interval resampling whole clusters with replacement.
    Honors clustering across (graph_family x seed).
    """
    if rng is None:
        rng = np.random.default_rng(2026)
        
    clusters = df[cluster_col].unique()
    n_clusters = len(clusters)
    if n_clusters <= 1:
        # Fallback to standard bootstrap if single cluster
        vals = df[val_col].dropna().values
        return compute_cell_bootstrap_ci(vals, n_boot=n_boot, ci=ci, rng=rng)
        
    # Pre-aggregate cluster sums and counts for fast vectorized bootstrap
    cluster_grouped = df.groupby(cluster_col)[val_col]
    c_sums = cluster_grouped.sum().values
    c_counts = cluster_grouped.count().values
    
    point_mean = float(c_sums.sum() / max(1, c_counts.sum()))
    
    # Vectorized cluster resampling
    boot_indices = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    boot_sums = np.sum(c_sums[boot_indices], axis=1)
    boot_counts = np.sum(c_counts[boot_indices], axis=1)
    boot_means = boot_sums / np.maximum(1, boot_counts)
    
    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_means, 100.0 * alpha))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha)))
    
    return point_mean, low, high


def compute_cell_bootstrap_ci(
    vals: np.ndarray,
    n_boot: int = 2000,
    ci: float = 0.95,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[float, float, float]:
    """Standard cell-level bootstrap CI assuming i.i.d. observations."""
    if rng is None:
        rng = np.random.default_rng(2026)
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return 0.0, 0.0, 0.0
    point_mean = float(np.mean(vals))
    if len(vals) == 1:
        return point_mean, point_mean, point_mean
        
    n = len(vals)
    boot_samples = rng.choice(vals, size=(n_boot, n), replace=True)
    boot_means = np.mean(boot_samples, axis=1)
    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_means, 100.0 * alpha))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha)))
    return point_mean, low, high


def compute_cluster_paired_test(
    df: pd.DataFrame,
    method_a: str,
    method_b: str,
    metric_col: str,
    pairing_col: str = "pairing_key",
    cluster_col: str = "cluster_id",
) -> Dict[str, Any]:
    """
    Paired hypothesis tests reporting BOTH cell-level and cluster-aware tests side-by-side.
    """
    sub_a = df[df["method"] == method_a].set_index(pairing_col)
    sub_b = df[df["method"] == method_b].set_index(pairing_col)
    
    common_pairs = sub_a.index.intersection(sub_b.index)
    if len(common_pairs) == 0:
        raise ValueError(f"No paired trials found between {method_a} and {method_b}!")
        
    va = sub_a.loc[common_pairs, metric_col].astype(float).values
    vb = sub_b.loc[common_pairs, metric_col].astype(float).values
    diffs = va - vb
    
    # 1. Registered cell-level paired Wilcoxon signed rank test
    try:
        if np.allclose(diffs, 0.0):
            w_stat, cell_p = 0.0, 1.0
        else:
            res = stats.wilcoxon(diffs, alternative="two-sided")
            w_stat, cell_p = float(res.statistic), float(res.pvalue)
    except Exception:
        w_stat, cell_p = 0.0, 1.0
        
    # Hodges-Lehmann median difference estimator
    # For speed, subsample diffs if N > 500
    if len(diffs) <= 500:
        walsh = [(diffs[i] + diffs[j]) / 2.0 for i in range(len(diffs)) for j in range(i, len(diffs))]
        hl_diff = float(np.median(walsh))
    else:
        rng = np.random.default_rng(2026)
        idx_i = rng.choice(len(diffs), size=5000)
        idx_j = rng.choice(len(diffs), size=5000)
        walsh = (diffs[idx_i] + diffs[idx_j]) / 2.0
        hl_diff = float(np.median(walsh))
        
    # 2. Cluster-aware test: cluster-level paired t-test on cluster mean differences
    cluster_a = sub_a.loc[common_pairs, cluster_col].values
    pair_df = pd.DataFrame({"diff": diffs, "cluster": cluster_a})
    cluster_diffs = pair_df.groupby("cluster")["diff"].mean().values
    
    if len(cluster_diffs) > 1 and not np.allclose(cluster_diffs, 0.0):
        t_res = stats.ttest_1samp(cluster_diffs, 0.0)
        cluster_t_stat, cluster_p = float(t_res.statistic), float(t_res.pvalue)
    else:
        cluster_t_stat, cluster_p = 0.0, 1.0
        
    return {
        "n_pairs": len(common_pairs),
        "n_clusters": len(cluster_diffs),
        "mean_diff": float(np.mean(diffs)),
        "hl_median_diff": hl_diff,
        "cell_wilcoxon_stat": w_stat,
        "cell_p_value": cell_p,
        "cluster_t_stat": cluster_t_stat,
        "cluster_p_value": cluster_p,
    }


def compute_population_summary(
    pop_df: pd.DataFrame,
    meta: Dict[str, Any],
    metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate comprehensive summary with both cell and cluster estimates side by side."""
    if metrics is None:
        metrics = ["completion_rate_pct", "net_welfare", "total_conflicts", "total_messages", "mean_tick_runtime_ms"]
        
    summary = {
        "population_id": meta["population_id"],
        "n_cells_total": meta["n_cells_total"],
        "n_pairs": meta["n_pairs"],
        "n_clusters": meta["n_clusters"],
        "methods": meta["methods"],
        "metrics": {},
    }
    
    for m in meta["methods"]:
        m_df = pop_df[pop_df["method"] == m]
        summary["metrics"][m] = {}
        for col in metrics:
            if col not in m_df.columns:
                continue
            vals = m_df[col].dropna().astype(float).values
            cell_mean, cell_low, cell_high = compute_cell_bootstrap_ci(vals)
            clust_mean, clust_low, clust_high = compute_cluster_aware_ci(m_df, val_col=col, cluster_col="cluster_id")
            summary["metrics"][m][col] = {
                "cell_mean": cell_mean,
                "cell_ci": (cell_low, cell_high),
                "cluster_mean": clust_mean,
                "cluster_ci": (clust_low, clust_high),
                "std": float(np.std(vals)) if len(vals) > 0 else 0.0,
            }
            
    return summary
