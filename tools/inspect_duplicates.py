"""
Inspect duplicate keys in raw_results.csv and runs.jsonl.
"""

import os
import pandas as pd
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_CSV = os.path.join(REPO_ROOT, "results", "raw_results.csv")

df = pd.read_csv(RAW_CSV)
print(f"Total rows in raw_results.csv: {len(df)}")

keys_5 = ["graph_family", "adversary", "comm_regime", "method", "seed"]
dup_5 = df.duplicated(subset=keys_5, keep=False)
print(f"Rows matching duplicate 5-tuple (graph_family, adversary, comm_regime, method, seed): {dup_5.sum()}")

if dup_5.sum() > 0:
    dup_df = df[dup_5][keys_5 + ["n_robots", "n_tasks", "status"]].sort_values(keys_5)
    print("\nSample duplicate rows with 5-tuple:")
    print(dup_df.head(20).to_string())

# What about 7-tuple including scale (n_robots, n_tasks)?
keys_7 = ["graph_family", "adversary", "comm_regime", "method", "seed", "n_robots", "n_tasks"]
dup_7 = df.duplicated(subset=keys_7, keep=False)
print(f"\nRows matching duplicate 7-tuple (+ n_robots, n_tasks): {dup_7.sum()}")

if dup_7.sum() > 0:
    dup7_df = df[dup_7][keys_7 + ["status"]].sort_values(keys_7)
    print("\nSample duplicate rows with 7-tuple:")
    print(dup7_df.head(20).to_string())
