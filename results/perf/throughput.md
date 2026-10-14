# Protocol v6 Throughput and Wall-Clock Scaling Report

**Authoritative Protocol Workload:** Protocol v6 Confirmatory Sweep  
- **Confirmatory Seeds:** 50 seeds  
- **Environments:** 5 families (`warehouse_movingai`, `road_osmnx`, `rgg`, `grid`, `er`)  
- **Adversaries:** 3 types (`theta_1_stochastic`, `theta_2_reactive`, `theta_4_cyclic_patrol`)  
- **Communication Regimes:** 1 nominal regime ($r_{\text{comm}}=30.0, p_{\text{drop}}=0.10$)  
- **Evaluated Methods:** 9 methods (`aca`, `aca_plus`, `aca_adaptive`, `aca_no_margin`, `aca_depth_0`, `cbba_lr`, `cbba_partial_lr`, `ctp_replan`, `ssi_lr`)  
- **Total Confirmatory Trials:** $50 \times 5 \times 3 \times 1 \times 9 = 6,750$ independent trials  

---

## 1. Per-Method Trial Runtime Benchmark

Empirical execution duration measured on the largest benchmark topology (`road_osmnx`, 216 nodes, 4 robots, 15 tasks, 80 steps):

| Method Label | Algorithm Description | Mean Trial Duration (s) | Steps / Makespan | Completion Rate |
|---|---|---|---|---|
| `aca` | Full ACA with Pinsker Margin ($d=1, \kappa=1.0$) | 20.82 s | 70 | 100.0% |
| `aca_plus` | ACA with Tree Pruning ($d=1, \tau=0.20$) | 20.11 s | 70 | 100.0% |
| `aca_adaptive` | ACA with Effective Horizon $\eta_{\text{eff}}(t)$ | 20.35 s | 70 | 100.0% |
| `aca_no_margin` | ACA without Pinsker Margin ($\kappa=0.0$) | 4.94 s | 39 | 100.0% |
| `aca_depth_0` | ACA without Recourse Tree ($d=0$) | 11.29 s | 80 | 86.7% |
| `cbba_lr` | Baseline CBBA with Local Repair ($d=1$) | 8.69 s | 80 | 93.3% |
| `cbba_partial_lr` | CBBA with Partial Re-auction | 9.62 s | 62 | 100.0% |
| `ctp_replan` | Stochastic Shortest Path CTP Re-planning | 9.09 s | 60 | 100.0% |
| `ssi_lr` | Sequential Single-Item Auction ($d=1$) | 12.49 s | 80 | 80.0% |

**Cross-Topology Mean:** On synthetic topologies (30–38 nodes), mean trial duration is 0.8–1.6 s. Across the mixed 5-topology universe, the weighted average trial execution time is approximately **3.6 seconds / trial**.

---

## 2. Multi-Core Scaling and Wall-Clock Estimates

Using multiprocess parallelism with `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=1` to prevent core oversubscription:

| Worker Count | Throughput (trials / hour) | Total CPU-Hours | Estimated Wall Time |
|---|---|---|---|
| **4 workers** | ~675 trials/h | ~40.0 CPU-h | **~10.0 hours** |
| **8 workers** | ~1,350 trials/h | ~40.0 CPU-h | **~5.0 hours** |
| **16 workers** | ~2,700 trials/h | ~40.0 CPU-h | **~2.5 hours** |
| **32 workers** | ~5,400 trials/h | ~40.0 CPU-h | **~1.25 hours** |
| **64 workers** | ~10,800 trials/h | ~40.0 CPU-h | **~38 minutes** |

---

## 3. Worker Configuration Guidance

- **Default Workers:** Physical cores (`psutil.cpu_count(logical=False)`), defaulting to 6 on a 6P/12T CPU.
- **Process Isolation:** Worker processes run completely independent RNG streams spawned via `np.random.SeedSequence(seed).spawn(5)`.
- **BLAS Environment:** Single-threaded BLAS (`OMP_NUM_THREADS=1`) is enforced per worker process so that linear algebra operations do not saturate the thread pool or throttle neighboring workers.
