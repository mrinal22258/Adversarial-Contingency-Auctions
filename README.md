# Belief-Divergence-Aware Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 46 Passing](https://img.shields.io/badge/tests-46%20passing-brightgreen.svg)]()
[![Validation: Tier A SITL](https://img.shields.io/badge/validation-Tier%20A%20SITL-blue.svg)]()

---

## 📌 Executive Summary
In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays.

**Belief-Divergence-Aware Contingency Auctions (ACA)** addresses these vulnerabilities through three mechanisms:
1. **Expected-Recourse Valuation (Theorem 1):** Robots bid their expected recourse cost over a depth-$d$ contingency branching policy under a Bayesian posterior over adversary types.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 3):** Tasks are claimed safely via a closed-form margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ derived from Pinsker's inequality and total variation triangle bounds, guaranteeing conflict-free safe claims under bounded belief estimation error without exchanging belief vectors.
3. **Local Detour Execution (Proposition 2):** Blockage encounters activate local precomputed detours with zero communication messages, resorting to market re-auctions only upon recourse tree exhaustion.

---

## 🏗 Repository Layout

```
acalib/
  env/        # Graph families (ER, RGG, Warehouse Grid), 2-state Markov blockages, adversaries theta_1-theta_4, comm network
  agents/     # Bayesian type filter, Theory of Mind tracker, Pinsker margin calculator, contingency planner, robot agent
  alloc/      # ACA-CBBA, ablations, CBBA (Choi '09), CBBA-PR (Adapted), CC-CBBA (Ponda '12), Implicit, SSI, Oracle
  sim/        # Discrete-event simulation engine, wall-clock metrics, and statistical logging
experiments/  # Configs, parallel sweep runner, bootstrap CIs, paired Wilcoxon + Holm-Bonferroni tests, LaTeX table & figure generators
tests/        # 28 unit, property-based, and Monte Carlo verification tests
results/      # Raw CSV trials, LaTeX tables, numbers macros, and publication PDF/PNG figures
```

---

## 🚀 Quickstart & Reproduction

### 1. Run Verification Test Suite
Run the 28 automated unit and property-based verification tests:
```powershell
pytest tests/ -v
```

### 2. Full Reproduction via Makefile
To rerun the complete experiment sweep, regenerate Table II, and generate publication figures:
```powershell
make reproduce
```
Or run individually:
```powershell
python experiments/run_sweep.py --workers 8
python experiments/make_tables.py
python experiments/make_figures.py
```

Outputs:
- `results/raw_results.csv`
- `results/table_main_results.tex`
- `results/table_main_results.md`
- `results/numbers.tex`
- `results/table_per_condition.csv`
- `results/fig_completion_conflicts.pdf` / `.png`
- `results/fig_welfare_messages.pdf` / `.png`

---

## 📊 Benchmark Summary

Main benchmark results across 5 graph topologies (MovingAI warehouse benchmark, Boston road network, RGG, Warehouse Grid, ER) and 4 adversary profiles ($N = 900$ Paired Trials per Method, 17,100 total trials, Mean $\pm$ 95% Bootstrap CI):

| Method | Literature Source | Completion (%) | Net Welfare | Distinct Conflicts | Total Conflicts | Messages | Runtime (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **ACA (Ours)** | This Work | **91.6 ± 0.8** | 886 ± 21 | 5.6 ± 0.2 | 35.5 ± 2.5 | 203 ± 9 | 25.59 ± 0.87 |
| ACA (No Margin Ablation) | Ablation (Consensus On) | 91.3 ± 0.8 | 861 ± 20$^\dagger$ | 8.0 ± 0.2$^\dagger$ | 51.4 ± 2.7$^\dagger$ | 214 ± 9$^\dagger$ | 16.09 ± 0.46$^\dagger$ |
| ACA (Depth-0 Ablation) | Ablation (No Recourse) | 87.4 ± 1.0$^\dagger$ | 893 ± 17 | 5.6 ± 0.2 | 33.5 ± 2.0 | 252 ± 9$^\dagger$ | 21.24 ± 0.72$^\dagger$ |
| ACA (Depth-2) | Ablation (Deep Recourse) | 91.8 ± 0.8 | 887 ± 21 | 5.5 ± 0.2 | 35.2 ± 2.6 | 201 ± 9 | 25.53 ± 0.87 |
| ACA (No Inference) | Ablation (Uniform Prior) | 91.5 ± 0.8 | 883 ± 21 | 5.6 ± 0.2 | 34.6 ± 2.6 | 203 ± 9 | 23.73 ± 0.78$^\dagger$ |
| ACA (Oracle Adversary) | Ablation (Known Type) | 91.2 ± 0.9 | 881 ± 22 | 5.4 ± 0.2 | 34.6 ± 2.6 | 200 ± 9 | 24.57 ± 0.88$^\dagger$ |
| CBBA | Choi et al. (IEEE T-RO 2009) | 84.4 ± 1.0$^\dagger$ | 870 ± 16$^\dagger$ | 8.3 ± 0.2$^\dagger$ | 51.4 ± 2.3$^\dagger$ | 277 ± 8$^\dagger$ | 14.35 ± 0.39$^\dagger$ |
| CBBA (+LR) | Level Execution | 89.9 ± 0.9$^\dagger$ | 859 ± 19$^\dagger$ | 8.3 ± 0.2$^\dagger$ | 54.5 ± 2.7$^\dagger$ | 232 ± 9$^\dagger$ | 14.70 ± 0.40$^\dagger$ |
| CBBA-PR (Adapted) | Buckman et al. (AIAA 2019) | 91.9 ± 0.7 | 950 ± 14$^\dagger$ | 8.3 ± 0.2$^\dagger$ | 62.5 ± 3.2$^\dagger$ | 251 ± 9$^\dagger$ | 15.69 ± 0.43$^\dagger$ |
| CBBA-PR (+LR) | Level Execution | 91.2 ± 0.8 | 864 ± 19$^\dagger$ | 8.3 ± 0.2$^\dagger$ | 56.3 ± 2.9$^\dagger$ | 221 ± 9$^\dagger$ | 15.10 ± 0.42$^\dagger$ |
| CC-CBBA | Ponda et al. (IEEE TCST 2012) | 82.9 ± 1.2$^\dagger$ | 886 ± 17 | 7.4 ± 0.2$^\dagger$ | 46.9 ± 2.2$^\dagger$ | 277 ± 8$^\dagger$ | 20.94 ± 0.61$^\dagger$ |
| CC-CBBA (+LR) | Level Execution | 88.2 ± 1.0$^\dagger$ | 893 ± 19 | 7.3 ± 0.2$^\dagger$ | 50.2 ± 2.6$^\dagger$ | 237 ± 9$^\dagger$ | 20.06 ± 0.58$^\dagger$ |
| SSI | Koenig et al. (AAAI 2006) | 84.2 ± 1.2$^\dagger$ | 668 ± 22$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 292 ± 11$^\dagger$ | 7.88 ± 0.24$^\dagger$ |
| SSI (+LR) | Level Execution | 82.8 ± 1.3$^\dagger$ | 581 ± 26$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 249 ± 11$^\dagger$ | 7.85 ± 0.23$^\dagger$ |
| CTP Replan | Replan on Discovery | 97.3 ± 0.4$^\dagger$ | 849 ± 21$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 76 ± 3$^\dagger$ | 7.33 ± 0.24$^\dagger$ |
| CBBA Belief Gossip | Full Belief Exchange | 84.0 ± 1.1$^\dagger$ | 864 ± 16$^\dagger$ | 8.4 ± 0.2$^\dagger$ | 51.3 ± 2.4$^\dagger$ | 274 ± 8$^\dagger$ | 14.76 ± 0.40$^\dagger$ |
| Implicit (No Consensus) | Alighanbari & How (ACC 2005) | 96.4 ± 0.5$^\dagger$ | 745 ± 20$^\dagger$ | 11.5 ± 0.2$^\dagger$ | 111.0 ± 3.9$^\dagger$ | 0 ± 0$^\dagger$ | 12.11 ± 0.37$^\dagger$ |
| Pessimistic Robust | Unblockable Corridors | 11.6 ± 0.5$^\dagger$ | 173 ± 8$^\dagger$ | 0.1 ± 0.0$^\dagger$ | 0.1 ± 0.0$^\dagger$ | 323 ± 0$^\dagger$ | 35.11 ± 0.97$^\dagger$ |
| Full-Info Matching (Oracle) | Ground-Truth Matching Bound | 97.1 ± 0.5$^\dagger$ | 910 ± 24$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0 ± 0$^\dagger$ | 10.03 ± 0.33$^\dagger$ |

*$^\dagger$ indicates statistically significant difference vs. ACA ($p < 0.05$, paired Wilcoxon signed-rank test with Holm–Bonferroni correction).*

---

## 📜 Citation
```bibtex
@article{mrinal2026aca,
  author  = {Mrinal, Kumar},
  title   = {Belief-Divergence-Aware Contingency Auctions for Decentralized Multi-Robot Task Allocation under Strategic Blockages},
  journal = {IEEE Robotics and Automation Letters},
  year    = {2026}
}
```
