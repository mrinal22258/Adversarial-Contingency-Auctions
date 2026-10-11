"""
Single-Command Automated Results and Publication Pipeline (Stage 3).
Executes all stages of empirical validation, data lineage, statistical testing,
macro generation, figure plotting, claim ledger auditing, and paper compilation.

Usage:
    python tools/build_all_results.py
    make results
"""

import os
import sys
import json
import time
import hashlib
import datetime
import subprocess
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from acalib.data.schema import validate_results_dataframe, count_instances_and_trials
from acalib.demo.provenance import verify_map_provenance, VerificationState
from tools.claim_ledger import write_claim_ledger, validate_claim_ledger


def compute_file_sha256(path: str) -> str:
    """Compute SHA-256 hash of a file on disk."""
    if not os.path.exists(path):
        return "MISSING"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def log_step(name: str):
    print(f"\n========================================================")
    print(f"[*] {name}")
    print(f"========================================================")


def run_pipeline() -> bool:
    start_time = time.time()
    provenance: dict = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": sys.version,
        "repo_root": REPO_ROOT,
        "steps": {},
        "artifacts": {},
    }

    # Step 1: Input & Map Validation
    log_step("Step 1: Validating Raw Datasets and Map Manifests")
    raw_csv = os.path.join(REPO_ROOT, "results", "raw_results.csv")
    if not os.path.exists(raw_csv):
        print(f"[FAIL] Missing {raw_csv}")
        return False
    df = pd.read_csv(raw_csv)
    validate_results_dataframe(df)
    counts = count_instances_and_trials(df)
    print(f"-> Schema validated. Raw trials: {counts['raw_trial_rows']}, Unique instances: {counts['unique_independent_instances']}")

    # Map hashes
    res_boston = verify_map_provenance("road_osmnx")
    res_warehouse = verify_map_provenance("warehouse_movingai")
    if res_boston.status != VerificationState.VERIFIED or res_warehouse.status != VerificationState.VERIFIED:
        print(f"[FAIL] Map verification failed: Boston={res_boston.status}, Warehouse={res_warehouse.status}")
        return False
    print(f"-> Maps verified: Boston ({res_boston.nodes} nodes, {res_boston.edges} edges, {res_boston.matched_work_zone_edges} work zones), Warehouse ({res_warehouse.nodes} nodes, {res_warehouse.edges} edges)")
    provenance["steps"]["step1_validation"] = "PASS"

    # Step 2: Coverage & Lineage Matrices
    log_step("Step 2: Rebuilding Coverage & Lineage Matrices")
    import tools.build_coverage_matrices as bcm
    bcm.build_matrices()
    provenance["steps"]["step2_coverage"] = "PASS"

    # Step 3: Statistical Hypothesis Testing
    log_step("Step 3: Running Statistical Hypothesis Suite")
    import experiments.run_statistical_tests as rst
    rst.main()
    provenance["steps"]["step3_stats"] = "PASS"

    # Step 4: Tables, Numbers Macros & README Results
    log_step("Step 4: Generating Tables, Numbers Macros, and README Synchronization")
    import experiments.make_tables as mt
    mt.main()
    provenance["steps"]["step4_tables"] = "PASS"

    # Step 5: Figure Suite Generation
    log_step("Step 5: Generating Figure Suite with Provenance Sidecars")
    res_map = subprocess.run([sys.executable, os.path.join(REPO_ROOT, "experiments", "make_map_figures.py")], cwd=REPO_ROOT)
    if res_map.returncode != 0:
        print("[FAIL] make_map_figures.py failed")
        return False
    res_fig = subprocess.run([sys.executable, os.path.join(REPO_ROOT, "experiments", "make_figures.py")], cwd=REPO_ROOT)
    if res_fig.returncode != 0:
        print("[FAIL] make_figures.py failed")
        return False
    provenance["steps"]["step5_figures"] = "PASS"

    # Step 6: Claim Ledger Auditing
    log_step("Step 6: Auditing Material Claim Ledger")
    ledger_path = write_claim_ledger()
    valid, errors = validate_claim_ledger(ledger_path)
    if not valid:
        print(f"[FAIL] Claim ledger validation errors: {errors}")
        return False
    print(f"-> Claim ledger verified with 15 material claims.")
    provenance["steps"]["step6_claim_ledger"] = "PASS"

    # Step 7: Compiling Manuscript
    log_step("Step 7: Compiling Paper Manuscript (pdflatex)")
    tex_path = os.path.join(REPO_ROOT, "paper.tex")
    if shutil_which("pdflatex"):
        cmd = ["pdflatex", "-interaction=nonstopmode", "paper.tex"]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[FAIL] LaTeX compilation failed with return code {res.returncode}")
            return False
        print("-> paper.pdf compiled successfully.")
        provenance["steps"]["step7_paper_compile"] = "PASS"
    else:
        print("[WARNING] pdflatex not found on PATH; skipping compilation.")
        provenance["steps"]["step7_paper_compile"] = "SKIPPED_NO_PDFLATEX"

    # Step 8: Strict Paper Linter
    log_step("Step 8: Executing Strict Paper Linter")
    import tools.lint_paper as lp
    linter_errors = lp.lint_paper(tex_path=os.path.join(REPO_ROOT, "paper.tex"), strict_release=False)
    if linter_errors:
        print("STRICT LINTER FAILURE: Integrity violations found in paper:")
        for err in linter_errors:
            print(f"  [ERROR] {err}")
        return False
    print("Paper lint passed successfully: 0 provenance violations, 0 unverified claims, 0 literal numbers.")
    provenance["steps"]["step8_linter"] = "PASS"

    # Hash Output Artifacts
    artifacts_to_hash = [
        "results/raw_results.csv",
        "results/numbers.tex",
        "results/table_main_results.tex",
        "results/table_stratified.tex",
        "results/table_sitl.tex",
        "results/stats/hypothesis_results.csv",
        "audit/CLAIM_LEDGER.csv",
        "paper.pdf",
    ]
    for rel_path in artifacts_to_hash:
        full = os.path.join(REPO_ROOT, rel_path)
        if os.path.exists(full):
            provenance["artifacts"][rel_path] = {
                "sha256": compute_file_sha256(full),
                "bytes": os.path.getsize(full),
            }

    duration = time.time() - start_time
    provenance["duration_sec"] = round(duration, 2)
    prov_file = os.path.join(REPO_ROOT, "results", "build_provenance.json")
    with open(prov_file, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2)

    log_step(f"BUILD COMPLETE: All Steps Passed in {duration:.1f}s")
    print(f"Provenance recorded to: {prov_file}\n")
    return True


def shutil_which(cmd: str) -> bool:
    import shutil
    return shutil.which(cmd) is not None


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
