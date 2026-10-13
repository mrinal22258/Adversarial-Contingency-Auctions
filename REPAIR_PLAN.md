# ACA Comprehensive Repair Plan (Atomic Commit Sequence)

Each repair step is committed atomically on branch `fix/audit-repairs` with its own test suite and documented output impact.

---

### Step 1: P0-01 — Population Locking & Statistical Consistency
- **Commit Message:** `P0-01: Isolate and lock evaluation population in experiments/population.py`
- **Scope:** 
  - Create `experiments/population.py` defining locked populations: `NominalBalancedCoreGrid` ($N=750$), `ProtocolV5Confirmatory` ($N=3,600$), `ScaleSensitivityGrid`.
  - Refactor `experiments/make_tables.py` to source all means, bootstrap CIs, and paired tests strictly from the locked population dataframe.
- **Tests Added:** `tests/test_population.py` testing population row counts, pairing uniqueness, and zero mixing with raw omnibus rows.
- **Output Impact:** Table II in LaTeX and Markdown matches the caption sample size ($N=750$) exactly.

---

### Step 2: P0-02 / P0-08 — Claim Ledger V2 & Legacy Annotation
- **Commit Message:** `P0-02: Finalize CLAIM_LEDGER_V2.csv and annotate legacy ledger`
- **Scope:**
  - Annotate each row of `audit/CLAIM_LEDGER.csv` as `INVALID_EMPTY_FILTER` or `VALID`.
  - Create `tools/build_claim_ledger_v2.py` and generate `audit/CLAIM_LEDGER_V2.csv` with valid, executable filters on nominal grid (`n_robots == 4, n_tasks == 15`) and confirmatory populations.
  - Build `experiments/claims.py` defining claim evaluation logic.
- **Tests Added:** `tests/test_claim_ledger.py` failing build if any ledger row yields zero matching trials.
- **Output Impact:** 100% executable traceability for all paper claims.

---

### Step 3: P0-03 — True Recursive Depth-$d$ Recourse Trees
- **Commit Message:** `P0-03: Implement true recursive depth-d contingency trees`
- **Scope:**
  - Overhaul `acalib/agents/contingency.py` to implement recursive tree expansion (`RecourseTree`) for risky edges on detour paths up to `max_depth`.
  - Unify expected cost computation over the full recursive branching tree.
  - Fix `find_risk_aware_path` to return `None` (infeasible) when only paths traverse blocked/excluded edges, instead of a silent `1e9` weight path.
- **Tests Added:** `tests/test_contingency.py` verifying depth-2 strictly outperforms depth-1 on multi-level corridor interdictions against an independent brute-force oracle.
- **Output Impact:** Fulfills theoretical depth-$d$ capability claim in Proposition 1.

---

### Step 4: P0-04 / P0-05 — Pure-Type Lipschitz Bound & Pruning Consistency
- **Commit Message:** `P0-04: Harmonize pure-type Lipschitz bound and pruning consistency`
- **Scope:**
  - Implement Proposition 2 analytical bound $L_j = \max_{\theta} V(\mathcal{T}, \theta) - \min_{\theta} V(\mathcal{T}, \theta)$ over the recursive tree.
  - Ensure `prune_threshold` modifications in `acalib/alloc/aca.py` actually prune the executed `RecoursePlan`.
  - Require `compute_lipschitz_bound` to raise `ValueError` on missing edge marginals rather than silently dropping terms.
- **Tests Added:** `tests/test_lipschitz.py` validating the bound against exhaustive joint state enumeration over 10,000 Dirichlet belief samples.
- **Output Impact:** Restores rigorous mathematical validity to Proposition 2 and Phase-1 margin guarantees.

---

### Step 5: P1-05 — Robust Belief Filter & Unsupported Type Guard
- **Commit Message:** `P1-05: Robust adversary belief tracking and rejection of unsupported types`
- **Scope:**
  - Update `acalib/agents/belief.py`: `set_oracle` strictly checks that `adv_type in self.types`, raising `ValueError` for unsupported adversaries (e.g., `theta_4_cyclic_patrol`).
  - Document that cyclic patrol is an out-of-model adversary for the 3-type Bayesian filter.
  - Add calibration metrics harness (Brier score, reliability curve) for evaluation on fresh data.
- **Tests Added:** `tests/test_bayes.py::test_set_oracle_unsupported_rejection`.
- **Output Impact:** Eliminates silent uniform collapse bug.

---

### Step 6: P0-06 — Atomic Single-Writer JSONL Logger & Integrity Verifier
- **Commit Message:** `P0-06: Atomic single-writer JSONL logger and log verification tool`
- **Scope:**
  - Implement single-writer thread-safe JSONL logger with atomic flushes and mutex locking in `acalib/data/logger.py`.
  - Build `tools/verify_log_integrity.py` to audit line parseability, duplicate detection, and hash parity against CSV outputs.
  - Pin historical v5 status as `DECLARED-INCOMPLETE`.
- **Tests Added:** `tests/test_logger_integrity.py` stress-testing concurrent appends and verifying v5 known counts (3,600 / 3,541 / 3,491 / 50 / 109).
- **Output Impact:** Prevents future log truncation and corruption.

---

### Step 7: P0-07 — Versioned Result Model & Macro Generation
- **Commit Message:** `P0-07: Single versioned result model and elimination of hardcoded fallbacks`
- **Scope:**
  - Build `tools/build_result_model.py` generating `results/result_model_v1.json` containing all point estimates, cluster-aware CIs, and hypothesis tests.
  - Refactor `experiments/make_tables.py` and macro generators to read exclusively from `result_model_v1.json`.
  - Replace hardcoded p-value `\newcommand` lines in `paper.tex` with result-model-backed macros.
- **Tests Added:** `tests/test_provenance.py` verifying every LaTeX macro resolves to a hash-backed entry in the result model.
- **Output Impact:** Complete elimination of manual numeric literals and silent fallbacks.

---

### Step 8: P1-06 — Environment & Test Suite Separation
- **Commit Message:** `P1-06: Split test suite markers for core and extras environments`
- **Scope:**
  - Configure pytest markers in `pyproject.toml`: `core`, `sitl`, `ortools`, `ui`.
  - Use `pytest.importorskip` inside optional test modules.
  - Ensure `pytest -m core` passes 100% cleanly in `venv_core` with zero skips.
- **Tests Added:** CI matrix configuration and suite validation script.
- **Output Impact:** Verifiable reproducibility across standard environments.

---

### Step 9: P1-07 — Perception Metric Disambiguation & Open-Loop Status
- **Commit Message:** `P1-07: SITL vision metric redefinition and open-loop synthetic disclaimer`
- **Scope:**
  - Refactor `experiments/sitl/vision.py` metrics: separate `opportunities`, `occlusions`, `true_positive`, `false_positive`, `id_swap`.
  - Explicitly document open-loop synthetic perception status in code, README, and paper.
- **Tests Added:** Hand-crafted scene tests with known detection and occlusion ground truths in `tests/test_sitl_regression.py`.
- **Output Impact:** Eliminates misattribution of synthetic vision to physical robots or in-the-loop control.

---

### Step 10: P2-08 — UI Semantics & Mobile Viewport Responsiveness
- **Commit Message:** `P2-08: UI detours semantics disambiguation and mobile responsive layout`
- **Scope:**
  - Disambiguate KPI strip: show both "Active Detours (Current Step)" and "Cumulative Detours (Total)".
  - Update `MISSION_CONTROL_CSS` to use responsive CSS grid (`grid-template-columns: repeat(auto-fit, minmax(130px, 1fr))`) preventing clipping on 390px mobile viewports.
  - Add data provenance banner in UI displaying result model version and input hash.
- **Tests Added:** Playwright viewport test in `tools/test_ui_playwright.py` asserting no horizontal overflow at 390px, 768px, and 1440px.
- **Output Impact:** Flawless cross-viewport display and semantic clarity.

---

### Step 11: DOCS-09 — Preregistration V6 & Final Paper Synchronization
- **Commit Message:** `DOCS-09: Synchronize paper text, README, and protocol v6 specification`
- **Scope:**
  - Author `protocols/prereg-v6.md` specifying hypotheses, fresh seeds disjoint from v1-v5, cluster unit, Holm families, and equal compute budgets.
  - Tag git repository `prereg-v6`.
  - Update README and paper text to reflect the three-tier evidence hierarchy and recompiled `paper.pdf`.
- **Tests Added:** `tools/lint_paper.py` strict execution check.
- **Output Impact:** Clean, defensible, end-to-end reproducible publication package.
