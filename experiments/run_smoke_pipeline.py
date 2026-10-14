#!/usr/bin/env python3
"""
Smoke Test Runner: Executes End-to-End Pipeline (Run -> Verify -> Build -> Ledger).
Uses 2 development seeds (40484, 40506) on a minimal grid topology.
Saves execution logs to results/smoke/smoke_pipeline.log.
"""

import os
import sys
import shutil
import subprocess
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.data.schema import validate_results_dataframe, count_instances_and_trials
from tools.verify_log_integrity import verify_log_integrity


def run_smoke_pipeline():
    smoke_dir = os.path.join(REPO_ROOT, "results", "smoke")
    os.makedirs(smoke_dir, exist_ok=True)
    log_path = os.path.join(smoke_dir, "smoke_pipeline.log")

    with open(log_path, "w", encoding="utf-8") as log_f:
        def log(msg: str):
            print(msg)
            log_f.write(msg + "\n")
            log_f.flush()

        log("==================================================================")
        log("            ACA END-TO-END SMOKE TEST PIPELINE EXECUTION          ")
        log("==================================================================")
        log("DISCLAIMER: Developmental smoke test only (2 dev seeds). NOT EVIDENCE.")
        log("Pipeline Stages: Run -> Verify -> Build -> Ledger Check")
        log("------------------------------------------------------------------")

        # 1. RUN STAGE
        log("\n[STAGE 1] RUNNING SIMULATION SWEEP (2 DEV SEEDS)...")
        run_cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "experiments", "run_sweep.py"),
            "--config", os.path.join(REPO_ROOT, "experiments", "configs", "smoke_config.yaml"),
            "--output-dir", smoke_dir,
            "--workers", "2",
        ]
        res_run = subprocess.run(run_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        log(res_run.stdout)
        if res_run.returncode != 0:
            log(f"[FAIL] Simulation runner failed:\n{res_run.stderr}")
            return False
        log("[PASS] Stage 1 (Run) completed successfully.")

        # 2. VERIFY STAGE
        log("\n[STAGE 2] VERIFYING LOG INTEGRITY AND PER-RECORD HASHES...")
        csv_path = os.path.join(smoke_dir, "results.csv")
        jsonl_path = os.path.join(smoke_dir, "runs.jsonl")
        verify_results = verify_log_integrity(
            csv_path=csv_path,
            jsonl_path=jsonl_path,
            strict=True,
            require_record_hashes=True,
        )
        log(f"CSV Rows: {verify_results['csv_rows']}")
        log(f"JSONL Valid Records: {verify_results['jsonl_valid_records']}")
        log(f"JSONL Malformed Lines: {verify_results['jsonl_malformed_lines']}")
        log(f"Record Hash Mismatches: {verify_results['hash_mismatches']}")
        if not verify_results["is_clean"]:
            log("[FAIL] Stage 2 (Verify) failed: corruption or hash mismatch detected.")
            return False
        log("[PASS] Stage 2 (Verify) passed 100% clean and atomic.")

        # 3. BUILD STAGE
        log("\n[STAGE 3] BUILDING DATA SUMMARY AND SCHEMA VALIDATION...")
        df_smoke = pd.read_csv(csv_path)
        validate_results_dataframe(df_smoke)
        counts = count_instances_and_trials(df_smoke)
        log(f"Schema validated. Trials: {counts['raw_trial_rows']}, Unique instances: {counts['unique_independent_instances']}")
        summary = df_smoke.groupby("method")[["completion_rate_pct", "total_conflicts", "net_welfare"]].mean()
        summary_str = summary.to_string()
        log("Performance Summary (Smoke Run):\n" + summary_str)
        summary.to_csv(os.path.join(smoke_dir, "smoke_summary.csv"))
        log("[PASS] Stage 3 (Build) completed successfully.")

        # 4. LEDGER STAGE
        log("\n[STAGE 4] VERIFYING CLAIM LEDGER PIPELINE INTEGRATION...")
        # Verify that smoke trials conform to claim evaluation schemas without modifying production ledgers
        required_cols = {"completion_rate_pct", "total_conflicts", "net_welfare", "trial_hash", "seed", "method"}
        missing_cols = required_cols - set(df_smoke.columns)
        if missing_cols:
            log(f"[FAIL] Missing required evaluation columns in smoke data: {missing_cols}")
            return False
        log("Smoke data structure successfully verified against claim evaluation schema.")
        log("[PASS] Stage 4 (Ledger) completed successfully.")

        log("\n==================================================================")
        log("STATUS: SMOKE PIPELINE VERIFIED END-TO-END (ALL 4 STAGES PASS)")
        log("==================================================================")

    # Write README in smoke dir
    readme_path = os.path.join(smoke_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("# Smoke Test Run Artifacts\n\n")
        f.write("> [!WARNING]\n")
        f.write("> **NOT EMPIRICAL EVIDENCE**: The data and logs in this directory were generated from a minimal pipeline smoke test using 2 development seeds (`40484`, `40506`).\n")
        f.write("> They exist solely to verify the end-to-end execution, logging, verification, and summary pipeline in accordance with Gate 5 requirements.\n")
        f.write("> They must never be cited or presented as experimental evidence for any algorithm or paper claim.\n")

    return True


if __name__ == "__main__":
    success = run_smoke_pipeline()
    sys.exit(0 if success else 1)
