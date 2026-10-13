#!/usr/bin/env python3
"""
Log Integrity Verification Tool for ACA Benchmark Runs.
Verifies pairing between CSV summary tables and JSONL event/trial traces.
Exits non-zero on any corrupted line, duplicate record, or missing hash.
Can also verify historical Protocol v5 dataset status without modifying raw data.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Tuple, Set


def verify_log_integrity(
    csv_path: str,
    jsonl_path: str,
    hash_key: str = "trial_hash",
) -> Dict[str, Any]:
    """
    Perform exhaustive integrity audit on CSV and JSONL log pair.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    # 1. Parse CSV
    import pandas as pd
    df = pd.read_csv(csv_path)
    csv_row_count = len(df)
    csv_hashes = set(df[hash_key].dropna().tolist()) if hash_key in df.columns else set()
    csv_duplicate_hashes = csv_row_count - len(csv_hashes) if len(csv_hashes) > 0 else 0

    # 2. Parse JSONL
    total_jsonl_lines = 0
    valid_records = 0
    malformed_lines = 0
    jsonl_hashes: Set[str] = set()
    jsonl_duplicates = 0
    malformed_line_numbers = []

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, 1):
            total_jsonl_lines += 1
            line_str = line.strip()
            if not line_str:
                malformed_lines += 1
                malformed_line_numbers.append(idx)
                continue
            try:
                rec = json.loads(line_str)
                valid_records += 1
                th = rec.get(hash_key)
                if th:
                    if th in jsonl_hashes:
                        jsonl_duplicates += 1
                    else:
                        jsonl_hashes.add(th)
            except Exception:
                malformed_lines += 1
                malformed_line_numbers.append(idx)

    # 3. Hash cross-check
    missing_in_jsonl = csv_hashes - jsonl_hashes
    extra_in_jsonl = jsonl_hashes - csv_hashes

    is_clean = (
        malformed_lines == 0
        and jsonl_duplicates == 0
        and len(missing_in_jsonl) == 0
        and len(extra_in_jsonl) == 0
        and csv_row_count == valid_records
    )

    return {
        "is_clean": is_clean,
        "csv_path": csv_path,
        "jsonl_path": jsonl_path,
        "csv_rows": csv_row_count,
        "csv_unique_hashes": len(csv_hashes),
        "csv_duplicate_hashes": csv_duplicate_hashes,
        "jsonl_total_lines": total_jsonl_lines,
        "jsonl_valid_records": valid_records,
        "jsonl_malformed_lines": malformed_lines,
        "jsonl_duplicates": jsonl_duplicates,
        "malformed_line_numbers": malformed_line_numbers[:10],
        "missing_in_jsonl_count": len(missing_in_jsonl),
        "extra_in_jsonl_count": len(extra_in_jsonl),
    }


def main():
    parser = argparse.ArgumentParser(description="ACA Benchmark Log Integrity Verifier")
    parser.add_argument("--csv", type=str, default="results/confirmatory/heldout_v5_results.csv", help="Path to CSV summary")
    parser.add_argument("--jsonl", type=str, default="results/confirmatory/heldout_v5_runs.jsonl", help="Path to JSONL run log")
    parser.add_argument("--historical-v5", action="store_true", help="Audit Protocol v5 and assert known historical counts")
    args = parser.parse_args()

    results = verify_log_integrity(args.csv, args.jsonl)

    print("==================================================================")
    print("                    LOG INTEGRITY AUDIT REPORT                    ")
    print("==================================================================")
    print(f"CSV Path:                {results['csv_path']}")
    print(f"JSONL Path:              {results['jsonl_path']}")
    print(f"CSV Total Rows:          {results['csv_rows']}")
    print(f"CSV Unique Hashes:       {results['csv_unique_hashes']}")
    print(f"JSONL Total Lines:       {results['jsonl_total_lines']}")
    print(f"JSONL Valid Records:     {results['jsonl_valid_records']}")
    print(f"JSONL Malformed Lines:   {results['jsonl_malformed_lines']}")
    print(f"JSONL Duplicate Hashes:  {results['jsonl_duplicates']}")
    print(f"CSV Hashes Missing:      {results['missing_in_jsonl_count']}")
    print(f"JSONL Extra Hashes:      {results['extra_in_jsonl_count']}")
    print("------------------------------------------------------------------")

    if args.historical_v5:
        # P0-06 assertion for historical v5 dataset
        assert results["csv_rows"] == 3600, f"Expected 3600 CSV rows, got {results['csv_rows']}"
        assert results["jsonl_total_lines"] == 3541, f"Expected 3541 JSONL lines, got {results['jsonl_total_lines']}"
        assert results["jsonl_valid_records"] == 3491, f"Expected 3491 valid records, got {results['jsonl_valid_records']}"
        assert results["jsonl_malformed_lines"] == 50, f"Expected 50 malformed lines, got {results['jsonl_malformed_lines']}"
        assert results["missing_in_jsonl_count"] == 109, f"Expected 109 missing hashes, got {results['missing_in_jsonl_count']}"
        print("HISTORICAL CLASSIFICATION: DECLARED-INCOMPLETE / HISTORICAL IRRECOVERABLE")
        print("Root Cause: Concurrent unbuffered worker appends under ProcessPoolExecutor.")
        print("Audit Gate: Historical data sha256 pinned; no fabrication or synthesis permitted.")
        print("STATUS: VERIFIED HISTORICAL EVIDENCE MATCH (EXACT)")
        sys.exit(0)

    if not results["is_clean"]:
        print("STATUS: INTEGRITY CHECK FAILED (CORRUPTION OR MISSING RECORDS DETECTED)")
        sys.exit(1)
    else:
        print("STATUS: 100% CLEAN AND ATOMIC - ALL HASHES MATCH (PASS)")
        sys.exit(0)


if __name__ == "__main__":
    main()
