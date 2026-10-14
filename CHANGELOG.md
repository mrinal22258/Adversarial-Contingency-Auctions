# Changelog

All notable changes to the Adversarial Contingency Auctions (ACA) project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.1.0] - 2026-10-14: Audit Repairs, Policy Equivalence, and Protocol v6 Pre-Registration

### Highlights
- **Gate 1 (Runner Protocol & Single Source of Truth)**: Registered authoritative 50 confirmatory seeds (`09638b69...`) and 15 development seeds (`19a8aabd...`) in `experiments/configs/protocol_v6.yaml`; fixed trial identity hashing in `experiments/run_sweep.py`; guaranteed isolated output directories; added atomic file locking.
- **Gate 2 (Policy Equivalence & Active Pruning)**: Implemented full recursive recourse trees with stable node and branch IDs; unified `plan_hash` across valuation, Lipschitz bound, cache, and executor; defined active pruning with explicit recovery cost leaves; calibrated active threshold $\tau_{\text{prune}} = 0.20 > 0.12$; removed default marginal fallbacks.
- **Gate 3 (Hazard Event Contract & Grounded Beliefs)**: Formulated explicit sensing contract in `docs/HAZARD_CONTRACT.md`; eliminated all ungrounded default-state marginal queries; added held-out Brier calibration reporting.
- **Gate 4 (Cluster-Aware Statistics & Claim Ledger V2)**: Standardized on cluster-level (`graph_family × seed`) primary estimands; rewrote `audit/CLAIM_LEDGER_V2.csv` with executable verification; linked Theorem 1 commitment evidence into the cryptographic hash chain.
- **Gate 5 (Protocol v6 Preparation & Smoke Validation)**: Built `tools/verify_protocol.py`; authored execution guide `RUN_V6.md`; created reproducible smoke test pipeline in `results/smoke/`; tagged `prereg-v6.1`.
- **Gate 6 (Manuscript, UI, and Documentation Synchronization)**: Reflected three-tier evidence hierarchy (exploratory grid, held-out v5 reversal, pending v6); enforced double-blind anonymity; updated UI telemetry with live hashes and protocol pending status.

---

## [2.0.0] - 2026-10-11: Complete Repository Overhaul, Rigorous Evaluation & Mission Control

### Highlights
- **Strict Protocol v5 Pre-Registration & Confirmatory Evaluation**: Strict separation of hyperparameter tuning (seeds 1–30) and confirmatory evaluation on un-tuned seeds (seeds 101–130, $N = 450$ instances, 3,600 trials) across 5 graph families and 3 adversary regimes.
- **RA-L 8-Page Main Manuscript & 3-Page Supplement**: Manuscript fits strictly within the 8-page IEEE RA-L ceiling with column-balanced references; extended distributions, forest plots, and sweeps compiled cleanly in `supplement.pdf`. Strict automated provenance linter (`tools/lint_paper.py`) passes with 0 violations.
- **Mission-Control Telemetry Web Interface**: Production-ready, modularized interactive dashboard with persistent left-shell navigation, real map backdrops (Downtown Boston OSMnx, MovingAI warehouse), live telemetry, step-by-step playback, and reproducible CLI command generation.
- **Complete Verification & Scientific Honesty**: Zero hand-typed numbers across repository; all public surfaces (`index.html`, `README.md`, `RESULTS_VERDICT.md`, `paper.tex`) synchronized with result logs; negative results and trade-offs reported transparently.

---

### Section 1: Algorithmic, Theoretical, and Experimental Pipeline Overhaul

#### Phase 0: Baseline Reproduction & Defect Verification
- Verified initial defects: SSI domination due to missing baseline recourse, lack of execution leveling (`contingency_depth=1` only on ACA), sticky replan requests in `SimulationEngine`, cumulative metric calculation bugs, and psuedo-replication.
- Diagnosed identifiability gap in discrete Markov adversary models and TV Lipschitz continuity bounds in early proofs.

#### Phase 1: Code and Experimental Design Fixes
- `acalib/alloc/aca.py`: Implemented `handle_replan_requests` for bounded partial re-auctions; cleared `robot.replan_requests`; returned round delta for `safe_claims` and `deferred_tasks`; returned `replan_events`.
- `acalib/sim/metrics.py`: Added `total_bytes` property alias for consistent message accounting.
- `tests/test_audit_regression.py`: Added regression test suite covering replan clearing, round deltas, unified accounting, and common random numbers.
- **Execution Leveling**: Prepared shared `+LR` baselines (`cbba_lr`, `cbba_partial_lr`, `ssi_lr`) to separate detour capabilities from auction mechanism.

#### Phase 2: Mathematical Rigor & Stabilization
- Closed Theorem 1 proof gap: Derived explicit Lipschitz constant $L_j = \Delta_j = \max_\theta c(j\mid\theta) - \min_\theta c(j\mid\theta)$ bounding expected recourse valuation differences under Total Variation distance via Kantorovich–Rubinstein duality.
- Verified Safe-Claim Monotonicity (Proposition 2) and Consensus Convergence in `tests/test_stabilization.py`.
- Formulated Theorem 1 conflict-freedom conditionally on bounded estimation error (Assumption 1: $\mathrm{TV}(B_s, \hat{B}_s) \le \eta_{\text{eff}}$).

#### Phase 3: Pre-Registration of Hypotheses (prereg-v4)
- Created `experiments/hypotheses.yaml` with explicit pre-registered hypotheses H1–H8.
- Defined primary and secondary families, test directions, minimum effects of interest, Holm/BH corrections, and instance-level analysis units.
- Categorized exploratory/post-hoc analyses honestly, controlling family-wise error rates under pre-registered Holm step-down correction.

#### Phase 4: Experimental Sweep Execution ($N = 13,800$ Trials)
- `run_sweep.py`: Completely rewritten with support for:
  - Reading `comm_regimes` (`benign`, `constrained`, `lossy`), `final_seeds` (50 per cell), fleet/task grids.
  - Decoupled RNG via `numpy.random.SeedSequence.spawn(5)` for graph topology, robot starts, task draws, blockage realizations, and communication packet drops.
  - Pre-drawn per-edge, per-step blockage uniform variates $(U_{\text{clear}}, U_{\text{onset}})$ guaranteeing 100% strict Common Random Numbers (CRN) across all tested methods.
  - Resumability keyed on `(config_hash, seed, graph_family, adversary, comm_regime, method)`.
- Environments: Integrated MovingAI MAPF warehouse benchmark (`warehouse_movingai`) and Downtown Boston urban street network (`road_osmnx`) with SHA-256 verification and topological sizing.
- Baselines: Implemented CTP Replan-on-Discovery (`ctp_replan`), CBBA Belief Gossip (`cbba_gossip`), Decentralized SSI with reachability (`ssi`), Clairvoyant Greedy (`clairvoyant_greedy`), and level-execution `+LR` variants (`cbba_lr`, `ssi_lr`, etc.).
- Ablations: Evaluated `aca_no_margin`, `aca_depth_0`, `aca_depth_2`, `aca_no_inference` (frozen uniform prior), `aca_oracle_adv` (known adversary type), and interdiction budget sweeps ($\kappa \in \{2, 4, 6\}$).

#### Phase 5: Software-in-the-Loop (SITL) Physics & Synthetic Vision Simulation
- Built headless PyBullet simulation (`p.DIRECT`) on MovingAI warehouse and Boston road networks with differential-drive unicycle kinematics.
- Verified 1,440 continuous simulation trials; identified Bland-Altman completion domain gap (-18.9 pp) and rank correlation ($\rho = 0.486$) between instantaneous graph planning and continuous physical execution.
- Evaluated synthetic-vision overhead tracking pipeline with ArUco fiducials (82.9% detection rate, 0.416 m position error, 0.62° orientation error).
- Disclaimed all physical hardware in manuscript, README, and web UI.

---

### Section 2: Web Application & Mission Control Telemetry Rebuild

#### Phase A: Installation & Dependency Hygiene
- Unified dependencies in `pyproject.toml`; pinned `gradio>=5.0.0,<7.0.0`.
- Added lazy imports for optional solvers (`ortools`), preventing import failures when running demo without CP-SAT.
- Added standard `Dockerfile` with Python 3.10-slim, non-root user, and pinned dependencies.

#### Phase B: Application Rebuild on Real Environments
- Removed synthetic graphs from demo interface: restricted runtime options to Downtown Boston OSMnx (216 nodes) and MovingAI warehouse (38, 56, 420 nodes).
- Fixed geometry rendering bug in `acalib/demo/render.py` by extracting spatial positions from tuple attribute `"pos"`.
- Added real City of Boston Public Works permitted active work zone overlays and ASCII warehouse grid backdrop rasterization.

#### Phase C: Telemetry, Diagnostics & UX
- Implemented modern calm indigo design system (zero emojis) with accessible contrast.
- Implemented dynamic 7-card KPI ribbon (Completion, Conflicts, Messages, Welfare, Runtime, TV Bound, Safe Claims).
- Added timeline scrubber with `gr.Timer` playback controls.
- Added sticky event log with category filter, "Why did tasks fail?" diagnostic table, and paired baseline benchmarking.
- Added one-click CLI command reproduction string generator for terminal execution.

---

### Section 3: Protocol v5 Hyperparameter Tuning & Held-Out Confirmatory Sweep

#### Tuning Search (Seeds 1–30)
- Pre-registered grid search executed across 42 parameter combinations on seeds 1–30 via `experiments/run_tuning_search.py`.
- Selected optimal configuration saved to `results/tuning/best_hyperparameters.json`:
  - Prune threshold: $m_{\text{prune}} = 0.06$
  - Adaptive margin scaling factor: $\kappa = 0.5$
  - Adaptive base factor: $0.75$, weight factor: $0.25$

#### Confirmatory Evaluation (Held-Out Seeds 101–130)
- Executed confirmatory evaluation on un-tuned seeds 101–130 ($N = 450$ instances, 3,600 total trials) via `experiments/run_heldout_eval.py`.
- Evaluated pre-registered hypotheses H1–H7 under family-wise Holm–Bonferroni error control:
  - **H1 (Parity ACA+ vs ACA Static)**: Mean diff +0.04 pp completion (Holm $p = 1.0000$).
  - **H3/H4 (Parity with Level-Recourse Baselines)**: Parity with CBBA (+LR) and CBBA-PR (+LR) under local detour leveling.
  - **H6 (Superiority over SSI)**: ACA+ achieves +11.96 pp completion superiority over SSI (+LR) ($p < 0.001$, Cohen's $d_z = 0.584$).
  - **H7 (Margin Conflict Reduction Confirmed)**: ACA reduces total conflicts by 20.6% vs `aca_no_margin` (39.66 vs 49.93, $p < 0.001$) without significant completion penalty ($p = 0.0906$).
- Logged confirmatory artifacts: `results/confirmatory/heldout_v5_results.csv`, `heldout_v5_summary.csv`, and `heldout_v5_statistical_tests.json`.
