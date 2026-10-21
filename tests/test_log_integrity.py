"""
Regression and concurrency verification tests for JSONL logging and log integrity (P0-06 / Finding F).
"""

import os
import json
import pytest
import tempfile
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from tools.verify_log_integrity import verify_log_integrity
from acalib.data.logger import AtomicJsonlWriter, SingleWriterJsonlLogger


def test_historical_v5_verification_and_counts():
    """Verify that verify_log_integrity matches exact historical v5 counts and classifies as DECLARED-INCOMPLETE."""
    csv_path = "results/confirmatory/heldout_v5_results.csv"
    jsonl_path = "results/confirmatory/heldout_v5_runs.jsonl"
    
    res = verify_log_integrity(csv_path, jsonl_path)
    
    assert res["csv_rows"] == 3600
    assert res["jsonl_total_lines"] == 3541
    assert res["jsonl_valid_records"] == 3491
    assert res["jsonl_malformed_lines"] == 50
    assert res["missing_in_jsonl_count"] == 109
    assert res["is_clean"] is False, "Historical v5 must NOT be reported as clean!"


def test_clean_fixture_passes_verification():
    """Verify clean log fixture returns is_clean == True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_p = os.path.join(tmpdir, "test.csv")
        jsonl_p = os.path.join(tmpdir, "test.jsonl")

        records = [
            {"trial_hash": f"hash_{i}", "metric": float(i)}
            for i in range(100)
        ]
        pd.DataFrame(records).to_csv(csv_p, index=False)
        with open(jsonl_p, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        res = verify_log_integrity(csv_p, jsonl_p)
        assert res["is_clean"] is True
        assert res["csv_rows"] == 100
        assert res["jsonl_valid_records"] == 100
        assert res["jsonl_malformed_lines"] == 0
        assert res["missing_in_jsonl_count"] == 0


def test_corrupted_fixture_fails_verification():
    """Verify corrupted JSONL file is caught and exits with is_clean == False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_p = os.path.join(tmpdir, "test.csv")
        jsonl_p = os.path.join(tmpdir, "test.jsonl")

        records = [
            {"trial_hash": f"hash_{i}", "metric": float(i)}
            for i in range(20)
        ]
        pd.DataFrame(records).to_csv(csv_p, index=False)
        with open(jsonl_p, "w", encoding="utf-8") as f:
            for r in records[:10]:
                f.write(json.dumps(r) + "\n")
            # Injected truncated tail (reproducing the v5 bug pattern)
            f.write('{"timestamp": "2026-10-11T07:16:49Z"}\n')
            f.write('truncated_non_json_line\n')

        res = verify_log_integrity(csv_p, jsonl_p)
        assert res["is_clean"] is False
        assert res["jsonl_malformed_lines"] >= 1


def _worker_atomic_write(args):
    filepath, batch_id, count = args
    writer = AtomicJsonlWriter(filepath)
    for i in range(count):
        rec = {
            "trial_hash": f"h_{batch_id}_{i}",
            "batch": batch_id,
            "val": i * 1.5,
            "data": "x" * 200,
        }
        writer.append(rec)


def test_atomic_writer_concurrency():
    """Stress test: concurrent workers writing to the same file via AtomicJsonlWriter produce 0 corrupt lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_p = os.path.join(tmpdir, "concurrent.jsonl")
        csv_p = os.path.join(tmpdir, "concurrent.csv")

        n_workers = 8
        records_per_worker = 50
        total_records = n_workers * records_per_worker

        # Launch concurrent writes across processes
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            tasks = [(jsonl_p, w, records_per_worker) for w in range(n_workers)]
            list(executor.map(_worker_atomic_write, tasks))

        # Check all lines in jsonl_p
        valid_count = 0
        all_hashes = []
        with open(jsonl_p, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line.strip())
                all_hashes.append(rec["trial_hash"])
                valid_count += 1

        assert valid_count == total_records, f"Expected {total_records} valid lines, got {valid_count}"
        assert len(set(all_hashes)) == total_records, "All trial hashes should be unique"


def test_missing_trial_hash_fails_closed():
    """Verify audit fix: CSV/JSONL pairs lacking trial_hash fail closed in both strict and non-strict modes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_p = os.path.join(tmpdir, "no_hashes.csv")
        jsonl_p = os.path.join(tmpdir, "no_hashes.jsonl")

        # Create CSV and JSONL without trial_hash column/field
        records = [{"metric_a": 10.0, "metric_b": 20.0} for _ in range(10)]
        pd.DataFrame(records).to_csv(csv_p, index=False)
        with open(jsonl_p, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        # Non-strict check MUST return is_clean == False
        res = verify_log_integrity(csv_p, jsonl_p, strict=False)
        assert res["is_clean"] is False, "Must fail closed (is_clean=False) when trial_hash is absent"
        assert res["csv_unique_hashes"] == 0

        # Strict check MUST raise ValueError
        with pytest.raises(ValueError, match="Strict validation failed"):
            verify_log_integrity(csv_p, jsonl_p, strict=True)

