# Protocol v6: Pre-Registered Multi-Robot Contingency Benchmark Confirmation

**Date of Cryptographic Freeze**: 2026-10-13  
**Protocol Version**: 6.0.0  
**Git Tag**: `prereg-v6`  
**Status**: REGISTERED_FROZEN (Confirmation execution pending compute allocation)

---

## 1. Scientific Mission & Evidence Tiers

This protocol governs the confirmatory evaluation of **Adversarial Contingency Auctions (ACA)** and all comparators. To prevent confirmation bias and p-hacking, all experimental evidence is strictly partitioned into three labelled tiers:

1. **Tier 1 (Exploratory Main Grid)**: Historical exploratory parameter grid ($N=18{,}720$ runs, seeds $1 \dots 30$). Used exclusively for descriptive mechanism analysis, theorem adherence exploration, and initial baselines.
2. **Tier 2 (Stage 4 Pilot Grid)**: Exploratory pilot evaluation ($N=60$ runs, seeds $1000 \dots 1060$). Negative finding preserved: exploratory gains did not replicate out-of-sample.
3. **Tier 3 (Protocol v5 Held-Out Benchmark)**: Confirmatory evaluation ($N=3{,}600$ paired trials, seeds $101 \dots 130$). Evaluated out-of-sample under family-wide Holm–Bonferroni correction.
4. **Tier 4 (Protocol v6 Confirmatory Confirmation - THIS PROTOCOL)**: Confirmatory replication with recursive recourse trees, process-safe atomic logging, and freshly generated seeds strictly disjoint from all prior tiers.

---

## 2. Hypothesis Registry & Family-Wise Error Control

Hypotheses are evaluated as a single frozen family under step-down **Holm–Bonferroni FWER control ($\alpha = 0.05$)**:

| Hypothesis ID | Title | Test Method vs Baseline | Metric | Direction / Margin | Estimator & Statistical Test |
|---|---|---|---|---|---|
| **$H_1$** | Recursive Recourse Efficacy | `aca` vs `aca_depth_0` | `completion_rate_pct` | Greater ($+4.0$ pp target) | Paired Wilcoxon signed-rank + Holm |
| **$H_2$** | Pinsker Margin Conflict Reduction | `aca` vs `aca_no_margin` | `total_conflicts` | Less ($-10.0$ conflicts target) | Paired Wilcoxon signed-rank + Holm |
| **$H_3$** | Pinsker Margin Completion Cost | `aca` vs `aca_no_margin` | `completion_rate_pct` | Non-inferiority ($\delta = 5.0$ pp) | Two One-Sided Tests (TOST paired $t$-test) |
| **$H_4$** | Level Execution vs CBBA+LR | `aca` vs `cbba_lr` | `completion_rate_pct` | Two-sided equivalence | Paired Wilcoxon signed-rank + Holm |
| **$H_5$** | Level Execution vs CBBA-PR+LR | `aca` vs `cbba_partial_lr` | `completion_rate_pct` | Two-sided parity | Paired Wilcoxon signed-rank + Holm |
| **$H_6$** | Single-Agent Replan Trade-off | `aca` vs `ctp_replan` | `total_conflicts` & `completion_rate_pct` | Two-sided trade-off | Paired Wilcoxon signed-rank + Holm |

### Decision Rules:
- **Equivalence / Non-Inferiority**: Requires TOST within the pre-registered margin $\delta = 5.0$ percentage points. If unproven, no equivalence claim is permitted.
- **Negative Results Preservation**: If ACA+ or adaptive variants fail to outperform static ACA after Holm adjustment, the null result is explicitly reported as a headline finding.

---

## 3. Seed Schedule & Disjointness Guarantee

All Protocol v6 confirmatory instances are instantiated with fresh random seeds generated via `np.random.default_rng(20261013)`.

- **Confirmatory Seeds ($N=50$)**:
  `[50084, 50257, 50381, 50419, 50572, 50731, 50924, 51105, 51348, 51602, 51833, 52049, 52271, 52490, 52714, 52938, 53160, 53381, 53605, 53829, 54051, 54273, 54495, 54718, 54940, 55163, 55385, 55608, 55830, 56053, 56275, 56498, 56720, 56943, 57165, 57388, 57610, 57833, 58055, 58278, 58500, 58723, 58945, 59168, 59390, 59613, 59835, 59912, 59945, 59981]`
- **Development / Tuning Seeds ($N=15$)**: Generated separately in the range $[40000, 45000]$.
- **Disjointness Assertion**: Confirmed by unit test `tests/test_prereg_v6_seeds.py` (intersection with all prior seeds $= \emptyset$).

---

## 4. Evaluated Methods & Equal Budgets

All methods are evaluated on identical shared cells (Common Random Numbers) across:
- 5 Map Topologies: `warehouse_movingai` (38 nodes), `road_osmnx` (216 nodes), `rgg` (35 nodes), `grid` (30 nodes), `er` (35 nodes).
- 3 Adversary Regimes: $\theta_1$ (Stochastic), $\theta_2$ (Reactive), $\theta_4$ (Cyclic Patrol).
- Fleet Configuration: 4 robots, 15 tasks, bundle capacity 4, sensor range 25.0, communication range 30.0, packet drop prob 0.10, horizon 80 ticks.

### Evaluated Methods:
1. `aca`: Adversarial Contingency Auctions with recursive depth-$d$ recourse and closed-form Pinsker margin.
2. `aca_plus`: Pruned recourse tree with calibrated threshold $\tau > \tau_{\text{planner}}$.
3. `aca_adaptive`: Shannon entropy-adaptive margin inflation.
4. `aca_no_margin`: Ablation with $\kappa = 0.0$ (no Pinsker margin).
5. `aca_depth_0`: Ablation with $d = 0$ (no contingency detour branches).
6. `cbba_lr`: Consensus-Based Bundle Algorithm (Choi '09) equipped with local recourse detours.
7. `cbba_partial_lr`: CBBA with Partial Release (Buckman '19) equipped with local recourse detours.
8. `ctp_replan`: Single-agent Canadian Traveler Problem reactive replanning.
9. `ssi_lr`: Sequential Single-Item auction equipped with local recourse detours.
10. `exact_cpsat`: Exact reference solver via OR-Tools CP-SAT on small benchmark instances ($N \le 8$ tasks).

---

## 5. Statistical Estimation & Cluster Independence

- **Unit of Analysis**: Independent instance $(G, \text{seed})$.
- **Cluster Unit**: `graph_family x seed` ($n=50$ clusters per topology/seed combination).
- **Estimators**:
  - Point estimate: Paired sample mean difference.
  - Hodges–Lehmann pseudo-median difference with $95\%$ bootstrap confidence intervals.
  - Cliff's $\delta$ non-parametric effect size.
  - Both cell-level ($N$) and cluster-level ($n$) statistics reported side-by-side in all public tables.

---

## 6. Execution Safeguards & Integrity Verification

1. **Logging**: All execution writes strictly through `AtomicJsonlWriter` or `SingleWriterJsonlLogger` with per-record SHA-256 hashing and deterministic merge.
2. **Post-Run Validation**: Mandatory execution of `tools/verify_log_integrity.py`. If any malformed line, duplicate, missing hash, or race condition occurs, the run is invalidated immediately.
3. **Zero Fallbacks**: All analysis tools ingest `results/result_model_v1.json` directly with missing-data exceptions.

---

## 7. Compute Allocation & Execution Status

- **Status**: Registered and cryptographically frozen.
- **Compute Availability**: Formal 50-seed execution requires ~40 CPU-hours. Dry run on 5 development seeds verified. Full confirmatory benchmark run will proceed when high-throughput cluster compute is scheduled.
- **Hold-Out Integrity**: Seeds $50000 \dots 60000$ remain strictly untouched.
