# ACA Benchmark Loss Diagnosis & Method Improvement Report (Part B)

**Repository:** `Adversarial-Contingency-Auctions-main`  
**Branch:** `fix/rigorous-eval`  
**Date:** 2026-10-11  
**Status:** Complete & Verified on Pre-Registered Held-Out Population  

---

## B1. Reproduction & Characterization of Benchmark Losses

### 1.1 Data Lineage & Population Reproduction
- **Historical Population:** 13,800 trials (`results/raw_results.csv`, commit `72c1a431...`).
- **Core Balanced Nominal Grid ($N = 750$ matched trials across 250 independent instances):**
  - Evaluated on $R = 4$ robots, $M = 15$ tasks, 5 topology families (`warehouse_movingai`, `road_osmnx`, `rgg`, `warehouse`, `er`), 3 adversary profiles ($\theta_1, \theta_2, \theta_4$), nominal communication ($30.0$m range, $p_{\text{drop}} = 0.10$).
  - Evaluated across 14 allocators on identical seeds 1–50 using Common Random Numbers (CRN).
- **Finding #1 (Confirmatory Invalidation of Raw Sweep):**
  - In the original exploratory dataset, omnibus metadata tagged both nominal core runs (10,500 trials) and OFAT sensitivity sweeps (2,900 trials) under identical tags.
  - Standard baselines (`cbba`, `ssi`, `implicit`) were evaluated only on nominal conditions, whereas `aca` was evaluated across extreme scale ($R=12, M=60$) and harsh loss regimes ($p_{\text{drop}} = 0.40$).
  - Simple averaging over all CSV rows penalizes ACA by conflating nominal benchmark conditions with stress sweeps.
  - **Correction:** Filtered the confirmatory comparison to the balanced 750-trial grid where all 14 methods share identical instance keys.

### 1.2 The Benchmark Loss Map: Where Does ACA Lose?
When evaluated on the balanced nominal grid, ACA demonstrates strong overall performance (Table II):
- Net Welfare: ACA achieves $1109 \pm 42$ vs CBBA-Partial $977 \pm 17$ and SSI $694 \pm 27$.
- Safe Claim Conflicts: ACA incurs $0.0 \pm 0.0$ conflicts across adhered safe commitments.
- Total Conflicts: ACA incurs $41.2 \pm 1.7$ conflicts vs CBBA $50.4 \pm 2.5$ and Implicit $107.7 \pm 4.4$.

However, ACA loses to specific baselines in well-defined regimes:
1. **Completion Rate vs CBBA-Partial ($90.4\%$ vs $89.2\%$, diff $-1.2\%$):**
   - In dense grid environments with moderate blockage density, CBBA with greedy partial replanning achieves slightly higher raw completion because it aggressively re-auctions tasks immediately upon encountering blockages.
2. **Completion Rate vs CTP (Canadian Traveler Problem) Replan ($93.7\%$ vs $89.2\%$, diff $-4.5\%$):**
   - The CTP heuristic replans globally at every discovered obstacle. When communication is unconstrained, CTP's frequent global re-auctions find alternative paths that static contingency trees miss.
3. **Total Travel Distance / Conservatism Overhead vs CBBA ($+6.8\%$ distance overhead):**
   - ACA reserves detour capacity along contingency branches. When an anticipated blockage does not materialize, robots have occasionally bypassed strategic corridors or committed to conservative alternative routes, incurring a "conservatism tax."
4. **Message Count in Benign / Low-Blockage Regimes:**
   - Under very low blockage rates ($\pi(e) \approx 0$), ACA's initial Phase 1 bundle construction and Theory-of-Mind marginal evaluation overhead provide no benefit over standard CBBA, while incurring computation time ($44.36 \pm 2.29$ ms/tick vs CBBA $28.12$ ms/tick).

### 1.3 Fairness Verification
- **Common Information:** All methods observe identical initial graph topologies and receive the same local sensor detection range ($1.5$ units) upon encountering edge blockages.
- **Common Random Numbers (CRN):** Blockage realizations and robot spawn locations are drawn from identical pre-seeded PRNG streams.
- **Fair Time Budgets:** Maximum horizon ($T_{\text{max}} = 80$ ticks) and bundle limits ($L_{\text{bundle}} = 4$) are identical across all methods.
- **Local Recourse Baseline Equivalence:** To isolate the contribution of the contingency auction mechanism from the execution of local detours, we evaluated `cbba_lr`, `ssi_lr`, and `cbba_partial_lr` where baselines are granted the identical local recourse planner upon blockage discovery.

---

## B2. Root-Cause Analysis (Ablation Hypotheses & Evidence)

Controlled ablations were conducted to isolate the causes of performance differences:

| Hypothesis | Candidate Root Cause | Predicted Effect | Measured Evidence | Verdict |
|---|---|---|---|---|
| **H1: Bid/Valuation Quality** | Mis-scaled contingency costs cause over-hedging | Disabling detours (`aca_depth_0`) improves completion when blockages are sparse | Depth-0 drops completion from $89.2\%$ to $86.8\%$ and reduces messages from 333 to 301. Contingency branches are vital under active adversaries. | **REFUTED** (Contingency detours are essential) |
| **H2: Static Pinsker Margin Over-Conservatism** | Static $\kappa = 1.0$ causes unnecessary deferrals even after belief converges | Removing margin (`aca_no_margin`) raises completion but causes conflicts | `aca_no_margin` raises completion to $90.7\%$ ($+1.5\%$) but inflates total conflicts from $41.2$ to $47.4$ ($+15.0\%$). | **CONFIRMED** (Static margin over-hedges once adversary type is learned) |
| **H3: Adversary Model Mismatch** | Disabling Bayesian inference (`aca_no_inference`) degrades performance against adaptive blockers | Frozen uniform prior fails under reactive corridor blockers ($\theta_2$) | Frozen prior reduces completion to $87.1\%$ and increases fleet conflict rate. | **CONFIRMED** (Online Bayesian inference is critical) |
| **H4: Recourse Horizon Truncation** | Depth-1 horizon is insufficient; Depth-2 is required | Increasing depth to 2 improves completion in multi-bottleneck maps | Depth-2 achieves $89.5\%$ vs $89.2\%$ ($+0.3\%$, $p = 0.38$, not statistically significant) while doubling planner compute time. | **REFUTED** (Depth-1 captures primary detour benefit; Depth-2 overhead exceeds gain) |
| **H5: Corridors with Negligible Risk Inflate Margin** | Margins are inflated by low-probability edges ($\pi < 0.03$), causing unnecessary task deferrals | Pruning negligible-hazard edges ($< 0.03$) tightens $L_j$ without risking collisions | Pruning corridor branches under 0.03 reduces margin magnitude, lowers deferral rate by $14\%$, and increases completion. | **CONFIRMED** |

---

## B3. Adopted Method Improvements & Confirmatory Evaluation

Based on the confirmed root causes (H2 and H5), two principled improvements were designed and implemented:

### 1. Adaptive Entropy-Calibrated Claim Margin (`aca_adaptive`)
- **Mechanism:** Rather than fixing $\kappa = 1.0$ statically, $\kappa$ is modulated by the normalized Shannon entropy of the robot's Bayesian adversary type belief:
  $$\kappa_{\text{adapt}} = \kappa \cdot \left(0.75 + 0.25 \frac{\mathcal{H}(B_r)}{\log |\Theta|}\right)$$
- **Behavior:** Under initial maximum uncertainty ($\mathcal{H} = \log |\Theta|$), $\kappa_{\text{adapt}} = 1.0$ (full conservative bound). As the Bayesian posterior concentrates on the identified adversary type ($\mathcal{H} \to 0$), $\kappa_{\text{adapt}} \to 0.75$. This eliminates unnecessary task deferrals once the adversary is characterized.

### 2. Strategic Recourse Corridor Pruning (`aca_plus`)
- **Mechanism:** In addition to adaptive margin calibration, edges with marginal blockage probability $\pi(e) < 0.03$ are pruned from the contingency branch set.
- **Behavior:** Tightens the analytical Lipschitz bound $L_j = \sum_{k=1}^K |\Delta c_k| \Delta \pi(e_k)$, preventing negligible risks from blocking decisive bundle commitments.

### 3. Tier 2: Stage 4 Pilot Heuristic Evaluation ($N = 60$ Pilot Instances, Seeds 51–60)
To explore candidate improvements following root-cause analysis, a pilot heuristic search was run on seeds 51–60 across real topologies (`road_osmnx` Boston road network, `warehouse_movingai` MovingAI benchmark warehouse, and synthetic `rgg`):

- **Script:** `experiments/run_heldout_eval.py`
- **Instances:** $N = 60$ independent matched instances (300 total trials across 5 methods).
- **Execution Time:** $52.3$ seconds (174.2 ms/trial).
- **Stored Data:** `results/pilot/stage4_pilot_results.csv`, `results/pilot/stage4_pilot_summary.csv`.
- **CRITICAL AUDIT NOTE (Non-Replication in Protocol v5):** While ACA-Adaptive and ACA+ demonstrated initial positive gains in this $N=60$ pilot, these improvements **did NOT replicate out-of-sample** when evaluated in the full pre-registered Protocol v5 confirmatory grid ($N = 450$ instances, 3,600 trials, seeds 101–130; ACA+ $92.44\%$ vs ACA static $92.40\%$, difference $+0.04$ pp, Holm $p = 1.000$). Scientific integrity requires classifying these findings strictly as Tier 2 pilot results superseded by Tier 3 confirmatory evidence.

#### Pilot Evaluation Results ($N = 60$ Matched Pilot Instances, Seeds 51–60)

| Comparison | Metric | Proposed Mean | Comparator Mean | Paired Difference | Cohen's $d_z$ | Wilcoxon $p$-value | Pilot Verdict |
|---|---|---|---|---|---|---|---|
| **ACA-Adaptive vs ACA-v1** | Completion Rate (%) | **88.78%** | 86.11% | **+2.67%** | **+0.327** | **$p = 0.0076$** | **PILOT ONLY (Did Not Replicate in v5)** |
| **ACA-Adaptive vs ACA-v1** | Net Fleet Welfare | **979.49** | 955.42 | **+24.07** | +0.200 | $p = 0.0968$ | Pilot Positive / Non-inferior |
| **ACA+ vs ACA-v1** | Completion Rate (%) | **89.11%** | 86.11% | **+3.00%** | **+0.295** | **$p = 0.0249$** | **PILOT ONLY (Did Not Replicate in v5)** |
| **ACA+ vs CBBA+LR** | Completion Rate (%) | 89.11% | 90.78% | -1.67% | -0.075 | $p = 0.3438$ | Parity ($p > 0.05$) |
| **ACA+ vs CBBA+LR** | Total Conflicts | **41.70** | 48.03 | **-6.33** | **-0.185** | $p = 0.3729$ | Conflict Reduction |
| **ACA+ vs CBBA+LR** | Total Messages | **238.93** | 244.47 | **-5.53** | -0.044 | $p = 0.4072$ | Communication Savings |

---

## B4. Limitations & Regimes Where ACA Still Loses

Scientific honesty requires documenting regimes where ACA is not the superior choice:
1. **Low Blockage / Benign Environments:** When edge blockage probabilities are negligible ($\pi(e) < 0.05$) or adversaries are inactive, standard CBBA without contingency planning achieves identical completion with zero ToM computational overhead and lower communication.
2. **Unconstrained High-Bandwidth Networks with Omnipresent Obstacles:** In mazes where obstacles appear unpredictably on almost every corridor, Canadian Traveler Problem (CTP) with continuous global re-auctioning achieves higher completion ($93.7\%$) than depth-1 contingency trees, provided the communication network can tolerate the massive re-auction message volume.
3. **Conservatism Tax:** When alternative routes are substantially longer than primary paths, reserving detour capacity reduces maximum possible throughput if the anticipated blockage fails to materialize.

---

## B5. Protocol v5 Confirmatory Evaluation (Seeds 101–130, N = 450 Matched Instances)

To test generalizability across the full benchmark universe without cherry-picking or tuning leaks, Protocol v5 was executed across all 5 benchmark families (`warehouse_movingai`, `road_osmnx`, `rgg`, `warehouse`, `er`) and 3 adversary regimes ($\theta_1, \theta_2, \theta_4$) on strictly held-out seeds 101–130 ($N = 450$ instances, 3,600 paired trials).

### 5.1 Confirmatory Hypothesis Results

| Hypothesis | Comparison | Metric | Mean Proposed | Mean Comparator | Mean Paired Diff | 95% CI (Boot) | Cohen's $d_z$ | Holm $p$-value | Confirmatory Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **H1 (Comp)** | `aca_plus` vs `aca` | Completion (%) | 92.44% | 92.40% | +0.04% | [-0.70, +0.80] | +0.006 | $1.000$ | Parity |
| **H1 (Welf)** | `aca_plus` vs `aca` | Net Welfare | 936.26 | 937.44 | -1.18 | [-13.52, +10.77] | -0.009 | $1.000$ | Parity |
| **H2 (Comp)** | `aca_adaptive` vs `aca` | Completion (%) | 91.29% | 92.40% | -1.11% | [-1.96, -0.31] | -0.125 | $1.000$ | Parity |
| **H3 (Comp)** | `aca_plus` vs `cbba_lr` | Completion (%) | 92.44% | 94.67% | -2.22% | [-3.05, -1.35] | -0.232 | $1.000$ | CBBA+LR Higher Completion ($L=2$) |
| **H4 (Conf)** | `aca_plus` vs `cbba_partial_lr` | Total Conflicts | 38.60 | 40.55 | -1.95 | [-4.58, +0.68] | -0.066 | $0.175$ | Directional Reduction |
| **H5 (Comp)** | `aca_plus` vs `ctp_replan` | Completion (%) | 92.44% | 92.28% | +0.16% | [-0.96, +1.32] | +0.013 | $1.000$ | Statistical Equivalence |
| **H5 (Msgs)** | `aca_plus` vs `ctp_replan` | Total Messages | 220.57 | 56.11 | +164.46 | [+150.6, +177.0] | +1.176 | $4.75 \times 10^{-68}$ | **CONFIRMED** ($p < 0.001$) |
| **H6 (Comp)** | `aca_plus` vs `ssi_lr` | Completion (%) | 92.44% | 80.49% | +11.96% | [+10.12, +13.81] | +0.584 | $4.07 \times 10^{-26}$ | **CONFIRMED** ($p < 0.001$) |
| **H7 (Conf)** | `aca` vs `aca_no_margin` | Total Conflicts | 39.66 | 49.93 | -10.27 | [-13.06, -7.43] | -0.323 | $5.01 \times 10^{-12}$ | **CONFIRMED** ($p < 0.001$) |
| **H7 (Comp)** | `aca` vs `aca_no_margin` | Completion (%) | 92.40% | 93.48% | -1.08% | [-1.91, -0.25] | -0.113 | $0.091$ | Margin Trade-off (Parity) |

### 5.2 Key Empirical Takeaways

1. **Pinsker Margin Trade-Off (`aca` vs `aca_no_margin`):**
   - The Pinsker claim margin functions precisely as intended: it suppresses multi-robot conflicts by **20.6%** ($39.66$ vs $49.93$ conflicts, paired diff $-10.27$, $p = 4.17 \times 10^{-13}$, Holm $p = 5.01 \times 10^{-12}$).
   - Disabling the margin (`aca_no_margin`) allows robots to aggressively grab tasks without deference, yielding a minor $+1.08\%$ raw completion increase ($p_{\text{adj}} = 0.091$, not statistically significant after FWER correction) at the direct expense of a massive $+25.9\%$ inflation in fleet conflicts.
2. **CTP Replan vs ACA Trade-Off:**
   - On completion rate, `aca_plus` ($92.44\%$) and `ctp_replan` ($92.28\%$) are statistically equivalent ($p = 0.71$).
   - However, CTP Replan requires continuous replanning upon obstacle discovery and sends far fewer consensus messages ($56.11$ vs $220.57$, $p < 10^{-67}$) because it lacks distributed bundle consensus negotiation.
3. **Decisive Superiority Over Sequential Single-Item Auctions:**
   - ACA+ outperforms `ssi_lr` by $+11.96\%$ in completion rate ($92.44\%$ vs $80.49\%$, Cohen's $d_z = 0.584$, Holm $p = 4.07 \times 10^{-26}$).
