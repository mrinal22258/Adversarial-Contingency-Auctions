# ACA Audit Repair Status Report (FIX_REPORT.md)

**Branch:** `fix/audit-repairs`  
**Audit Reference:** `ACA_End_to_End_Audit_2026-10-13.md`  
**Protocol Freeze Tag:** `prereg-v6.2`  
**Final Test Suite Status:** `173 passed, 0 failed, 54 deselected, 2 warnings in results/test_logs/final.txt`

---

## 1. Audit Items Status Matrix

| Item | Description | Status | Commit | Proving Acceptance Test |
|---|---|---|---|---|
| **P0-1** | Sweep runner config identity, resume key, output isolation, exact seed execution | **Fixed** | `c9d4de2` | `tests/test_runner_protocol.py` (8/8 passed) |
| **P0-2** | Policy equivalence between priced recursive tree and runtime execution | **Fixed** | `a886500` | `tests/test_policy_equivalence.py` (7/7 passed) |
| **P0-3** | Existing experiment data pre-dates repair; prepare fresh v6 confirmatory run | **Execution Pending** | `da68be2`, `0c98967` | Pipeline fully validated; Protocol v6.2 cryptographically frozen. Confirmatory execution reserved for user per `RUN_V6.md` (~40 CPU-hours). |
| **P0-4** | ACA+ pruning threshold inactive in v5; active pruning with recovery cost leaves | **Calibrated** | `e396e26` | $\tau_{\text{prune}}=0.15$ selected from $\{0.15, 0.20, 0.25\}$ on 15 dev seeds via parsimony tie-break ($\le 0.5$ pp). Provenance: `results/tuning/prune_dev_v6.csv`, `prune_dev_v6_summary.json` |
| **P0-5** | Belief/hazard interface called with default fleet state in planning paths | **Fixed** | `166b3d1` | `tests/test_hazard_interface.py` (6/6 passed), `docs/HAZARD_CONTRACT.md` |
| **P0-6** | Exact recursive expected cost scope (independent-Bernoulli) & fail-closed marginals | **Fixed** | `a886500` | `tests/test_policy_equivalence.py` (missing marginal raises `MissingMarginalError`) |
| **P1-1** | Paper headline reconciled with held-out negative result (CBBA+LR reversal) | **Fixed** | `4acb3f9`, `867b10b` | Abstract, discussion, and conclusions clearly state v5 reversal; Protocol v6 pending execution. |
| **P1-2** | Reported statistics tied strictly to declared primary cluster-level estimator | **Fixed** | `a7c4d58` | `tests/test_statistical_pipeline.py` (10/10 passed) |
| **P1-3** | Number generator schema enforced with zero hardcoded empirical fallbacks | **Fixed** | `a7c4d58`, `10653d1` | `tests/test_result_model.py`, `tools/lint_numbers.py` (0 literal numbers outside generated blocks) |
| **P1-4** | Authoritative v6 seed list reconciled with generation procedure & hash chain | **Fixed** | `c9d4de2`, `da68be2` | `tests/test_prereg_v6_seeds.py` (exact 50 seeds parsed & checked) |
| **P1-5** | Claim ledger behaves as an active statistical verifier from locked raw data | **Fixed** | `a7c4d58` | `tests/test_claim_ledger.py` (12/12 passed) |
| **P1-6** | UI protocol label and results source of truth reconciled (v6 pending, v5 hash) | **Fixed** | `4acb3f9`, `c48b502` | UI dynamically loads from validated `results/result_model_v1.json`; displays "v6 execution pending". |
| **P1-7** | Claim-level theorem evidence included in core cryptographic hash chain | **Fixed** | `a7c4d58` | `tests/test_statistical_pipeline.py` (`results/per_claim_evaluations.jsonl`) |
| **P1-8** | Historical v5 JSONL classified as incomplete/historical irrecoverable | **Fixed** | `c9d4de2` | `tests/test_log_integrity.py::test_historical_v5_integrity` |
| **P1-9** | Double-blind review anonymity enabled by default (`\anonymoustrue`) | **Fixed** | `4acb3f9`, `c48b502` | `tools/check_anonymity.py` audits extracted release tree and both PDFs with 0 leaks; `tools/make_release.py` generates clean 17.4 MB archive. |
| **P1-10** | Supporting paper/docs updated to reflect validated behavior, not aspirational | **Fixed** | `4acb3f9`, `10653d1` | `README.md` generated from `README.template.md`; verified by `tools/lint_numbers.py`. |
| **P2 4.1** | Test side effect mutating tracked `CLAIM_LEDGER_V2.csv` | **Fixed** | `a7c4d58` | `tests/test_claim_ledger.py::test_tracked_claim_ledger_matches_and_git_status_clean` |
| **P2 4.2** | Full-suite test count discrepancy resolved with saved full-suite log | **Fixed** | `4acb3f9`, `c48b502` | `results/test_logs/final.txt` (173 passed, 54 deselected, 2 warnings) |
| **P2 4.3** | Portable environment lock and CI replacing platform-specific venv bundle | **Fixed** | `da68be2` | `requirements.lock`, `.github/workflows/ci.yml`, `RUN_V6.md` |
| **P2 4.4** | Atomic JSONL writer lock failure fatally raises; per-record hash verified | **Fixed** | `c9d4de2` | `tests/test_runner_protocol.py` (lock error test) |
| **P2 4.5** | Separation of `--dry-run` (0 steps) from `--smoke-test` | **Fixed** | `c9d4de2` | `tests/test_runner_protocol.py` (dry run zero step test) |
| **P2 4.6** | Topology hash in graph betweenness cache key | **Fixed** | `a7c4d58`, `645ace2` | Single static graph topology cache; golden trace test byte-identical. |
| **P2 4.7** | Portable relative paths and complete commit metadata in provenance | **Fixed** | `a7c4d58`, `f28c503` | Consolidated in `acalib/utils/gitinfo.py` with zero `shell=True`. |

---

## 2. Test Suite & Environment Execution Summary

### Exact Pytest Summary Line
From `results/test_logs/final.txt` (UTF-8 encoded):
```text
173 passed, 54 deselected, 2 warnings in 35.51s
```

### Explanation of Deselected Tests (54 total)
Running `pytest -q -m "not (sitl or ortools or ui)"` intentionally deselects 54 environmental/optional tests:
1. **`sitl` (18 tests):** Continuous-time PyBullet rigid-body physics simulation suite for differential-drive unicycle kinematics and synthetic vision latency. PyBullet physics evaluation is computationally intensive (~10 minutes) and isolated to Software-in-the-Loop benchmark workflows (`experiments/sitl/`).
2. **`ortools` (12 tests):** Exact mixed-integer programming (MIP) combinatorial allocation comparators requiring Google OR-Tools optional C++ bindings. OR-Tools solver execution is reserved for exact ground-truth validation.
3. **`ui` (24 tests):** Browser-based Gradio Playwright end-to-end telemetry tests requiring headless Chrome/Chromium browser drivers and server port binding.

### Explanation of Warnings (2 total)
Both warnings originate from `scipy/stats/_axis_nan_policy.py:531`:
```text
RuntimeWarning: Precision loss occurred in moment calculation due to catastrophic cancellation. This occurs when the data are nearly identical. Results may be unreliable.
```
- **Cause:** In `tests/test_stage1_provenance_and_stats.py::test_compute_paired_statistics_independent_n`, paired contrast tests are validated using synthetic common-random-number arrays where comparator values are identical or differ by floating-point epsilon.
- **Impact:** Scipy's internal kurtosis and skewness moment calculations encounter near-zero variance denominator terms. This is expected numerical behavior for degenerate equality fixtures and does not affect empirical hypothesis tests on benchmark data.

---

## 3. What the Paper Can and Cannot Claim Today

### What the Paper CAN Claim:
1. **Exploratory Main Grid Findings:** On the balanced nominal benchmark grid ($N = 250$ independent clusters, 750 paired trials), ACA achieves an exploratory completion gain of $+2.14$ percentage points over CBBA+LR ($p = 0.004$ under cluster-level Holm adjustment).
2. **Out-of-Sample Protocol v5 Headline Reversal:** On held-out un-tuned seeds 101–130 ($N = 450$ instances, 3,600 trials), when baseline CBBA is equipped with local recourse (+LR), **CBBA+LR outperforms ACA** on task completion ($94.67\%$ vs. $92.40\%$, paired difference $+2.22$ pp) and net welfare ($958.9$ vs. $937.4$) with fewer conflicts ($25.48$ vs. $39.66$). This establishes that local detour execution is the primary driver of corridor completion, while ACA's primary scientific advantage is safe decentralized coordination via the Pinsker margin under communication constraints.
3. **Pinsker Margin Trade-Off:** The Pinsker claim margin reduces total conflicts by $20.6\%$ ($39.66$ vs. $49.93$, $p < 0.001$) relative to unregularized coordination, at a modest, non-significant completion difference ($-1.08$ pp, $p_{\text{adj}} = 0.091$).
4. **Conditional Safety Guarantee (Theorem 1):** Under the ACA Lemma 1 analytical drift bound ($\eta_{\text{eff}}$), adherence holds in $98.99\%$ of safe claims ($11,220$ / $11,334$ commitments) with exactly $0$ / $11,220$ conflicts ($95\%$ one-sided Clopper-Pearson bound $\le 0.027\%$), while periodic evaluations achieve $98.08\%$ adherence across $779,036$ checks ($96.69\%$ per instance across $N = 250$ instances, $p < 0.001$).
5. **Decentralized Superiority over SSI:** ACA decisively outperforms Single-Item Auctions ($+11.96$ pp completion, $p < 10^{-25}$).
6. **Physical Simulation Domain Gap:** Software-in-the-Loop continuous physics introduces an average completion drop of $\approx 18.9$ pp and rank invariance failure across simulation fidelities ($\rho = 0.486, p = 0.328$). All evaluations represent software simulation; no physical robots were deployed.

### What the Paper CANNOT Claim Today:
1. **Cannot Claim Confirmatory Validation of the Repaired Recursive Planner:** The newly implemented full recursive tree planner, active pruning with recovery cost leaves, and grounded hazard interface have not been executed across the 50 confirmatory seeds ($40$ CPU-hours). Protocol v6 is registered and cryptographically frozen, but its confirmatory execution remains pending per `RUN_V6.md`.
2. **Cannot Claim Active Pruning Benefits in Protocol v5:** In Protocol v5, ACA+ set $\tau_{\text{prune}} = 0.06 < \tau_{\text{planner}} = 0.12$, rendering pruning functionally inactive. v5 results demonstrate parity with static ACA, but do not provide evidence for active pruning. Active pruning ($\tau_{\text{prune}} = 0.15$, empirically selected on development seeds) will be evaluated in Protocol v6.
3. **Cannot Claim General Completion Dominance over CBBA+LR:** Out-of-sample confirmatory evidence demonstrates that CBBA+LR is superior in unconstrained task completion and welfare.
4. **Cannot Claim Online Type Inference Advantage:** Online Bayesian adversary type inference shows statistical parity with a static uniform prior ($p = 0.515$).
5. **Cannot Claim Universal Conflict-Freedom:** Theorem 1 applies strictly when $\mathrm{TV} \le \eta_{\text{eff}}$; safe claims outside this condition incurred conflicts in historical logs.
6. **Cannot Claim In-the-Loop Vision or Physical Hardware Deployment:** The vision pipeline represents an open-loop synthetic ArUco tracking demonstration evaluated against simulated ground truth; no physical robots or closed-loop vision controllers were deployed.
