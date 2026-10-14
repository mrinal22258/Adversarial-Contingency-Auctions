# Protocol v6 Confirmatory Benchmark Execution Guide

This document provides the exact, reproducible execution procedure for running the pre-registered **Protocol v6 confirmatory evaluation** on a clean machine.

---

## 1. Environment & Prerequisites

- **Operating System:** Linux (Ubuntu 22.04+ recommended) or Windows 10/11
- **Python Version:** Python 3.10, 3.11, or 3.12
- **Compute Recommendation:** 8 to 16 physical CPU cores, 16 GB RAM

### Environment Setup
```bash
# 1. Clone or navigate to the repository root
cd Adversarial-Contingency-Auctions

# 2. Checkout the verified branch and tag
git checkout fix/audit-repairs
git checkout prereg-v6.1

# 3. Create a clean virtual environment
python -m venv venv_v6
# Linux/macOS:
source venv_v6/bin/activate
# Windows:
.\venv_v6\Scripts\activate

# 4. Install pinned dependencies from requirements.lock
pip install --upgrade pip
pip install -r requirements.lock
pip install -e .
```

---

## 2. Pre-Execution Protocol Verification

Before executing any benchmark trials, verify that the protocol configuration and seed list match the pre-registered cryptographic freeze:

```bash
python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml --strict
```

**Expected output:**
```
STATUS: PROTOCOL VERIFIED 100% VALID AND FROZEN (PASS)
```
- Total confirmatory seeds: 50 (SHA-256: `09638b69b6d331eb3738023b4ad7502116e7d4768405235cf396d76bc3eea5cb`)
- Candidate range: `[50000, 60000]`, disjoint from all historical seeds.

---

## 3. Workload & Expected Runtime

| Parameter | Value |
|---|---|
| Map Topologies | 5 (`warehouse_movingai`, `road_osmnx`, `rgg`, `grid`, `er`) |
| Adversary Models | 3 ($\theta_1$ Stochastic, $\theta_2$ Reactive, $\theta_4$ Cyclic Patrol) |
| Communication Regime | Nominal ($R_{\text{comm}} = 30.0$, $p_{\text{drop}} = 0.10$) |
| Confirmatory Seeds | 50 seeds ($N = 250$ independent clusters) |
| Evaluated Methods | 9 (`aca`, `aca_plus`, `aca_adaptive`, `aca_no_margin`, `aca_depth_0`, `cbba_lr`, `cbba_partial_lr`, `ctp_replan`, `ssi_lr`) |
| Fleet / Tasks | 4 robots, 15 tasks, bundle capacity 4, horizon 80 ticks |
| **Total Trials** | **6,750 trials** ($5 \times 3 \times 1 \times 50 \times 9$) |
| **Estimated Runtime** | **~35–45 CPU-hours** (~4.5 hours on an 8-core CPU) |

Output is strictly isolated under `results/confirmatory_v6/`. Global `results/runs.jsonl` is not touched.

---

## 4. Execution Commands

### A. Dry-Run Check (0 simulator steps)
Validate configuration parsing, trial conditioning, and directory creation without simulating:
```bash
python experiments/run_sweep.py --protocol v6 --output-dir results/confirmatory_v6 --workers 8 --dry-run
```

### B. Launch Full Confirmatory Sweep
```bash
python experiments/run_sweep.py --protocol v6 --output-dir results/confirmatory_v6 --workers 8 --strict
```
*(Adjust `--workers` to match your CPU core count, e.g. `--workers 16` on a 16-core machine).*

---

## 5. Crash Recovery & Resumability

The runner uses full 256-bit SHA-256 trial identities and atomic, locked per-record JSONL writes. If the run is interrupted by power failure, reboot, or user cancellation:

Simply re-run the exact same command:
```bash
python experiments/run_sweep.py --protocol v6 --output-dir results/confirmatory_v6 --workers 8 --strict
```

The runner will:
1. Strictly validate the integrity and SHA-256 of all previously completed records in `results/confirmatory_v6/runs.jsonl`.
2. Skip all completed trial hashes (`Skipping N already completed trials`).
3. Seamlessly resume simulation from the remaining unfinished trials.

---

## 6. Post-Run Verification & Results Generation

Once the sweep completes:

### Step 1: Verify Log Integrity
Ensure zero dropped writes, zero malformed JSON lines, and exact pairing between CSV and JSONL:
```bash
python tools/verify_log_integrity.py --protocol v6 --strict
```
**Expected output:**
```
STATUS: 100% CLEAN AND ATOMIC - ALL HASHES MATCH (PASS)
```

### Step 2: Build All Results & Claim Ledger
Recompute all primary cluster-level estimands, hypothesis tests under Holm–Bonferroni correction, tables, and figures:
```bash
python tools/build_all_results.py --protocol v6 --strict
```

### Step 3: Strict Paper Linter
Verify that all manuscript tables, macros, and figure sidecars match the verified build:
```bash
python tools/lint_paper.py --strict
```

### Step 4: Full Test Suite
Run the full test suite to confirm all statistical and behavioral invariants:
```bash
pytest -v -m "not (sitl or ortools or ui)"
```
