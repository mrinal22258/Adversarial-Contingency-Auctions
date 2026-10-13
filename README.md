---
title: Adversarial Contingency Auctions Mission Control
emoji: 🛰️
colorFrom: indigo
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
license: mit
---

# Adversarial Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: Verified Core & Extras](https://img.shields.io/badge/tests-verified%20clean-brightgreen.svg)]()
[![Simulation: Pure Software](https://img.shields.io/badge/simulation-pure%20software-informational.svg)]()
[![Protocol: prereg--v6](https://img.shields.io/badge/protocol-prereg--v6-blueviolet.svg)]()

---

## 📌 Executive Summary
In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays.

**Adversarial Contingency Auctions (ACA)** addresses these vulnerabilities through three mechanisms:
1. **Expected-Recourse Valuation (Proposition 1):** Robots bid their expected recourse cost over a depth-$d$ contingency branching policy under a Bayesian posterior over adversary types.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 1):** Tasks are claimed safely via a closed-form margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ derived from Pinsker's inequality and total variation triangle bounds, guaranteeing conflict-free safe claims under bounded belief estimation error without exchanging belief vectors (conditional on fixed policy tree and bounded peer estimation error).
3. **Local Detour Execution (Section III-D & Proposition 3):** Blockage encounters activate local precomputed detours with zero communication messages, resorting to market re-auctions only upon recourse tree exhaustion.

---

## ⚠️ Simulation Disclaimer & Physical Reality
> **PURE SOFTWARE SIMULATION ONLY:** All experiments in this repository (including software-in-the-loop physics evaluations) are conducted strictly in **SOFTWARE SIMULATION** (NetworkX graph simulation and PyBullet rigid-body physics). **No physical hardware, physical robots, or physical camera testbeds were used.** All multi-robot trials, sensor measurements (including ArUco marker pose detection and TurtleBot3 differential-drive kinematics), and communication channels are simulated.

### Metric Definitions: Physical Collisions vs. Abstract Conflicts
To ensure clear evaluation across domains:
- **Physical Collisions:** Measured in continuous PyBullet simulation (`p.getContactPoints > 0`), representing physical surface contact between robot chassis/wheels and static or dynamic physical barriers.
- **Abstract Conflicts:** Measured in discrete task allocation rounds, representing combinatorial double-claim inconsistencies where two or more robots concurrently claim the identical discrete task bundle or node without consensus.

### Open-Loop Synthetic Vision Demonstration
In the SITL synthetic-vision pipeline, overhead camera observations track ArUco markers atop simulated robot chassis. The 4x4 binary code (`DICT_4X4_50`) provides rotationally asymmetric patterns that eliminate 180-degree planar flip ambiguity. Marker top-edge image vectors map to the world frame via $(dx_{world}, dy_{world}) = (u_1 - u_0, -(v_1 - v_0))$, calculating continuous yaw headings $\psi = \mathrm{atan2}(dy_{world}, dx_{world})$ consistent with the camera projection. **State estimates are evaluated in open loop against simulated ground truth; poses are not fed into the task allocator or motion controllers, and no closed-loop physical validation is claimed.**

---

## 🔬 Three Demarcated Evidence Tiers & Key Scientific Findings

All claims and metrics in this repository are partitioned into three explicitly labelled evidence tiers:

1. **Tier 1 (Exploratory / Discovery — Nominal Main Grid, $N = 750$ Matched Trials Across 250 Instances):** Initial benchmark exploration across 14 allocators on seeds 1–250.
2. **Tier 2 (Pilot Heuristic Search — Stage 4 Pilot, $N = 60$ Instances, Seeds 51–60):** Pilot exploration for adaptive margin calibration and low-hazard pruning.
3. **Tier 3 (Confirmatory Out-of-Sample — Protocol v5 Held-Out, $N = 450$ Instances, 3,600 Trials, Seeds 101–130):** Frozen pre-registered confirmatory evaluation on un-tuned instances.

### Key Empirical Takeaways Across Tiers:
- **Pinsker Margin Trade-Off Confirmed (Tier 3):** On the confirmatory held-out grid, the Pinsker margin reduces total task conflicts by 20.6% ($38.6$ vs. $49.9$, paired difference $-10.27$, $p_{\text{adj}} < 0.001$) relative to unregularized coordination (`no-margin`), with only a modest, non-significant completion difference ($-1.08$ pp, $p_{\text{adj}} = 0.091$).
- **Stage 4 Pilot Gains Did Not Replicate (Tier 2 vs. Tier 3):** While ACA+ and ACA-Adaptive achieved nominal $+2.67\%$ completion gains in the $N=60$ pilot, they exhibited statistical completion parity with static ACA in the full $N=450$ confirmation ($92.44\%$ vs. $92.40\%$, $\Delta = +0.04$ pp, $p_{\text{adj}} = 0.505$).
- **Baseline Strengths (Tier 1 & Tier 3):** When CBBA is equipped with local recourse execution (`CBBA+LR`), it achieves higher completion ($94.67\%$), higher net welfare ($958.9$), and lower conflicts ($25.48$) in Protocol v5. On the balanced nominal core, `CTP Replan` achieves higher raw completion ($96.4\%$ vs. $90.9\%$) via continuous global re-auctions, while ACA excels in decentralized communication conservation.
- **Negative Result on Type Inference (Tier 1):** Online Bayesian adversary type inference shows statistical parity with a static uniform prior ($p = 0.515$), indicating that generic corridor detour structures saturate benefit before fine-grained type identification.

All empirical data is generated automatically with zero hand-typed numbers:

<!-- RESULTS_TABLE_START -->

### Benchmark Results ($N = 750$ Paired Trials per Method Across 250 Independent Instances)

| Method | Completion (%) | Net Welfare | Distinct Conflicts | Total Conflicts | Messages | Tick RT (ms) |
|:-------|:--------------:|:-----------:|:------------------:|:---------------:|:--------:|:------------:|
| **ACA (Ours)** | 90.9 ± 0.9 | 921 ± 22 | 6.3 ± 0.2 | 38.1 ± 2.3 | 236 ± 11 | 35.52 ± 2.40 |
| ACA (No Margin Ablation) | 90.7 ± 0.9 | 910 ± 21 | 7.8 ± 0.2 † | 47.4 ± 2.6 † | 238 ± 10 | 24.60 ± 1.59 † |
| ACA (Depth-0 Ablation) | 86.8 ± 1.0 † | 916 ± 19 | 6.6 ± 0.2 † | 42.0 ± 2.3 † | 301 ± 11 † | 23.43 ± 1.22 † |
| ACA (Depth-2) | 91.2 ± 0.9 | 925 ± 21 | 6.3 ± 0.2 | 38.5 ± 2.4 | 234 ± 10 | 34.79 ± 2.27 |
| ACA (No Inference) | 90.9 ± 0.9 | 928 ± 21 | 6.3 ± 0.2 | 38.7 ± 2.4 | 235 ± 10 | 31.98 ± 2.00 † |
| CBBA [Choi '09] | 82.1 ± 1.2 † | 879 ± 19 † | 8.0 ± 0.2 † | 50.4 ± 2.5 † | 312 ± 10 † | 11.89 ± 0.63 † |
| CBBA (+LR) | 88.8 ± 0.9 † | 910 ± 19 | 7.9 ± 0.2 † | 50.6 ± 2.7 † | 263 ± 10 † | 12.67 ± 0.70 † |
| CBBA-PR (Adapted) [Buckman '19] | 90.4 ± 0.9 | 977 ± 17 † | 8.0 ± 0.2 † | 59.7 ± 3.2 † | 295 ± 12 † | 12.57 ± 0.67 † |
| CBBA-PR (+LR) | 90.3 ± 0.9 | 923 ± 19 | 7.9 ± 0.2 † | 50.1 ± 2.7 † | 245 ± 11 † | 12.77 ± 0.70 † |
| SSI [Koenig '06] | 84.3 ± 1.4 † | 694 ± 27 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 252 ± 11 | 12.33 ± 0.69 † |
| SSI (+LR) | 84.1 ± 1.4 † | 635 ± 29 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 214 ± 10 † | 12.79 ± 0.76 † |
| CTP Replan | 96.4 ± 0.5 † | 832 ± 27 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 77 ± 3 † | 11.64 ± 0.66 † |
| Implicit (No Consensus) [Alighanbari '05] | 94.5 ± 0.7 † | 781 ± 22 † | 10.6 ± 0.2 † | 107.7 ± 4.4 † | 0 ± 0 † | 19.57 ± 1.09 † |
| Clairvoyant greedy (reference, not a bound) | 96.9 ± 0.5 † | 925 ± 27 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 0 ± 0 † | 15.89 ± 0.86 † |

<!-- RESULTS_TABLE_END -->

### Protocol v5 Confirmatory Held-Out Results ($N = 450$ Instances, Seeds 101–130)

| Method | Variant Description | Completion (%) | Net Welfare | Total Conflicts | Messages |
|:-------|:-------------------|:--------------:|:-----------:|:---------------:|:--------:|
| **ACA+ (Ours)** | Adaptive Margin + Pruning | 92.4 ± 1.0 | 936 ± 25 | 38.6 ± 2.9 | 221 ± 13 |
| ACA-Adaptive | Adaptive Margin Only | 91.3 ± 1.1 | 920 ± 25 | 39.0 ± 3.0 | 232 ± 14 |
| ACA (Static Pinsker) | Constant Margin | 92.4 ± 1.1 | 937 ± 25 | 39.7 ± 3.0 | 218 ± 13 |
| ACA (No Margin) | Margin Ablation | 93.5 ± 1.0 | 939 ± 23 | 49.9 ± 3.3 | 213 ± 12 |
| CBBA (+LR) [Choi '09] | Level Execution (+LR) | 94.7 ± 0.9 | 959 ± 22 | 25.5 ± 1.8 | 243 ± 11 |
| CBBA-PR (+LR) [Buckman '19] | Partial Release (+LR) | 93.4 ± 1.0 | 953 ± 22 | 40.6 ± 2.8 | 239 ± 12 |
| CTP Replan [Papadimitriou '91] | Continuous Re-solve | 92.3 ± 1.1 | 540 ± 42 | 0.0 ± 0.0 | 56 ± 3 |
| SSI (+LR) [Koenig '06] | Single-Item Auction (+LR) | 80.5 ± 2.0 | 666 ± 41 | 0.0 ± 0.0 | 146 ± 10 |

- Auto-generated Markdown Table: [`results/table_main_results.md`](results/table_main_results.md)
- Auto-generated LaTeX Table: [`results/table_main_results.tex`](results/table_main_results.tex)
- Stratified Results Table: [`results/table_stratified.tex`](results/table_stratified.tex)
- Confirmatory Held-Out Table: [`results/table_heldout_v5.tex`](results/table_heldout_v5.tex)
- Paired SITL Simulation Table: [`results/table_sitl.tex`](results/table_sitl.tex)
- Pre-registered Hypothesis Verdict: [`RESULTS_VERDICT.md`](RESULTS_VERDICT.md)
- Raw Trial Logs: [`results/raw_results.csv`](results/raw_results.csv) (13,800 records)
- Confirmatory Trial Logs: [`results/confirmatory/heldout_v5_results.csv`](results/confirmatory/heldout_v5_results.csv) (3,600 records)

---

## 🏗 Repository Layout

```
acalib/
  env/        # Real maps (MovingAI warehouse, OSMnx Boston), synthetic models, adversary models
  agents/     # Bayesian type filter, Theory of Mind tracker, Pinsker margin calculator, contingency planner
  alloc/      # ACA-CBBA, ablations, CBBA (Choi '09), CBBA-PR, CC-CBBA, Implicit, SSI, Foresight Opt (CP-SAT)
  sim/        # Simulation engine, wall-clock metrics, and statistical logging
experiments/  # Parallel sweep runner, bootstrap CIs, paired Wilcoxon + Holm-Bonferroni tests, figures/tables
tests/        # 145 automated verification and regression tests
results/      # Raw CSV trials, LaTeX tables, numbers macros, and publication PDF/PNG figures
```

---

## 🚀 Quickstart & Reproduction

### 1. Run Verification Test Suite
Run the 145 automated unit, property-based, and regression tests:
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
  author = {Mrinal, Kumar},
  title  = {Adversarial Contingency Auctions for Decentralized Multi-Robot Task Allocation under Strategic Blockages},
  note   = {Preprint / under review},
  year   = {2026}
}
```
