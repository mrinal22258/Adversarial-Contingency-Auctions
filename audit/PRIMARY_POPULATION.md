# PRIMARY POPULATION AUDIT & DATA LINEAGE SPECIFICATION

**Audit Date:** 2026-10-10  
**Data Source:** `results/raw_results.csv` (13,800 rows) & `results/runs.jsonl`  
**Execution Generator:** `experiments/run_extended_sweep.py` (`build_ofat_design()`)  
**Commit:** `72c1a431f61d82783cbdfbcf22ca9d52121f4bfa` (2026-10-08T08:38:06Z)  

---

## 1. Executive Verdict on Confirmatory Population Validity

> **STATUS: HISTORICAL / EXPLORATORY ONLY (Original Confirmatory Comparison INVALIDATED / UNAVAILABLE)**

The original dataset cannot serve as a valid pre-registered confirmatory study for the following definitive reasons:
1. **Confounded Population Pooling:** The sweep execution script generated both the primary nominal grid and all OFAT sensitivity variations into a single output file with identical provenance tags (`simulation_disclaimer: "SIMULATION ONLY -- Primary Grid Sweep"`, commit `72c1a431...`).
2. **Harmful Instance Aggregation:** `experiments/run_statistical_tests.py` grouped by `(graph_family, map_class, seed, method)` and averaged across ALL rows in the CSV. For methods evaluated in OFAT sweeps (`aca`, `cbba_partial_lr`, `ctp_replan`), their instance scores averaged disparate experimental conditions (fleet sizes $R \in \{4, 8, 12\}$, task counts $M \in \{15, 30, 60\}$, lossy comm regimes), while standard baselines (`cbba`, `ssi`, `implicit`) were evaluated exclusively at $R=4, M=15$.
3. **Data Loss During Recovery:** The deduplication logic in `tools/recover_runs.py` used a 5-tuple key `(graph_family, adversary, comm_regime, method, seed)`, which omitted $R$ and $M$, collapsing 300 distinct OFAT trials.
4. **README Claims Disproven:** The README claims a design of *"5 families × 4 adversaries × 3 comm regimes = 13,800 trials"*. This claim is demonstrably false: $5 \times 4 \times 3 \times 50 \times 14 = 42,000$, and the data actually contains 1 nominal regime and 15 OFAT regimes, with no runs for $\theta_5$ in the sweep.

Therefore, under Non-Negotiable Integrity Rule 2 and Rule 4, all existing 13,800 rows are classified as **historical exploratory data**. Confirmatory claims are deferred to the clean held-out evaluation in Stage 4.

---

## 2. Complete Decomposition of the 13,800 Experimental Rows

By reverse-engineering `build_ofat_design()` in `experiments/run_extended_sweep.py` against the raw CSV rows, the exact provenance of all 13,800 rows is established:

### A. Balanced Core Nominal Grid (10,500 trials)
- **Topologies (5 families):** `warehouse_movingai` (38), `road_osmnx` (216), `rgg` (35), `warehouse` (30), `er` (35)
- **Seeds:** 1 through 50 (50 independent instances per family $\times$ 5 families = 250 instances)
- **Adversaries (3 core profiles):** $\theta_1$ (stochastic), $\theta_2$ (reactive), $\theta_4$ (cyclic patrol)
- **Communication Regime:** `nominal` (comm range = 30.0 m, $p_{\text{drop}} = 0.10$)
- **Scale:** $R = 4$ robots, $M = 15$ tasks, max steps = 80
- **Methods Evaluated (14 methods):**
  - Proposed & Ablations: `aca`, `aca_depth_0`, `aca_depth_2`, `aca_no_inference`, `aca_no_margin`
  - Baselines: `cbba`, `cbba_lr`, `cbba_partial`, `cbba_partial_lr`, `ssi`, `ssi_lr`, `ctp_replan`, `implicit`, `clairvoyant_greedy`
- **Total Rows:** $5 \times 50 \times 3 \times 14 = \mathbf{10,500}$ trials.
- **Coverage:** Perfectly balanced. Every method has exactly 750 trials across the same 250 instances.

### B. Targeted Adversary Stress Tests (400 trials)
- **Topologies (2 families):** `warehouse_movingai`, `rgg`
- **Seeds:** 1 through 25 (25 seeds)
- **Adversaries (2 profiles):** $\theta_3$ (budgeted interdiction), $\theta_6$ (switching)
- **Methods (4 methods only):** `aca`, `ctp_replan`, `cbba_partial_lr`, `cbba_lr`
- **Total Rows:** $2 \times 25 \times 2 \times 4 = \mathbf{400}$ trials (100 trials per method).
- *Note:* Other baselines (`cbba`, `ssi`, ablations) were NOT evaluated on $\theta_3$ or $\theta_6$.

### C. OFAT Sensitivity & Parameter Variations (2,900 trials)
All OFAT variations were evaluated on seeds 1–25 across selected topologies:
1. **Foresight Optimal (`ofat_foresight`, 150 trials):**
   - 2 families (`warehouse_movingai`, `rgg`) $\times$ 25 seeds $\times$ 3 methods (`aca`, `clairvoyant_greedy`, `foresight_opt`) at $M=10$.
2. **Pinsker Kappa Sweep (`ofat_kappa`, 300 trials):**
   - 2 families $\times$ 25 seeds $\times$ 6 kappa variants (`aca_kappa_0`, `0.1`, `0.25`, `0.5`, `1`, `2`).
3. **Fleet Size Scaling (`ofat_R`, 300 trials):**
   - $R \in \{8, 12\}$ at $M=30$: 2 families $\times$ 25 seeds $\times$ 2 fleet sizes $\times$ 3 methods (`aca`, `cbba_partial_lr`, `ctp_replan`).
4. **Task Count Scaling (`ofat_M`, 300 trials):**
   - $M \in \{30, 60\}$ at $R=4$: 2 families $\times$ 25 seeds $\times$ 2 task counts $\times$ 3 methods (`aca`, `cbba_partial_lr`, `ctp_replan`).
5. **Comm Range Sweep (`ofat_range_*`, 750 trials):**
   - Range $\in \{15, 25, 35, 50, 80\}$ m on $\theta_1$: 2 families (`road_osmnx`, `er`) $\times$ 25 seeds $\times$ 5 ranges $\times$ 3 methods.
6. **Packet Drop Rate Sweep (`ofat_pdrop_*`, 800 trials):**
   - $p_{\text{drop}} \in \{0.0, 0.05, 0.20, 0.40\}$ on $\theta_2$: 2 families (`road_osmnx`, `er`) $\times$ 25 seeds $\times$ 4 drop rates $\times$ 4 methods (`aca`, `cbba_lr`, `cbba_partial_lr`, `ctp_replan`).
7. **Environmental Perturbations (`ofat_poisson_arrivals`, `ofat_network_partitions`, 300 trials):**
   - 2 variants $\times$ 2 families $\times$ 25 seeds $\times$ 3 methods (`aca`, `cbba_partial_lr`, `ctp_replan`).

**Grand Total:** $10,500 + 400 + 2,900 = \mathbf{13,800}$ trials.

---

## 3. Explanation of Missing Adversary $\theta_5$

- `theta_5_real_trace_replay` is defined in `acalib/env/adversaries.py` (line 20).
- It replays physical road closure events from `data/maps/boston_work_zones.csv` (Analyze Boston dataset).
- Because it requires geospatial road street matching against the Boston downtown arterial network, it is meaningless on abstract synthetic topologies (`rgg`, `er`, `warehouse`).
- It was intentionally excluded from the synthetic grid sweep and evaluated in `tests/test_real_trace_adversary.py` and SITL simulation on Boston road network.
- The README statement claiming "4 adversary profiles" across all environments was inaccurate in failing to explain this domain-specific separation.

---

## 4. Recover Runs (`tools/recover_runs.py`) Effects

- **Raw Records Read:** 13,800 valid JSON lines in `results/runs.jsonl`.
- **Corrupted Lines:** 0 unparseable lines in the committed `results/runs.jsonl`.
- **Deduplication Defect:**
  - `recover_runs.py` defined key as: `(graph_family, adversary, comm_regime, method, seed)`.
  - When run, this collapses the 300 trials where $R$ or $M$ varied within the same `comm_regime` (`ofat_R` with $R=8$ vs $R=12$; `ofat_M` with $M=30$ vs $M=60$), leaving only 13,500 rows.
  - **Resolution:** The true unique experimental unit key must be:
    `instance_key = (graph_family, adversary, comm_regime, method, seed, n_robots, n_tasks)`.
    Under this 7-tuple key, exactly 13,800 unique trials exist, with 0 duplicates.

---

## 5. Comparability Matrix Summary

Detailed CSV matrices are generated in:
- `audit/coverage_matrix_trials.csv`
- `audit/coverage_matrix_instances.csv`
- `audit/method_comparability.csv`

| Method | Total Trials | Paired with ACA | ACA Unmatched | Method Unmatched | Fully Paired? |
|---|---|---|---|---|---|
| `aca` | 1650 | 1650 | 0 | 0 | Yes (Self) |
| `aca_depth_0` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `aca_depth_2` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `aca_no_inference` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `aca_no_margin` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `cbba` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `cbba_lr` | 1050 | 1050 | 600 | 0 | Yes (Core + $\theta_3$/$\theta_6$ + pdrop) |
| `cbba_partial` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `cbba_partial_lr` | 1600 | 1600 | 50 | 0 | Yes (Core + OFAT sweeps) |
| `ctp_replan` | 1600 | 1600 | 50 | 0 | Yes (Core + OFAT sweeps) |
| `ssi` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `ssi_lr` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `implicit` | 750 | 750 | 900 | 0 | Yes (Core only) |
| `clairvoyant_greedy` | 800 | 800 | 850 | 0 | Yes (Core + foresight) |
| `foresight_opt` | 50 | 50 | 1600 | 0 | Yes (Foresight only) |
| `aca_kappa_*` (6) | 50 each | 0 | 1650 | 50 | No (Separate method names) |

### Comparability Rule for Honest Benchmarking:
- In any comparison between ACA and a baseline $M$, statistics must be computed strictly on the intersection $\mathrm{Trials}(\text{ACA}) \cap \mathrm{Trials}(M)$.
- The core nominal comparison ($N = 750$ paired trials across 250 instances) is the ONLY benchmark where all literature baselines are directly and fairly comparable.
- No table may report unpaired aggregate means alongside paired Wilcoxon test markers.
