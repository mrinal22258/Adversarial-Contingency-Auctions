# RESULTS_VERDICT.md: Empirical Verdict for Hypotheses H1-H8 (prereg-v4)

**Strict Rule R5**: Every empirical claim in the paper maps directly to a verified hypothesis ID below.
Generated directly from executed raw runs, matched independent instance-level tests, and directional decision rules.

| ID | Title | Metric | N | Mean Diff | HL Median [95% CI] | Cliff's Delta | Raw p | Adj p (Holm/BH) | Bonferroni p | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 | Recourse Efficacy (ACA vs ACA-d0) | completion_rate_pct | 250 instances | 4.14 | 3.33 [2.22, 4.44] | 0.241 | 3.4774e-12 | 2.0865e-11 | 2.0865e-11 | **SUPPORTED (ACA SUPERIOR)** |
| H2 | Level Execution (ACA vs cbba_lr) | completion_rate_pct | 250 instances | 2.14 | 1.9 [1.11, 3.02] | 0.114 | 2.6288e-04 | 7.8864e-04 | 0.0016 | **SIGNIFICANT DIFFERENCE (ACA HIGHER)** |
| H2 | Level Execution (ACA vs cbba_partial_lr) | completion_rate_pct | 250 instances | 0.25 | 0.0 [-0.83, 0.83] | -0.015 | 0.8836 | 0.8836 | 1.0000 | **PARITY (NO SIGNIFICANT DIFFERENCE)** |
| H2 | Level Execution (ACA vs ssi_lr) | completion_rate_pct | 250 instances | 6.77 | 5.56 [3.33, 7.78] | 0.151 | 2.5947e-07 | 1.0379e-06 | 1.5568e-06 | **SIGNIFICANT DIFFERENCE (ACA HIGHER)** |
| H2_REGIME | Lossy Regime Resilience (p_drop in [0.2, 0.4]) | completion_rate_pct | 50 instances | 1.73 | 0.0 [-1.67, 5.0] | 0.089 | 0.2536 | 0.5073 | 1.0000 | **NOT SUPPORTED / PARITY** |
| H2_CTP | Comparator Evaluation (ACA vs CTP Replan) | completion_rate_pct | 250 instances | -4.86 | -3.61 [-4.72, -2.53] | -0.306 | 1.1313e-15 | 2.2625e-15 | N/A | **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)** |
| H2_IMPLICIT | Comparator Evaluation (ACA vs Implicit) | completion_rate_pct | 250 instances | -3.56 | -3.33 [-3.33, -1.11] | -0.257 | 1.9997e-09 | 2.6663e-09 | N/A | **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)** |
| H3 | Welfare Non-Inferiority (ACA vs best literature baseline: cbba_partial_lr) | net_welfare | 250 instances | -6.51 | -6.51 [-20.73, 7.72] | 0.008 | 9.3413e-08 | 4.6707e-07 | 5.6048e-07 | **NON-INFERIOR / EQUIVALENT (SUPPORTED)** |
| H4 | Pinsker Margin Safe Conflict Reduction | safe_claim_conflicts | 250 instances | -4.847 | -4.833 [-5.0, -4.667] | -0.995 | 5.6143e-43 | 4.4915e-42 | N/A | **SUPPORTED (SIGNIFICANT REDUCTION)** |
| H4_COMPLETION | Pinsker Margin Completion Equivalence (TOST 5pp) | completion_rate_pct | 250 instances | 0.22 | 0.22 [-0.58, 1.02] | -0.005 | 6.6663e-20 | 2.6665e-19 | N/A | **NON-INFERIOR / EQUIVALENT (SUPPORTED)** |
| H5 | Bayesian Inference Advantage (ACA vs ACA-NoInference) | completion_rate_pct | 250 instances | -0.03 | 0.0 [0.0, 0.0] | -0.007 | 0.4505 | 0.5149 | N/A | **NOT SUPPORTED / PARITY** |
| H6 | Communication Efficiency (ACA vs CBBA) | total_messages | 250 instances | -76.06 | -73.33 [-89.33, -57.33] | -0.347 | 9.0984e-19 | 2.4262e-18 | N/A | **SUPPORTED (SIGNIFICANT REDUCTION)** |
| H7 | Assumption 1 Empirical TV Adherence (TV <= eta_eff vs 0.90) | tv_bound_adherence_rate | 250 instances | -0.3395 | 0.5605 [0.5318, 0.589] | 0.0 | 1.0000 | 1.0000 | N/A | **NOT SUPPORTED (BELOW THRESHOLD)** |
| H7_CONFLICT_FREE_RATE | Conflict-Free-Run Rate (0 Safe-Claim Conflicts) | conflict_free_run_rate | 1,650 runs | 0.0824 | 0.9824 [0.9761, 1.0] | 0.0 | N/A | N/A | N/A | **DESCRIPTIVE (98.24% CONFLICT-FREE)** |
| H8 | Robustness on theta_4 (ACA vs best ctp_replan) | completion_rate_pct | 250 instances | -5.33 | -3.33 [-3.33, -3.33] | -0.28 | 6.7940e-14 | 1.0870e-13 | N/A | **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)** |

## Pre-Registered Sample Sizes (n per family)

- **Independent Seeds per Family**: n = 50 per graph family across all 5 families (Total N = 250 independent benchmark instances).
  - `er` (Erdős–Rényi random network): n = 50
  - `rgg` (Random Geometric Graph): n = 50
  - `road_osmnx` (Downtown Boston road network): n = 50
  - `warehouse` (Synthetic grid warehouse): n = 50
  - `warehouse_movingai` (MovingAI automated warehouse MAPF benchmark): n = 50
- **Evaluation Trials**: N = 13,800 executed trials in extended LHS + OFAT grid (50 to 1,650 trials per method).

## Key Scientific Findings & Narrative Decision Rules

- **H1 (Recourse Efficacy (ACA vs ACA-d0))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = +4.14 (HL median diff = +3.33, 95% CI [2.22, 4.44], Cliff's delta = 0.241, adjusted p = 2.0865e-11). Verdict: **SUPPORTED (ACA SUPERIOR)**.
- **H2 (Level Execution (ACA vs cbba_lr))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = +2.14 (HL median diff = +1.90, 95% CI [1.11, 3.02], Cliff's delta = 0.114, adjusted p = 7.8864e-04). Verdict: **SIGNIFICANT DIFFERENCE (ACA HIGHER)**.
- **H2 (Level Execution (ACA vs cbba_partial_lr))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = +0.25 (HL median diff = +0.00, 95% CI [-0.83, 0.83], Cliff's delta = -0.015, adjusted p = 0.8836). Verdict: **PARITY (NO SIGNIFICANT DIFFERENCE)**.
- **H2 (Level Execution (ACA vs ssi_lr))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = +6.77 (HL median diff = +5.56, 95% CI [3.33, 7.78], Cliff's delta = 0.151, adjusted p = 1.0379e-06). Verdict: **SIGNIFICANT DIFFERENCE (ACA HIGHER)**.
- **H2_REGIME (Lossy Regime Resilience (p_drop in [0.2, 0.4]))** [N=50 instances; n=50 per family]: completion_rate_pct mean difference = +1.73 (HL median diff = +0.00, 95% CI [-1.67, 5.0], Cliff's delta = 0.089, adjusted p = 0.5073). Verdict: **NOT SUPPORTED / PARITY**.
- **H2_CTP (Comparator Evaluation (ACA vs CTP Replan))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = -4.86 (HL median diff = -3.61, 95% CI [-4.72, -2.53], Cliff's delta = -0.306, adjusted p = 2.2625e-15). Verdict: **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)**.
- **H2_IMPLICIT (Comparator Evaluation (ACA vs Implicit))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = -3.56 (HL median diff = -3.33, 95% CI [-3.33, -1.11], Cliff's delta = -0.257, adjusted p = 2.6663e-09). Verdict: **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)**.
- **H3 (Welfare Non-Inferiority (ACA vs best literature baseline: cbba_partial_lr))** [N=250 instances; n=50 per family]: net_welfare mean difference = -6.51 (HL median diff = -6.51, 95% CI [-20.73, 7.72], Cliff's delta = 0.008, adjusted p = 4.6707e-07). Verdict: **NON-INFERIOR / EQUIVALENT (SUPPORTED)**.
- **H4 (Pinsker Margin Safe Conflict Reduction)** [N=250 instances; n=50 per family]: safe_claim_conflicts mean difference = -4.85 (HL median diff = -4.83, 95% CI [-5.0, -4.667], Cliff's delta = -0.995, adjusted p = 4.4915e-42). Verdict: **SUPPORTED (SIGNIFICANT REDUCTION)**.
- **H4_COMPLETION (Pinsker Margin Completion Equivalence (TOST 5pp))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = +0.22 (HL median diff = +0.22, 95% CI [-0.58, 1.02], Cliff's delta = -0.005, adjusted p = 2.6665e-19). Verdict: **NON-INFERIOR / EQUIVALENT (SUPPORTED)**.
- **H5 (Bayesian Inference Advantage (ACA vs ACA-NoInference))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = -0.03 (HL median diff = +0.00, 95% CI [0.0, 0.0], Cliff's delta = -0.007, adjusted p = 0.5149). Verdict: **NOT SUPPORTED / PARITY**.
- **H6 (Communication Efficiency (ACA vs CBBA))** [N=250 instances; n=50 per family]: total_messages mean difference = -76.06 (HL median diff = -73.33, 95% CI [-89.33, -57.33], Cliff's delta = -0.347, adjusted p = 2.4262e-18). Verdict: **SUPPORTED (SIGNIFICANT REDUCTION)**.
- **H7 (Assumption 1 Empirical TV Adherence (TV <= eta_eff vs 0.90))** [N=250 instances; n=50 per family]: tv_bound_adherence_rate mean difference = -0.3395 (Bootstrap Mean = 0.5605, 95% CI [0.5318, 0.589], Cliff's delta = 0.000, adjusted p = 1.0000). Verdict: **NOT SUPPORTED (BELOW THRESHOLD)**.
- **H7_CONFLICT_FREE_RATE (Conflict-Free-Run Rate (0 Safe-Claim Conflicts))** [N=1,650 runs]: conflict_free_run_rate = 0.9824 (95% CI [0.9761, 1.0], Cliff's delta = 0.000). Verdict: **DESCRIPTIVE (98.24% CONFLICT-FREE)**.
- **H8 (Robustness on theta_4 (ACA vs best ctp_replan))** [N=250 instances; n=50 per family]: completion_rate_pct mean difference = -5.33 (HL median diff = -3.33, 95% CI [-3.33, -3.33], Cliff's delta = -0.280, adjusted p = 1.0870e-13). Verdict: **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)**.

### Step 4B Dedicated Methodological Analyses

#### 1. Baseline Comparator Evaluation: ACA vs CBBA-PR+LR (H2)
- **Statistical Significance Status**: NOT STATISTICALLY SIGNIFICANT under primary Holm step-down ($p_{\text{adj}} = 0.8836$), and Bonferroni ($p_{\text{bonf}} = 1.0000$).
- **Observed Effect**: Completion difference is +0.25 pp (HL median diff +0.00 [-0.83, 0.83]), showing that when CBBA-PR is equipped with identical local recourse execution (+LR), ACA and CBBA-PR+LR achieve approximate performance parity.
- **Per-Regime Breakdown**:
  - Nominal/Benign Comm: ACA 91.00% vs CBBA-PR+LR 90.45% (+0.55 pp difference)
  - Range-Constrained Comm: ACA 89.13% vs CBBA-PR+LR 87.47% (+1.67 pp difference)
  - Packet Loss Comm: ACA 83.80% vs CBBA-PR+LR 82.07% (+1.73 pp difference)

#### 2. Pinsker Claim Margin Efficacy & Cost Decomposition (H4)
- **Safe-Claim Conflict Reduction**: 32 total safe-claim conflicts for ACA vs 3,646 for ACA-no-margin (99.1% reduction; Wilcoxon $p = 5.6143e-43$).
- **Conflicts Per Claimed Task**: 0.0009 conflicts/safe claim (ACA) vs 3,646 safe conflicts (ACA-no-margin).
- **Total Conflicts (All Types)**: 67,999 (ACA) vs 35,581 (ACA-no-margin). ACA incurs negotiation conflicts during fallback consensus but isolates safe claims.
- **Conservative Deferral Rate**: ACA safely claims 36,024 tasks and conservatively defers 232,102 tasks to consensus negotiation (Deferral Rate: 86.56%).
- **Completion Preservation & Cost**: ACA completes 89.23% of tasks vs 90.68% for ACA-no-margin (-1.45 pp completion difference, reflecting the cost of conservative deferral). Equivalence confirmed via TOST within 5.0 pp margin ($p_{\text{TOST}} = 6.6663e-20$).

#### 3. Assumption 1 Empirical Total Variation Adherence (H7)
- **True TV Adherence vs $\eta_{\text{eff}}$**: Under dynamic blockages and packet drops, empirical total variation between true and estimated peer beliefs satisfies $\mathrm{TV}(B_s, \hat{B}_s) \le \eta_{\text{eff}}$ with an independent instance-level mean of 56.05% (Independent Instance Bootstrap 95% CI: [0.5318, 0.589]).
- **Hypothesis Test vs Pre-Declared Threshold 0.90**: **NOT SUPPORTED (BELOW THRESHOLD)** ($p = 1.0000$, one-sided Wilcoxon signed-rank test across independent instances). Assumption 1 is an idealized theoretical model that is frequently violated empirically, necessitating the conservative consensus fallback.
- **Theorem 1 Empirical Verification**: Across all claims where $\mathrm{TV} \le \eta_{\text{eff}}$, the empirical conflict rate is strictly 0.0% (0 conflicts), demonstrating that whenever Assumption 1 holds, local claims are empirically conflict-free.
- **Conflict-Free-Run Rate (Reported Separately as Distinct Descriptive Metric)**: Despite Assumption 1 violations, ACA achieves a **98.24% conflict-free-run rate** (1,621 of 1,650 ACA runs have 0 safe-claim conflicts; Clopper-Pearson 95% CI: [97.61%, 100.00%]), demonstrating that conservative margin inflation prevents coordination failures even under imperfect state estimation.

