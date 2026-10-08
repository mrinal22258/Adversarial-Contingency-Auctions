"""
Unit test verifying the mechanism behind completion rise under degraded communication:
Auction churn, cascading re-assignments, and packet drop shielding.
"""

import os
import pandas as pd
import numpy as np
import pytest


def test_comm_degradation_data_consistency():
    """Verify raw empirical data demonstrates the completion rise phenomenon across CBBA family."""
    csv_path = "results/supplement/pilot_sweep_17100.csv" if os.path.exists("results/supplement/pilot_sweep_17100.csv") else "results/raw_results.csv"
    assert os.path.exists(csv_path), f"Missing {csv_path}"
    df = pd.read_csv(csv_path)

    # Filter to CBBA family methods
    cbba_methods = ["cbba", "cbba_lr", "cbba_partial", "cbba_partial_lr", "aca", "aca_no_margin"]
    sub_df = df[df["method"].isin(cbba_methods)]

    # Compute mean completion by method and comm_regime
    piv_comp = sub_df.pivot_table(index="method", columns="comm_regime", values="completion_rate_pct", aggfunc="mean")
    
    # Assert monotonic or near-monotonic rise for every CBBA method from benign to lossy
    for m in cbba_methods:
        benign_val = piv_comp.loc[m, "benign"]
        lossy_val = piv_comp.loc[m, "lossy"]
        assert lossy_val > benign_val, (
            f"Method {m} was expected to have higher completion in lossy ({lossy_val:.2f}) than benign ({benign_val:.2f})"
        )

    # Verify that SSI behaves oppositely (sequential auction collapses without communication)
    ssi_df = df[df["method"] == "ssi"]
    piv_ssi = ssi_df.pivot_table(index="method", columns="comm_regime", values="completion_rate_pct", aggfunc="mean")
    assert piv_ssi.loc["ssi", "benign"] > piv_ssi.loc["ssi", "lossy"], (
        "SSI must show expected performance degradation under lossy communication"
    )


def test_comm_churn_and_conflict_tradeoff():
    """
    Verify the scientific mechanism:
    In lossy communication:
    1. Duplicated travel distance and conflicts increase significantly (lack of coordination).
    2. But makespan decreases because robots are shielded from outbid cascading truncations (churn).
    """
    csv_path = "results/supplement/pilot_sweep_17100.csv" if os.path.exists("results/supplement/pilot_sweep_17100.csv") else "results/raw_results.csv"
    df = pd.read_csv(csv_path)
    cbba_df = df[df["method"] == "cbba"]

    mean_conf_benign = cbba_df[cbba_df["comm_regime"] == "benign"]["total_conflicts"].mean()
    mean_conf_lossy = cbba_df[cbba_df["comm_regime"] == "lossy"]["total_conflicts"].mean()
    assert mean_conf_lossy > mean_conf_benign, "Conflicts must increase under lossy comms due to lack of coordination"

    mean_dup_benign = cbba_df[cbba_df["comm_regime"] == "benign"]["duplicated_distance"].mean()
    mean_dup_lossy = cbba_df[cbba_df["comm_regime"] == "lossy"]["duplicated_distance"].mean()
    assert mean_dup_lossy > mean_dup_benign, "Duplicated distance must increase under lossy comms"

    mean_makespan_benign = cbba_df[cbba_df["comm_regime"] == "benign"]["makespan"].mean()
    mean_makespan_lossy = cbba_df[cbba_df["comm_regime"] == "lossy"]["makespan"].mean()
    assert mean_makespan_benign > mean_makespan_lossy, "Makespan must be higher in benign comms due to churn/thrashing"
