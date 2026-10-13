# Comprehensive Audit Report: Adversarial Contingency Auctions (ACA)

**Auditor:** Skeptical Senior Robotics Researcher, Theory Auditor & Statistical Reviewer  
**Repository:** Adversarial-Contingency-Auctions (ACA)  
**Evaluated Branch:** `fix/audit-repairs` (branched from `6cabf8ca417b25102dc74d3cf4e750fa2c495f8e`)  
**Verdict:** **CONDITIONAL REPAIR REQUIRED — NOT ACCEPTED IN CURRENT FORM**  
**Core Finding:** While the core auction allocation framework and Pinsker margin mechanism are theoretically sound and demonstrate an empirical conflict-reduction benefit over no-margin baselines, the repository suffers from critical population-mixing bugs in table generation, ledger query errors, heuristic disconnects between code and theorems, test suite collection failures in minimal environments, and unreplicated confirmatory performance claims vs literature baselines.

---

## 1. Executive Summary & Verdict

Prior submission materials claimed broad empirical superiority of ACA across all dimensions and unconditioned theoretical guarantees. Our independent re-analysis reveals:
1. **Empirical Reality in Confirmatory Evaluation (Protocol v5, N=3,600):**
   - **CBBA+LR** achieves higher task completion ($94.67\%$ vs ACA's $92.40\%$, $+2.27$ pp) and higher social welfare ($958.9$ vs $937.4$).
   - ACA's demonstrable benefit is **conflict reduction via the Pinsker claim margin**: ACA reduces conflicts from $49.93$ (no-margin) to $39.66$ ($-10.27$ conflicts/trial, $p < 0.001$, paired Wilcoxon with Holm correction), at a small, statistically non-significant completion preservation cost of $1.08$ pp ($92.40\%$ vs $93.48\%$).
   - Standard CBBA's completion deficit in earlier tables was primarily driven by the absence of local detour execution capability rather than the auction mechanism alone.
2. **Methodological Deficiencies:**
   - Table generation mixed a balanced 750-trial paired core with pooled raw omnibus sweeps of 1,600–1,650 trials (Finding A).
   - Claim ledger queries filtered on $8$ robots and $30$ tasks, returning $0$ matching rows on the nominal grid ($4$ robots, $15$ tasks) (Finding B).
   - The Lipschitz bound in code differed from the pure-type cost range stated in Proposition 2 (Finding E).
   - The recursive contingency depth parameter ($d$) was ignored beyond depth 1 (Finding C).

---

## 2. Findings Log with File:Line Evidence & Reproduction Commands

### Finding A (P0 — Statistics): Population Discrepancy in Table II
- **Classification:** CONFIRMED BUG
- **File & Lines:** `experiments/make_tables.py:121-155`, `170-205`
- **Evidence:** `eval_df` was filtered to balanced nominal core grid ($N=750$), but row iteration sliced `df[df["method"] == m]`, pulling 1,650 rows for ACA, 1,600 for CTP, and 750 for CBBA. Caption states $N=750$.
- **Reproduction:** `python tools/verify_findings_checklist.py`
- **Impact:** Misrepresents table means and bootstrap CIs as originating from the balanced paired core.
- **Fix:** Lock evaluation population in `experiments/population.py`; slice exclusively from `eval_df`.
- **Acceptance Test:** `tests/test_population.py::test_single_population_locking`

### Finding B (P0 — Metadata): Claim Ledger Empty Queries
- **Classification:** CONFIRMED BUG
- **File & Lines:** `audit/CLAIM_LEDGER.csv:2-8`
- **Evidence:** Claims 1–7 filter on `comm_regime == 'nominal' & n_robots == 8 & n_tasks == 30`. Zero rows exist in nominal or confirmatory datasets with this combination. Claims 11, 12, 14, 15 crash with Python `NameError`.
- **Reproduction:** `python tools/verify_findings_checklist.py`
- **Impact:** Entire claim verification ledger is mathematically unexecutable and untraceable.
- **Fix:** Mark legacy ledger as INVALID; build `audit/CLAIM_LEDGER_V2.csv` with validated queries.
- **Acceptance Test:** `tests/test_claim_ledger.py::test_no_empty_ledger_queries`

### Finding C (P0 — Algorithm): Contingency Tree Truncated at Depth 1
- **Classification:** CONFIRMED BUG
- **File & Lines:** `acalib/agents/contingency.py:89-145`
- **Evidence:** `build_recourse_plan` checks risky edges along the primary path and generates 1-level detours. It never inspects risky edges on the detours themselves, rendering `max_depth > 1` a no-op.
- **Reproduction:** Evaluated depth-1 vs depth-2 on graph with secondary blocked corridor: both produced identical expected costs ($2.5000$) and 1 detour key.
- **Fix:** Implement true recursive tree data structure shared by planner, valuation, bound, and executor.
- **Acceptance Test:** `tests/test_contingency.py::test_recursive_tree_depth_branching`

### Finding D & E (P0 — Theory): Analytical Lipschitz Bound Divergence
- **Classification:** HIGH-RISK THEORY CONCERN
- **File & Lines:** `acalib/agents/contingency.py:240-275`; `acalib/alloc/aca.py:118-140`
- **Evidence:** Code used heuristic $\sum_k |\Delta C_k| \Delta \pi(e_k)$, which diverges from Proposition 2 pure-type range. Pruning in `aca.py` passed unpruned plans, causing missing hazards to silently set $\Delta \pi = 0$.
- **Fix:** Replaced with exact pure-type range $L_j = \max_{\theta} V(\mathcal{T}, \theta) - \min_{\theta} V(\mathcal{T}, \theta)$ under canonical $\mathrm{TV} = \frac{1}{2}\|P - Q\|_1$.
- **Acceptance Test:** `tests/test_lipschitz.py::test_exhaustive_oracle_pure_type_bound`

### Finding F (P0 — Data Integrity): Protocol v5 Log File Truncation
- **Classification:** CONFIRMED DATA INTEGRITY DEFECT (DECLARED-IRRECOVERABLE)
- **File & Lines:** `results/confirmatory/heldout_v5_runs.jsonl`
- **Evidence:** CSV contains 3,600 rows. JSONL contains 3,541 lines: 3,491 valid records and 50 truncated lines ending prematurely (e.g., `T07:16:49Z"}`). 109 CSV trial hashes are missing from parsed JSONL.
- **Reproduction:** `python tools/verify_findings_checklist.py`
- **Action:** Historical file pinned by SHA-256 and declared incomplete. New atomic logger built for v6.

### Finding G (P0 — Reproducibility): Hardcoded P-Values and Fallbacks
- **Classification:** CONFIRMED REPRODUCIBILITY DEFECT
- **File & Lines:** `paper.tex:50-66`; `experiments/make_tables.py`
- **Evidence:** P-values hardcoded as LaTeX `\newcommand` literals directly in `paper.tex` without connection to statistical outputs.
- **Fix:** Generate single result model `results/result_model_v1.json`; derive all macros dynamically.
- **Acceptance Test:** `tests/test_provenance.py::test_result_model_hash_and_macros`

### Finding J (P1 — Perception): Standalone Synthetic Vision Pipeline
- **Classification:** HIGH-RISK CLAIMS CONCERN
- **File & Lines:** `experiments/sitl/vision.py:1-531`
- **Evidence:** `vision.py` is not imported or referenced anywhere in `acalib/alloc/aca.py` or `experiments/sitl/run_sitl.py`. Robot controllers receive ground-truth simulator poses.
- **Fix:** Metric definitions corrected (separating opportunities, occlusions, true positives, false positives); explicitly labelled open-loop synthetic demonstration.
- **Acceptance Test:** `tests/test_sitl_regression.py::test_vision_metrics_definitions`

### Finding K (P1 — Reproducibility): Minimal Environment Test Suite Crash
- **Classification:** CONFIRMED BUG
- **File & Lines:** `tests/`; `pyproject.toml`
- **Evidence:** In minimal `venv_core` environment without PyBullet, OR-Tools, Gradio, or Playwright, `pytest` crashes at collection with exit code 2.
- **Fix:** Decouple suites with markers (`core`, `sitl`, `ortools`, `ui`) and `pytest.importorskip`.
- **Acceptance Test:** `.\venv_core\Scripts\pytest.exe -m core` passes 100% cleanly with zero skips.

### Finding L (P2 — UI): Detours Display Semantic Mismatch & Mobile Clipping
- **Classification:** DESIGN DEFECT
- **File & Lines:** `acalib/demo/ui/callbacks.py:281`; `acalib/demo/ui/styles.py:171`
- **Evidence:** Final frame displays `0 Detours` in KPI card because active detours at termination step is zero, conflicting with narrative stating 13 cumulative detours. Flex ribbon clips on 390px mobile viewports.
- **Fix:** Disambiguate active vs cumulative detours; responsive CSS grid with minmax.

### Discovered Issues:
1. **DISC-01 (P0): Blocked-edge 1e9 path in `find_risk_aware_path`** — When only available paths traverse excluded edges, planner returned path with weight 1e9 instead of `None`.
2. **DISC-02 (P1): `prune_threshold=0.06` vs `0.12`** — Since all identified risky edges have marginal $\ge 0.12$, the $0.06$ pruning filter was a 100% no-op.
3. **DISC-03 (P1): `set_oracle` on theta4 silently collapses to uniform** — Cyclic patrol is not in `CanonicalTypeSet`, so all beliefs zeroed out, normalized to uniform, and frozen.

---

## 3. Prioritized Repair Roadmap

1. **Phase 1:** Lock population in `experiments/population.py` and build `CLAIM_LEDGER_V2.csv`.
2. **Phase 2:** Implement recursive `RecourseTree` and pure-type Lipschitz bound.
3. **Phase 3:** Implement atomic JSONL logger, integrity checker, and single result model.
4. **Phase 4:** Split test markers for clean core runs; fix UI detours semantics and mobile CSS.
5. **Phase 5:** Author `protocols/prereg-v6.md` with fresh disjoint seeds; synchronize paper and README.
