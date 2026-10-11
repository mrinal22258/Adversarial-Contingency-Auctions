"""
Comprehensive analysis of raw_results.csv, runs.jsonl, and coverage matrices.
"""

import os
import json
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
RAW_CSV = os.path.join(RESULTS_DIR, "raw_results.csv")
RUNS_JSONL = os.path.join(RESULTS_DIR, "runs.jsonl")


def analyze_data():
    df = pd.read_csv(RAW_CSV)
    print(f"Total rows in raw_results.csv: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # Method counts
    print("\n--- Rows per method ---")
    method_counts = df["method"].value_counts().to_dict()
    for m, c in sorted(method_counts.items(), key=lambda x: -x[1]):
        print(f"  {m:25s}: {c}")

    # Adversary counts
    print("\n--- Rows per adversary ---")
    adv_counts = df["adversary"].value_counts().to_dict()
    for a, c in sorted(adv_counts.items(), key=lambda x: -x[1]):
        print(f"  {a:30s}: {c}")

    # Comm regime counts
    print("\n--- Rows per comm_regime ---")
    comm_counts = df["comm_regime"].value_counts().to_dict()
    for cr, c in sorted(comm_counts.items(), key=lambda x: -x[1]):
        print(f"  {cr:30s}: {c}")

    # Graph family counts
    print("\n--- Rows per graph_family ---")
    gf_counts = df["graph_family"].value_counts().to_dict()
    for gf, c in sorted(gf_counts.items(), key=lambda x: -x[1]):
        print(f"  {gf:30s}: {c}")

    # Seeds
    seeds = sorted(df["seed"].unique())
    print(f"\nUnique seeds ({len(seeds)}): min={min(seeds)}, max={max(seeds)}")

    # Check commit and simulation_disclaimer columns
    commits = df["git_commit"].unique() if "git_commit" in df.columns else (df["commit"].unique() if "commit" in df.columns else "N/A")
    print(f"\nGit commits in CSV: {commits}")
    if "simulation_disclaimer" in df.columns:
        print(f"Disclaimers: {df['simulation_disclaimer'].value_counts().to_dict()}")

    # Cross-tab of method x comm_regime
    print("\n--- Cross-tab: method x comm_regime ---")
    ct_comm = pd.crosstab(df["method"], df["comm_regime"])
    print(ct_comm.to_string())

    # Cross-tab of method x adversary
    print("\n--- Cross-tab: method x adversary ---")
    ct_adv = pd.crosstab(df["method"], df["adversary"])
    print(ct_adv.to_string())

    # Cross-tab of adversary x comm_regime
    print("\n--- Cross-tab: adversary x comm_regime ---")
    ct_adv_comm = pd.crosstab(df["adversary"], df["comm_regime"])
    print(ct_adv_comm.to_string())

    # Cross-tab of method x graph_family
    print("\n--- Cross-tab: method x graph_family ---")
    ct_gf = pd.crosstab(df["method"], df["graph_family"])
    print(ct_gf.to_string())


def analyze_runs_jsonl():
    raw_lines = 0
    clean_parsed = 0
    corrupted_lines = 0
    multi_records = 0
    records = []

    with open(RUNS_JSONL, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            raw_lines += 1
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
                clean_parsed += 1
                records.append(rec)
            except Exception:
                corrupted_lines += 1

    print("\n--- runs.jsonl Analysis ---")
    print(f"Total lines in current runs.jsonl: {raw_lines}")
    print(f"Successfully parsed lines: {clean_parsed}")
    print(f"Corrupted lines in current file: {corrupted_lines}")

    keys = [(r.get("graph_family"), r.get("adversary"), r.get("comm_regime"), r.get("method"), r.get("seed")) for r in records]
    print(f"Total records in runs.jsonl: {len(keys)}")
    print(f"Unique keys in runs.jsonl: {len(set(keys))}")


if __name__ == "__main__":
    analyze_data()
    analyze_runs_jsonl()
