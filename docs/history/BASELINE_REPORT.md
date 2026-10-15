# BASELINE AUDIT REPORT

**Date & Time (UTC):** 2026-10-10T05:39:00Z  
**Branch:** `fix/rigorous-eval`  
**Git HEAD Commit:** `44d73b0cf1dec8e301e0a43a4961d22dba33a614`  
**Working Tree Status:** DIRTY (53 uncommitted / untracked files)  
**Dirty Diff SHA-256:** `e26b429513c735ef2ece161b1008bce3659a9a7f959f98f0e71b647188febc89`  
**Sweep Run Metadata Commit:** `72c1a431f61d82783cbdfbcf22ca9d52121f4bfa` (ancestor commit on 2026-10-08T08:38:06Z)  

---

## 1. System Environment & Capability Probe

A full hardware and toolchain probe was conducted on the host system:
- **Operating System:** Windows 11 (AMD64)
- **CPU Count:** 12 logical cores
- **Python Version:** 3.12.7 (Anaconda distribution, `[REDACTED_USER]\anaconda3\python.exe`)
- **Key Installed Packages:**
  - `pybullet`: installed (build Oct 7 2026)
  - `ortools`: 9.14.6206
  - `gradio`: 6.28.0
  - `playwright`: installed
  - `scipy`: 1.13.1
  - `numpy`: 2.2.4
  - `pandas`: 2.2.3
  - `networkx`: 3.4.2
  - `pytest`: 9.1.1
  - `statsmodels`: 0.15.0
  - `matplotlib`: 3.10.0
  - `seaborn`: 0.13.2
  - `pyyaml`: 6.0.2
- **LaTeX Toolchain:**
  - `pdflatex`: `C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.EXE` (AVAILABLE)
  - `latexmk`: `C:\Program Files\MiKTeX\miktex\bin\x64\latexmk.EXE` (AVAILABLE)
  - `bibtex`: `C:\Program Files\MiKTeX\miktex\bin\x64\bibtex.EXE` (AVAILABLE)
- **Network Access:** AVAILABLE (verified via ping and HTTP handshake)

All dependencies and execution engines are functional. No blocked environments.

---

## 2. Baseline Test Suite Verification

- **Command Executed:** `pytest -v` (logged in `audit/command_log.jsonl`)
- **Collection Count:** 116 tests collected across 22 test modules
- **Execution Outcome:** 116 passed, 0 failed, 0 errors in 193.04s (03:13)
- **Environmental Failures:** 0
- **Assertion Failures:** 0

All 116 baseline regression tests pass in the current working copy.

---

## 3. Baseline Generated Artifacts Snapshot

In accordance with non-negotiable integrity rule 3, all pre-existing generated artifacts were copied to `audit/baseline_snapshot/` before any modifications:
- **Snapshot Location:** `audit/baseline_snapshot/`
- **Total Artifacts Preserved:** 99 files
- **Hash Manifest:** `audit/baseline_snapshot/manifest.json` (SHA-256, byte sizes, UTC mtimes)
- **Inventory Manifest:** `audit/repository_inventory.json` (2,486 workspace files hashed and inventoried)

Key preserved artifacts include:
- `results/numbers.tex` (SHA-256: `69894e6377759d58a18357a7e1fba74044146a81b3731ea54eeef9948092a061`)
- `results/table_main_results.tex` & `.md`
- `results/table_sitl.tex` & `.md`
- `results/table_stratified.tex` & `.md`
- `results/table_per_condition.csv`
- `results/run_metadata.json`
- `results/config_used.yaml`
- `results/power_analysis.csv`
- `results/demo_baseline_20seeds.json`
- `paper.pdf` & `supplement.pdf`
- All 62 figure files in `results/figures/`
- All 18 screenshots in `docs/screenshots/`
- SITL vision metrics and video assets

---

## 4. Code & Data-Flow Map

The complete lineage of empirical numbers from configuration to publication is mapped as follows:

```
[experiments/configs/config_extended_grid.yaml]
                      │
                      ▼
       [experiments/run_extended_sweep.py]
         (executes build_ofat_design:
          10,500 core nominal runs +
          400 targeted θ3/θ6 runs +
          2,900 OFAT parameter sensitivity runs)
                      │
                      ▼
             [results/runs.jsonl]
         (13,800 JSON records,
          commit: 72c1a431...)
                      │
                      ▼
           [tools/recover_runs.py]
         (deduplication & export;
          CRITICAL BUG: 5-tuple key collapses OFAT scales!)
                      │
                      ▼
           [results/raw_results.csv]
         (13,800 rows, all status=COMPLETED)
                      │
         ┌────────────┴────────────────────────┐
         │                                     │
         ▼                                     ▼
[experiments/run_statistical_tests.py]    [experiments/make_tables.py]
  - loads raw_results.csv                   - compute_paired_statistics
  - aggregates (family, seed, method)         (CRITICAL BUG: stale len(paired) loop)
  - tests H1-H8                             - generate_main_results_table
  - writes:                                   (CRITICAL BUG: unpaired means + paired sig)
    - RESULTS_VERDICT.md                    - generate_numbers_macro_file
    - results/stats/*.csv                     (CRITICAL BUG: hardcoded empirical literals)
    - results/table_per_condition.csv       - writes:
                                              - results/numbers.tex
                                              - results/table_main_results.tex / .md
                                              - results/table_stratified.tex / .md
                                              - results/table_sitl.tex / .md
         │                                     │
         └────────────┬────────────────────────┘
                      │
                      ▼
         [Downstream Consumers]
         - paper.tex (imports results/numbers.tex and table_*.tex)
         - supplement.tex
         - README.md (markdown tables and badges)
         - index.html (web overview)
         - app.py (Gradio demo dashboard)
```

---

## 5. Critical Baseline Anomalies Identified

1. **OFAT & Primary Data Confounding:**
   - 13,800 rows were generated in one batch under commit `72c1a431...`.
   - Every single row carries `simulation_disclaimer: "SIMULATION ONLY -- Primary Grid Sweep"`.
   - 10,500 rows form the balanced nominal core (5 families × 50 seeds × 3 adversaries = 750 trials for each of 14 methods).
   - 2,900 rows are OFAT sensitivity variations with varying fleet sizes ($R \in \{8, 12\}$), task counts ($M \in \{30, 60\}$), comm ranges, packet drop rates, and perturbations.
   - `run_statistical_tests.py` averaged ALL rows together across `(graph_family, seed, method)`, which biased ACA, CBBA-PR+LR, and CTP-replan averages by mixing OFAT variations into their instance scores.

2. **Deduplication Key Defect in `recover_runs.py`:**
   - The key used was `(graph_family, adversary, comm_regime, method, seed)`.
   - This 5-tuple omits `n_robots` and `n_tasks`.
   - Under this key, 300 OFAT runs ($M=30$ vs $M=60$, $R=8$ vs $R=12$) were collapsed, overwriting trials and corrupting denominators.
   - The true unique key requires the 7-tuple including `n_robots` and `n_tasks`.

3. **Stale Loop Variable in `make_tables.py`:**
   - In `compute_paired_statistics`, `"n_pairs": len(paired)` was assigned outside the inner loop, causing every baseline to report the pair count of the last baseline evaluated.

4. **Population Mismatch in Table II:**
   - The main results table computed means and bootstrap CIs from ALL rows per method (including OFAT rows), but attached significance markers from paired tests on nominal rows, claiming $N = 1650$ paired trials when baselines only had 750 trials.

5. **Hardcoded Fallbacks & Map Discrepancies:**
   - `make_tables.py` contains hardcoded numeric literals in `generate_numbers_macro_file` instead of dynamic calculations.
   - `boston_downtown_drive.graphml` contains 326 multigraph edges which collapse into 323 simple undirected edges when loaded for simulation. `provenance.py` and `numbers.tex` had inconsistent counts and hardcoded fallback hashes.
   - `provenance.py` always rendered the `VERIFIED` pill regardless of verification status.
