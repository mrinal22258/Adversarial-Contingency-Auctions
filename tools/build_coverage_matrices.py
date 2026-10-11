"""
Build complete coverage matrices and analyze primary vs exploratory population.
"""

import os
import json
import pandas as pd
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIT_DIR = os.path.join(REPO_ROOT, "audit")
RAW_CSV = os.path.join(REPO_ROOT, "results", "raw_results.csv")


def build_matrices():
    df = pd.read_csv(RAW_CSV)
    os.makedirs(AUDIT_DIR, exist_ok=True)

    # 1. Full trial coverage matrix: method x (family, adversary, comm_regime, n_robots, n_tasks)
    dim_cols = ["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks"]
    ct_trials = pd.crosstab(
        df["method"],
        [df[c] for c in dim_cols],
        rownames=["method"],
        colnames=dim_cols
    )
    trials_csv = os.path.join(AUDIT_DIR, "coverage_matrix_trials.csv")
    ct_trials.to_csv(trials_csv)
    print(f"Wrote full trial coverage matrix ({ct_trials.shape}) to {trials_csv}")

    # 2. Instance coverage matrix (unique seeds per cell)
    inst_pivot = df.pivot_table(
        index="method",
        columns=["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks"],
        values="seed",
        aggfunc="nunique",
        fill_value=0
    )
    inst_csv = os.path.join(AUDIT_DIR, "coverage_matrix_instances.csv")
    inst_pivot.to_csv(inst_csv)
    print(f"Wrote instance coverage matrix ({inst_pivot.shape}) to {inst_csv}")

    # 3. Method comparability summary
    methods = sorted(df["method"].unique())
    aca_df = df[df["method"] == "aca"]
    aca_keys = set(zip(aca_df["graph_family"], aca_df["adversary"], aca_df["comm_regime"], aca_df["n_robots"], aca_df["n_tasks"], aca_df["seed"]))

    comparability = []
    for m in methods:
        m_df = df[df["method"] == m]
        m_keys = set(zip(m_df["graph_family"], m_df["adversary"], m_df["comm_regime"], m_df["n_robots"], m_df["n_tasks"], m_df["seed"]))
        overlap = aca_keys.intersection(m_keys)
        aca_only = aca_keys - m_keys
        m_only = m_keys - aca_keys
        comparability.append({
            "method": m,
            "total_trials": len(m_df),
            "paired_with_aca": len(overlap),
            "aca_unmatched": len(aca_only),
            "method_unmatched": len(m_only),
            "is_fully_paired": (len(overlap) == len(m_df)),
            "coverage_pct_vs_aca": round(len(overlap) / len(aca_keys) * 100, 2)
        })

    comp_df = pd.DataFrame(comparability)
    comp_csv = os.path.join(AUDIT_DIR, "method_comparability.csv")
    comp_df.to_csv(comp_csv, index=False)
    print(f"Wrote method comparability summary to {comp_csv}")
    print("\nMethod Comparability Overview:")
    print(comp_df.to_string(index=False))


if __name__ == "__main__":
    build_matrices()
