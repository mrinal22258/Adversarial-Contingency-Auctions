# Physics-Based Software-in-the-Loop (SITL) vs. Graph Simulation Report

> **DISCLAIMER**: Everything reported herein is SOFTWARE SIMULATION in PyBullet. No physical robots were used.

- **Total Independent Trials**: 1440 completed, 0 failed
- **Git Commit**: `8bbe703c6747811aefe07bc71bad3e1b89e5ea81`

## 1. Method Performance Summary in Physical SITL

| Method | Trials | Completion Rate [%] | Welfare | Messages | Recourses | Collisions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `aca` | 240 | 71.61 ± 20.06 | 261.1 | 38.5 | 186.0 | 185.97 |
| `aca_no_margin` | 240 | 73.54 ± 17.01 | 221.5 | 38.6 | 175.8 | 175.76 |
| `cbba_partial_lr` | 240 | 72.50 ± 19.45 | 225.7 | 42.8 | 178.8 | 178.75 |
| `ctp_replan` | 240 | 65.47 ± 20.03 | 244.3 | 25.5 | 0.0 | 152.91 |
| `implicit` | 240 | 75.78 ± 18.76 | 172.5 | 50.1 | 0.0 | 235.15 |
| `ssi_lr` | 240 | 36.30 ± 22.91 | 95.2 | 42.0 | 121.7 | 121.71 |

## 2. Ranking Preservation Analysis

- **Graph-Sim Ranking (Completion)**: `ctp_replan > implicit > aca_no_margin > aca > cbba_partial_lr > ssi_lr`
- **SITL Physics Ranking (Completion)**: `implicit > aca_no_margin > cbba_partial_lr > aca > ctp_replan > ssi_lr`
- **Spearman Rank Correlation**: $\rho = 0.371$ ($p = 0.4685$)
- **Kendall's $\tau$**: $\tau = 0.333$ ($p = 0.4694$)
- **Preserved**: `NO (Rank inversions present)`

## 3. Bland-Altman Agreement

- **Mean Difference (Bias)**: -26.00%
- **95% Limits of Agreement**: [-52.13%, 0.13%]
- **Interpretation**: Physical SITL simulation exhibits a mean bias of -26.00% relative to abstract graph simulation (95% Limits of Agreement: [-52.13%, 0.13%]). Performance differences reflect continuous physical execution, sensor/odometry drift, and dynamic obstacle avoidance.

## 4. Paired SITL Method Comparisons vs ACA

| Comparison | N Pairs | Mean Diff [%] | Median Diff [%] | Wilcoxon Stat | p-value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `aca_vs_aca_no_margin` | 240 | -1.93 | +0.00 | 7225.0 | 1.8326e-01 |
| `aca_vs_cbba_partial_lr` | 240 | -0.89 | +0.00 | 8011.0 | 6.5360e-01 |
| `aca_vs_ctp_replan` | 240 | +6.15 | +12.50 | 8294.0 | 2.0151e-03 |
| `aca_vs_implicit` | 240 | -4.17 | +0.00 | 8097.5 | 1.1808e-02 |
| `aca_vs_ssi_lr` | 240 | +35.31 | +37.50 | 1616.5 | 4.4526e-31 |
