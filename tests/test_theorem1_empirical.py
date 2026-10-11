"""
Test verifying Theorem 1 empirical guarantee and Assumption 1 instance bootstrap.
- Theorem 1: Under Assumption 1 (TV <= eta_eff), claim conflict rate is strictly 0.0.
- Assumption 1 (H7): Evaluated over independent instances (graph_family, seed) via bootstrap.
- Conflict-Free-Run Rate: Distinct descriptive row separated from Assumption 1.
"""

import json
import os
import pandas as pd
import numpy as np
import pytest

pytest.importorskip("statsmodels")

from experiments.run_statistical_tests import (
    load_and_aggregate_instances,
    evaluate_hypotheses_prereg_v3,
)
from experiments.stats import bootstrap_ci


def test_theorem1_empirical_guarantee():
    """
    Verify Theorem 1: Across all claims where TV <= eta_eff,
    the empirical conflict rate is strictly 0.0 (zero conflicts).
    """
    jsonl_path = "results/per_claim_evaluations.jsonl"
    assert os.path.exists(jsonl_path), f"Missing per-claim evaluations at {jsonl_path}"

    tv_le_eta_count = 0
    conflicts_count = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            for c in rec.get("claims", []):
                if c.get("claimed_safe") and c.get("tv_le_eta"):
                    tv_le_eta_count += 1
                    if c.get("conflicted"):
                        conflicts_count += 1

    assert tv_le_eta_count > 0, "Expected non-zero claims satisfying TV <= eta_eff"
    assert conflicts_count == 0, (
        f"Theorem 1 violation! Observed {conflicts_count} conflicts out of {tv_le_eta_count} claims with TV <= eta_eff."
    )


def test_assumption1_independent_instance_bootstrap():
    """
    Verify Assumption 1 (H7) is evaluated at independent instance level (N=250),
    not via pseudo-replicated raw evaluations.
    """
    raw_path = "results/raw_results.csv"
    assert os.path.exists(raw_path), f"Missing {raw_path}"
    df = pd.read_csv(raw_path)

    aca_df = df[df["method"] == "aca"]
    inst_tv = aca_df.groupby(["graph_family", "seed"])[["tv_evaluations_count", "tv_adhered_count"]].sum()
    inst_tv["rate"] = inst_tv["tv_adhered_count"] / inst_tv["tv_evaluations_count"].replace(0, np.nan)
    rates = inst_tv["rate"].dropna().tolist()

    assert len(rates) == 250, f"Expected 250 independent instances, found {len(rates)}"
    mean_val, ci_low, ci_high = bootstrap_ci(rates, n_resamples=5000, ci=0.95, seed=42)

    assert 0.0 < mean_val < 1.0, f"Instance mean adherence {mean_val} out of bounds"
    assert ci_low < mean_val < ci_high, f"Bootstrap CI [{ci_low}, {ci_high}] does not bound mean {mean_val}"


def test_conflict_free_run_rate_distinct_descriptive_row():
    """
    Verify conflict-free-run rate is reported in a distinct descriptive row in hypothesis results.
    """
    inst_df, raw_df = load_and_aggregate_instances("results/raw_results.csv")
    res_df = evaluate_hypotheses_prereg_v3(inst_df, raw_df, {})

    h7_rows = res_df[res_df["hypothesis_id"] == "H7"]
    cfr_rows = res_df[res_df["hypothesis_id"] == "H7_CONFLICT_FREE_RATE"]

    assert len(h7_rows) == 1, "Expected exactly one H7 row"
    assert len(cfr_rows) == 1, "Expected exactly one H7_CONFLICT_FREE_RATE descriptive row"

    # Confirm distinct metrics and tiers
    assert h7_rows.iloc[0]["metric"] == "tv_bound_adherence_rate"
    assert cfr_rows.iloc[0]["metric"] == "conflict_free_run_rate"
    assert cfr_rows.iloc[0]["tier"] == "descriptive"
    assert cfr_rows.iloc[0]["mean_aca"] > 0.90, "Conflict-free rate should be high (> 90%)"
