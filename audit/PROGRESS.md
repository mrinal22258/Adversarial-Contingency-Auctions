# ACA Repository Audit & Overhaul Progress Log

**Branch:** `fix/rigorous-eval`  
**Current Stage:** Overhaul & Audit Complete (Stages 1–4 PASSED)  
**Stage 1 Gate Status:** **PASSED**  
**Stage 2 Gate Status:** **PASSED**  
**Stage 3 Gate Status:** **PASSED**  
**Stage 4 Gate Status:** **PASSED** (Overhaul Complete)  
**Last Updated:** 2026-10-10  

---

## 1. Stage 1 Execution Summary (Complete)

- [x] **Capability Probe:** Logged system environment in `audit/BASELINE_REPORT.md` (Python 3.12.7, 12 CPUs, PyBullet, OR-Tools, Gradio, Playwright, MiKTeX, Network active).
- [x] **Audit Command Logger:** Created `tools/audit_logger.py`, logging commands, exit codes, and timestamps to `audit/command_log.jsonl`.
- [x] **Baseline Snapshot & Inventory:** Preserved 99 generated artifacts to `audit/baseline_snapshot/` with cryptographic manifest (`audit/baseline_snapshot/manifest.json`); complete 2,486-file inventory saved to `audit/repository_inventory.json`.
- [x] **Data Lineage & Population Reconstruction:** Built `tools/build_coverage_matrices.py`, generating `coverage_matrix_trials.csv`, `coverage_matrix_instances.csv`, and `method_comparability.csv`.
- [x] **Primary Population Declaration:** Authored `audit/PRIMARY_POPULATION.md`, formally declaring the original confirmatory comparison invalidated/unavailable due to omnibus OFAT sweep mixing, establishing the balanced nominal grid ($N=750$ matched trials across 250 instances).
- [x] **Strict Data Schema & Keys:** Implemented in `acalib/data/schema.py` and `acalib/data/__init__.py`. Enforces 7-tuple unique trial keys and 6-tuple pairing keys.
- [x] **Machine-Readable Analysis Protocol:** Created `experiments/configs/analysis_protocol.yaml`.
- [x] **Map Verification Engine:** Rewrote `acalib/demo/provenance.py` to eliminate fallback hashes and implement 5 explicit states (`VERIFIED`, `MISMATCH`, `MISSING`, `UNAVAILABLE`, `UNVERIFIED`). Reconciled Boston graph topology (326 raw GraphML vs 323 simple undirected navigation edges, 112 work-zone intersections) in `data/maps/manifest.json`.
- [x] **Data Recovery Key Bug:** Fixed 5-tuple to 7-tuple key in `tools/recover_runs.py`, preventing the silent dropping of 300 OFAT scale sensitivity trials.
- [x] **Development Tree Linter:** Added `--strict-release` flag to `tools/lint_paper.py`, enabling dirty-tree development auditing without crashing.
- [x] **Statistical Table & Macro Pipeline:** Fixed stale pair-count scoping bug in `compute_paired_statistics` in `experiments/make_tables.py`; isolated balanced 750-trial grid in `generate_main_results_table`; dynamically linked `results/numbers.tex` to statistical outputs; eliminated false `0.00` p-values via `< 0.001` thresholding.
- [x] **Stage 1 Regression Test Suite:** Created `tests/test_stage1_provenance_and_stats.py` with 15 passing unit tests covering schema, failed trial retention, duplicates, map verification, paired statistics, and p-value formatting.

---

## 2. Stage 2 Execution Summary (Complete)

- [x] **Theorem-to-Code Traceability Map:** Authored `audit/THEOREM_CODE_MAP.md` mapping all formal definitions, assumptions, propositions, theorems, and corollaries to implementing code symbols, proof dependencies, and test coverage.
- [x] **Rigorous Pinsker Margin Re-Derivation:** Re-derived the total variation triangle bound and Pinsker step in `audit/THEOREM_CODE_MAP.md`; verified directional KL divergence ($D_{\mathrm{KL}}(B_r \parallel \hat{B}_s)$), posterior clipping support ($\epsilon = 10^{-6}$), and dimensional unit consistency.
- [x] **Analytical Lipschitz Bound (`compute_lipschitz_bound`):** Eliminated unproven heuristic multipliers (`1.5 * nominal_cost` in production, `2.5 * nominal_len` in test). Implemented the multivariable Mean Value Theorem bound in `acalib/agents/contingency.py`: $L_j = \sum_{k=1}^K |\text{branch\_cost}_k - \text{primary\_cost}| \cdot \Delta \pi(e_k)$. Exposes $L_j = 0.0$ when no risky edges exist.
- [x] **Production & Test Harness Unification:** Removed duplicate test oracle `compute_explicit_lipschitz` in `tests/test_theorem3_montecarlo.py`. Both production (`acalib/alloc/aca.py`) and test suites call the exact same `compute_lipschitz_bound` function.
- [x] **Monte Carlo Sample Verification:** Updated docstrings in `tests/test_theorem3_montecarlo.py` to truthfully state the verified sample size ($5,000$ sampled belief pairs across 100 RGG graphs) and clearly noted that sampling demonstrates numerical consistency rather than mathematical proof.
- [x] **Limiting Case & Boundary Tests:** Added unit tests in `tests/test_theorem3_montecarlo.py` for zero divergence ($TV=0, KL=0$), zero estimation error ($\eta = 0$), disconnected graphs, and depth-0 recourse disabled ($d=0$).
- [x] **Label Reconciliations:** Reconciled formal numbering across `README.md`, docstrings, and `paper.tex`:
  - Proposition 1: Expected-Recourse Valuation (`prop:valuation`)
  - Proposition 2: Lipschitz Continuity of Recourse Bids (`prop:lipschitz`)
  - Theorem 1: Conditional Conflict-Freedom of Phase-1 Safe Claims (`thm:conflict_freedom`)
  - Proposition 3: Safe-Claim Monotonicity (`prop:safe_monotonicity`)
  - Proposition 4: Message Reduction via Local Recourse (`prop:messages`)
- [x] **Narrowed Claim Scope & Antecedent Adherence:** Explicitly documented that Theorem 1 is strictly conditional on Assumption 1 ($\mathrm{TV} \le \eta_{\text{eff}}$), which holds in $21.1\%$ of safe commitments. Confirmed that across adhered claims, exactly 0 conflicts occurred. Overall fleet coordination safety across unconditioned runs is an empirical property driven by conservative fallback deferrals.
- [x] **Comprehensive Findings Log Update:** Appended findings F-11, F-12, and F-13 to `audit/REPOSITORY_AUDIT.md`.

---

## 3. Stage 3 Execution Summary (Complete)

- [x] **Material Claim Ledger:** Implemented `tools/claim_ledger.py` auditing 15 material claims in `audit/CLAIM_LEDGER.csv` linking each claim to its primary population, statistical test, and status (`SUPPORTED`, `CONDITIONAL`, `EXPLORATORY`, `NOT_SUPPORTED`).
- [x] **Deterministic Single Results Pipeline:** Created `tools/build_all_results.py` and `make results` executing 8 sequential steps with 100% exit code 0 in 59.0s. Emits `results/build_provenance.json` with cryptographic SHA-256 hashes of all outputs.
- [x] **Zero Hardcoded Numbers & Strict Paper Linter:** `tools/lint_paper.py` passes with 0 provenance violations, 0 unverified claims, and 0 unmacroed literal numbers. All numbers derived strictly from `results/numbers.tex`.
- [x] **Clean LaTeX Compilation:** Compiled 8-page `paper.pdf` (780,542 bytes) via MiKTeX `pdflatex` with verified typeset tables, macro bindings, and vector figures.
- [x] **README Synchronization:** Reconciled test badge (135 Passing), proposition labels, and benchmark results against `results/numbers.tex`.
- [x] **UI Redesign & Specification:** Authored `audit/UI_REDESIGN_SPEC.md`; redesigned `app.py` into a dark-calm control room with dual-encoded accessible status badges, tabular numeric KPI strip, and trajectory visualizer.
- [x] **Cross-Viewport Playwright Testing:** Executed `tools/test_ui_playwright.py` passing 100% across Desktop (1920x1080), Laptop (1366x768), Tablet (768x1024), and Mobile (390x844).
- [x] **Stage 3 Validation Report:** Documented all commands, exit codes, hashes, and gate results in `audit/VALIDATION_REPORT.md`.

---

## 4. Stage 4 Execution Summary (Complete)

- [x] **Method Improvements Implemented:** Implemented adaptive Shannon entropy calibration (`adaptive_margin=True`) and strategic corridor pruning (`prune_threshold=0.03`) in `acalib/alloc/aca.py` and registered `aca_adaptive` and `aca_plus` in `acalib/sim/engine.py`.
- [x] **Method Improvement Unit Tests:** Authored `tests/test_stage4_method_improvement.py` with 3 passing unit tests verifying initialization, entropy modulation, and smoke execution.
- [x] **Full Regression Test Suite:** Executed full test suite with **138 tests passing in 135.56s** with zero regressions.
- [x] **Pre-Registered Held-Out Confirmatory Evaluation:** Created `experiments/run_heldout_eval.py` and executed 300 trials on strictly disjoint held-out seeds (51–60) across Boston OSMnx, MovingAI warehouse, and RGG topologies.
- [x] **Statistically Significant Improvement Confirmed:** ACA-Adaptive demonstrated a statistically significant $+2.67\%$ completion gain ($p = 0.0076$, Cohen's $d_z = 0.327$) over standard ACA on held-out instances; ACA+ demonstrated $+3.00\%$ gain ($p = 0.0249$).
- [x] **Confirmatory Telemetry & Provenance:** Output saved to `results/confirmatory/heldout_results.csv` and `results/confirmatory/heldout_summary.csv`.
- [x] **Stage 4 Confirmatory Report:** Authored `audit/STAGE4_CONFIRMATORY_REPORT.md`.

---

## 5. Final Key Assumptions & Research Verdict

1. **Analytical Lipschitz Constant:** Derived from the multivariable Mean Value Theorem on expected recourse valuation. For depth-1 single risky edge ($K=1$), $L_j = \Delta_j$ holds with mathematical equality. For general contingency trees ($K > 1$), $L_j$ serves as an analytical upper bound over the simplex $\Delta(\Theta)$.
2. **Conditional Scope of Theorem 1:** Theorem 1 guarantees conflict-freedom if and only if $\mathrm{TV}(B_s, \hat{B}_s^{(r)}) \le \eta_{\text{eff}}$ and map discrepancy is bounded. It does **not** guarantee conflict-freedom when belief error exceeds $\eta_{\text{eff}}$; in those cases, conflict reduction relies on empirical fallback deferrals.
3. **Entropy-Adaptive Margin Efficacy:** Confirmatory evaluation confirms that scaling $\kappa$ adaptively with posterior Shannon entropy relaxes over-conservatism as the adversary type is identified, significantly improving task throughput without violating safe claim guarantees.

