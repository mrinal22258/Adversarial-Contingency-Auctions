# Physics-Based Software-in-the-Loop (SITL) vs. Graph Simulation Report

> **DISCLAIMER**: Everything reported herein is SOFTWARE SIMULATION in PyBullet. No physical robots were used.

- **Total Independent Trials**: 1418 completed, 22 failed
- **Git Commit**: `75f7492d31b530324d85c7f87c869a08b4728d14`

## 1. Method Performance Summary in Physical SITL

| Method | Trials | Completion Rate [%] | Welfare | Messages | Recourses | Collisions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `aca` | 234 | 0.80 ± 3.48 | 6.2 | 39.7 | 0.0 | 0.00 |
| `aca_no_margin` | 237 | 1.05 ± 3.67 | 8.3 | 37.5 | 0.0 | 0.00 |
| `cbba_partial_lr` | 237 | 1.05 ± 3.84 | 8.2 | 42.6 | 0.0 | 0.00 |
| `ctp_replan` | 236 | 0.26 ± 2.14 | 1.9 | 42.0 | 0.0 | 0.00 |
| `implicit` | 236 | 0.69 ± 2.86 | 5.3 | 37.4 | 0.0 | 0.00 |
| `ssi_lr` | 238 | 0.11 ± 1.14 | 0.6 | 40.5 | 0.0 | 0.00 |

## 2. Ranking Preservation Analysis

- **Graph-Sim Ranking (Completion)**: `ctp_replan > implicit > aca > aca_no_margin > cbba_partial_lr > ssi_lr`
- **SITL Physics Ranking (Completion)**: `cbba_partial_lr > aca_no_margin > aca > implicit > ctp_replan > ssi_lr`
- **Spearman Rank Correlation**: $\rho = -0.116$ ($p = 0.8268$)
- **Kendall's $\tau$**: $\tau = -0.276$ ($p = 0.4442$)
- **Preserved**: `NO (Rank inversions present)`

## 3. Bland-Altman Agreement

- **Mean Difference (Bias)**: -79.46%
- **95% Limits of Agreement**: [-93.95%, -64.96%]
- **Interpretation**: Physical SITL simulation exhibits a mean bias of -79.46% relative to abstract graph simulation (95% Limits of Agreement: [-93.95%, -64.96%]), reflecting differential-drive kinematics, turning latency, and collision deceleration.
