# ACA Repository Comprehensive Audit Findings (Stage 1)

This document records all confirmed defects, discrepancies, integrity violations, and statistical bugs identified during the Stage 1 audit of `Adversarial-Contingency-Auctions-main` (branch `fix/rigorous-eval`).

---

## Findings Summary Matrix

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

## Detailed Finding Logs

### Finding F-01: Primary Confirmatory Population Confounded with OFAT Sweeps
- **Severity:** `BLOCKER`
- **Location:** `results/raw_results.csv`, `experiments/run_extended_sweep.py`
- **Reproduction:**
  ```powershell
  python tools/build_coverage_matrices.py
  ```
- **Evidence:** All 13,800 rows carry the exact same git commit `72c1a431...` and metadata comment `"SIMULATION ONLY -- Primary Grid Sweep"`. However, `comm_regime` contains 16 distinct values: 10,900 `nominal` rows and 2,900 sensitivity sweep rows (`ofat_kappa_*`, `ofat_loss_*`, `ofat_scale_*`, `ofat_depth_*`).
- **Impact:** Previous documentation claimed a full factorial $5 \times 4 \times 3$ grid produced 13,800 rows, obscuring the fact that 2,900 rows are exploratory OFAT sweeps and 400 rows are targeted adversary sweeps ($\theta_3, \theta_6$).
- **Root Cause:** Single sweep script execution with omnibus metadata tagging.
- **Resolution:** Formally declared the original confirmatory comparison invalidated/unavailable in `audit/PRIMARY_POPULATION.md`. Reconstructed the balanced nominal population ($N=750$ paired trials across 250 independent instances) and isolated OFAT/targeted conditions.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_instance_vs_row_count`.

---

### Finding F-02: Stale Pair Count Loop Leak across Baselines
- **Severity:** `BLOCKER`
- **Location:** `experiments/make_tables.py`, lines 97 & 109
- **Reproduction:**
  ```python
  from experiments.make_tables import compute_paired_statistics
  # Run across baselines with unequal sample sizes
  ```
- **Evidence:** `len(paired)` was assigned outside or at the termination of baseline comparisons, attaching the pair count of the final baseline to all other baselines.
- **Impact:** Misrepresented the statistical sample size of matched comparisons.
- **Root Cause:** Scoping bug reusing mutable `paired` dataframe variable.
- **Fix:** Per-baseline dictionary indexing `paired_dfs[m]` with explicit guard assertions against duplicate keys.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_compute_paired_statistics_independent_n`.

---

### Finding F-03: Unpaired Aggregate Means Paired with Matched-Pair Markers in Table II
- **Severity:** `BLOCKER`
- **Location:** `experiments/make_tables.py`, lines 165–210
- **Reproduction:**
  ```powershell
  python experiments/make_tables.py
  ```
- **Evidence:** Table II computed method-level means and bootstrap CIs over all available rows (e.g. 1,650 rows for ACA including OFAT scale variants) but juxtaposed paired Wilcoxon significance markers computed only on nominal subsets.
- **Impact:** Violates statistical integrity rule: means, intervals, and hypothesis markers must describe the identical experimental population.
- **Root Cause:** Mixing exploratory sensitivity runs with nominal benchmark runs in table aggregation.
- **Fix:** Filtered `generate_main_results_table` to evaluate exclusively on the balanced core grid (nominal regime, 8 robots, 30 tasks, $\theta_1/\theta_2/\theta_4$), where all 14 evaluated methods share exactly 750 trials across 250 instances.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_paired_estimand_consistency`.

---

### Finding F-04: 5-Tuple Key Collapsed Distinct Scale Sweep Trials
- **Severity:** `HIGH`
- **Location:** `tools/recover_runs.py`, lines 34–42
- **Reproduction:**
  ```python
  from tools.recover_runs import recover_from_jsonl
  # Run recovery on runs.jsonl containing ofat_scale_robots_12 runs
  ```
- **Evidence:** The deduplication key `(graph_family, adversary, comm_regime, method, seed)` omitted `n_robots` and `n_tasks`.
- **Impact:** 300 OFAT scale sensitivity trials ($R \in \{8, 12\}, M \in \{30, 60\}$) sharing the same seed were silently dropped during recovery from `runs.jsonl`.
- **Root Cause:** Incomplete tuple definition for experimental unit keys.
- **Fix:** Expanded deduplication key to the 7-tuple: `(graph_family, adversary, comm_regime, method, seed, n_robots, n_tasks)`.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_scale_collision_differentiation`.

---

### Finding F-05: Boston Road Network Edge Count Discrepancy (323 vs 326)
- **Severity:** `HIGH`
- **Location:** `data/maps/manifest.json`, `results/numbers.tex`, `acalib/demo/provenance.py`
- **Reproduction:**
  ```python
  from acalib.env.real_maps import generate_real_road_network
  g = generate_real_road_network()
  print("Nodes:", g.number_of_nodes(), "Edges:", g.number_of_edges())
  ```
- **Evidence:** OSMnx GraphML file contains 326 raw XML edge records. Loading into NetworkX simple undirected graph produces 216 nodes and 323 edges. Previous documentation inconsistently cited 323 and 326.
- **Impact:** Caused hash/topology verification failures and inconsistency between text macros and map parser.
- **Root Cause:** Parallel multigraph edge collapse during conversion from directed OSMnx multigraph to simple navigation graph.
- **Fix:** Documented both statistics in `data/maps/manifest.json` (`raw_graphml_edges: 326`, `edges: 323`), synchronized `results/numbers.tex`, and verified that exactly 112 simple edges intersect active Boston work zones.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_boston_map_edge_counts_in_manifest`.

---

### Finding F-06: Hardcoded Empirical Macros Bypassing Dynamic Pipeline
- **Severity:** `HIGH`
- **Location:** `experiments/make_tables.py`, lines 500–680
- **Reproduction:** Compare `results/numbers.tex` against upstream JSON/CSV artifacts.
- **Evidence:** Empirical results such as `\aeHtwoCbbaLrDiff = +1.90`, Hodges-Lehmann medians, yaw CIs, and map edge counts were hardcoded literals in `generate_numbers_macro_file`.
- **Impact:** Disconnect between raw data and reported values; hand-edited values could survive code changes.
- **Root Cause:** Script convenience shortcuts during draft preparation.
- **Fix:** Rewrote `generate_numbers_macro_file` to ingest dynamic outputs from `results/stats/hypothesis_results.csv`, `data/maps/manifest.json`, `results/sitl/analysis/sitl_vs_graph_summary.json`, and `results/stats/friedman_nemenyi_completion.json`.
- **Regression Test:** `experiments/make_tables.py` execution logged via audit logger.

---

### Finding F-07: Fallback SHA-256 Hashes Masking Missing / Corrupted Map Files
- **Severity:** `HIGH`
- **Location:** `acalib/demo/provenance.py`, lines 37 & 67–69
- **Reproduction:**
  ```python
  from acalib.demo.provenance import verify_map_provenance
  ```
- **Evidence:** Hardcoded hash string fallback constants allowed file verification to report `VERIFIED` even when manifest files were absent.
- **Impact:** Created false sense of cryptographic integrity.
- **Root Cause:** Baked-in default arguments.
- **Fix:** Prohibited all fallback constants. Implemented strict 5-state verification engine: `VERIFIED`, `MISMATCH`, `MISSING`, `UNAVAILABLE`, `UNVERIFIED`.
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_no_fallback_hashes_in_provenance`.

---

### Finding F-08: Linter Enforcing Clean Git State on Development Trees
- **Severity:** `MEDIUM`
- **Location:** `tools/lint_paper.py`, lines 230–245
- **Reproduction:**
  ```powershell
  python tools/lint_paper.py
  ```
- **Evidence:** Linter crashed with exit code 1 if git working tree was dirty, preventing continuous audit and development.
- **Impact:** Blocked local verification workflows and invited risky git reset operations.
- **Root Cause:** Conflation of development verification with release gate.
- **Fix:** Added `--strict-release` flag. In development mode, the dirty tree is reported truthfully as a notice without halting execution.
- **Regression Test:** `python tools/lint_paper.py` passes cleanly on dirty tree.

---

### Finding F-09: Float Formatting Emitting False `p = 0.00`
- **Severity:** `MEDIUM`
- **Location:** `experiments/make_tables.py`, lines 488 & 496
- **Reproduction:** Inspect generated `results/numbers.tex` line 104 (`\newcommand{\aePvalNoMargin}{0.00}`).
- **Evidence:** Standard float formatting `{pval:.2f}` rendered valid infinitesimal p-values ($p < 10^{-4}$) as literal `0.00`.
- **Impact:** Scientifically false reporting; p-values cannot be identically zero.
- **Root Cause:** Precision-truncated string formatting.
- **Fix:** Enforced `format_p_value_macro` formatting threshold ($< 0.001$).
- **Regression Test:** `tests/test_stage1_provenance_and_stats.py::test_p_value_formatting_no_false_zero`.

---

### Finding F-10: Inaccurate Benchmark Grid Description in Documentation
- **Severity:** `LOW`
- **Location:** `README.md`
- **Evidence:** Described raw results as "5 families x 4 adversaries x 3 comm regimes = 13,800 trials".
- **Impact:** Misled readers on benchmark structure.
- **Root Cause:** Stale documentation written prior to OFAT sensitivity sweep expansion.
- **Fix:** Full breakdown documented in `audit/PRIMARY_POPULATION.md`; scheduled for synchronization in Stage 3.

---

### Finding F-11: Heuristic Lipschitz Multipliers and Duplicate Test Oracle
- **Severity:** `BLOCKER`
- **Location:** `acalib/alloc/aca.py:96-126`, `tests/test_theorem3_montecarlo.py:21-41`
- **Reproduction:** Inspect docstring ("Rigorous Lipschitz Constant") vs code (`delta_path = max(5.0, nominal_cost * 1.5)`).
- **Evidence:** Code used heuristic multipliers (`1.5 * nominal_cost` in production, `2.5 * nominal_len` in test) and arbitrary floors instead of computing analytical branch bounds. The test harness defined its own duplicate function `compute_explicit_lipschitz` rather than testing production.
- **Impact:** Theoretical claims in Proposition 2 were mathematically decoupled from the code implementation.
- **Root Cause:** Incomplete formal derivation during early implementation.
- **Fix:** Derived and implemented exact multivariable Mean Value Theorem bound `compute_lipschitz_bound` in `acalib/agents/contingency.py`: $L_j = \sum_{k=1}^K |\text{branch\_cost}_k - \text{primary\_cost}| \cdot \Delta \pi(e_k)$. Replaced heuristic code in both `acalib/alloc/aca.py` and unified `tests/test_theorem3_montecarlo.py` to call production.
- **Regression Test:** `tests/test_theorem3_montecarlo.py::test_lipschitz_cost_bound_monte_carlo` and `test_pure_type_sensitivity_range`.

---

### Finding F-12: Discrepant Theorem/Proposition Numbering vs `paper.tex`
- **Severity:** `HIGH`
- **Location:** `README.md:27-29`, `acalib/alloc/aca.py:98`, `acalib/agents/tom.py:2`
- **Reproduction:** Grep for "Theorem 1", "Theorem 3", "Proposition 2" across repo and compare against `paper.tex`.
- **Evidence:** Code and README referred to expected recourse valuation as "Theorem 1" (paper: Proposition 1, `prop:valuation`), Pinsker claim margin as "Theorem 3" (paper: Theorem 1, `thm:conflict_freedom`), and detours as "Proposition 2" (paper: Proposition 4, `prop:messages`).
- **Impact:** Severe reader confusion and broken traceability between formal manuscript proofs and repository code symbols.
- **Root Cause:** Working draft numbering survived into release branch.
- **Fix:** Systematically reconciled all references in `README.md`, docstrings, and created comprehensive traceability map in `audit/THEOREM_CODE_MAP.md`.
- **Regression Test:** `tests/test_theorem3_montecarlo.py` updated docstrings and assertions.

---

### Finding F-13: False Claim of ">= 100,000 instances" in Test Docstring
- **Severity:** `MEDIUM`
- **Location:** `tests/test_theorem3_montecarlo.py:7`
- **Reproduction:** Inspect test loops ($100 \times 50 = 5,000$, and $50 \times 100 = 5,000$).
- **Evidence:** Docstring asserted "across >= 100,000 Monte Carlo graph instances", whereas execution ran exactly 5,000 samples.
- **Impact:** False audit claims and misleading test documentation.
- **Root Cause:** Stale docstring from an unexecuted heavy benchmark script.
- **Fix:** Updated docstrings to state exact verified count (5,000 sampled belief pairs across 100 graphs) and clearly noted that sampling demonstrates numerical consistency, not mathematical proof.
- **Regression Test:** `tests/test_theorem3_montecarlo.py` passes all 6 tests.

