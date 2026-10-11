# ACA Comprehensive Repository Audit (Part A)

**Repository:** `Adversarial-Contingency-Auctions-main`  
**Branch:** `fix/rigorous-eval`  
**Date:** 2026-10-11  
**Status:** Audit & Overhaul Complete (138 Tests Passing)  

---

## 1. Repository Map & Architecture

### 1.1 Languages & Frameworks
- **Primary Language:** Python 3.12 (core algorithms, simulation engine, Bayesian inference, experiment pipelines, statistical analysis).
- **Web UI & Visualization:** Gradio 4.x + Vanilla CSS/HTML design tokens + Matplotlib 3.8 / Seaborn 0.13 (Agg backend).
- **Manuscript & Theory:** LaTeX (`IEEEtran.cls`), BibTeX, MiKTeX `pdflatex`.
- **E2E & Testing:** PyTest, Playwright (multi-viewport responsive UI verification), Typeguard.

### 1.2 Entry Points & Workflows
- **Interactive Web App / Mission Control:** `python app.py` (serves Gradio app on `localhost:7860`).
- **Reproducible Pipeline:** `python tools/build_all_results.py` / `make reproduce` (executes end-to-end 8-stage data pipeline).
- **Benchmark Sweeps:** `experiments/run_sweep.py`, `experiments/run_extended_sweep.py`, `experiments/run_heldout_eval.py`.
- **Statistical Analysis & Paper Tables:** `experiments/make_tables.py` (generates `results/table_main_results.tex`, `results/numbers.tex`, hypothesis testing outputs).
- **Publication Figures:** `experiments/make_figures.py` (generates vector PDF / PNG with Okabe-Ito colorblind-safe palettes and `.provenance.json` sidecars).
- **Strict Paper & Macro Linter:** `python tools/lint_paper.py` (verifies zero unmacroed literal numbers, figure sidecars, claim integrity).

### 1.3 Simulation Engine & Core Components
- **Agents:**
  - `acalib/agents/robot.py`: Autonomous robot agent, bundle management, local recourse execution.
  - `acalib/agents/belief.py`: Bayesian type filter (`DiscreteTypeFilter`), recursive Bayesian update on observed edge blockages, clearance rate tracking.
  - `acalib/agents/tom.py`: Theory of Mind (`TheoryOfMindTracker`) tracking peer belief distributions and estimating peer divergence ($D_{\mathrm{KL}}$, $TV$).
  - `acalib/agents/contingency.py`: Contingency tree construction, recourse planning, analytical Mean Value Theorem Lipschitz bound computation (`compute_lipschitz_bound`).
- **Allocation Mechanisms:**
  - `acalib/alloc/aca.py`: Core Adversarial Contingency Auction algorithm with Pinsker divergence claim margins ($\kappa$), adaptive entropy margin, and corridor pruning.
  - `acalib/alloc/cbba.py`: Consensus-Based Bundle Algorithm baseline.
  - `acalib/alloc/cbba_partial.py`: CBBA with partial path replanning.
  - `acalib/alloc/cbba_lr.py`, `acalib/alloc/ssi_lr.py`, `acalib/alloc/cbba_partial_lr.py`: Baselines equipped with local recourse for fairness comparison.
  - `acalib/alloc/ssi.py`: Sequential Single-Item auction baseline.
  - `acalib/alloc/implicit.py`: Implicit decentralized task allocation without explicit consensus rounds.
  - `acalib/alloc/cc_cbba.py`: Chance-Constrained CBBA baseline.
  - `acalib/alloc/ctp.py`: Canadian Traveler Problem heuristic allocator.
  - `acalib/alloc/oracle.py`: Clairvoyant greedy reference heuristic (clarified as reference heuristic, not theoretical bound).
- **Simulation & Environment:**
  - `acalib/sim/engine.py`: Discrete-time multi-robot simulator with message passing, task completion tracking, path traversal, conflict recording.
  - `acalib/env/adversaries.py`: Strategic adversary models: $\theta_1$ (Reactive corridor interdictor), $\theta_2$ (Proactive bottleneck blocker), $\theta_3$ (Omniscient adaptive adversary), $\theta_4$ (Random Poisson/Bernoulli blockages).
  - `acalib/env/real_maps.py`: Real-world environment parsers for OSMnx Boston downtown road network (`boston_downtown_drive.graphml`) and MovingAI warehouse benchmarks (`warehouse-10-20-10-2-1.map`).
  - `acalib/env/graph_families.py`: Synthetic benchmark graph generators (RGG, Delaunay, Grid, Scale-Free).

---

## 2. Findings Matrix

| ID | Severity | Category | File & Line | Summary | Status |
|---|---|---|---|---|---|
| **F-01** | **BLOCKER** | Data Lineage | `experiments/run_extended_sweep.py`, `results/raw_results.csv` | Primary Confirmatory Population Confounded with OFAT Sweeps | **RESOLVED / DECLARED** (`audit/PRIMARY_POPULATION.md`) |
| **F-02** | **BLOCKER** | Statistics | `experiments/make_tables.py:97,109` | Stale Pair Count Loop Leak across Baselines | **FIXED** (`paired_dfs[m]`, Regression Tested) |
| **F-03** | **BLOCKER** | Statistics | `experiments/make_tables.py:165-210` | Unpaired Aggregate Means Paired with Matched-Pair Markers in Table II | **FIXED** (Balanced 750-trial Grid Filtered) |
| **F-04** | **HIGH** | Data Recovery | `tools/recover_runs.py:34-42` | 5-Tuple Key Collapsed Distinct Scale Sweep Trials | **FIXED** (Expanded to 7-Tuple Key) |
| **F-05** | **HIGH** | Map Topology | `data/maps/manifest.json`, `results/numbers.tex`, `acalib/demo/provenance.py` | Boston Road Network Edge Count Discrepancy (323 vs 326) | **FIXED** (Raw GraphML 326 vs Undirected Simple Graph 323) |
| **F-06** | **HIGH** | Hardcoded Constants | `experiments/make_tables.py:500-680` | Hardcoded Empirical Macros Bypassing Dynamic Pipeline | **FIXED** (Dynamic Load from Stats/Manifest/SITL) |
| **F-07** | **HIGH** | Provenance | `acalib/demo/provenance.py:37,67-69` | Fallback SHA-256 Hashes Masking Missing / Corrupted Map Files | **FIXED** (Removed Fallbacks; Explicit 5-State Engine) |
| **F-08** | **MEDIUM** | Tooling / CI | `tools/lint_paper.py:230-245` | Linter Enforcing Clean Git State on Development Trees | **FIXED** (`--strict-release` flag added) |
| **F-09** | **MEDIUM** | Statistics | `experiments/make_tables.py:488,496` | Float Formatting Emitting False `p = 0.00` | **FIXED** (`< 0.001` Formatter Enforced) |
| **F-10** | **LOW** | Documentation | `README.md` | Inaccurate Benchmark Grid Description ("5x4x3 = 13,800") | **RECONSTRUCTED** (Documented in Data Lineage) |
| **F-11** | **BLOCKER** | Theory / Rigor | `acalib/alloc/aca.py:117`, `tests/test_theorem3_montecarlo.py` | Heuristic Lipschitz Multipliers and Duplicate Test Oracle | **FIXED** (`compute_lipschitz_bound` MVT Bound) |
| **F-12** | **HIGH** | Theory / Alignment | `README.md`, `acalib/alloc/aca.py`, `acalib/agents/tom.py` | Discrepant Theorem/Proposition Numbering vs `paper.tex` | **RECONCILED** (Aligned to `paper.tex`) |
| **F-13** | **MEDIUM** | Testing / Provenance | `tests/test_theorem3_montecarlo.py:7` | False Claim of ">=100,000 instances" in Test Docstring | **FIXED** (Updated to Real 5,000 Sample Count) |

---

## 3. Core Logic & Implementation Fixes

### 3.1 Mean Value Theorem Lipschitz Constant (Finding F-11)
- **Previous state:** Heuristic multipliers (`1.5 * nominal_cost`) and arbitrary floors disconnected theoretical Proposition 2 from executable code.
- **Fix:** Implemented exact multivariable Mean Value Theorem bound in `acalib/agents/contingency.py:compute_lipschitz_bound`:
  $$L_j = \sum_{k=1}^K |\text{branch\_cost}_k - \text{primary\_cost}| \cdot \Delta \pi(e_k)$$
  Returns $0.0$ when no risky edges exist. Unified both production (`acalib/alloc/aca.py`) and test suites (`tests/test_theorem3_montecarlo.py`) to execute this production function.

### 3.2 Paired Statistics & Estimand Integrity (Findings F-02, F-03)
- **Previous state:** `len(paired)` leaked across baseline loop iterations; aggregate means pooled all exploratory sensitivity rows while reporting Wilcoxon paired tests from nominal subsets.
- **Fix:** Main results in Table II are strictly partitioned to the balanced confirmatory grid ($N=750$ paired trials across 250 matched problem instances) where all 14 evaluated allocators share identical environments, seeds, and robot-task assignments.

### 3.3 Map Provenance & Cryptographic Validation (Finding F-05, F-07)
- **Previous state:** Fallback hashes allowed fake verification. Boston road network edge counts differed between XML records and graph nodes.
- **Fix:** Eliminated all fallback constants in `acalib/demo/provenance.py`. Explicitly verified both raw GraphML edge records ($E_{\text{raw}} = 326$) and simple undirected navigation graph edges ($E = 323$), with exactly 112 edges intersecting active work zones.

---

## 4. Test Suite Coverage & Verification Status

- Full regression suite consists of 26 test files (138 tests total) covering:
  - Unit tests for bidding, bundle insertion, Bayesian filtering, and ToM tracking.
  - Property tests for invariant allocation (every task assigned at most once, non-negative costs, seed determinism).
  - Analytical Lipschitz Monte Carlo bounds (5,000 sampled belief pairs across 100 random geometric graphs).
  - Cross-method comparability and matched-pair trial validation.
  - End-to-end regression benchmarks on real OSMnx and MovingAI maps.
- **Baseline execution:** 138 / 138 tests passing.
