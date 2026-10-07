# RESULTS_VERDICT.md: Empirical Verdict for Hypotheses H1-H8

**Strict Rule R5**: Every claim in the paper maps directly to an entry below.
Generated directly from executed raw runs and independent instance-level tests.

| ID | Title | Metric | Mean Diff | HL Median [95% CI] | Cliff's Delta | Raw p | Holm Adj p | Verdict |
|---|---|---|---|---|---|---|---|---|
| H1 | Recourse Efficacy (ACA vs ACA-d0) | completion_rate_pct | 3.62 | 3.33 [1.94, 4.72] | 0.238 | 4.4433e-06 | 2.6660e-05 | **SUPPORTED (ACA SUPERIOR)** |
| H2 | Level Execution (ACA vs cbba_lr) | completion_rate_pct | 3.67 | 3.61 [1.94, 5.28] | 0.194 | 8.9400e-05 | 4.4700e-04 | **SIGNIFICANT DIFFERENCE (ACA HIGHER)** |
| H2 | Level Execution (ACA vs cbba_partial_lr) | completion_rate_pct | 1.93 | 1.94 [0.28, 3.61] | 0.11 | 0.0231 | 0.0694 | **PARITY (NO SIGNIFICANT DIFFERENCE)** |
| H2 | Level Execution (ACA vs ssi_lr) | completion_rate_pct | 9.02 | 8.06 [3.89, 12.22] | 0.246 | 1.2571e-04 | 5.0285e-04 | **SIGNIFICANT DIFFERENCE (ACA HIGHER)** |
| H3 | Welfare Non-Inferiority (ACA vs best cbba_partial) | net_welfare | -65.44 | -65.44 [-92.7, -38.18] | -0.113 | 0.8684 | 0.8684 | **NOT EQUIVALENT / INCONCLUSIVE** |
| H4 | Margin Conflict Impact (ACA vs ACA-NoMargin) | completion_rate_pct | -1.53 | -1.11 [-2.22, -0.0] | -0.088 | 0.0379 | 0.0758 | **PARITY (NO SIGNIFICANT DIFFERENCE)** |
| H5 | Bayesian Inference Advantage (ACA vs ACA-NoInference) | completion_rate_pct | -0.47 | -0.28 [-1.11, 0.56] | 0.015 | 0.7861 | 0.7861 | **NOT SUPPORTED / PARITY** |
| H6 | Communication Efficiency (ACA vs CBBA) | total_messages | -82.81 | -82.67 [-99.33, -66.0] | -0.474 | 5.4738e-12 | 1.0948e-11 | **REJECTED (BASELINE SUPERIOR)** |
| H7 | Assumption 1 Empirical Adherence Rate | tv_bound_adherence_rate | 0.0822 | 0.9822 [0.9731, 1.0] | 0.0 | 3.2773e-23 | 1.3109e-22 | **SUPPORTED (ACA SUPERIOR)** |
| H8 | Robustness on theta_4 (ACA vs best clairvoyant_greedy) | completion_rate_pct | -7.47 | -5.56 [-7.78, -4.44] | -0.631 | 3.6923e-10 | 4.9231e-10 | **SIGNIFICANT DIFFERENCE (COMPARATOR HIGHER)** |

## Key Scientific Findings & Narrative Decision Rule

- **H1 (Recourse Efficacy (ACA vs ACA-d0))** [n=75]: completion_rate_pct mean difference = +3.62 (HL median diff = +3.33, 95% CI [1.94, 4.72], Cliff's delta = 0.238, adjusted p = 2.6660e-05). Result is statistically significant at alpha=0.05.
- **H2 (Level Execution (ACA vs cbba_lr))** [n=75]: completion_rate_pct mean difference = +3.67 (HL median diff = +3.61, 95% CI [1.94, 5.28], Cliff's delta = 0.194, adjusted p = 4.4700e-04). Result is statistically significant at alpha=0.05.
- **H2 (Level Execution (ACA vs cbba_partial_lr))** [n=75]: completion_rate_pct mean difference = +1.93 (HL median diff = +1.94, 95% CI [0.28, 3.61], Cliff's delta = 0.110, adjusted p = 0.0694). Result is not statistically significant at alpha=0.05.
- **H2 (Level Execution (ACA vs ssi_lr))** [n=75]: completion_rate_pct mean difference = +9.02 (HL median diff = +8.06, 95% CI [3.89, 12.22], Cliff's delta = 0.246, adjusted p = 5.0285e-04). Result is statistically significant at alpha=0.05.
- **H3 (Welfare Non-Inferiority (ACA vs best cbba_partial))** [n=75]: net_welfare mean difference = -65.44 (HL median diff = -65.44, 95% CI [-92.7, -38.18], Cliff's delta = -0.113, adjusted p = 0.8684). Result is not statistically significant at alpha=0.05.
- **H4 (Margin Conflict Impact (ACA vs ACA-NoMargin))** [n=75]: completion_rate_pct mean difference = -1.53 (HL median diff = -1.11, 95% CI [-2.22, -0.0], Cliff's delta = -0.088, adjusted p = 0.0758). Result is not statistically significant at alpha=0.05.
- **H5 (Bayesian Inference Advantage (ACA vs ACA-NoInference))** [n=75]: completion_rate_pct mean difference = -0.47 (HL median diff = -0.28, 95% CI [-1.11, 0.56], Cliff's delta = 0.015, adjusted p = 0.7861). Result is not statistically significant at alpha=0.05.
- **H6 (Communication Efficiency (ACA vs CBBA))** [n=75]: total_messages mean difference = -82.81 (HL median diff = -82.67, 95% CI [-99.33, -66.0], Cliff's delta = -0.474, adjusted p = 1.0948e-11). Result is statistically significant at alpha=0.05.
- **H7 (Assumption 1 Empirical Adherence Rate)** [n=900]: tv_bound_adherence_rate mean difference = +0.08 (HL median diff = +0.98, 95% CI [0.9731, 1.0], Cliff's delta = 0.000, adjusted p = 1.3109e-22). Result is statistically significant at alpha=0.05.
- **H8 (Robustness on theta_4 (ACA vs best clairvoyant_greedy))** [n=75]: completion_rate_pct mean difference = -7.47 (HL median diff = -5.56, 95% CI [-7.78, -4.44], Cliff's delta = -0.631, adjusted p = 4.9231e-10). Result is statistically significant at alpha=0.05.
