# Physics-Based Software-in-the-Loop (SITL) vs. Graph Simulation Report

> **DISCLAIMER**: Everything reported herein is SOFTWARE SIMULATION in PyBullet. No physical robots were used.

- **Total Independent Trials**: 1440 completed, 0 failed
- **Git Commit**: `d11295d439a4f3cb73ed98889a395377b71067c6`

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

- **Graph-Sim Ranking (Completion)**: `ctp_replan > implicit > aca > aca_no_margin > cbba_partial_lr > ssi_lr`
- **SITL Physics Ranking (Completion)**: `implicit > aca_no_margin > cbba_partial_lr > aca > ctp_replan > ssi_lr`
- **Spearman Rank Correlation**: $\rho = 0.257$ ($p = 0.6228$)
- **Kendall's $\tau$**: $\tau = 0.200$ ($p = 0.7194$)
- **Preserved**: `NO (Rank inversions present)`

## 3. Bland-Altman Agreement

- **Mean Difference (Bias)**: -14.25%
- **95% Limits of Agreement**: [-35.77%, 7.28%]
- **Interpretation**: Physical SITL simulation exhibits a mean bias of -14.25% relative to abstract graph simulation (95% Limits of Agreement: [-35.77%, 7.28%]). Performance differences reflect continuous physical execution, sensor/odometry drift, and dynamic obstacle avoidance.
