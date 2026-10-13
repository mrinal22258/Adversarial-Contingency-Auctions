# Protocol v6: Pre-Registered Multi-Robot Contingency Benchmark Confirmation

**Date of Cryptographic Freeze**: 2026-10-13  
**Protocol Version**: 6.1.0  
**Git Tag**: `prereg-v6.1`  
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

> [!IMPORTANT]
> **v6.1 pre-execution correction: original list did not match the stated derivation; corrected before any v6 data existed.**
> In v6.0, the written seed list was inadvertently evenly spaced and did not correspond to the pseudo-random draw from `np.random.default_rng(20261013)`. The exact algorithmically derived sequence below is declared authoritative and is cryptographically hashed.

All Protocol v6 confirmatory instances are instantiated with fresh random seeds generated via `np.random.default_rng(20261013)` (`rng.choice(np.arange(50000, 60000), size=100, replace=False)` filtered for disjointness and sorted).

- **Confirmatory Seeds ($N=50$)**:
  `[50515, 50594, 50806, 50971, 51085, 51276, 51357, 51470, 51776, 52166, 52184, 52279, 52822, 52851, 53040, 53147, 53328, 53579, 53654, 53868, 53890, 54014, 54514, 54540, 54594, 54984, 55009, 55184, 55401, 55442, 55805, 55966, 56357, 56394, 56806, 57016, 57034, 57182, 57559, 57652, 58002, 58128, 58382, 58513, 58531, 58616, 58668, 59283, 59685, 59762]`
  - SHA-256: `09638b69b6d331eb3738023b4ad7502116e7d4768405235cf396d76bc3eea5cb`
- **Development / Tuning Seeds ($N=15$)**: Generated separately in $[40000, 45000]$ via `np.random.default_rng(9992026)`:
  `[40484, 40506, 40601, 40685, 40827, 41625, 41883, 41904, 42246, 42740, 43213, 44518, 44544, 44637, 44867]`
  - SHA-256: `19a8aabd61d3f15800164feae865f285ec0d8b4ccc13619534a940d57d63417c`
- **Disjointness Assertion**: Confirmed by unit test `tests/test_prereg_v6_seeds.py` (intersection with all prior seeds $= \emptyset$).

---

## 4. Evaluated Methods & Equal Budgets

All methods are evaluated on identical shared cells (Common Random Numbers) across:
- 5 Map Topologies: `warehouse_movingai` (38 nodes), `road_osmnx` (216 nodes), `rgg` (35 nodes), `grid` (30 nodes), `er` (35 nodes).
- 3 Adversary Regimes: $\theta_1$ (Stochastic), $\theta_2$ (Reactive), $\theta_4$ (Cyclic Patrol).
- Fleet Configuration: 4 robots, 15 tasks, bundle capacity 4, sensor range 25.0, communication range 30.0, packet drop prob 0.10, horizon 80 ticks.

### Evaluated Methods:
1. `aca`: Adversarial Contingency Auctions with recursive depth-$d$ recourse and closed-form Pinsker margin ($\kappa=1.0$).
2. `aca_plus`: Pruned recourse tree with calibrated threshold $\tau_{\text{prune}} = 0.20 > \tau_{\text{planner}} = 0.12$.
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
