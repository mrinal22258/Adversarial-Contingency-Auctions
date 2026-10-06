"""
Statistical Analysis Module for Rigorous Robotics Empirical Validation:
- Bootstrap 95% Confidence Intervals (10,000 resamples)
- Paired Wilcoxon Signed-Rank Tests
- Holm-Bonferroni Family-Wise Error Correction
- Cliff's Delta Effect Sizes
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import scipy.stats as stats


def bootstrap_ci(
    data: List[float],
    n_resamples: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Compute mean and two-sided bootstrap confidence interval.
    Returns (mean, lower_bound, upper_bound).
    """
    arr = np.array(data, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0
    if len(arr) == 1:
        return float(arr[0]), float(arr[0]), float(arr[0])

    mean_val = float(np.mean(arr))
    rng = np.random.default_rng(seed)

    # Resample
    boot_indices = rng.integers(0, len(arr), size=(n_resamples, len(arr)))
    boot_means = np.mean(arr[boot_indices], axis=1)

    alpha = 1.0 - ci
    lower = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    upper = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))

    return mean_val, lower, upper


def cliffs_delta(x: List[float], y: List[float]) -> float:
    """
    Compute Cliff's delta non-parametric effect size between paired or unpaired distributions.
    d in [-1, 1]. |d| < 0.147 (negligible), < 0.33 (small), < 0.474 (medium), >= 0.474 (large).
    """
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    n_x, n_y = len(x_arr), len(y_arr)
    if n_x == 0 or n_y == 0:
        return 0.0

    # Pairwise comparisons
    diff = x_arr[:, None] - y_arr[None, :]
    greater = np.sum(diff > 0)
    less = np.sum(diff < 0)

    delta = float((greater - less) / (n_x * n_y))
    return delta


def paired_wilcoxon_test(
    aca_data: List[float],
    baseline_data: List[float],
) -> Tuple[float, float]:
    """
    Compute paired Wilcoxon signed-rank test.
    Returns (statistic, p_value).
    """
    a = np.array(aca_data, dtype=float)
    b = np.array(baseline_data, dtype=float)
    if len(a) != len(b) or len(a) < 5:
        return 0.0, 1.0

    diff = a - b
    if np.all(diff == 0):
        return 0.0, 1.0

    try:
        res = stats.wilcoxon(a, b, alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        return 0.0, 1.0


def holm_bonferroni_correction(
    p_values: List[float],
    alpha: float = 0.05,
) -> List[Tuple[float, bool]]:
    """
    Holm-Bonferroni step-down procedure for multiple testing correction.
    Returns list of (adjusted_p_value, is_significant) tuples in original order.
    """
    m = len(p_values)
    if m == 0:
        return []

    sorted_indices = np.argsort(p_values)
    adj_p = np.zeros(m)
    sig_flags = np.zeros(m, dtype=bool)

    running_max = 0.0
    for rank, idx in enumerate(sorted_indices):
        raw_p = p_values[idx]
        adj = raw_p * (m - rank)
        adj = min(1.0, max(running_max, adj))
        running_max = adj
        adj_p[idx] = adj
        sig_flags[idx] = adj <= alpha

    return [(float(adj_p[i]), bool(sig_flags[i])) for i in range(m)]


def format_latex_ci(mean: float, lower: float, upper: float, decimals: int = 1) -> str:
    """Format as LaTeX mean \pm half-width CI string."""
    half_ci = 0.5 * (upper - lower)
    return f"${mean:.{decimals}f} \\pm {half_ci:.{decimals}f}$"
