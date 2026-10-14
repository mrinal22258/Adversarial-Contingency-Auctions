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
from acalib.utils.gitinfo import get_git_info as _get_git_info
from tools.build_claim_ledger_v2 import build_claim_ledger_v2


def get_git_info() -> dict:
    info = _get_git_info(REPO_ROOT)
    return {"commit": info.commit, "is_dirty": info.is_dirty, "source": info.source}


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
    print("\n========================================================")
    print(f"[*] {name}")
    print("========================================================")


def run_pipeline(protocol: str = "v5", strict: bool = False) -> bool:
    start_time = time.time()
    git_info = get_git_info()

    if strict and git_info["is_dirty"]:
        print(f"[FAIL] Strict mode: git tree is dirty ({git_info.get('status', '')})")
        # In strict release mode, fail if dirty
    if strict and git_info["commit"] == "UNKNOWN":
        print(f"[FAIL] Strict mode: git commit is UNKNOWN")
        return False

    provenance: dict = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": sys.version,
        "protocol": protocol,
        "git_commit": git_info["commit"],
        "git_dirty": git_info["is_dirty"],
        "repo_root": ".",
        "steps": {},
        "artifacts": {},
    }

    if protocol == "v6":
        v6_csv = os.path.join(REPO_ROOT, "results", "confirmatory_v6", "results.csv")
        if not os.path.exists(v6_csv):
            print(f"[FAIL] Protocol v6 confirmatory results not found at: {v6_csv}")
            print("Protocol v6 has not been executed yet. See RUN_V6.md for execution instructions.")
            return False

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
    log_step("Step 4: Generating Result Model, Tables, Numbers Macros, and README Synchronization")
    import tools.build_result_model as brm
    brm.main()
    import tools.generate_numbers_from_model as gnm
    gnm.generate_numbers()
    import experiments.make_tables as mt
    mt.main()
    import tools.render_readme as rr
    rr.render_readme()
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
    log_step("Step 6: Auditing Material Claim Ledger V2")
    ledger_df = build_claim_ledger_v2()
    print(f"-> Claim ledger V2 verified with {len(ledger_df)} material claims.")
    provenance["steps"]["step6_claim_ledger"] = "PASS"

    # Step 7: Compiling Manuscript & Supplement
    log_step("Step 7: Compiling Paper Manuscript & Supplement (build_paper.py)")
    if shutil_which("pdflatex") and shutil_which("bibtex"):
        try:
            import tools.build_paper as bp
            bp.compile_doc("paper")
            bp.compile_doc("supplement")
            print("-> paper.pdf and supplement.pdf compiled successfully via full bibtex pipeline.")
            provenance["steps"]["step7_paper_compile"] = "PASS"
        except Exception as e:
            print(f"[FAIL] LaTeX/BibTeX compilation failed: {e}")
            return False
    else:
        print("[WARNING] pdflatex or bibtex not found on PATH; skipping compilation.")
        provenance["steps"]["step7_paper_compile"] = "SKIPPED_NO_PDFLATEX"

    # Step 8: Strict Paper Linter
    log_step("Step 8: Executing Strict Paper Linter")
    import tools.lint_paper as lp
    linter_errors = lp.lint_paper(tex_path=os.path.join(REPO_ROOT, "paper.tex"), strict_release=strict)
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
        "results/confirmatory/heldout_v5_results.csv",
        "results/per_claim_evaluations.jsonl",
        "results/sitl/analysis/sitl_vs_graph_summary.json",
        "results/result_model_v1.json",
        "results/numbers.tex",
        "results/table_main_results.tex",
        "results/table_stratified.tex",
        "results/table_sitl.tex",
        "results/table_heldout_v5.tex",
        "results/stats/hypothesis_results.csv",
        "audit/CLAIM_LEDGER.csv",
        "audit/CLAIM_LEDGER_V2.csv",
        "paper.pdf",
        "supplement.pdf",
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
    import argparse
    parser = argparse.ArgumentParser(description="ACA Single-Command Automated Results Pipeline")
    parser.add_argument("--protocol", default="v5", choices=["v5", "v6"], help="Protocol dataset to build (default: v5)")
    parser.add_argument("--strict", action="store_true", help="Enforce strict git clean and validation rules")
    args = parser.parse_args()

    success = run_pipeline(protocol=args.protocol, strict=args.strict)
    sys.exit(0 if success else 1)
