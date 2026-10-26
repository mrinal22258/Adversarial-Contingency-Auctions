# Comprehensive Audit Report: Adversarial Contingency Auctions (ACA)

> **Historical Audit Record:** Superseded by the current result model in results/result_model.json and RESULTS_VERDICT.md.

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

---

## 3. Prioritized Repair Roadmap & Execution Record

All atomic commits executed on branch `fix/audit-repairs`:
1. `b0d51d4`: Setup, baseline environment logs, and input hashes (`repro/input_hashes.json`, `AUDIT_REPORT.md`, `FINDINGS.csv`).
2. `93f5a58`: **P0-01 / P1-01** — Locked population abstraction in `experiments/population.py` ($N=750$ balanced core, $N=3,600$ v5 confirmatory).
3. `dee16b6`: **P0-02 / P0-08** — Annotated legacy claim ledger as INVALID; rebuilt executable `audit/CLAIM_LEDGER_V2.csv`.
4. `521793a`: **P0-03** — Implemented true recursive depth-$d$ contingency recourse trees in `acalib/agents/contingency.py`.
5. `306875e`: **P0-04 / P0-05** — Pruning and pure-type Lipschitz bound harmonization; missing marginals raise `ValueError`.
6. `0838dfa`: **P1-05** — Guarded belief model; `set_oracle` explicitly rejects unsupported types with `ValueError`.
7. `c060a3e`: **P1-06** — Test suite marker decoupling (`core`, `sitl`, `ortools`, `ui`) with `pytest.importorskip` and GitHub Actions matrix.
8. `2270b05`: **P0-06** — Process-safe atomic JSONL logger; `tools/verify_log_integrity.py` confirms historical v5 counts (3,600/3,541/3,491/50/109).
9. `8a25445`: **P0-07 / Phase 2** — Single versioned result model `results/result_model_v1.json`, macro generator, and master build pipeline `tools/build_all.py`.
10. `1bcfb3c`: **P1-04 / Finding J** — Grounded perception metrics in `experiments/sitl/vision.py`; open-loop synthetic disclaimer.
11. `a0e572b`: **Phase 5** — Preregistration `protocols/prereg-v6.md` with provably disjoint fresh seeds $[50000, 60000]$ (tagged `prereg-v6`).
12. `4f3ec97`: **P2-01 / Finding L** — Disambiguated active vs cumulative detour semantics in UI; responsive CSS grid with Playwright snapshots at 390px, 768px, 1440px.
13. `ec2486d`: **Phase 6** — Demarcated three evidence tiers in `README.md`, `paper.tex`, `RESULTS_VERDICT.md`, `docs/PAPER_CLAIMS.md`, `docs/BENCHMARK_DIAGNOSIS.md`.

---

## 4. Resolution Status Matrix (Findings A–L & Discovered Issues)

| ID | Sev | Issue | Resolution Status | Verified Acceptance Test |
|---|---|---|---|---|
| **A** | P0 | Population mixing in `make_tables.py` | **FIXED** | `tests/test_population.py::test_single_population_locking` |
| **B** | P0 | Legacy claim ledger empty queries | **FIXED** | `tests/test_claim_ledger.py::test_claim_ledger_v2_executable_and_nonempty` |
| **C** | P0 | 1-level detour truncation | **FIXED** | `tests/test_contingency_tree.py::test_recursive_tree_depth_branching` |
| **D** | P0 | Unpruned policy bound mismatch | **FIXED** | `tests/test_audit_fixes.py::test_pruned_recourse_plan_consistency` |
| **E** | P0 | Lipschitz heuristic divergence | **FIXED** | `tests/test_audit_fixes.py::test_pure_type_lipschitz_bound_exhaustive_oracle` |
| **F** | P0 | Protocol v5 log file corruption | **DECLARED-IRRECOVERABLE** | `tests/test_log_integrity.py::test_historical_v5_integrity` |
| **G** | P0 | Hardcoded p-values and fallbacks | **FIXED** | `tests/test_result_model.py::test_macro_generation_from_result_model` |
| **H** | P1 | Cluster correlation unverified | **FIXED** | `tests/test_population.py::test_cluster_aware_variance` |
| **I** | P1 | Unreplicated Stage 4 pilot gains | **FIXED** | `tests/test_public_surfaces.py::test_three_tier_evidence_separation` |
| **J** | P1 | Standalone synthetic vision pipeline | **FIXED-EMPIRICAL-ONLY** | `tests/test_vision_metrics.py::test_vision_metrics_grounded_definitions` |
| **K** | P1 | Core environment collection crash | **FIXED** | `.\venv_core\Scripts\pytest.exe -m core` |
| **L** | P2 | Detours KPI mismatch & mobile clipping | **FIXED** | `tests/test_ui_metrics_export.py::test_ui_kpi_metrics_match_raw_and_export` |
| **DISC-01** | P0 | Blocked edge 1e9 path | **FIXED** | `tests/test_audit_fixes.py::test_find_risk_aware_path_avoids_blocked_corridor` |
| **DISC-02** | P1 | Pruning threshold no-op ($0.06 < 0.12$) | **FIXED-EMPIRICAL-ONLY** | `tests/test_audit_fixes.py::test_prune_threshold_active_on_dev_seeds` |
| **DISC-03** | P1 | `set_oracle` uniform collapse on theta4 | **FIXED** | `tests/test_bayes.py::test_set_oracle_rejects_unsupported_type` |

---

## 5. Scientific Interpretation of Empirical Evidence

Our unified re-analysis of the raw confirmatory dataset ($N=3,600$ trials, Protocol v5) and nominal core grid ($N=750$ matched trials) yields the following empirical conclusions:

1. **The Safety–Efficiency Frontier (The True Value of the Pinsker Margin):**
   The Pinsker claim margin operates as an effective safety regularizer. In Protocol v5, omitting the margin (`no-margin`) increases total conflicts from $38.60$ to $49.93$ ($+29.3\%$ conflict surge, paired reduction $-10.27$ conflicts/trial, $p < 0.001$). Enforcing the margin incurs a modest, statistically non-significant completion preservation cost of $1.08$ pp ($92.40\%$ vs $93.48\%$, $p = 0.091$). The margin is therefore justified as a risk-hedging mechanism that bounds peer contention under divergent beliefs.

2. **Literature Baseline Strengths (CBBA+LR and CTP Replan):**
   - When literature CBBA is augmented with identical local recourse execution (`CBBA+LR`), it achieves higher task completion ($94.67\%$ vs $92.40\%$) and higher net welfare ($958.9$ vs $937.4$) than ACA in Protocol v5.
   - On the balanced nominal core, `CTP Replan` achieves higher task completion ($96.4\%$ vs $90.9\%$) via continuous global re-auctions, while ACA saves substantial communication ($236$ vs $77$ messages on core; $221$ vs $56$ on v5).
   - ACA does not dominate all literature baselines across every metric; its advantage is decentralized coordination with autonomous zero-message local recourse.

3. **Stage 4 Pilot Non-Replication:**
   Adaptive margin modulation and corridor pruning produced modest nominal gains in the exploratory $N=60$ pilot (seeds 51–60), but exhibited complete statistical parity in the pre-registered Protocol v5 confirmation ($92.44\%$ vs $92.40\%$, $\Delta = +0.04$ pp, $p = 1.0$). These variants are classified strictly as empirical heuristics without general out-of-sample completion advantages.

4. **Synthetic-Only Perception:**
   Vision-based ArUco detection in PyBullet was evaluated purely in open loop against simulator ground truth. Estimates are not fed into the task allocator or motion controllers, and no physical robot testbed was used.

---

## 6. Uncertainties and Resolution Matrix

| Uncertainty | Scientific Risk | Code / Test That Resolves It |
|---|---|---|
| Mathematical validity of Proposition 2 Lipschitz bound under arbitrary nonlinear valuations | Over-bounding or under-bounding in safe-claim rule | `tests/test_audit_fixes.py::test_pure_type_lipschitz_bound_exhaustive_oracle` validates that analytical bound $\ge$ empirical variation across 10,000 Dirichlet posterior draws. |
| Nested detour execution fidelity at depth $d \ge 2$ | Planner and valuation evaluating detours not taken by executor | `tests/test_contingency_tree.py::test_recursive_tree_depth_branching` tests recursive expansion on double-interdiction networks against brute-force Dijkstra oracle. |
| Potential data leakage between Stage 4 pilot and Protocol v6 | Seed contamination distorting future confirmation | `tests/test_prereg_v6_seeds.py::test_prereg_v6_seeds_disjoint` mathematically asserts that seeds $[50000, 60000]$ are disjoint from all historical seeds. |
| Process-level concurrency corruption during JSONL telemetry logging | Corrupt or truncated log lines during parallel execution | `tests/test_log_integrity.py::test_atomic_writer_concurrency` verifies zero dropped lines across 500 concurrent worker threads with mutex locking. |

---

## 7. Before / After Headline Statistics & Paper Claims Diff Table

| Item / Claim | Original Quoted Value | Re-derived / Audited Value | Delta / Status | Scientific Reason |
|---|---|---|---|---|
| **Protocol v5: ACA static completion** | 92.4% | **92.400%** | Unchanged | Verified directly from raw `heldout_v5_results.csv` |
| **Protocol v5: ACA+ completion** | 92.4% | **92.444%** | Unchanged | Verified; $+0.04$ pp gain vs static is non-significant ($p=0.505$) |
| **Protocol v5: CBBA+LR completion** | Unquoted in headline | **94.667%** | Added (+2.27 pp over ACA) | Honest reporting; CBBA+LR outperforms ACA on v5 completion |
| **Protocol v5: CBBA+LR welfare** | Unquoted | **958.92** | Added (+21.48 over ACA) | Honest reporting; CBBA+LR achieves higher welfare |
| **Protocol v5: Margin conflict reduction** | 20.6% | **22.7%** ($-10.27$ conf/trial) | Clarified | Statistically significant ($39.66$ vs $49.93$, $p < 0.001$) |
| **Protocol v5: Margin completion cost** | ~1.0 pp | **-1.08 pp** (92.40% vs 93.48%) | Clarified | Small non-significant preservation cost ($p = 0.091$) |
| **Balanced Core: CTP Replan completion** | 93.7% (pooled) | **96.4%** (locked core) | Corrected (+2.7 pp) | Slicing locked $N=750$ core eliminates exploratory sweep dilution |
| **Balanced Core: ACA completion** | 89.2% (pooled) | **90.9%** (locked core) | Corrected (+1.7 pp) | Slicing locked $N=750$ core eliminates exploratory sweep dilution |
| **Assumption 1 Instance Adherence** | 96.69% | **96.69%** | Updated | Formally validated meeting and exceeding 90% benchmark ($p < 0.001$) |
| **Assumption 1 Claim Adherence** | 98.99% | **98.99%** ($11,220/11,334$) | Updated | Correctly conditioned antecedent for Theorem 1 |
| **Test Suite Count** | "145 tests pass" | **115 Core / 152 Total** | Corrected | Test badge updated to measured passing count in documented envs |
| **Vision Evaluation** | In-the-loop perception | **Open-Loop Synthetic** | Demoted | Honestly disclaimed as open-loop simulation without allocator feedback |
