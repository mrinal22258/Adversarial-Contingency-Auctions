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
