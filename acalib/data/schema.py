"""
Strict Schema and Key Validation for Experimental Trial Rows and Datasets.
Enforces type safety, finite numerical values, canonical domain labels,
and distinct definitions for instance keys and pairing keys.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Set
import math
import numpy as np
import pandas as pd


ALLOWED_STATUSES = {"COMPLETED", "FAILED", "TIMEOUT"}

ALLOWED_METHODS = {
    "aca",
    "aca_depth_0",
    "aca_depth_2",
    "aca_no_inference",
    "aca_no_margin",
    "cbba",
    "cbba_lr",
    "cbba_partial",
    "cbba_partial_lr",
    "ssi",
    "ssi_lr",
    "ctp_replan",
    "implicit",
    "clairvoyant_greedy",
    "foresight_opt",
    "aca_kappa_0",
    "aca_kappa_0.1",
    "aca_kappa_0.25",
    "aca_kappa_0.5",
    "aca_kappa_1",
    "aca_kappa_2",
    "pessimistic",
    "oracle",
    "cc_cbba",
}

ALLOWED_ADVERSARIES = {
    "theta_1_stochastic",
    "theta_2_reactive",
    "theta_3_budgeted_interdiction",
    "theta_4_cyclic_patrol",
    "theta_5_real_trace_replay",
    "theta_6_switching",
}

ALLOWED_FAMILIES = {
    "warehouse_movingai",
    "road_osmnx",
    "rgg",
    "warehouse",
    "er",
    "grid",
}

class TrialValidationError(ValueError):
    """Raised when a trial row or dataframe fails strict schema validation."""
    pass


REQUIRED_COLUMNS = [
    "graph_family", "adversary", "comm_regime", "method", "seed",
    "n_robots", "n_tasks", "status", "completion_rate_pct"
]

REQUIRED_NUMERIC_COLS = {
    "completion_rate_pct": (0.0, 100.0),
    "net_welfare": (-100000.0, 100000.0),
    "distinct_conflicts": (0.0, 10000.0),
    "total_conflicts": (0.0, 100000.0),
    "total_messages": (0.0, 1000000.0),
    "mean_tick_runtime_ms": (0.0, 60000.0),
    "n_robots": (1, 100),
    "n_tasks": (1, 500),
    "seed": (0, 1000000),
}


def validate_trial_row(row: Dict[str, Any]) -> None:
    """Validate a single trial row dictionary against schema rules."""
    for col in REQUIRED_COLUMNS:
        if col not in row:
            raise TrialValidationError(f"Missing required column: '{col}'")

    status = row.get("status")
    if status not in ALLOWED_STATUSES:
        raise TrialValidationError(f"Invalid status: '{status}'. Allowed: {ALLOWED_STATUSES}")

    method = row.get("method")
    if method not in ALLOWED_METHODS:
        raise TrialValidationError(f"Invalid method: '{method}'. Allowed: {ALLOWED_METHODS}")

    for col, (min_v, max_v) in REQUIRED_NUMERIC_COLS.items():
        if col in row:
            val = row[col]
            if val is None or not (isinstance(val, (int, float, np.number)) and np.isfinite(val)):
                raise TrialValidationError(f"Column '{col}' must be non-finite/valid number, got {val}")
            if not (min_v <= float(val) <= max_v):
                raise TrialValidationError(f"Column '{col}' value {val} out of valid range [{min_v}, {max_v}]")


def get_independent_instance_key(row: Any) -> Tuple[str, int, int, int]:
    """
    Independent Experimental Unit Key: (graph_family, seed, n_robots, n_tasks).
    Adversary profiles and communication regimes are conditions evaluated on this unit.
    """
    if isinstance(row, dict):
        return (
            str(row.get("graph_family")),
            int(row.get("seed", 0)),
            int(row.get("n_robots", 4)),
            int(row.get("n_tasks", 15)),
        )
    return (
        str(row["graph_family"]),
        int(row["seed"]),
        int(row["n_robots"]),
        int(row["n_tasks"]),
    )


def get_pairing_key(row: Any) -> Tuple[str, str, str, int, int, int]:
    """
    Exact Match Pairing Key for Direct Baseline Comparisons:
    (graph_family, adversary, comm_regime, seed, n_robots, n_tasks).
    Two methods are paired if and only if they share this exact 6-tuple key.
    """
    if isinstance(row, dict):
        return (
            str(row.get("graph_family")),
            str(row.get("adversary")),
            str(row.get("comm_regime")),
            int(row.get("seed", 0)),
            int(row.get("n_robots", 4)),
            int(row.get("n_tasks", 15)),
        )
    return (
        str(row["graph_family"]),
        str(row["adversary"]),
        str(row["comm_regime"]),
        int(row["seed"]),
        int(row["n_robots"]),
        int(row["n_tasks"]),
    )


def get_unique_trial_key(row: Any) -> Tuple[str, str, str, str, int, int, int]:
    """
    Unique Trial Key: (graph_family, adversary, comm_regime, method, seed, n_robots, n_tasks).
    Every valid experimental execution row must have a unique trial key.
    """
    if isinstance(row, dict):
        return (
            str(row.get("graph_family")),
            str(row.get("adversary")),
            str(row.get("comm_regime")),
            str(row.get("method")),
            int(row.get("seed", 0)),
            int(row.get("n_robots", 4)),
            int(row.get("n_tasks", 15)),
        )
    return (
        str(row["graph_family"]),
        str(row["adversary"]),
        str(row["comm_regime"]),
        str(row["method"]),
        int(row["seed"]),
        int(row["n_robots"]),
        int(row["n_tasks"]),
    )


def validate_dataframe(df: pd.DataFrame, strict_status: bool = False) -> Tuple[bool, List[str]]:
    """
    Validates experimental DataFrame against strict schema requirements:
    - Required columns present
    - No NaN/Inf in numerical columns
    - Domain values belong to allowed sets
    - No duplicate trial keys
    - Retains failed trials (does not silently drop)
    """
    errors = []

    required_cols = [
        "graph_family", "adversary", "comm_regime", "method", "seed",
        "n_robots", "n_tasks", "status", "completion_rate_pct", "net_welfare"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required schema columns: {missing_cols}")
        return False, errors

    # Check labels
    bad_statuses = set(df["status"].dropna().unique()) - ALLOWED_STATUSES
    if bad_statuses:
        errors.append(f"Invalid status values found: {bad_statuses}")

    bad_methods = set(df["method"].dropna().unique()) - ALLOWED_METHODS
    if bad_methods:
        errors.append(f"Invalid method values found: {bad_methods}")

    bad_advs = set(df["adversary"].dropna().unique()) - ALLOWED_ADVERSARIES
    if bad_advs:
        errors.append(f"Invalid adversary values found: {bad_advs}")

    bad_fams = set(df["graph_family"].dropna().unique()) - ALLOWED_FAMILIES
    if bad_fams:
        errors.append(f"Invalid graph_family values found: {bad_fams}")

    # Check finite numbers and ranges
    for col, (min_v, max_v) in REQUIRED_NUMERIC_COLS.items():
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce")
            nan_count = vals.isna().sum()
            # If failed trials exist, metrics may be NaN or 0; check status
            if nan_count > 0:
                completed_nans = vals[df["status"] == "COMPLETED"].isna().sum()
                if completed_nans > 0:
                    errors.append(f"Column '{col}' contains {completed_nans} non-finite/NaN values in COMPLETED trials")

    # Check duplicate trial keys (7-tuple)
    dup_mask = df.duplicated(
        subset=["graph_family", "adversary", "comm_regime", "method", "seed", "n_robots", "n_tasks"],
        keep=False
    )
    if dup_mask.sum() > 0:
        dup_count = dup_mask.sum()
        errors.append(f"Detected {dup_count} duplicate trial records for 7-tuple unique trial keys")

    return (len(errors) == 0), errors


def count_instances_and_trials(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns separate counts for raw trial rows and unique independent instances.
    """
    raw_trials = len(df)
    inst_keys = set(df.apply(get_independent_instance_key, axis=1))
    pairing_keys = set(df.apply(get_pairing_key, axis=1))
    methods = df["method"].unique().tolist() if "method" in df.columns else []

    return {
        "raw_trial_rows": raw_trials,
        "unique_independent_instances": len(inst_keys),
        "unique_pairing_conditions": len(pairing_keys),
        "methods_evaluated": methods,
        "completed_trials": int((df["status"] == "COMPLETED").sum()) if "status" in df.columns else raw_trials,
        "failed_trials": int((df["status"] != "COMPLETED").sum()) if "status" in df.columns else 0,
    }


def validate_results_dataframe(df: pd.DataFrame, strict: bool = True) -> None:
    """Convenience validator for results DataFrame that raises TrialValidationError on failure."""
    is_valid, errors = validate_dataframe(df, strict_status=strict)
    if not is_valid:
        raise TrialValidationError("; ".join(errors))


def check_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Return subset of rows that are duplicates on the 7-tuple unique trial key."""
    subset = ["graph_family", "adversary", "comm_regime", "method", "seed", "n_robots", "n_tasks"]
    cols = [c for c in subset if c in df.columns]
    return df[df.duplicated(subset=cols, keep=False)]

