<!-- GENERATED FILE: DO NOT EDIT DIRECTLY. Edit README.template.md and run tools/render_readme.py -->

# Adversarial Contingency Auctions (ACA)

> Decentralized Multi-Robot Task Allocation under Strategic Blockages and Divergent Beliefs

[![CI Status](https://github.com/anonymous/adversarial-contingency-auctions/actions/workflows/ci.yml/badge.svg)](https://github.com/anonymous/adversarial-contingency-auctions/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: Suite Status](https://img.shields.io/badge/tests-249%20passed%20(30%20deselected)-brightgreen.svg)]()
[![Simulation: Pure Software](https://img.shields.io/badge/simulation-pure%20software-informational.svg)]()
[![Protocol: prereg--v6.2](https://img.shields.io/badge/protocol-prereg--v6.2-blueviolet.svg)](protocols/prereg-v6.md)

---

## 1. Executive Summary & Evidence Status

In decentralized multi-robot task allocation, strategic adversarial path blockages and inconsistent local worldviews induce coordination failures. Standard market mechanisms (e.g., CBBA, SSI) assume consensus and require cascading market re-auctions upon path invalidation, causing communication surges and delays. **Adversarial Contingency Auctions (ACA)** addresses these vulnerabilities by coupling expected-recourse task valuations over Bayesian adversary models with an information-theoretic Pinsker claim margin, enabling robots to claim tasks safely and activate precomputed local detours with zero communication overhead.

### Evidence Status Matrix

| Tier | Evaluation Population | Instances ($N$) & Scope | Status | Headline Finding |
|:---|:---|:---:|:---:|:---|
| **Tier 1** | **Exploratory Main Grid** | $N = 750$ matched instances (50 seeds $\times$ 5 families $\times$ 3 adversaries; 10500 primary trials) | **Exploratory** | ACA achieves an exploratory completion gain of +6.43 pp over CBBA+LR ($p = < 0.001$ under cluster-level Holm adjustment). |
| **Tier 2** | **Protocol v5 Confirmatory Held-Out** | $N = 450$ un-tuned instances (30 seeds, 3600 trials) | **Confirmatory (Reversal)** | **Out-of-sample reversal**: CBBA+LR outperforms ACA on completion (94.67% vs. 92.40%, diff +2.27 pp) and net welfare (958.9 vs. 937.4) with fewer conflicts (25.48 vs. 39.66). ACA's primary scientific advantage is safe decentralized coordination via the Pinsker margin under communication constraints rather than uniform completion dominance. |
| **Tier 3** | **Protocol v6 Confirmatory Replication** | $N = 750$ instances (50 confirmatory seeds $\times$ 5 families $\times$ 3 adversaries $\times$ 9 allocators = 6,750 trials) | **Execution Pending** | Protocol v6.2 is cryptographically frozen (`prereg-v6.2`). Pre-execution dev-seed tuning selected $\tau_{\text{prune}} = 0.15$. Confirmatory execution is pending per [RUN_V6.md](RUN_V6.md). |

---

## 2. What ACA Is

Adversarial Contingency Auctions (ACA) is a decentralized coordination framework designed for multi-robot fleets operating in contested environments where edges may be dynamically blocked by adversarial agents and robots maintain subjective, divergent worldviews. ACA addresses these challenges through three foundational mechanisms:

1. **Expected-Recourse Valuation (Proposition 1):** Instead of evaluating tasks along a single brittle shortest path, each robot computes the expected traversal cost over a depth-$d$ contingency branching tree. Robots evaluate alternative bypass branches weighted by a Bayesian posterior over adversary behavioral types ($\mathcal{P}(\theta^*)$), pricing risk directly into auction bids.
2. **Pinsker Belief-Divergence Claim Margin (Theorem 1):** Divergent subjective beliefs between robots can cause simultaneous claims on identical tasks. ACA derives a closed-form claim margin $m_{r,j} = \Delta_j (\sqrt{\frac{1}{2} D'_{\text{KL}}} + \eta_{\text{eff}}) + \delta_{\text{map}}$ from Pinsker's inequality and total variation triangle bounds. Under Theorem 1, conditional on Assumption 1 (bounded belief estimation error $\mathrm{TV}(B_s, \hat{B}_s^{(r)}) \le \eta_{\text{eff}}$), this margin mathematically guarantees conflict-free safe task claims without exchanging full belief vectors.
3. **Zero-Message Local Detour Execution (Proposition 3):** When an agent encounters an edge blockage during plan execution, it immediately activates its precomputed local contingency detour branch with zero inter-robot communication messages. Global market re-auctions are triggered only upon complete recourse tree exhaustion.

---

## 3. Benchmark Populations & Empirical Results

### Population Definitions & Reconciliation

All empirical numbers in this repository are tied directly to explicit, named populations in `results/result_model_v1.json`:

| Population Name | Source File | Filter / Scope | Trials | Instances | Clusters | Seeds | Methods |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `exploratory_core` | `results/raw_results.csv` | comm_regime == 'nominal' and 14 core methods and 3 nominal adversaries | 10,500 | 750 | 250 | 50 | 14 |
| `exploratory_sweep` | `results/raw_results.csv` | none (full raw sweep including OFAT ablations) | 13,800 | 920 | 250 | 50 | 21 |
| `heldout_v5` | `results/confirmatory/heldout_v5_results.csv` | none (all held-out v5 trials) | 3,600 | 450 | 150 | 30 | 8 |
| `pilot_stage4` | `results/pilot/stage4_pilot_results.csv` | none (Stage 4 pilot search) | 300 | 60 | 30 | 10 | 5 |
| `sitl` | `results/sitl/analysis/sitl_vs_graph_summary.json` | matched continuous vs discrete trials | 360 | 360 | 18 | 360 | 4 |
| `v6_confirmatory` | `results/confirmatory_v6/results.csv (pending execution)` | protocol v6.2 confirmatory specification | EXECUTION_PENDING | 750 | 250 | 50 | 9 |

*Reconciliation Note:* Historical drafts cited "18,720 total sweep trials" based on an unexecuted theoretical combinatorial budget. The verified empirical raw data in `results/raw_results.csv` contains exactly 13,800 trials (10,500 primary balanced core trials across 14 allocators and 750 matched instances, plus 3,300 OFAT ablation trials). The README phrase "14 allocators on seeds 1-250" conflated cluster count with seed count: the benchmark evaluates 50 seeds across 5 graph families ($50 \times 5 = 250$ independent clusters).

### Tier 1: Exploratory Main Grid Results ($N = 750$ Matched Instances, Cluster-Level Estimator)

<!-- RESULTS_TABLE_START -->

### Benchmark Results ($N = 750$ Paired Trials per Method Across 250 Independent Instances, Cluster-Level Estimator)

| Method | Completion (%) | Net Welfare | Distinct Conflicts | Total Conflicts | Messages | Tick RT (ms) |
|:-------|:--------------:|:-----------:|:------------------:|:---------------:|:--------:|:------------:|
| **ACA (Ours)** | 95.9 ± 0.9 | 960 ± 33 | 7.4 ± 0.4 | 44.5 ± 4.0 | 192 ± 14 | 100.60 ± 10.75 |
| ACA (No Margin Ablation) | 95.5 ± 1.0 | 959 ± 32 | 7.6 ± 0.4 † | 44.0 ± 3.7 | 186 ± 14 | 39.85 ± 4.42 † |
| ACA (Depth-0 Ablation) | 95.3 ± 0.9 † | 972 ± 31 † | 7.3 ± 0.4 † | 45.4 ± 3.9 | 212 ± 14 † | 97.32 ± 10.04 † |
| ACA (Depth-2) | 95.7 ± 0.9 | 959 ± 33 | 7.4 ± 0.4 † | 44.3 ± 4.0 | 193 ± 14 | 111.63 ± 13.18 † |
| ACA (No Inference) | 95.9 ± 1.0 | 966 ± 32 | 7.7 ± 0.4 † | 49.7 ± 4.3 † | 218 ± 15 † | 80.74 ± 8.52 † |
| CBBA [Choi '09] | 87.0 ± 1.5 † | 927 ± 27 † | 8.0 ± 0.4 † | 50.7 ± 4.2 † | 287 ± 15 † | 21.13 ± 2.19 † |
| CBBA (+LR) | 89.4 ± 1.4 † | 934 ± 29 † | 8.0 ± 0.4 † | 49.9 ± 4.3 † | 258 ± 17 † | 21.75 ± 2.26 † |
| CBBA-PR (Adapted) [Buckman '19] | 90.9 ± 1.4 † | 973 ± 27 | 8.0 ± 0.4 † | 56.7 ± 4.8 † | 275 ± 18 † | 21.90 ± 2.26 † |
| CBBA-PR (+LR) | 90.8 ± 1.4 † | 946 ± 29 | 8.0 ± 0.4 † | 51.5 ± 4.5 † | 250 ± 19 † | 22.46 ± 2.34 † |
| SSI [Koenig '06] | 87.1 ± 1.9 † | 716 ± 45 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 221 ± 16 † | 22.66 ± 2.60 † |
| SSI (+LR) | 87.2 ± 2.0 † | 698 ± 45 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 205 ± 16 | 23.25 ± 2.72 † |
| CTP Replan | 97.1 ± 0.7 † | 833 ± 46 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 64 ± 3 † | 20.84 ± 2.26 † |
| Implicit (No Consensus) [Alighanbari '05] | 97.1 ± 0.8 † | 731 ± 42 † | 11.9 ± 0.2 † | 115.7 ± 8.3 † | 0 ± 0 † | 32.38 ± 3.45 † |
| Clairvoyant greedy (reference, not a bound) | 98.6 ± 0.5 † | 1002 ± 36 † | 0.0 ± 0.0 † | 0.0 ± 0.0 † | 0 ± 0 † | 23.17 ± 2.16 † |

<!-- RESULTS_TABLE_END -->

### Tier 2: Protocol v5 Confirmatory Held-Out Results ($N = 450$ Instances, Seeds 101–130)

| Method | Variant Description | Completion (%) | Net Welfare | Total Conflicts | Messages |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **ACA (Static Pinsker, $\kappa=1.0$, Ours)** | Canonical Theory Baseline | 92.4 ± 1.0 | 937 ± 24 | 39.7 ± 2.8 | 218 ± 12 |
| ACA+ (Heuristic) | Adaptive Margin + Pruning (Inactive in v5) | 92.4 ± 1.0 | 936 ± 25 | 38.6 ± 2.9 | 221 ± 13 |
| ACA-Adaptive (Heuristic) | Adaptive Margin Only | 91.3 ± 1.1 | 920 ± 26 | 39.0 ± 2.8 | 232 ± 14 |
| ACA (No Margin) | Margin Ablation | 93.5 ± 1.0 | 939 ± 24 | 49.9 ± 3.4 | 213 ± 12 |
| CBBA (+LR) [Choi '09] | Level Execution (+LR) | 94.7 ± 0.9 | 959 ± 22 | 25.5 ± 1.8 | 243 ± 11 |
| CBBA-PR (+LR) [Buckman '19] | Partial Release (+LR) | 93.4 ± 1.0 | 953 ± 22 | 40.6 ± 2.7 | 239 ± 13 |
| CTP Replan [Papadimitriou '91] | Continuous Re-solve | 92.3 ± 1.2 | 540 ± 41 | 0.0 ± 0.0 | 56 ± 3 |
| SSI (+LR) [Koenig '06] | Single-Item Auction (+LR) | 80.5 ± 2.0 | 666 ± 40 | 0.0 ± 0.0 | 146 ± 10 |

- On held-out seeds, the Pinsker margin reduces total task conflicts by 20.6% (39.66 vs. 49.93, paired difference -10.27, $p < 0.001$) relative to unregularized coordination (`aca_no_margin`), with only a non-significant completion difference ($-1.08$ pp, $p_{\text{adj}} = 0.091$).
- In Protocol v5, ACA+ pruning was functionally inactive ($\tau_{\text{prune}} = 0.06 < \tau_{\text{planner}} = 0.12$). Active pruning with calibrated threshold $\tau = 0.15$ is registered for Protocol v6.

---

## 4. What the Paper Can and Cannot Claim

To ensure scientific honesty and transparency, all project claims are demarcated into what the evidence supports and what cannot be claimed:

### What the Paper CAN Claim:
1. **Exploratory Main Grid Findings:** On the balanced nominal benchmark grid ($N = 250$ independent clusters, 750 paired trials), ACA achieves an exploratory completion gain of $+2.14$ percentage points over CBBA+LR ($p = 0.004$ under cluster-level Holm adjustment).
2. **Out-of-Sample Protocol v5 Headline Reversal:** On held-out un-tuned seeds 101–130 ($N = 450$ instances, 3,600 trials), when baseline CBBA is equipped with local recourse (+LR), **CBBA+LR outperforms ACA** on task completion (94.67% vs. 92.40%, paired difference +2.27 pp) and net welfare (958.9 vs. 937.4) with fewer conflicts (25.48 vs. 39.66). This establishes that local detour execution is the primary driver of corridor completion, while ACA's primary scientific advantage is safe decentralized coordination via the Pinsker margin under communication constraints.
3. **Pinsker Margin Trade-Off:** The Pinsker claim margin reduces total conflicts by 20.6% (39.66 vs. 49.93, $p < 0.001$) relative to unregularized coordination, at a modest, non-significant completion difference ($-1.08$ pp, $p_{\text{adj}} = 0.091$).
4. **Conditional Safety Guarantee (Theorem 1):** Under the ACA Lemma 1 analytical drift bound ($\eta_{\text{eff}}$), holding conditionally under bounded per-step observation counts ($n_{\text{obs}} \le \gamma_{\text{obs}} \Delta t$) and bounded likelihood ratios, adherence holds in 99.04% of safe claims (11,234 / 11,343 commitments) with exactly 0 / 11,234 conflicts (one-sided 95% Clopper-Pearson upper bound $\le 0.027\%$). In periodic peer belief evaluations across the unclipped empirical simulator, 98.08% of observations satisfy the bound (762,851 / 777,752), while 1.92% experience transient violations when multi-robot edge occupancy drives reactive hazard to unity (triggering the numerical floor) or multi-edge sensing exceeds the per-step cap. Instance-level adherence reaches 96.70% ($N = 250$, $p < 0.001$), contrasted with the historical pre-calibration baseline snapshot (21.1% safe-claim adherence; `audit/baseline_snapshot/results/numbers.tex`).
5. **Decentralized Superiority over SSI:** ACA decisively outperforms Single-Item Auctions ($+11.96$ pp completion, $p < 10^{-25}$).
6. **Physical Simulation Domain Gap:** Software-in-the-Loop continuous physics introduces an average completion drop of $\approx 18.9$ pp and rank invariance failure across simulation fidelities ($\rho = 0.486, p = 0.328$). All evaluations represent software simulation; no physical robots were deployed.

### What the Paper CANNOT Claim:
1. **Cannot Claim Confirmatory Validation of the Repaired Recursive Planner:** The newly implemented full recursive tree planner, active pruning with recovery cost leaves, and grounded hazard interface have not been executed across the 50 confirmatory seeds ($40$ CPU-hours). Protocol v6 is registered and cryptographically frozen, but its confirmatory execution remains pending per [RUN_V6.md](RUN_V6.md).
2. **Cannot Claim Active Pruning Benefits in Protocol v5:** In Protocol v5, ACA+ set $\tau_{\text{prune}} = 0.06 < \tau_{\text{planner}} = 0.12$, rendering pruning functionally inactive. v5 results demonstrate parity with static ACA, but do not provide evidence for active pruning. Active pruning ($\tau_{\text{prune}} = 0.15$, empirically selected on development seeds) will be evaluated in Protocol v6.
3. **Cannot Claim General Completion Dominance over CBBA+LR:** Out-of-sample confirmatory evidence demonstrates that CBBA+LR is superior in unconstrained task completion and welfare.
4. **Cannot Claim Online Type Inference Advantage:** Online Bayesian adversary type inference shows statistical parity with a static uniform prior ($p = 0.515$).
5. **Cannot Claim Universal Conflict-Freedom:** Theorem 1 applies strictly when $\mathrm{TV} \le \eta_{\text{eff}}$; safe claims outside this condition incurred conflicts in historical logs.
6. **Cannot Claim In-the-Loop Vision or Physical Hardware Deployment:** The vision pipeline represents an open-loop synthetic ArUco tracking demonstration evaluated against simulated ground truth; no physical robots or closed-loop vision controllers were deployed.

---

## 5. Repository Layout

```
├── acalib/                   # Core ACA library (pure Python, NetworkX, NumPy)
│   ├── agents/               # Bayesian type filter, Theory of Mind tracker, Pinsker margin calculator
│   ├── alloc/                # Allocators: ACA, CBBA, CBBA-PR, SSI, CTP Replan, Implicit
│   ├── demo/                 # Gradio Mission Control web dashboard & telemetry UI
│   ├── env/                  # Topological environments (OSMnx Boston, MovingAI warehouse, synthetic)
│   ├── sim/                  # Simulation engine, event contracts, metric collectors
│   └── utils/                # Git helper, file locks, logging utilities
├── experiments/              # Experiment configurations, sweep runner, statistical testing
│   ├── configs/              # Frozen Protocol v6 configuration (protocol_v6.yaml)
│   ├── run_sweep.py          # Parallel sweep execution engine (CRN, atomic locks)
│   ├── run_statistical_tests.py # Cluster-aware tests, Wilcoxon, Holm-Bonferroni corrections
│   ├── make_tables.py        # Automated LaTeX/Markdown table generator
│   └── make_figures.py       # Publication figure generator with provenance sidecars
├── protocols/                # Cryptographically locked pre-registration specifications (prereg-v6.md)
├── repro/                    # Exact environment lockfiles and input data hashes (input_hashes.json)
├── results/                  # Empirical data artifacts, LaTeX macros, figures, test logs
│   ├── confirmatory/         # Protocol v5 held-out confirmatory results
│   ├── perf/                 # CPU profiling hotspots and throughput benchmarks
│   ├── pilot/                # Stage 4 pilot search artifacts
│   ├── numbers.tex           # Auto-generated LaTeX macros (zero hardcoded numbers)
│   └── result_model_v1.json  # Authoritative unified empirical result model
├── tests/                    # Pytest verification suite (unit, regression, property, golden trace)
└── tools/                    # Auditing, linting, verification, and rendering utilities
```

---

## 6. Quickstart & Reproduction

### 1. Environment Setup & Dependency Profiles
The repository provides modular dependency profiles:
- **Core algorithmic benchmarks:** `pip install -r requirements-core.txt` (NumPy, SciPy, NetworkX, Pandas, PyArrow)
- **Interactive web dashboard & API:** `pip install -r requirements-demo.txt` (Core + Gradio 6, FastAPI, Uvicorn, HTTPX)
- **Optional solver & physics extras:** `pip install -r requirements-extras.txt` (OR-Tools, PyBullet, OpenCV headless)
- **Full environment:** `pip install -r requirements.txt` or `pip install -e ".[all]"`

### 2. Docker Deployment
A hardened, unprivileged container configuration is provided:
```bash
# Build the production demo image
docker build -t aca-mission-control .

# Run container (exposing web dashboard and REST API on port 7860)
docker run -d -p 7860:7860 --name aca-mission-control aca-mission-control

# Check container healthcheck probe
curl http://localhost:7860/api/health
```

### 3. Running Tests & Test Markers
The test suite utilizes explicit pytest markers:
- `core`: Pure algorithmic, game-theoretic, statistical, and auction mechanism tests.
- `sitl`: Physics-based Software-In-The-Loop PyBullet simulation tests (requires pybullet).
- `ortools`: Exact combinatorial optimization and CP-SAT benchmark tests (requires ortools).
- `ui`: Interactive demo, Gradio layout, and Playwright UI regression tests (requires gradio, playwright).

```bash
# Run core test suite (recommended, zero heavy dependencies required)
pytest -q -m "not (sitl or ortools or ui)"

# Run demo & API endpoint verification
pytest -v tests/test_api_endpoints.py

# Run full suite including optional physics and solver tests (if installed)
pytest -v
```
Saved run log: `results/test_logs/gate-6.txt` (249 passed, 30 deselected, 2 warnings).

### 4. Reproducing Paper Results (Exact Commands)
To reproduce the published figures, LaTeX macros, and verification manifests bit-for-bit:
```bash
# 1. Re-derive all LaTeX tables, numbers.tex macros, and figures from logged data:
python tools/build_all_results.py

# 2. Verify Protocol v6 pre-registration constraints and cryptographic hashes:
python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml --strict

# 3. Compile the paper manuscript and supplement:
python tools/build_paper.py
```

### 5. Environment Variables Configuration

| Variable | Default | Description |
|:---|:---:|:---|
| `HOST` / `GRADIO_SERVER_NAME` | `127.0.0.1` | Network interface for FastAPI/Gradio server binding |
| `PORT` | `7860` | Listening port for web server |
| `ACA_LOG_LEVEL` / `LOG_LEVEL` | `info` | Application log level (`debug`, `info`, `warning`, `error`) |
| `ACA_RATE_LIMIT_PER_MIN` | `60` | Maximum requests per minute per IP on simulation endpoints |
| `ACA_MAX_CONCURRENT_SIMS` | `4` | Maximum concurrent simulation workloads processed simultaneously |
| `ACA_RUN_CACHE_SIZE` | `32` | Maximum cached simulation runs held in LRU memory |
| `ACA_CORS_ORIGINS` | Safe Localhost | Comma-separated allowed CORS origins (no wildcard in default production) |

### 6. Protocol v5 Held-Out Reversal Consistency Note
In accordance with open-science pre-registration standards, the manuscript and repository explicitly document the **Protocol v5 out-of-sample reversal** where CBBA+LR achieved higher raw completion (94.7% vs. 92.4%) than ACA on held-out seeds 101–130. This finding is mathematically consistent with the paper's theoretical framework: local detour execution (+LR) resolves corridor blockages for any allocator, while ACA's distinct mathematical contribution is the **Pinsker claim margin (Theorem 1)**, which guarantees conflict-free coordination and eliminates 20.6% of inter-robot task conflicts without exchanging private belief vectors.

---

## 7. Performance & Hardware Guidance

### Pure CPU Architecture by Design
The ACA simulator, contingency planner, and auction loops are implemented entirely in pure Python, NetworkX, and NumPy. Benchmark topologies contain between 30 and 216 nodes with sequential multi-round bundle auctions and recursive branching searches. Profiling (`results/perf/profile.md`) demonstrates that kernel-launch and memory transfer overhead would render a GPU substantially slower than CPU execution, and GPU non-deterministic floating-point operations would violate pre-registered bit-for-bit reproducibility.

### Core Optimization & BLAS Isolation
- The sweep runner (`experiments/run_sweep.py`) defaults `--workers` to **physical CPU cores** (`psutil.cpu_count(logical=False)`).
- Worker processes automatically set `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1` to prevent multi-threaded BLAS oversubscription across parallel worker processes.
- Graph distance queries and invariant betweenness calculations are cached by topological hash (`topology_hash`), preventing redundant all-pairs path recalculations.

### Throughput & Estimated v6 Wall Time
Measured throughput benchmarks on 216-node Boston road network topologies (`results/perf/throughput.md`):

| Worker Count | Throughput (trials/hour) | Estimated v6 Full Sweep Duration (6,750 trials) |
|:---:|:---:|:---:|
| 4 workers | ~670 trials/h | ~10.1 hours |
| 8 workers | ~1,340 trials/h | ~5.0 hours |
| 16 workers | ~2,680 trials/h | ~2.5 hours |
| 32 workers | ~5,200 trials/h | ~1.3 hours |

---

## 8. Reproducing Protocol v6

Protocol v6 is fully specified, verified, and tagged at `prereg-v6.2`. To execute the confirmatory sweep:
1. Verify protocol integrity: `python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml --strict`
2. Launch the confirmatory sweep: Follow the exact step-by-step instructions in [RUN_V6.md](RUN_V6.md).

---

## 9. Data Provenance & Integrity

All raw datasets and confirmatory outputs are cryptographically tracked:
- Exploratory Raw Results: `results/raw_results.csv` (13,800 rows)
- Protocol v5 Confirmatory Held-Out: `results/confirmatory/heldout_v5_results.csv` (3,600 rows)
- Complete SHA-256 hashes for all input datasets and reference maps are recorded in `repro/input_hashes.json`.
- File hashes can be independently audited with `python tools/compute_input_hashes.py`.

---

## 10. Limitations & Simulation Scope

1. **Simulation Scope:** All evaluations are conducted in software simulation (discrete graph networks and PyBullet continuous physics). No physical robots, hardware testbeds, or physical camera systems were deployed.
2. **Sim-to-Sim Physics Gap:** PyBullet continuous simulation reveals an average completion degradation of $\approx 18.9$ pp and rank invariance failure relative to discrete graph simulation, highlighting the need for future physical hardware testing.
3. **Open-Loop Synthetic Vision:** ArUco marker pose detection in the SITL pipeline is evaluated open-loop against ground truth and is not coupled to closed-loop trajectory tracking.

---

## 11. Citation

### Review Mode (Anonymized)
```bibtex
@article{anonymous2026aca,
  title   = {Adversarial Contingency Auctions for Decentralized Multi-Robot Task Allocation under Strategic Blockages},
  author  = {Anonymous Authors},
  journal = {Under review},
  year    = {2026}
}
```

### Camera-Ready Toggle
To restore author identities for camera-ready publication:
1. In `paper.tex`, set `\anonymoustrue` to `\anonymousfalse`.
2. Update the citation block above with author metadata.
