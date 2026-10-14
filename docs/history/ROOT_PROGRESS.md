# ACA Final End-to-End Repair Progress Log

**Branch:** `fix/audit-repairs`  
**Base Commit:** `6cabf8ca417b25102dc74d3cf4e750fa2c495f8e` (`v2.0-submission`)  
**Status:** Repaired & Audited (Gates 1–6 Complete; Verified Repaired; All Tests Passing)  

---

## Progress Checklist

- [x] **1. Setup, Baseline, Hashes (Section 2)**
  - [x] Branch checked out (`fix/audit-repairs` from `6cabf8c`)
  - [x] Virtual environments created: `core` and `extras`
  - [x] `pip freeze` recorded to `repro/env_core.txt` and `repro/env_extras.txt`
  - [x] Input hashes computed and stored to `repro/input_hashes.json`
  - [x] Baseline pytest runs on original HEAD recorded to `repro/baseline_core.txt` and `repro/baseline_extras.txt`
- [x] **2. Verification of Prior Work & Evidence Documents (Section 4)**
  - [x] Verify issues A through L on original HEAD (worktree / branch)
  - [x] Verify 3 discovered issues (blocked-edge 1e9, prune_threshold 0.06 vs 0.12, set_oracle uniform collapse)
  - [x] Re-derive Lipschitz bound and verify total variation conventions against exhaustive oracle
  - [x] Verify recursive recourse tree counterexample (depth-2 vs depth-1)
  - [x] Write `AUDIT_REPORT.md`
  - [x] Write `FINDINGS.csv`
  - [x] Write `CLAIM_SOURCE_MATRIX.csv`
  - [x] Write `REPRODUCIBILITY_REPORT.md`
  - [x] Write `REPAIR_PLAN.md`
  - [x] Write `DECISIONS.md`
- [x] **3. Re-analysis of Existing Evidence (Section 5)**
  - [x] Build locked population definitions (`experiments/population.py`)
  - [x] Recompute raw v5 means and check against reported table
  - [x] Implement cluster-aware CIs and tests alongside registered cell-level tests
  - [x] Apply frozen Holm correction to registered hypothesis family
  - [x] Build single versioned result model (`results/result_model_v1.json`)
- [x] **4. Correctness Repairs (Section 6 - Atomic Commits)**
  - [x] P0-01 / P1-01: Population & statistics - wire result model into `make_tables.py`, remove raw-mean mixing
  - [x] P0-02 / P0-08: Claim ledger - finalize `audit/CLAIM_LEDGER_V2.csv`, annotate legacy ledger
  - [x] P0-03: Recursive recourse - true recursive tree in planner, valuation, bound, executor
  - [x] P0-04 / P0-05: Bound, margin, pruning - bound on actual pruned policy, label empirical variants
  - [x] P1-05: Belief model - validate `set_oracle`, reject unsupported or fix collapse, calibration harness
  - [x] P0-06: Logging & provenance - atomic single-writer JSONL, verify tool, concurrency tests
  - [x] P0-07: Generated outputs - eliminate all hardcoded fallbacks in scripts and paper macros
  - [x] P1-06: Tests & packaging - split core vs extras markers, clean imports, update badge
- [x] **5. Perception / SITL (Section 7 - Issue J)**
  - [x] Audit `experiments/sitl/vision.py` closed-loop connection (verified open loop)
  - [x] Redefine detection/perception metrics (opportunities, occluded, TP, FP, FN, ID-swap)
  - [x] Document as open-loop synthetic perception demo; disclaimer added everywhere
- [x] **6. New Preregistered Confirmation Protocol (Section 8)**
  - [x] Author `protocols/prereg-v6.md` with disjoint fresh seeds and equal budgets
  - [x] Fresh seeds disjointness test `tests/test_prereg_v6_seeds.py`
  - [x] Tagged `prereg-v6`
- [x] **7. Paper, Documentation, and UI (Section 9)**
  - [x] Synchronize paper claims with three-tier evidence hierarchy
  - [x] Replace hardcoded p-values with result model macros; compile `paper.pdf`
  - [x] UI fixes: detours active vs cumulative semantics, mobile KPI grid responsiveness
  - [x] Verify UI exports match displayed numbers by script (`tests/test_ui_metrics_export.py`)
  - [x] Playwright screenshots captured at 390px, 768px, 1440px (`docs/ui_checks/`)
- [x] **8. Final Builds, Acceptance Gates & Deliverables (Sections 10 & 11)**
  - [x] Rebuild pipeline cleanly with verified manifest (`tools/build_all.py`)
  - [x] Full pytest runs on core and extras suites; `TEST_REPORT_BEFORE_AFTER.md`
  - [x] Complete `CLAIM_SOURCE_MATRIX.csv`
  - [x] Audit all 12 Acceptance Gates and table A-L

