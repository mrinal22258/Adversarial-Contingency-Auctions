# Software-in-the-Loop (SITL) Physics Simulation vs. Discrete Graph Simulation

> **DISCLAIMER**: Everything reported herein is SOFTWARE SIMULATION in PyBullet rigid-body physics. No physical robots were used.

- **Git Commit**: `ef65b7dbd87f26912eed57d707b3f59fc9a1849e`
- **Matched Paired Instances**: 2160 trials across 18 cells (warehouse_movingai & road_osmnx, 3 adversaries, 3 regimes: nominal, constrained, lossy)

## 1. Method Performance in Physical SITL vs. Discrete Graph Simulation

| Method | SITL Comp. [%] | Graph Comp. [%] | Domain Gap [pp] | Gap 95% HL CI | Gap Wilcoxon $p$ (Holm) | Collisions (events/trial) | Conflicts |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `aca` | 69.4 ± 20.3 | 88.4 ± 16.7 | -18.9 | [-18.8, -18.8] | 2.0466e-44 | 158.6 | 37.5 |
| `aca_no_margin` | 68.6 ± 20.4 | 88.6 ± 14.9 | -20.1 | [-18.8, -18.8] | 2.6550e-45 | 171.7 | 66.5 |
| `cbba_partial_lr` | 68.8 ± 19.4 | 90.3 ± 13.7 | -21.5 | [-25.0, -18.8] | 4.2192e-47 | 194.7 | 70.0 |
| `ctp_replan` | 68.4 ± 20.8 | 91.3 ± 15.7 | -22.9 | [-25.0, -18.8] | 5.4338e-47 | 142.3 | 0.0 |
| `implicit` | 74.9 ± 19.5 | 92.1 ± 13.7 | -17.2 | [-18.8, -12.5] | 1.1097e-43 | 199.8 | 168.6 |
| `ssi_lr` | 42.2 ± 25.4 | 72.2 ± 30.1 | -30.1 | [-31.2, -25.0] | 1.2091e-48 | 143.6 | 0.0 |

## 2. Ranking Preservation Analysis

- **Graph Simulation Ranking**: `implicit > ctp_replan > cbba_partial_lr > aca_no_margin > aca > ssi_lr`
- **SITL Physics Ranking**: `implicit > aca > cbba_partial_lr > aca_no_margin > ctp_replan > ssi_lr`
- **Spearman Rank Correlation**: $\rho = 0.486$ ($p = 3.2872e-01$)
- **Kendall's Rank Correlation**: $\tau = 0.333$ ($p = 4.6944e-01$)
- **Strict Ranking Preserved**: `NO (Rank inversions present)`

## 3. Bland-Altman Agreement on Matched Instances

- **Matched Pairs**: $N = 2160$
- **Mean Bias (SITL - Graph)**: -21.78 pp
- **Standard Deviation of Difference**: 20.01 pp
- **95% Limits of Agreement**: [-61.00 pp, +17.45 pp]
- **Interpretation**: Physical SITL simulation exhibits a mean bias of -21.78 pp relative to matched discrete graph simulation (95% Limits of Agreement: [-61.00 pp, 17.45 pp]). Differences reflect continuous unicycle kinematics, barrier obstacle interactions, and odometric drift.

## 4. Paired Comparisons vs ACA in SITL Physics (Holm-Corrected)

| Comparison | N Pairs | Mean Diff [pp] | HL Median Diff [pp] | HL 95% CI | Wilcoxon Stat | Raw $p$ | Holm-Adjusted $p$ | Sig ($\alpha=0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `aca_vs_aca_no_margin` | 360 | +0.87 | +0.00 | [+0.00, +0.00] | 7491.5 | 2.7860e-01 | 8.3581e-01 | NO |
| `aca_vs_cbba_partial_lr` | 360 | +0.62 | +0.00 | [+0.00, +0.00] | 11239.5 | 5.1508e-01 | 8.3581e-01 | NO |
| `aca_vs_ctp_replan` | 360 | +1.04 | +0.00 | [+0.00, +6.25] | 16836.5 | 2.8980e-01 | 8.3581e-01 | NO |
| `aca_vs_implicit` | 360 | -5.42 | -6.25 | [-6.25, +0.00] | 7624.0 | 5.9975e-08 | 2.3990e-07 | YES |
| `aca_vs_ssi_lr` | 360 | +27.29 | +31.25 | [+25.00, +31.25] | 4487.0 | 7.3603e-39 | 3.6802e-38 | YES |

## 5. Physical Collisions Metric Definition and Recourse Check

- **Definition**: Rigid-body continuous surface contact events detected in PyBullet simulation (p.getContactPoints > 0) between robot chassis/wheels and static boundary or dynamic blockage barriers.
- **Units**: contact events per trial
- **Distinction from Conflicts**: Physical collisions measure spatial barrier contacts in continuous physics. Abstract conflicts measure combinatorial double-claims in the decentralized task allocation market.
- **Total Events Observed**: 363773
- **Mean Events per Trial**: 168.41
- **Correlation with Recourse Detours**: Physical collision contacts correlate with recourse detours (r = 0.775, p = 0.0000e+00; rho = 0.747, p = 0.0000e+00), confirming that barrier contacts correspond to detected blockage events that trigger contingency branch executions.
