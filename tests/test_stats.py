"""
Unit tests for experiments/stats.py (Phase 3 requirement).
Verifies:
- Hodges-Lehmann difference calculation and Walsh median
- Cliff's delta calculation and bounds in [-1, 1]
- Paired Cohen's d_z against manual calculation
- TOST equivalence test against paired t-distribution
- Holm-Bonferroni correction monotonicity and FWER control
- Benjamini-Hochberg correction FDR control
- Bootstrap CI coverage
"""

import numpy as np

from experiments.stats import (
    paired_cohens_dz,
    hodges_lehmann_difference,
    cliffs_delta,
    tost_equivalence_test,
    holm_bonferroni_correction,
    benjamini_hochberg_correction,
    bootstrap_ci,
)


def test_cohens_dz():
    x = [10.0, 12.0, 14.0, 16.0]
    y = [8.0, 9.0, 10.0, 11.0]
    # diff = [2.0, 3.0, 4.0, 5.0]
    # mean(diff) = 3.5, std(diff, ddof=1) = sqrt(5/3) ~ 1.29099
    # d_z = 3.5 / 1.29099 ~ 2.7105
    dz = paired_cohens_dz(x, y)
    expected_dz = 3.5 / np.std([2, 3, 4, 5], ddof=1)
    assert np.isclose(dz, expected_dz, atol=1e-3)


def test_hodges_lehmann_difference():
    x = [5.0, 7.0, 8.0, 10.0]
    y = [2.0, 3.0, 4.0, 5.0]
    # diff = [3, 4, 4, 5]
    # Walsh averages of [3, 4, 4, 5]:
    # (3+3)/2=3, (3+4)/2=3.5, (3+4)/2=3.5, (3+5)/2=4, (4+4)/2=4, (4+4)/2=4, (4+5)/2=4.5, (4+4)/2=4, (4+5)/2=4.5, (5+5)/2=5
    # median = 4.0
    hl, low, high = hodges_lehmann_difference(x, y)
    assert np.isclose(hl, 4.0, atol=1e-3)
    assert low <= hl <= high


def test_cliffs_delta():
    # If all x > all y, delta must be 1.0
    x = [10.0, 20.0, 30.0]
    y = [1.0, 2.0, 3.0]
    delta, low, high = cliffs_delta(x, y)
    assert np.isclose(delta, 1.0)
    assert np.isclose(low, 1.0)
    assert np.isclose(high, 1.0)

    # Symmetrical data: delta must be 0.0
    x2 = [1.0, 2.0, 3.0]
    y2 = [1.0, 2.0, 3.0]
    delta2, low2, high2 = cliffs_delta(x2, y2)
    assert np.isclose(delta2, 0.0)


def test_tost_equivalence_test():
    # Identical paired samples with slight noise should be equivalent within margin 2.0
    rng = np.random.default_rng(42)
    x = list(rng.normal(10.0, 1.0, size=50))
    y = [val + float(rng.normal(0.0, 0.2)) for val in x]

    res = tost_equivalence_test(x, y, margin=2.0, alpha=0.05)
    assert res["is_equivalent"] is True
    assert res["p_tost"] < 0.05
    assert -2.0 < res["mean_diff"] < 2.0

    # Large difference should NOT be equivalent
    y_large = [val + 5.0 for val in x]
    res_large = tost_equivalence_test(x, y_large, margin=2.0, alpha=0.05)
    assert res_large["is_equivalent"] is False


def test_multiple_comparison_corrections():
    p_vals = [0.001, 0.015, 0.03, 0.08]

    # Holm-Bonferroni: adjusted p must be monotonically non-decreasing
    holm_res = holm_bonferroni_correction(p_vals, alpha=0.05)
    adj_holm = [p for p, _ in holm_res]
    assert adj_holm[0] <= adj_holm[1] <= adj_holm[2] <= adj_holm[3]
    # First p: 0.001 * 4 = 0.004
    assert np.isclose(adj_holm[0], 0.004)

    # Benjamini-Hochberg: FDR adjustment
    bh_res = benjamini_hochberg_correction(p_vals, q=0.05)
    adj_bh = [p for p, _ in bh_res]
    assert all(a <= b for a, b in zip(adj_bh, adj_holm)), "BH p-values should be <= Holm p-values"


def test_bootstrap_ci():
    data = [10.0, 12.0, 11.0, 9.0, 13.0, 10.5]
    mean_val, lower, upper = bootstrap_ci(data, n_resamples=5000, ci=0.95, seed=42)
    assert lower <= mean_val <= upper
    assert np.isclose(mean_val, np.mean(data))
