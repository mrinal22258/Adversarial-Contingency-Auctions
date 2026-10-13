# Bayesian Belief Probability Calibration Report

- **Evaluated Samples:** 27,090
- **Overall Brier Score:** 0.1231
- **Expected Calibration Error (ECE):** 0.2578

## Adversary-Specific Calibration Breakdown

| Adversary Type | Samples | Brier Score | Mean Forecast | Realized Blockage Rate |
|---|---|---|---|---|
| `theta_1_stochastic` | 9,030 | 0.1269 | 0.3142 | 0.0507 |
| `theta_2_reactive` | 9,030 | 0.1149 | 0.3022 | 0.0410 |
| `theta_3_budgeted_interdiction` | 9,030 | 0.1274 | 0.3223 | 0.0518 |

## Reliability Diagram Bins

| Bin Center | Empirical Frequency | Observation Count |
|---|---|---|
| 0.05 | 0.0000 | 0 |
| 0.15 | 0.0000 | 0 |
| 0.25 | 0.0372 | 20,755 |
| 0.35 | 0.0367 | 1,579 |
| 0.45 | 0.0556 | 1,510 |
| 0.55 | 0.0813 | 2,927 |
| 0.65 | 0.5833 | 48 |
| 0.75 | 0.2463 | 134 |
| 0.85 | 0.6058 | 137 |
| 0.95 | 0.0000 | 0 |
