# Belief-Divergence-Aware Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 27 Passing](https://img.shields.io/badge/tests-27%20passing-brightgreen.svg)]()

---

## 📌 Executive Summary
In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays.

**Belief-Divergence-Aware Contingency Auctions (ACA)** resolves these vulnerabilities through three theoretical mechanisms:
1. **Expected-Recourse Valuation (Theorem 1):** Robots bid their expected recourse cost over a depth-$d$ contingency branching policy under a Bayesian posterior over adversary types.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 3):** Tasks are claimed safely via a closed-form margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ derived from Pinsker's inequality and total variation triangle bounds, guaranteeing conflict-free safe claims under bounded belief estimation error without exchanging belief vectors.
3. **Bounded Re-Auctions via Local Recourse (Theorem 4):** Blockage encounters trigger local recourse branch pivots with **zero communication messages**, triggering re-auctions only upon recourse tree exhaustion.

---

## 🏗 Repository Layout

```
acalib/
  env/        # Graph families (ER, RGG, Warehouse Grid), 2-state Markov blockages, adversaries theta_1-theta_4, comm network
  agents/     # Bayesian type filter, Theory of Mind tracker, Pinsker margin calculator, contingency planner, robot agent
  alloc/      # ACA-CBBA, CBBA (Choi '09), CBBA-Partial (Buckman '19), CC-CBBA (Ponda '12), Implicit (Alighanbari '05), SSI, Oracle
  sim/        # Discrete-event simulation engine, wall-clock metrics, and statistical logging
experiments/  # Configs, parallel sweep runner, bootstrap CIs, paired Wilcoxon + Holm-Bonferroni tests, LaTeX table & figure generators
tests/        # 27 unit, property-based, and Monte Carlo verification tests
results/      # Raw CSV trials, LaTeX tables, and publication PDF/PNG figures
```

---

## 🚀 Quickstart & Reproduction

### 1. Run Verification Test Suite
Run the 27 automated unit and property-based verification tests (including Monte Carlo verification of Theorem 1 and conflict-freedom proof of Theorem 3):
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
- `results/table_per_condition.csv`
- `results/fig_completion_conflicts.pdf` / `.png`
- `results/fig_welfare_messages.pdf` / `.png`

---

## 📊 Benchmark Summary

Main benchmark results across 3 graph topologies and 4 adversary profiles ($N = 120$ Paired Trials per Method, Mean $\pm$ 95% Bootstrap CI):

| Method | Literature Source | Completion (%) | Distinct Conflicts | Total Conflicts | Messages | Net Welfare | Runtime (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **ACA (Ours)** | **This Work** | **81.6 ± 3.0** | **5.7 ± 0.6** | **36.2 ± 9.5** | **342 ± 22** | **743 ± 61** | **44.54 ± 7.19** |
| CBBA | Choi et al. (IEEE T-RO 2009) | 68.6 ± 3.5$^\dagger$ | 5.7 ± 0.6 | 28.0 ± 5.6 | 376 ± 18$^\dagger$ | 724 ± 47 | 20.98 ± 4.32$^\dagger$ |
| CBBA-Partial | Buckman et al. (IEEE T-RO 2019) | 82.1 ± 3.1 | 5.7 ± 0.6 | 40.3 ± 10.0 | 353 ± 25$^\dagger$ | 864 ± 49$^\dagger$ | 23.42 ± 4.32$^\dagger$ |
| CC-CBBA | Ponda et al. (IEEE TCST 2012) | 75.4 ± 3.1$^\dagger$ | 4.4 ± 0.5$^\dagger$ | 27.2 ± 6.4$^\dagger$ | 371 ± 18 | 829 ± 53$^\dagger$ | 28.63 ± 3.56$^\dagger$ |
| Implicit (No Margin) | Alighanbari & How (ACC 2005) | 94.0 ± 2.2$^\dagger$ | 11.1 ± 0.5$^\dagger$ | 135.7 ± 12.7$^\dagger$ | 0 ± 0$^\dagger$ | 634 ± 70$^\dagger$ | 20.72 ± 2.81$^\dagger$ |
| SSI | Koenig et al. (AAAI 2006) | 97.7 ± 1.2$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 107 ± 15$^\dagger$ | 926 ± 55$^\dagger$ | 10.49 ± 1.73$^\dagger$ |
| Pessimistic Robust | Unblockable Corridors | 6.9 ± 1.1$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 363 ± 1 | 103 ± 17$^\dagger$ | 43.89 ± 4.97$^\dagger$ |
| Centralized Oracle | Full-Info Hungarian Matching | 95.2 ± 1.6$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0.0 ± 0.0$^\dagger$ | 0 ± 0$^\dagger$ | 626 ± 79$^\dagger$ | 12.19 ± 1.65$^\dagger$ |

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
