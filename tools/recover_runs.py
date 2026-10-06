"""
Robust JSONL reader and recovery tool for experimental sweep runs.
Handles interleaved multi-process writes (e.g. concatenated JSON objects).
Exports clean results/runs.jsonl and results/raw_results.csv.
"""

import json
import re
import pandas as pd

def recover_records(jsonl_path="results/runs.jsonl"):
    records = []
    corrupted_count = 0
    
    with open(jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except Exception:
                corrupted_count += 1
                # Try finding all balanced json objects in line
                # Regex for json object chunks
                matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', line)
                recovered_in_line = 0
                for m in matches:
                    try:
                        rec = json.loads(m)
                        records.append(rec)
                        recovered_in_line += 1
                    except Exception:
                        pass
                if recovered_in_line == 0:
                    print(f"Warning: Could not recover line {line_num}: {line[:100]}...")

    print(f"Raw records parsed: {len(records)}")
    print(f"Corrupted lines encountered: {corrupted_count}")

    # Deduplicate by key: (graph_family, adversary, comm_regime, method, seed)
    unique_map = {}
    for r in records:
        key = (
            r.get("graph_family"),
            r.get("adversary"),
            r.get("comm_regime"),
            r.get("method"),
            r.get("seed")
        )
        # Keep the latest record for each key
        unique_map[key] = r

    unique_records = list(unique_map.values())
    print(f"Unique experimental runs: {len(unique_records)}")

    # Write clean runs.jsonl
    with open("results/runs.jsonl", "w", encoding="utf-8") as f:
        for r in unique_records:
            f.write(json.dumps(r) + "\n")
    print("Wrote clean results/runs.jsonl")

    # Export raw_results.csv
    df = pd.DataFrame(unique_records)
    df.to_csv("results/raw_results.csv", index=False)
    print(f"Exported {len(df)} records to results/raw_results.csv")
    return df

if __name__ == "__main__":
    recover_records()
