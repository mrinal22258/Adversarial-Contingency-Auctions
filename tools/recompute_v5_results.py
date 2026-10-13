"""Direct recomputation of raw v5 outputs and comparison against reported table."""
import os
import sys
import pandas as pd
import numpy as np

csv_path = "results/confirmatory/heldout_v5_results.csv"
df = pd.read_csv(csv_path)

print(f"Loaded {csv_path}: {len(df)} rows, columns: {list(df.columns)}")
print("Unique methods in v5:", df["method"].unique())
print("Value counts per method:")
print(df["method"].value_counts())

# The target table from prompt:
reported_table = {
    "aca": {"completion": 92.400, "welfare": 937.437, "conflicts": 39.664, "messages": 218.000, "tick_ms": 14.886},
    "aca_plus": {"completion": 92.444, "welfare": 936.258, "conflicts": 38.602, "messages": 220.569, "tick_ms": 15.196},
    "aca_adaptive": {"completion": 91.289, "welfare": 919.669, "conflicts": 39.042, "messages": 232.373, "tick_ms": 14.543},
    "aca_no_margin": {"completion": 93.481, "welfare": 938.837, "conflicts": 49.933, "messages": 212.880, "tick_ms": 8.267},
    "cbba_lr": {"completion": 94.667, "welfare": 958.919, "conflicts": 25.484, "messages": 243.493, "tick_ms": 3.425},
    "cbba_partial_lr": {"completion": 93.393, "welfare": 953.355, "conflicts": 40.551, "messages": 239.162, "tick_ms": 3.479},
    "ctp_replan": {"completion": 92.281, "welfare": 539.882, "conflicts": 0.0, "messages": 56.107, "tick_ms": 3.161},
    "ssi_lr": {"completion": 80.489, "welfare": 666.021, "conflicts": 0.0, "messages": 145.958, "tick_ms": 3.385},
}

# Determine matching columns
comp_col = "completion_rate_pct" if "completion_rate_pct" in df.columns else [c for c in df.columns if "comp" in c][0]
welf_col = "net_welfare" if "net_welfare" in df.columns else [c for c in df.columns if "welf" in c][0]
conf_col = "total_conflicts" if "total_conflicts" in df.columns else [c for c in df.columns if "conf" in c][0]
msg_col = "total_messages" if "total_messages" in df.columns else [c for c in df.columns if "msg" in c or "message" in c][0]
tick_col = "mean_tick_runtime_ms" if "mean_tick_runtime_ms" in df.columns else [c for c in df.columns if "tick" in c or "runtime" in c][0]

print(f"\nUsing columns: comp={comp_col}, welf={welf_col}, conf={conf_col}, msg={msg_col}, tick={tick_col}\n")

print(f"{'Method':<15} | {'Metric':<12} | {'Reported':>10} | {'Recomputed':>10} | {'Diff':>10} | Match?")
print("-" * 75)

for m, rep in reported_table.items():
    sub = df[df["method"] == m]
    if len(sub) == 0:
        print(f"WARNING: Method {m} not found in v5!")
        continue
    
    recomp_comp = sub[comp_col].mean()
    recomp_welf = sub[welf_col].mean()
    recomp_conf = sub[conf_col].mean()
    recomp_msg = sub[msg_col].mean()
    recomp_tick = sub[tick_col].mean()
    
    metrics = [
        ("completion", rep["completion"], recomp_comp),
        ("welfare", rep["welfare"], recomp_welf),
        ("conflicts", rep["conflicts"], recomp_conf),
        ("messages", rep["messages"], recomp_msg),
        ("tick_ms", rep["tick_ms"], recomp_tick),
    ]
    
    for met_name, r_val, c_val in metrics:
        diff = c_val - r_val
        match = "YES" if abs(diff) < 0.005 else f"MISMATCH ({diff:+.4f})"
        print(f"{m:<15} | {met_name:<12} | {r_val:>10.3f} | {c_val:>10.3f} | {diff:>+10.4f} | {match}")
