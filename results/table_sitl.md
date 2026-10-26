### SITL Physics Simulation vs. Discrete Graph Simulation ($N = 360$ Total Trials Across 60 Paired Physical Instances for 6 Methods)

| Method | SITL Comp. (%) | Graph Comp. (%) | Domain Gap (pp) | Net Welfare | Contacts | Conflicts | vs. ACA ($p$) |
|:-------|:--------------:|:---------------:|:---------------:|:-----------:|:--------:|:---------:|:-------------:|
| **ACA (Ours)** | 69.4 ± 20.3 | 88.4 ± 16.7 | -18.9 | 261 ± 18 | 158.6 ± 36.2 | 37.5 ± 3.5 | -- |
| ACA (No Margin Ablation) | 68.6 ± 20.4 | 88.6 ± 14.9 | -20.1 | 224 ± 18 | 171.7 ± 40.2 | 66.5 ± 5.0 | 0.8358 |
| CBBA-PR (+LR) | 68.8 ± 19.4 | 90.3 ± 13.7 | -21.5 | 222 ± 18 | 194.7 ± 41.2 | 70.0 ± 5.3 | 0.8358 |
| CTP Replan | 68.4 ± 20.8 | 91.3 ± 15.7 | -22.9 | 263 ± 20 | 142.3 ± 38.0 | 0.0 | 0.8358 |
| Implicit (No Consensus) [Alighanbari '05] | 74.9 ± 19.5 | 92.1 ± 13.7 | -17.2 | 159 ± 21 | 199.8 ± 41.9 | 168.6 ± 3.8 | < 10^{-4} |
| SSI (+LR) | 42.2 ± 25.4 | 72.2 ± 30.1 | -30.1 | 133 ± 18 | 143.6 ± 34.4 | 0.0 | < 10^{-4} |
