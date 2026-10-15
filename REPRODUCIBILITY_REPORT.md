# ACA Reproducibility Report

**Date:** 2026-10-13  
**Audited Branch:** `fix/audit-repairs`  
**Base Commit:** `6cabf8ca417b25102dc74d3cf4e750fa2c495f8e` (tagged `v2.0-submission`)  
**Preregistration Tag:** `prereg-v5` (`9fa21c087507a86f0594830a7c16f300dce97420`)  
**Platform:** Windows 11, PowerShell, x86_64  

---

## 1. Environments Specification

Two isolated Python environments are established to verify reproducibility and decouple core algorithm requirements from optional dependencies:

### 1.1 Core Environment (`venv_core`)
- **Python Binary:** `venv_core/Scripts/python.exe` (Python 3.12.7)
- **Dependencies Record:** `repro/env_core.txt`
- **Scope:** Minimal runtime requirements strictly needed for auction and graph simulation:
  - `numpy==2.5.4`
  - `scipy==1.18.1`
  - `networkx==3.7`
  - `pandas==3.0.6`
  - `matplotlib==3.11.2`
  - `seaborn==0.13.2`
  - `statsmodels==0.15.0`
  - `pyyaml==6.0.3`
  - `pytest==9.1.1`
- **Excluded:** `pybullet`, `ortools`, `gradio`, `playwright`, `opencv-python`.

### 1.2 Extras Environment (`anaconda3 base`)
- **Python Binary:** `[REDACTED_USER]\anaconda3\python.exe` (Python 3.12.7)
- **Dependencies Record:** `repro/env_extras.txt`
- **Scope:** Core dependencies plus physical simulation and UI demonstration packages:
  - `pybullet==3.2.7`
  - `ortools==9.14.6206`
  - `gradio==6.28.0`
  - `opencv-python==4.11.0`
  - `playwright==1.63.0`
  - `osmnx==2.1.1`

---

## 2. Baseline Test Runs (Original Audited HEAD `6cabf8c`)

| Environment | Command | Exit Code | Collected Items | Outcome Summary | Log Artifact |
|---|---|---|---|---|---|
| **Core** (`venv_core`) | `pytest -v` | **2 (FAILED)** | 95 items | 4 Collection Errors (`ImportError: pybullet, gradio, ortools, playwright`), 1 skipped | `repro/baseline_core.txt` |
| **Extras** (`anaconda3`) | `pytest -v` | **0 (PASSED)** | 145 items | 145 Passed in 170.10s | `repro/baseline_extras.txt` |

### Key Baseline Diagnostic:
- On original HEAD, test collection in a minimal environment crashed unconditionally because optional test modules imported `pybullet`, `ortools`, `gradio`, and `playwright` at the module top level rather than guarding with `pytest.importorskip` or markers. This directly confirms **Finding K**.

---

## 3. Cryptographic Input Hashes

All baseline datasets, configuration files, and generated artifacts have been pinned in `repro/input_hashes.json` prior to any modifications:

| Artifact | Size (bytes) | SHA-256 Checksum | Line/Row Count | Status |
|---|---|---|---|---|
| `results/confirmatory/heldout_v5_results.csv` | 1,213,596 | `a7470feb9f649baa80ff7dfab5cf73595cfad68bc1a3b1944eeb1d1fcb4e7fe3` | 3,601 lines (3,600 data rows) | **PINNED (IMMUTABLE)** |
| `results/confirmatory/heldout_v5_runs.jsonl` | 4,005,975 | `be45670d256eed1999e5256e6900f0970dbd05d548fb3cbb28be485ec9267926` | 3,541 lines (3,491 valid, 50 corrupt) | **PINNED (DECLARED-INCOMPLETE)** |
| `results/raw_results.csv` | 4,709,334 | `3a1fc0416ce060f545a165cf3b5db3ebcc9ec460592e3135b91a7eb3f114c6ee` | 13,801 lines | **PINNED (EXPLORATORY)** |
| `paper.tex` | 55,808 | `cb331252db82b45f14e7a2b0db2d01869e5d4cb0d828bb79f53835cc983cb190` | 439 lines | Baseline |
| `paper.pdf` | 701,484 | `3d3680cfde46569f143714b0b14c30c30a6baaa7264ae2ec55e25a251786cb67` | 8 pages | Baseline compiled |
| `results/build_provenance.json` | 1,816 | `25ffe10b85a75d038bf37d9959e4556a3e5c94165507df13d5cf41fc0cf75027` | JSON manifest | Baseline (Stale) |
| `results/numbers.tex` | 10,698 | `53068b0c6ffd10d29d47228a0110300956b9c97b819f07a514d7979624fe4ce0` | 273 lines | Baseline |
| `data/maps/manifest.json` | 1,678 | `8a299e16d895a5413fcbe87f1cb12128a1c97a54a737f0ef54256eb918cf5ee1` | JSON manifest | Baseline |

---

## 4. Known Limitations & Integrity Status of Existing Evidence

1. **Protocol v5 JSONL Truncation (Finding F):**
   - 50 lines in `results/confirmatory/heldout_v5_runs.jsonl` are truncated records resulting from concurrent unbuffered file appends across parallel worker processes.
   - 109 unique trial hashes in the CSV do not appear in the parseable JSONL lines.
   - This file is formally classified as `DECLARED-INCOMPLETE`. No synthetic data will be fabricated to patch these records.
2. **Perception Loop Gap (Finding J):**
   - `experiments/sitl/vision.py` operates as an open-loop image generator and ArUco pose evaluator.
   - Ground-truth poses in PyBullet are used directly by the robot controllers.
   - Classified as an open-loop synthetic vision demonstration.
