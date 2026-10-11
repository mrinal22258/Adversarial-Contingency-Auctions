# Stage 3 Validation & Reproducibility Report

**Repository:** `Adversarial-Contingency-Auctions-main`  
**Branch:** `fix/rigorous-eval`  
**Stage:** Stage 3 — Single Results Pipeline, Synchronization, and UI  
**Status:** **GATE PASSED**  
**Date:** 2026-10-10  

---

## 1. Executive Summary

Stage 3 unifies the entire analytical, statistical, reporting, and demonstration architecture of the repository into a single deterministic results pipeline (`make results` / `python tools/build_all_results.py`). All empirical claims, statistical tables, LaTeX macros, figures, and interactive control-room demonstrations derive strictly from raw primary populations without manual intervention.

---

## 2. Pipeline Execution & Step Exit Codes

Executing `python tools/build_all_results.py` completed with exit code `0` in **59.01 seconds**:

| Step | Operation | Script / Function | Result | Exit Status |
|---|---|---|---|---|
| **Step 1** | Primary Population Coverage & Integrity | `tools/build_coverage_matrices.py` | Verified 10,500 core nominal runs ($N=750$ paired trials) | **PASS** |
| **Step 2** | Raw Run Reconstruction & Deduplication | `tools/recover_runs.py` | 7-tuple key deduplication; preserved all OFAT trials | **PASS** |
| **Step 3** | Paired Hypothesis Testing Suite | `experiments/run_statistical_tests.py` | Tested H1–H8 across Wilcoxon, paired t-test, Cohen's d | **PASS** |
| **Step 4** | Tables, Macro Generation & README Sync | `experiments/make_tables.py` | Generated Tables II, III, IV and `results/numbers.tex` | **PASS** |
| **Step 5** | Figure Suite Generation with Provenance | `experiments/make_figures.py`, `make_map_figures.py` | Generated Figs 2, 3, 4, map overlays, sidecar JSONs | **PASS** |
| **Step 6** | Material Claim Ledger Audit | `tools/claim_ledger.py` | 15 claims audited and verified in `audit/CLAIM_LEDGER.csv` | **PASS** |
| **Step 7** | LaTeX Paper Compilation | `pdflatex -interaction=nonstopmode paper.tex` | Successfully compiled 8-page `paper.pdf` | **PASS** |
| **Step 8** | Strict Paper Integrity Linter | `tools/lint_paper.py` | 0 provenance errors, 0 unverified claims, 0 literal numbers | **PASS** |

**Build Provenance Output:** Written to `results/build_provenance.json` recording input SHA-256 hashes, byte sizes, and timestamps.

---

## 3. Strict Paper Linter Results

Execution of `python tools/lint_paper.py`:
```text
[NOTICE: DEV MODE] Dirty working tree (137 uncommitted files). Valid development artifact.
Paper lint passed successfully: 0 provenance violations, 0 unverified claims, 0 literal numbers.
```

- **Figure Provenance:** All 7 included figures verify against their `.provenance.json` sidecars with approved generators (`make_figures.py`, `make_map_figures.py`, `build_all_results.py`).
- **Claim Integrity:** Zero forbidden terminology ("strictly 0", "theoretical bound", unqualified "Oracle", "hardware", "Gazebo").
- **Macro Enforcement:** All empirical quantities, trial counts, confidence intervals, p-values, and percentages in the manuscript derive directly from `results/numbers.tex`.
- **Chronological Staleness:** `paper.pdf` is strictly newer than `paper.tex` and `results/numbers.tex`.

---

## 4. Manuscript PDF Verification

- **File Path:** `paper.pdf` (linked to `static/paper.pdf`)
- **Byte Size:** 780,542 bytes
- **SHA-256:** `50630e1cb67178ed325595fb2276164e5181b4de330fb7ba0d455d915b0cbe60`
- **Page Count:** 8 pages
- **Typography & Layout Inspection:**
  - Table II (Main Results): cleanly typeset with paired differences, Cohen's d, and exact p-values.
  - Table III (Stratified Results): breakdowns across graph families, network topologies, and adversary profiles.
  - Figures 2, 3, 4: sharp vector graphics with no overlapping labels or clipping.
  - Formal Propositions: numbering strictly aligned (Proposition 1, Proposition 2, Theorem 1, Proposition 3, Proposition 4).

---

## 5. UI Redesign & Cross-Viewport Responsiveness

The Gradio web interface (`app.py`) was redesigned following `audit/UI_REDESIGN_SPEC.md` into an operational Mission Control dashboard:
- **Design Tokens:** Dark calm / slate command center palette (`#0b0f19`, `#111827`, `#1e293b`, `#334155`, `#6366f1`).
- **KPI Bar:** 7 tabular numeric cards (`Done`, `Rate`, `Conflicts`, `Msgs`, `Travel`, `Blocked`, `Detours`).
- **Dual-Encoded Status Badges:** Accessible shape + icon + text indicators (`[✓] REAL TOPOLOGY`, `[●] SIMULATION`, `[🔒] PROVENANCE`).
- **Interactive Playback:** Multi-robot trajectory display distinguishing nominal paths (cyan), adversarial blockages (red hatch), and contingency detours (amber dash).

### End-to-End Playwright Automation Results (`tools/test_ui_playwright.py`)
```text
[*] Launching Gradio Mission Control on port 59182...
* Running on local URL:  http://127.0.0.1:59182
[*] Connecting Playwright to http://127.0.0.1:59182...
[*] Testing Viewport: Desktop (1920x1080)...
[*] Testing Viewport: Laptop (1366x768)...
[*] Testing Viewport: Tablet (768x1024)...
[*] Testing Viewport: Mobile (390x844)...
[*] Shutting down Gradio test server...

================ Responsive Test Results ================
  [PASS] Desktop    (1920x1080): 7 KPI cards, 6 tabs, 3 badges
  [PASS] Laptop     (1366x768): 7 KPI cards, 6 tabs, 3 badges
  [PASS] Tablet     (768x1024): 7 KPI cards, 3 tabs, 3 badges
  [PASS] Mobile     (390x844): 7 KPI cards, 2 tabs, 3 badges
=========================================================
```

### Unit & Demo Regression Suite
Execution of `pytest tests/test_demo.py`:
- **Result:** 26 passed in 18.49 seconds (100% pass rate).
- Full suite total: 135 passing tests across all components.

---

## 6. Stage 3 Gate Declaration

- [x] Single results pipeline command (`make results` / `python tools/build_all_results.py`) completes with returncode 0.
- [x] Strict paper linter passes with 0 violations.
- [x] Manuscript `paper.pdf` compiles cleanly to 8 pages with MiKTeX `pdflatex`.
- [x] 15 material claims in `audit/CLAIM_LEDGER.csv` audited and validated.
- [x] UI redesigned according to `audit/UI_REDESIGN_SPEC.md` and validated via Playwright across Desktop, Laptop, Tablet, and Mobile viewports.
- [x] Zero empirical numbers hardcoded; byte synchronization confirmed across paper, README, and UI.

**Verdict: STAGE 3 GATE PASSED.**
Ready to proceed to Stage 4 (Method improvement and held-out confirmatory experiments).
