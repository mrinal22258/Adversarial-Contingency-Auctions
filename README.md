# Adversarial Contingency Auctions (ACA)

> **Decentralized Multi-Robot Task Allocation under Strategic Blockages & Divergent Beliefs**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 88 Passing](https://img.shields.io/badge/tests-88%20passing-brightgreen.svg)]()
[![Simulation: Pure Software](https://img.shields.io/badge/simulation-pure%20software-informational.svg)]()

---

## 📌 Executive Summary
In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays.

**Adversarial Contingency Auctions (ACA)** addresses these vulnerabilities through three mechanisms:
1. **Expected-Recourse Valuation (Theorem 1):** Robots bid their expected recourse cost over a depth-$d$ contingency branching policy under a Bayesian posterior over adversary types.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 3):** Tasks are claimed safely via a closed-form margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ derived from Pinsker's inequality and total variation triangle bounds, guaranteeing conflict-free safe claims under bounded belief estimation error without exchanging belief vectors.
3. **Local Detour Execution (Proposition 2):** Blockage encounters activate local precomputed detours with zero communication messages, resorting to market re-auctions only upon recourse tree exhaustion.

---

## ⚠️ Simulation Disclaimer & Physical Reality
> **PURE SOFTWARE SIMULATION ONLY:** All experiments in this repository (including software-in-the-loop physics evaluations) are conducted strictly in **SOFTWARE SIMULATION** (NetworkX graph simulation and PyBullet rigid-body physics). **No physical hardware, physical robots, or physical camera testbeds were used.** All multi-robot trials, sensor measurements (including ArUco marker pose detection and TurtleBot3 differential-drive kinematics), and communication channels are simulated.

### Metric Definitions: Physical Collisions vs. Abstract Conflicts
To ensure clear evaluation across domains:
- **Physical Collisions:** Measured in continuous PyBullet simulation (`p.getContactPoints > 0`), representing physical surface contact between robot chassis/wheels and static or dynamic physical barriers.
- **Abstract Conflicts:** Measured in discrete task allocation rounds, representing combinatorial double-claim inconsistencies where two or more robots concurrently claim the identical discrete task bundle or node without consensus.

### Synthetic Vision & ArUco Pose Tracking
In the SITL synthetic-vision pipeline, overhead camera observations track ArUco markers atop simulated robot chassis. The 4x4 binary code (`DICT_4X4_50`) provides rotationally asymmetric patterns that eliminate 180-degree planar flip ambiguity. Marker top-edge image vectors map to the world frame via $(dx_{world}, dy_{world}) = (u_1 - u_0, -(v_1 - v_0))$, calculating continuous yaw headings $\psi = \mathrm{atan2}(dy_{world}, dx_{world})$ consistent with the camera projection.

---

## 🔬 What This Repository Shows (Key Scientific Findings)

This repository implements a rigorous, pre-registered empirical benchmark ($N = 13,800$ total trials across 5 graph families $\times$ 4 adversary profiles $\times$ 3 communication regimes) comparing ACA against literature baselines, level-execution variants (+LR), and clean ablations:

1. **ACA vs. Standard CBBA:** Under dynamic corridor blockages, standard CBBA drops its entire bundle upon a single blockage. ACA leverages type-aware expected recourse cost valuation and zero-message local detour execution, achieving significantly higher completion with lower message volume ($p < 0.05$).
2. **Mechanism Attribution:** Disabling local contingency recourse (ACA Depth-0) drops completion, confirming that local detour evaluation drives ACA's completion advantage.
3. **Pinsker Safe Claim Behavior:** The Pinsker margin operates conservatively. Safe claims maintain conflict-freedom under bounded error as predicted by Theorem 1.
4. **Honest Comparative Trade-offs:** 
   - **CBBA-PR (Partial Release)** preserves unblocked routes, achieving higher net welfare.
   - **CTP Replan** and the **Clairvoyant Greedy reference** achieve higher completion via continuous single-robot replanning, trading off decentralized bundle coordination.

All empirical data is generated automatically with zero hand-typed numbers:
- Auto-generated Markdown Table: [`results/table_main_results.md`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_main_results.md)
- Auto-generated LaTeX Table: [`results/table_main_results.tex`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_main_results.tex)
- Stratified Results Table: [`results/table_stratified.tex`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_stratified.tex)
- Paired SITL Simulation Table: [`results/table_sitl.tex`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/table_sitl.tex)
- Pre-registered Hypothesis Verdict: [`RESULTS_VERDICT.md`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/RESULTS_VERDICT.md)
- Raw Trial Logs: [`results/raw_results.csv`](file:///c:/Users/krmri/Downloads/Adversarial-Contingency-Auctions-main/Adversarial-Contingency-Auctions-main/results/raw_results.csv) (13,800 records)

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
