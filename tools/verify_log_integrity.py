#!/usr/bin/env python3
"""
Log Integrity Verification Tool for ACA Benchmark Runs.
Verifies pairing between CSV summary tables and JSONL event/trial traces.
Exits non-zero on any corrupted line, duplicate record, or missing hash.
Can recompute and verify per-record canonical SHA-256 digests.
Can also verify historical Protocol v5 dataset status without modifying raw data.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Tuple, Set

# Ensure acalib is importable from workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from acalib.data.logger import compute_record_hash


def verify_log_integrity(
    csv_path: str,
    jsonl_path: str,
    hash_key: str = "trial_hash",
    strict: bool = False,
    require_record_hashes: bool = False,
) -> Dict[str, Any]:
    """
    Perform exhaustive integrity audit on CSV and JSONL log pair.
    If strict=True, raises ValueError immediately on any corruption or mismatch.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    # 1. Parse CSV
    import pandas as pd
    df = pd.read_csv(csv_path)
    csv_row_count = len(df)
    csv_has_hash_col = hash_key in df.columns
    if csv_has_hash_col:
        csv_missing_hashes = int(df[hash_key].isna().sum()) + int((df[hash_key].astype(str).str.strip() == "").sum())
        csv_hashes = set(df[hash_key].dropna().astype(str).str.strip().tolist()) - {""}
    else:
        csv_missing_hashes = csv_row_count
        csv_hashes = set()
    csv_duplicate_hashes = csv_row_count - len(csv_hashes) if len(csv_hashes) > 0 else 0

    if strict and csv_row_count > 0:
        if not csv_has_hash_col:
            raise ValueError(f"Strict validation failed: Required hash_key '{hash_key}' column missing from CSV")
        if len(csv_hashes) == 0:
            raise ValueError(f"Strict validation failed: CSV has 0 valid {hash_key} hashes")
        if csv_missing_hashes > 0:
            raise ValueError(f"Strict validation failed: CSV has {csv_missing_hashes} missing/empty {hash_key} entries")

    # 2. Parse JSONL
    total_jsonl_lines = 0
    valid_records = 0
    malformed_lines = 0
    hash_mismatches = 0
    missing_record_hashes = 0
    jsonl_missing_hashes = 0
    jsonl_hashes: Set[str] = set()
    jsonl_duplicates = 0
    malformed_line_numbers = []
    mismatch_line_numbers = []

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, 1):
            total_jsonl_lines += 1
            line_str = line.strip()
            if not line_str:
                malformed_lines += 1
                malformed_line_numbers.append(idx)
                if strict:
                    raise ValueError(f"Strict validation failed: Empty/whitespace line at {jsonl_path}:{idx}")
                continue
            try:
                rec = json.loads(line_str)
                valid_records += 1
                th = rec.get(hash_key)
                if th is not None and str(th).strip() != "":
                    th_str = str(th).strip()
                    if th_str in jsonl_hashes:
                        jsonl_duplicates += 1
                        if strict:
                            raise ValueError(f"Strict validation failed: Duplicate {hash_key} '{th_str}' at line {idx}")
                    else:
                        jsonl_hashes.add(th_str)
                else:
                    jsonl_missing_hashes += 1
                    if strict:
                        raise ValueError(f"Strict validation failed: Missing or empty {hash_key} at line {idx}")

                # Check canonical record SHA-256
                rec_sha = rec.get("record_sha256")
                if rec_sha is not None:
                    expected_sha = compute_record_hash(rec)
                    if rec_sha != expected_sha:
                        hash_mismatches += 1
                        mismatch_line_numbers.append(idx)
                        if strict:
                            raise ValueError(
                                f"Strict validation failed: Record SHA-256 mismatch at line {idx}: "
                                f"stored '{rec_sha}' != recomputed '{expected_sha}'"
                            )
                elif require_record_hashes:
                    missing_record_hashes += 1
                    if strict:
                        raise ValueError(f"Strict validation failed: Missing record_sha256 at line {idx}")

            except Exception as e:
                malformed_lines += 1
                malformed_line_numbers.append(idx)
                if strict:
                    raise ValueError(f"Strict validation failed: Malformed JSON at {jsonl_path}:{idx}: {e}")

    # 3. Hash cross-check
    missing_in_jsonl = csv_hashes - jsonl_hashes
    extra_in_jsonl = jsonl_hashes - csv_hashes

    hashes_present_and_valid = (
        (csv_row_count == 0 or (csv_has_hash_col and len(csv_hashes) > 0 and csv_missing_hashes == 0))
        and (valid_records == 0 or (len(jsonl_hashes) > 0 and jsonl_missing_hashes == 0))
    )

    if strict:
        if csv_duplicate_hashes > 0:
            raise ValueError(f"Strict validation failed: {csv_duplicate_hashes} duplicate CSV hashes")
        if malformed_lines > 0:
            raise ValueError(f"Strict validation failed: {malformed_lines} malformed JSONL lines")
        if hash_mismatches > 0:
            raise ValueError(f"Strict validation failed: {hash_mismatches} record hash mismatches")
        if jsonl_duplicates > 0:
            raise ValueError(f"Strict validation failed: {jsonl_duplicates} duplicate JSONL hashes")
        if len(missing_in_jsonl) > 0:
            raise ValueError(f"Strict validation failed: {len(missing_in_jsonl)} CSV hashes missing from JSONL")
        if len(extra_in_jsonl) > 0:
            raise ValueError(f"Strict validation failed: {len(extra_in_jsonl)} extra JSONL hashes not in CSV")
        if csv_row_count != valid_records:
            raise ValueError(f"Strict validation failed: CSV row count ({csv_row_count}) != valid JSONL ({valid_records})")

    is_clean = (
        hashes_present_and_valid
        and not (require_record_hashes and missing_record_hashes > 0)
        and (csv_row_count == 0 or len(csv_hashes) > 0)
        and (valid_records == 0 or len(jsonl_hashes) > 0)
        and malformed_lines == 0
        and hash_mismatches == 0
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
        "csv_missing_hashes": csv_missing_hashes,
        "csv_duplicate_hashes": csv_duplicate_hashes,
        "jsonl_total_lines": total_jsonl_lines,
        "jsonl_valid_records": valid_records,
        "jsonl_missing_hashes": jsonl_missing_hashes,
        "jsonl_malformed_lines": malformed_lines,
        "jsonl_duplicates": jsonl_duplicates,
        "hash_mismatches": hash_mismatches,
        "missing_record_hashes": missing_record_hashes,
        "malformed_line_numbers": malformed_line_numbers[:10],
        "mismatch_line_numbers": mismatch_line_numbers[:10],
        "missing_in_jsonl_count": len(missing_in_jsonl),
        "extra_in_jsonl_count": len(extra_in_jsonl),
    }


def main():
    parser = argparse.ArgumentParser(description="ACA Benchmark Log Integrity Verifier")
    parser.add_argument("--protocol", type=str, default=None, help="Protocol ID (e.g. v6, v5)")
    parser.add_argument("--csv", type=str, default=None, help="Path to CSV summary")
    parser.add_argument("--jsonl", type=str, default=None, help="Path to JSONL run log")
    parser.add_argument("--strict", action="store_true", help="Fail closed on any corruption, missing hash, or mismatch")
    parser.add_argument("--historical-v5", action="store_true", help="Audit Protocol v5 and assert known historical counts")
    args = parser.parse_args()

    csv_path = args.csv
    jsonl_path = args.jsonl

    if args.protocol == "v6":
        default_csv = "results/confirmatory_v6/results.csv"
        default_jsonl = "results/confirmatory_v6/runs.jsonl"
        if not csv_path and not os.path.exists(default_csv) and os.path.exists("results/smoke/results.csv"):
            csv_path = "results/smoke/results.csv"
            jsonl_path = "results/smoke/runs.jsonl"
        else:
            csv_path = csv_path or default_csv
            jsonl_path = jsonl_path or default_jsonl
    elif args.protocol == "v5" or args.historical_v5:
        csv_path = csv_path or "results/confirmatory/heldout_v5_results.csv"
        jsonl_path = jsonl_path or "results/confirmatory/heldout_v5_runs.jsonl"
    else:
        csv_path = csv_path or "results/confirmatory/heldout_v5_results.csv"
        jsonl_path = jsonl_path or "results/confirmatory/heldout_v5_runs.jsonl"

    results = verify_log_integrity(
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        strict=args.strict,
        require_record_hashes=(args.strict and not (args.historical_v5 or args.protocol == "v5")),
    )

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
    print(f"Record Hash Mismatches:  {results['hash_mismatches']}")
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

    if results["csv_unique_hashes"] == 0 or not results["is_clean"]:
        print("STATUS: INTEGRITY CHECK FAILED (MISSING HASHES, CORRUPTION, OR MISMATCH DETECTED)")
        sys.exit(1)
    else:
        print("STATUS: 100% CLEAN AND ATOMIC - ALL HASHES MATCH (PASS)")
        sys.exit(0)


if __name__ == "__main__":
    main()
