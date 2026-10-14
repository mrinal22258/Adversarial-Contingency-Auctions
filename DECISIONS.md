# Architectural and Methodological Decisions Log (ACA Repair)

In accordance with Section 0 and Section 1 of the End-to-End Repair Protocol, all ambiguous design and analytical choices follow the most conservative principle: fail closed, preserve raw data, and remove unsupported claims.

---

### Decision D-01: Historical Data Preservation and Integrity Status
- **Date:** 2026-10-13
- **Context:** Protocol v5 outputs consist of `results/confirmatory/heldout_v5_results.csv` (3,600 rows, SHA-256 `a7470feb...`) and `results/confirmatory/heldout_v5_runs.jsonl` (3,541 lines, 3,491 parseable, 50 malformed lines, 109 missing hashes).
- **Decision:** **DO NOT** reconstruct, edit, re-sort, or interpolate missing records in the historical v5 dataset. Pin exact SHA-256 hashes in `repro/input_hashes.json`. Mark the historical JSONL file as `DECLARED-INCOMPLETE`. Implement a verified atomic single-writer logger for all prospective runs (`protocols/prereg-v6.md`).
- **Rationale:** Rewriting or reconstructing historical experimental logs violates scientific provenance. Raw data must remain immutable.

---

### Decision D-02: Single Locked Population for Statistics and Reporting
- **Date:** 2026-10-13
- **Context:** `experiments/make_tables.py` previously defined a core balanced grid ($N=750$ per method across 250 instances) for paired tests, but sliced the raw omnibus CSV ($N=1,650$ for ACA, $N=1,600$ for CTP Replan) for means and bootstrap CIs, while stating $N=750$ in table captions (Finding A).
- **Decision:** Establish a single source of truth for population definitions in `experiments/population.py`. All table generators, figures, text macros, and statistical tests must evaluate the identical locked population. Any script attempting to mix pooled exploratory sweeps with balanced confirmatory cells must fail closed.
- **Rationale:** Estimand consistency is non-negotiable. Means, confidence intervals, and hypothesis tests must describe the exact same population.

---

### Decision D-03: Analytical Lipschitz Bound Formula and Total Variation Convention
- **Date:** 2026-10-13
- **Context:** `acalib/agents/contingency.py:251` implemented an ad-hoc Mean Value Theorem heuristic: $\sum_k |\text{branch\_cost}_k - \text{primary\_cost}| \cdot \Delta \pi(e_k)$. Meanwhile, the paper refers to Proposition 2 as the pure-type cost range (Findings D and E).
- **Decision:** Align production code and mathematical claims to the exact pure-type expected cost range:
  $$L_j = \max_{\theta \in \Theta} V(\mathcal{T}, \theta) - \min_{\theta \in \Theta} V(\mathcal{T}, \theta)$$
  under the standard statistical total variation distance:
  $$\mathrm{TV}(B_r, \hat{B}_s) = \frac{1}{2} \|B_r - \hat{B}_s\|_1 \in [0, 1]$$
  Pinsker's inequality is applied as $\mathrm{TV}(P, Q) \le \sqrt{\frac{1}{2} D_{\mathrm{KL}}(P \parallel Q)}$. The bound applies strictly to a fixed tree $\mathcal{T}$ evaluated under two beliefs, not to a policy dynamically replanned under different trees.
- **Rationale:** $V(\mathcal{T}, B) = \sum_\theta B(\theta) V(\mathcal{T}, \theta)$ is an exact linear function of belief $B$. Therefore, $|V(B) - V(B')| \le (\max_\theta V(\theta) - \min_\theta V(\theta)) \cdot \mathrm{TV}(B, B')$ is provably tight and exact across all network topologies and nonlinear valuations.

---

### Decision D-04: Full Recursive Depth-$d$ Recourse Trees
- **Date:** 2026-10-13
- **Context:** `contingency.py:89` configured `depth=max_depth` but only iterated over primary path risky edges once, creating a 1-level detour dictionary and assuming detours are never blocked (Finding C).
- **Decision:** Implement a true recursive branching tree `RecourseTree` where each risky edge on any active branch can recursively spawn detours up to depth $d$. The exact same recursive tree data structure is shared across planner, expected-cost valuation, Lipschitz bound, and executor.
- **Rationale:** A paper claiming depth-$d$ contingency planning must actually execute depth-$d$ branching, or remove the parameter.

---

### Decision D-05: Three-Tier Evidence Hierarchy and Claim Calibration
- **Date:** 2026-10-13
- **Context:** Prior documentation blended exploratory OFAT sweep runs ($N=1,650$), Stage 4 pilot runs ($N=60$), and Protocol v5 held-out confirmation ($N=450$/method). In Protocol v5, CBBA+LR outperformed ACA on completion ($94.67\%$ vs $92.40\%$) and welfare ($958.9$ vs $937.4$).
- **Decision:** Structure all public surfaces, README, and paper claims into three strictly separated tiers:
  1. *Tier 1 (Exploratory Main Grid):* Preliminary hypothesis generation.
  2. *Tier 2 (Stage 4 Pilot $N=60$):* Method development.
  3. *Tier 3 (Protocol v5 Confirmatory $N=3,600$):* Held-out confirmatory evaluation.
  Re-frame paper narrative: ACA's primary benefit is safety coordination (Pinsker margin significantly reduces conflicts by $\sim 10.3$ conflicts/trial with zero communication during detours at a modest non-significant completion cost of $1.08$ pp). Do not claim ACA dominates CBBA+LR in unconstrained completion.
- **Rationale:** Negative and nuanced results must be preserved honestly. CBBA+LR's competitive strength on completion is a valid scientific finding.

---

### Decision D-06: Perception Pipeline Classification
- **Date:** 2026-10-13
- **Context:** `experiments/sitl/vision.py` implements an overhead synthetic ArUco marker detector whose estimated poses were never piped into the robot task allocator or motion controller (Finding J).
- **Decision:** Explicitly classify `vision.py` as an "open-loop synthetic perception demonstration" in all docstrings, README, and paper prose. Disclaim any physical robot or in-the-loop perception validation. Separate detection opportunities, occlusions, true positives, and false positives in metric definitions.
- **Rationale:** Connecting an unvalidated synthetic detector to the allocator without physical testing would add uncalibrated error without scientific justification. Honest classification preserves integrity.

---

### Decision D-07: Telemetry Semantics, Mobile UI Layout, and Deterministic Build Pipeline
- **Date:** 2026-10-13
- **Context:** Finding L noted desktop UI displayed `0 DETOURS` while the narrative summary stated 13 local activations, and the mobile viewport clipped KPI labels. Finding G noted stale build provenance and lack of verified multi-pass build determinism.
- **Decision:** 
  1. Telemetry: Disambiguate active detours at current step vs cumulative detours across trial history in UI KPI cards (`{active} ({cum} cum)`) and narrative summary.
  2. Mobile UI: Adopt responsive CSS Grid `repeat(auto-fit, minmax(85px, 1fr))` with label wrapping; verify across 390px, 768px, 1440px via Playwright snapshots in `docs/ui_checks/`.
  3. Provenance & Determinism: Build pipeline `tools/build_all.py` compiles the single unified result model `results/result_model_v1.json`, generates `results/numbers.tex`, tables, figures, executes strict paper linting, and records SHA-256 hashes of all 12 key artifacts into `results/build_provenance.json`. Verified identical hashes across consecutive passes and enforced via `tests/test_build_manifest.py`.
- **Rationale:** UI transparency and complete build reproducibility are essential for end-to-end scientific integrity.

---

### Decision D-08: Authoritative Protocol v6 Seed List and Pre-Execution Amendment
- **Date:** 2026-10-13
- **Context:** Preregistration `protocols/prereg-v6.md` listed a hand-written / near-evenly spaced list of 50 seeds that did not match the derivation from `np.random.default_rng(20261013)`.
- **Decision:** The algorithmically generated list from `np.random.default_rng(20261013)` via `generate_v6_seeds(50)` is declared authoritative. It is frozen in `experiments/configs/protocol_v6.yaml` and replaces the listed seeds in `protocols/prereg-v6.md`. An explicit amendment note ("v6.1 pre-execution correction: original list did not match the stated derivation; corrected before any v6 data existed") is recorded in the preregistration. Development seeds ($N=15$) in $[40000, 45000]$ are generated with RNG seed 9992026 and stored separately.
- **Rationale:** Cryptographic and mathematical integrity requires verifiable derivation from the declared pseudo-random number generator, without human intervention or manual spacing.

---

### Decision D-09: Active ACA+ Pruning Semantics and Numeric Threshold Selection
- **Date:** 2026-10-13 (amended 2026-10-14 before execution)
- **Context:** In Protocol v5 held-out evaluations, `aca_plus` set `prune_threshold=0.06` while the planner admitted risky edges only at $\ge 0.12$, rendering pruning a dead no-op. Furthermore, dropping pruned edges could erase modeled failure probabilities.
- **Decision:** Pruning is strictly defined as removing pre-planned detours, NOT removing the underlying risk. A pruned edge remains in the probability model; if blocked during execution, it transitions to an explicit recovery/replan/failure leaf with its associated cost.
- **Pre-Execution Selection Rule:** The numerical pruning threshold $\tau_{\text{prune}}$ is selected empirically from candidate set $\{0.15, 0.20, 0.25\}$ evaluated exclusively on the 15 development seeds ($[40000, 45000]$) across the benchmark universe prior to any confirmatory run. The primary selection criterion is mean task completion rate (%); ties within 0.5 percentage points (pp) are broken by choosing the smaller threshold (parsimony). Confirmatory seeds ($[50000, 60000]$) are strictly held out. The exact same pruned plan object is shared across Lipschitz bound, bid score, cache, and executor. Historical v5 ACA+ is reported as "pruning inactive".
- **Outcome (2026-10-14):** Empirical evaluation ($N=675$ trials across 15 dev seeds, documented in `results/tuning/prune_dev_v6.csv` and `results/tuning/prune_dev_v6_summary.json`) yielded mean completion rates: $\tau=0.25$: $88.356\%$, $\tau=0.15$: $88.267\%$ (difference $0.089$ pp $\le 0.50$ pp), $\tau=0.20$: $86.815\%$. By the parsimony tie-breaking rule, $\tau_{\text{prune}} = 0.15$ was selected for Protocol v6.2 (achieving higher net welfare $895.46$ vs $893.84$ and fewer conflicts $37.9$ vs $39.6$).
- **Rationale:** Pruning must not erase modeled failure probability, and the threshold must exceed the candidate admission threshold to be functionally active. Preregistered selection rules must be documented before running evidence sweeps, and confirmatory seeds must never be used for parameter tuning.

---

### Decision D-10: Exactness Scope for Recursive Expected Cost
- **Date:** 2026-10-13
- **Context:** `compute_tree_expected_cost()` evaluates recursive expected cost under the assumption of independent Bernoulli edge failures with fixed marginal probabilities. Adversaries in simulation may induce persistent blockages and state-dependent/reactive correlations.
- **Decision:** Scope the analytical exactness claim explicitly to "exact under the independent-Bernoulli model" in all code docstrings, mathematical claims, paper prose, and documentation. Include simulation rollout tests quantifying the gap under reactive and persistent adversarial blocking. Remove all unapproved default marginal fallbacks (such as `0.15`).
- **Rationale:** Transparency regarding modeling assumptions prevents overclaiming exactness where edge interactions violate independence.

---

### Decision D-11: Primary Estimator Specification and Multiplicity Control
- **Date:** 2026-10-13
- **Context:** Discrepancies between cell-level Wilcoxon tests and cluster-level (`graph_family × seed`) bootstrap intervals led to inconsistent reported p-values and confidence intervals.
- **Decision:** Primary inferential estimands are strictly cluster-level ($n=50$ clusters per topology/seed combination) under step-down Holm–Bonferroni FWER adjustment. Cell-level paired tests are designated as secondary sensitivity analyses only. All primary tables, LaTeX macros, and claim validations must source their estimates, confidence intervals, raw p-values, and adjusted p-values from this cluster-level path in the unified result model.
- **Rationale:** Instances sharing topology and seed violate independent-sample assumptions; cluster-aware inference reflects the true degrees of freedom.

---

### Decision D-12: Double-Blind Anonymization Policy
- **Date:** 2026-10-13
- **Context:** `paper.tex` had `\anonymousfalse`, exposing author names, institutional affiliation, and contact details in rendered PDFs.
- **Decision:** Set `\anonymoustrue` by default for submission builds, while preserving a configurable camera-ready switch. Scrub all PDF metadata, author paths, institutional acknowledgments, and repository links from anonymous builds.
- **Rationale:** Adherence to double-blind conference review standards is mandatory for uncompromised peer review.

---

### Decision D-13: Executable Claim Verification and Negative Results Preservation
- **Date:** 2026-10-13
- **Context:** Claim ledgers previously recorded static `expected_verdict` without evaluating underlying data or handling empty populations.
- **Decision:** The claim ledger is refactored into an active verification engine: `EmpiricalClaim.evaluate()` computes effect sizes, confidence intervals, and hypothesis tests directly from raw locked data and verifies them against registered claims within declared tolerances. Empty populations or hash mismatches trigger hard failures. Negative results from Protocol v5 held-out evaluations (CBBA+LR superior on completion and welfare, with fewer conflicts) remain prominent across the paper, README, and ledgers.
- **Rationale:** Verifiable claims prevent drift between manuscript statements and empirical data.

---

### Decision D-14: Protocol Preparation, Tooling Validation, and Smoke Pipeline Isolation
- **Date:** 2026-10-14
- **Context:** Gate 5 requires preparing (but not executing) the 50-seed confirmatory v6 evaluation (~40 CPU-hours), validating protocol verification tools, and verifying the end-to-end execution pipeline on development seeds without polluting confirmatory data.
- **Decision:** Implement `tools/verify_protocol.py` to cryptographically validate the protocol, enforce clean Git status, check seed disjointness, and verify map file hashes. Deliver `RUN_V6.md` with explicit crash-resumption instructions and pinned environment setup (`requirements.lock`, `.github/workflows/ci.yml`). Execute a minimal 4-trial smoke test on 2 development seeds (`40484`, `40506`) demonstrating end-to-end pipeline execution (Run -> Verify -> Build -> Ledger) saved under `results/smoke/` with a prominent non-evidence disclaimer.
- **Rationale:** Proves operational readiness of the execution and verification tooling without expending large compute or compromising pre-registered confirmatory hold-outs.


