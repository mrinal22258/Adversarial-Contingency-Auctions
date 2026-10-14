# Confirmatory Results Directory

This directory stores frozen confirmatory datasets for the Adversarial Contingency Auctions (ACA) project.

All files in this directory must explicitly include a protocol version tag (`_v5_`, `_v6_`, etc.) in their filename to maintain strict separation between experimental tiers.

---

## Datasets

### 1. Protocol v5 Confirmatory Benchmark (`heldout_v5_*`)
- **Files:**
  - `heldout_v5_results.csv`: 3,600 execution records
  - `heldout_v5_runs.jsonl`: 3,541 raw streaming records (concurrent unbuffered write artifact)
  - `heldout_v5_summary.csv`: Summary statistics by method
  - `heldout_v5_statistical_tests.json`: Paired statistical tests under Holm–Bonferroni FWER control
- **Population:** $N = 450$ instances (30 seeds: 101–130 $\times$ 5 graph families $\times$ 3 adversary regimes), 8 methods.
- **Scientific Role:** Frozen out-of-sample confirmatory tier. Demonstrates the headline reversal where `CBBA+LR` outperforms `ACA` on completion ($94.67\%$ vs $92.40\%$, difference $+2.22$ pp) and net welfare ($958.9$ vs $937.4$) with fewer conflicts ($25.48$ vs $39.66$), and confirms the Pinsker margin trade-off ($-20.6\%$ conflicts relative to no-margin ablation).
- **Status:** Frozen, pinned, and immutable.

### 2. Protocol v6 Confirmatory Replication (Pending)
- **Target Directory:** `results/confirmatory_v6/`
- **Population:** 50 fresh random seeds ($[50000, 60000]$), 9 methods, full recursive tree execution with grounded hazard state, active calibrated pruning ($\tau_{\text{prune}} = 0.15$), atomic logging.
- **Status:** Pre-registered and cryptographically frozen in `protocols/prereg-v6.md` and `experiments/configs/protocol_v6.yaml`. Execution instructions in `RUN_V6.md`.

---

## Disambiguation Note: Stage-4 Pilot Relocation

The 300-row Stage-4 pilot evaluation on seeds 51–60 (5 methods) was historically named `heldout_results.csv`, `heldout_summary.csv`, and `heldout_runs.jsonl`. Because that dataset represents an exploratory pilot rather than confirmatory benchmark evidence, it has been relocated to:
- `results/pilot/stage4_pilot_results.csv`
- `results/pilot/stage4_pilot_summary.csv`
- `results/pilot/stage4_pilot_runs.jsonl`
