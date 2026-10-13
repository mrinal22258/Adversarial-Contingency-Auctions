# ACA Final End-to-End Repair Progress Log

**Branch:** `fix/audit-repairs`  
**Base Commit:** `6cabf8ca417b25102dc74d3cf4e750fa2c495f8e` (`v2.0-submission`)  
**Status:** In Progress - Section 2 Setup  

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
  - [x] Write `CLAIM_SOURCE_MATRIX.csv` (skeleton)
  - [x] Write `REPRODUCIBILITY_REPORT.md` (baseline part)
  - [x] Write `REPAIR_PLAN.md`
  - [x] Write `DECISIONS.md`
- [ ] **3. Re-analysis of Existing Evidence (Section 5)**
  - [x] Build locked population definitions (`experiments/population.py`)
  - [x] Recompute raw v5 means and check against reported table
  - [ ] Implement cluster-aware CIs and tests alongside registered cell-level tests
  - [ ] Apply frozen Holm correction to registered hypothesis family
  - [ ] Build single versioned result model (`results/result_model_vN.json`)
- [ ] **4. Correctness Repairs (Section 6 - Atomic Commits)**
  - [x] P0-01 / P1-01: Population & statistics - wire result model into `make_tables.py`, remove raw-mean mixing
  - [ ] P0-02 / P0-08: Claim ledger - finalize `audit/CLAIM_LEDGER_V2.csv`, annotate legacy ledger
  - [ ] P0-03: Recursive recourse - true recursive tree in planner, valuation, bound, executor
  - [ ] P0-04 / P0-05: Bound, margin, pruning - bound on actual pruned policy, label empirical variants
  - [ ] P1-05: Belief model - validate `set_oracle`, reject unsupported or fix collapse, calibration harness
  - [ ] P0-06: Logging & provenance - atomic single-writer JSONL, verify tool, concurrency tests
  - [ ] P0-07: Generated outputs - eliminate all hardcoded fallbacks in scripts and paper macros
  - [ ] P1-06: Tests & packaging - split core vs extras markers, clean imports, update badge
- [ ] **5. Perception / SITL (Section 7 - Issue J)**
  - [ ] Audit `experiments/sitl/vision.py` closed-loop connection
  - [ ] Redefine detection/perception metrics (opportunities, occluded, TP, FP, FN, ID-swap)
  - [ ] Document as open-loop synthetic perception demo or test closed-loop wiring
- [ ] **6. New Preregistered Confirmation Protocol (Section 8)**
  - [ ] Author `protocols/prereg-v6.md` with disjoint fresh seeds and equal budgets
  - [ ] Create dev seeds sensitivity analysis for hyperparameters
  - [ ] Tag `prereg-v6`
- [ ] **7. Paper, Documentation, and UI (Section 9)**
  - [ ] Synchronize paper claims with three-tier evidence hierarchy
  - [ ] Replace hardcoded p-values with result model macros; compile `paper.pdf`
  - [ ] UI fixes: detours active vs cumulative semantics, mobile KPI grid responsiveness
  - [ ] Verify UI exports match displayed numbers by script
- [ ] **8. Final Builds, Acceptance Gates & Deliverables (Sections 10 & 11)**
  - [ ] Rebuild pipeline cleanly with verified manifest
  - [ ] Full pytest runs on core and extras suites; `TEST_REPORT_BEFORE_AFTER.md`
  - [ ] Complete `CLAIM_SOURCE_MATRIX.csv`
  - [ ] Audit all 12 Acceptance Gates and table A-L
