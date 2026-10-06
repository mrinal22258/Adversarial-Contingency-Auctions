# Belief-Divergence-Aware Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 28 Passing](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)]()

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

Main benchmark results across 3 graph topologies and 4 adversary profiles ($N = 120$ Paired Trials per Method, Mean $\pm$ 95% Bootstrap CI):

| Method | Literature Source | Completion (%) | Distinct Conflicts | Total Conflicts | Messages | Net Welfare | Runtime (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| ACA (Ours) | This Work | 81.6 ± 3.0 | 5.7 ± 0.6 | 36.2 ± 9.5 | 342 ± 22 | 743 ± 61 | 29.36 ± 2.97 |
| ACA (No Margin Ablation) | Ablation (Consensus On) | 83.2 ± 3.3 | 5.4 ± 0.6 | 32.3 ± 9.3 | 306 ± 26 | 805 ± 69$^\dagger$ | 19.00 ± 1.21$^\dagger$ |
| ACA (Depth-0 Ablation) | Ablation (No Recourse) | 69.4 ± 3.3$^\dagger$ | 5.7 ± 0.6 | 29.2 ± 5.6 | 377 ± 17$^\dagger$ | 708 ± 47$^\dagger$ | 23.73 ± 2.51$^\dagger$ |
| CBBA | Choi et al. (IEEE T-RO 2009) | 68.6 ± 3.5$^\dagger$ | 5.7 ± 0.6 | 28.0 ± 5.6 | 376 ± 18$^\dagger$ | 724 ± 47 | 13.45 ± 1.05$^\dagger$ |
| CBBA-PR (Adapted) | Buckman et al. (AIAA 2019) | 82.1 ± 3.1 | 5.7 ± 0.6 | 40.3 ± 10.0 | 353 ± 25$^\dagger$ | 864 ± 49$^\dagger$ | 14.96 ± 1.20$^\dagger$ |
| CC-CBBA | Ponda et al. (IEEE TCST 2012) | 75.4 ± 3.1$^\dagger$ | 4.4 ± 0.5$^\dagger$ | 27.2 ± 6.4$^\dagger$ | 371 ± 18 | 829 ± 53$^\dagger$ | 19.30 ± 1.10$^\dagger$ |
| Implicit (No Consensus) | Alighanbari & How (ACC 2005) | 94.0 ± 2.2$^\dagger$ | 11.1 ± 0.5$^\dagger$ | 135.7 ± 12.7$^\dagger$ | 0 ± 0$^\dagger$ | 634 ± 70$^\dagger$ | 14.35 ± 1.20$^\dagger$ |
| SSI | Koenig et al. (AAAI 2006) | 97.7 ± 1.2$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 107 ± 15$^\dagger$ | 926 ± 55$^\dagger$ | 6.99 ± 0.57$^\dagger$ |
| Pessimistic Robust | Unblockable Corridors | 6.9 ± 1.1$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 363 ± 1 | 103 ± 17$^\dagger$ | 32.39 ± 2.37$^\dagger$ |
| Full-Info Matching (Oracle) | Ground-Truth Matching Bound | 96.7 ± 1.3$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0 ± 0$^\dagger$ | 829 ± 72$^\dagger$ | 8.53 ± 0.70$^\dagger$ |

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
