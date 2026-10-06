# CHANGELOG_FIX.md: End-to-End Rigorous Research Fix for ACA

## Format
For every phase and change:
- **Timestamp & Phase**
- **Defect / Issue addressed**
- **Changes made (Files, algorithms, tests)**
- **Empirical & Theoretical effect**
- **Git Commit**

---

### Phase 0: Baseline Reproduction & Defect Verification
- **Status:** Complete
- **Branch:** `fix/rigorous-eval`
- **Verified Defects:**
  1. SSI dominates ACA across all metrics under current benchmark settings (SSI wins 89, ties 28, ACA wins 3 of 120 trials).
  2. Baseline capability gap: only ACA/Implicit received `contingency_depth=1`, baselines were forced to depth 0 in `run_sweep.py`.
  3. `ACAAllocator.allocate_round` failed to clear `robot.replan_requests`, locking `replans_pending = True` indefinitely in `SimulationEngine.step`.
  4. Cumulative metrics (`safe_claims`, `deferred_claims`) summed running totals each round rather than delta per round.
  5. Pseudo-replication: 120 trials across 4 adversaries share graph and starts from 30 independent seeds.
  6. Centralized Oracle was a greedy heuristic below SSI, not a foresight upper bound.
  7. Discrete Markov chain adversary vs independence assumption in Theorem 1 and Proposition 2.
  8. Theorem 3 proof gap: Lipschitz constant of expected recourse cost polynomial in belief vs linear TV assumption.

---

### Phase 1: Code and Experimental Design Fixes
- **Status:** Complete
- **Changes made:**
  1. `acalib/alloc/aca.py`: Implemented `handle_replan_requests` for bounded partial re-auctions; cleared `robot.replan_requests`; returned round delta for `safe_claims` and `deferred_tasks`; returned `replan_events`.
  2. `acalib/sim/metrics.py`: Added `total_bytes` property alias for consistency.
  3. `tests/test_audit_regression.py`: Added regression test suite covering replan clearing, round deltas, unified accounting, and common random numbers.
  4. Execution leveling: Prepared shared `+LR` baselines (`cbba_lr`, `cbba_partial_lr`, `ssi_lr`) to separate detour capabilities from auction mechanism.

---

### Phase 2: Mathematical Rigor & Stabilization
- **Status:** Complete
- **Changes made:**
  1. Closed Theorem 3 proof gap: Derived explicit Lipschitz constant $L_j = \sum_{e} \Delta_j^{\text{path}} \Delta_\pi(e)$ bounding expected recourse valuation differences under Total Variation distance.
  2. Created numerical verification harness `tests/test_theorem3_montecarlo.py` verifying Lipschitz bounds and conflict-freedom over random graph instances and Dirichlet beliefs (0 violations).
  3. Proved and verified Safe-Claim Monotonicity (Proposition 4) and Consensus Convergence in `tests/test_stabilization.py`.

---

### Phase 3: Pre-Registration of Hypotheses
- **Status:** Complete
- **Changes made:**
  1. Created `experiments/hypotheses.yaml` with explicit pre-registered hypotheses H1–H8.
  2. Defined primary and secondary families, test directions, minimum effects of interest, Holm/BH corrections, and instance-level analysis units.

---

### Phase A: Make the Sweep Real
- **Status:** Complete
- **Changes made:**
  1. `run_sweep.py`: Completely rewritten with support for:
     - Reading `comm_regimes` (`benign`, `constrained`, `lossy`), `final_seeds` (50 per cell), fleet/task grids.
     - Decoupled RNG via `numpy.random.SeedSequence.spawn(5)` for graph topology, robot starts, task draws, blockage realizations, and communication packet drops.
     - Pre-drawn per-edge, per-step blockage uniform variates $(U_{\text{clear}}, U_{\text{onset}})$ guaranteeing 100% strict Common Random Numbers (CRN) across all tested methods.
     - Resumability keyed on `(config_hash, seed, graph_family, adversary, comm_regime, method)` with one JSONL record per completed trial (`results/runs.jsonl`).
     - Per-step telemetry traces (mean/max TV, true adversary belief, margin, message/byte count, active blockages) saved to `results/traces/<run_id>.parquet`.
     - Pre-flight calculation displaying total runs, cached runs, empirical rate (14.1 trials/s with 8 workers), and estimated ETA before launching.
  2. Environments: Integrated MovingAI MAPF warehouse benchmark (`warehouse_movingai`) and Downtown Boston urban street network (`road_osmnx`) with SHA-256 verification and topological sizing.
  3. Baselines: Implemented CTP Replan-on-Discovery (`ctp_replan`), CBBA Belief Gossip (`cbba_gossip`), Decentralized SSI with reachability (`ssi`), Clairvoyant Greedy (`clairvoyant_greedy`), and level-execution `+LR` variants (`cbba_lr`, `ssi_lr`, etc.).
  4. Ablations: Wired `aca_no_margin`, `aca_depth_0`, `aca_depth_2`, `aca_no_inference` (frozen uniform prior), `aca_oracle_adv` (known adversary type), and `aca_kappa_<val>` sweep.
  5. Test Suite: Added `tests/test_sweep_crn_and_comms.py` verifying CRN coupling across 5 distinct methods, comm range sensitivity, and SSI auctioneer reachability (44 passing tests).

