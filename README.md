# Adversarial Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 60 Passing](https://img.shields.io/badge/tests-60%20passing-brightgreen.svg)]()
[![Simulation: Pure Software](https://img.shields.io/badge/simulation-pure%20software-informational.svg)]()

---

## 📌 Executive Summary
In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays.

**Adversarial Contingency Auctions (ACA)** addresses these vulnerabilities through three mechanisms:
1. **Expected-Recourse Valuation (Theorem 1):** Robots bid their expected recourse cost over a depth-$d$ contingency branching policy under a Bayesian posterior over adversary types.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 3):** Tasks are claimed safely via a closed-form margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ derived from Pinsker's inequality and total variation triangle bounds, guaranteeing conflict-free safe claims under bounded belief estimation error without exchanging belief vectors.
3. **Local Detour Execution (Proposition 2):** Blockage encounters activate local precomputed detours with zero communication messages, resorting to market re-auctions only upon recourse tree exhaustion.

---

## 🔬 What This Repository Shows (Key Scientific Findings)

This repository implements a rigorous, pre-registered empirical benchmark ($N = 17,100$ total trials across 15 seeds $\times$ 5 graph families $\times$ 4 adversary profiles $\times$ 3 communication regimes) comparing ACA against literature baselines, level-execution variants (+LR), and clean ablations:

1. **ACA vs. Standard CBBA:** Under dynamic corridor blockages, standard CBBA achieves only $78.0 \pm 1.3\%$ completion while generating $328 \pm 9$ messages. ACA achieves **$88.8 \pm 1.0\%$ completion** ($+10.8$ percentage points, Cliff's $\delta = 0.36$) while requiring only **$245 \pm 9$ messages** ($-83$ messages, $p = 1.09 \times 10^{-11}$).
2. **Mechanism Attribution:** Disabling local contingency recourse (ACA Depth-0) drops completion to $85.2 \pm 1.0\%$ ($p = 2.67 \times 10^{-5}$), confirming that local detour evaluation drives ACA's completion advantage.
3. **Pinsker Safe Claim Behavior:** The Pinsker margin operates conservatively ($11.2\%$ safe claim rate, $88.8\%$ deferred to consensus). Safe claims maintain conflict-freedom under bounded error as predicted by Theorem 1.
4. **Honest Comparative Trade-offs:** 
   - **CBBA-PR (Partial Release)** preserves unblocked routes, achieving higher net welfare ($940 \pm 16$ vs $874 \pm 22$).
   - **CTP Replan** and the **Clairvoyant Greedy reference** achieve higher completion ($95.8\%$ and $96.5\%$) via continuous single-robot replanning, trading off decentralized bundle coordination.

All empirical data is generated automatically with zero hand-typed numbers:
- Auto-generated Markdown Table: [`results/table_main_results.md`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_main_results.md)
- Auto-generated LaTeX Table: [`results/table_main_results.tex`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_main_results.tex)
- Pre-registered Hypothesis Verdict: [`RESULTS_VERDICT.md`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/RESULTS_VERDICT.md)
- Raw Trial Logs: [`results/raw_results.csv`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/raw_results.csv) (17,100 records)

---

## 🏗 Repository Layout

```
acalib/
  env/        # Real maps (MovingAI warehouse, OSMnx Boston), synthetic models, adversary models
  agents/     # Bayesian type filter, Theory of Mind tracker, Pinsker margin calculator, contingency planner
  alloc/      # ACA-CBBA, ablations, CBBA (Choi '09), CBBA-PR, CC-CBBA, Implicit, SSI, Foresight Opt (CP-SAT)
  sim/        # Simulation engine, wall-clock metrics, and statistical logging
experiments/  # Parallel sweep runner, bootstrap CIs, paired Wilcoxon + Holm-Bonferroni tests, figures/tables
tests/        # 60 automated verification and regression tests
results/      # Raw CSV trials, LaTeX tables, numbers macros, and publication PDF/PNG figures
```

---

## 🚀 Quickstart & Reproduction

### 1. Run Verification Test Suite
Run the 60 automated unit, property-based, and regression tests:
```powershell
pytest tests/ -v
```

### 2. Full Reproduction via Scripts
To rerun the complete experiment sweep, evaluate hypotheses, and regenerate all tables and figures:
```powershell
python experiments/run_sweep.py --workers 10
python experiments/run_statistical_tests.py
python experiments/make_tables.py
python experiments/make_figures.py
python tools/lint_paper.py
```

---

## 📜 Citation
```bibtex
@article{mrinal2026aca,
  author  = {Mrinal, Kumar},
  title   = {Adversarial Contingency Auctions for Decentralized Multi-Robot Task Allocation under Strategic Blockages},
  journal = {IEEE Robotics and Automation Letters},
  year    = {2026}
}
```
