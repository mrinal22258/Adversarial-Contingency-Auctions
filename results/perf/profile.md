# Performance Profile and Cumulative Hotspot Analysis

**Benchmark Target:** Largest topology (`road_osmnx`, 216 nodes, 326 edges), 4 robots, 15 tasks, 80 steps, `theta_1_stochastic` adversary.  
**Profiler:** Python `cProfile` with cumulative time sorting.

---

## 1. Top-15 Cumulative Hotspots

| Rank | Function / Location | Cumulative Time (s) | Calls | Self Time (s) | Primary Cost Driver |
|---|---|---|---|---|---|
| 1 | `engine.py:step` | 58.64 | 68 | 0.01 | Main simulation step loop across fleet |
| 2 | `aca.py:allocate_round` | 44.37 | 46 | 0.01 | Sequential auction rounds and bid consensus |
| 3 | `aca.py:_build_bundle_aca` | 38.49 | 184 | 0.14 | Robot candidate bundle search and recourse valuation |
| 4 | `contingency.py:build_recourse_plan` | 31.15 | 4,068 | 0.06 | Construction of depth-$d$ contingency recourse trees |
| 5 | `networkx:...:shortest_path` | 30.33 | 63,398 | 0.08 | Graph path search for candidate branch evaluation |
| 6 | `contingency.py:_build_tree_recursive` | 30.20 | 16,658 | 0.31 | Recursive contingency tree branching |
| 7 | `contingency.py:find_risk_aware_path` | 29.33 | 16,658 | 0.15 | Risk-weighted shortest path search under belief marginals |
| 8 | `networkx:...:bidirectional_dijkstra` | 28.55 | 16,620 | 6.37 | Graph path traversal core loop |
| 9 | `adversaries.py:compute_interdiction_cut` | 19.11 | 20,270 | 0.29 | Redundant cut evaluations during auction margin checks |
| 10 | `aca.py:_estimate_peer_cost` | 17.32 | 2,451 | 0.01 | Estimating peer recourse cost for margin evaluation |
| 11 | `adversaries.py:baseline_cost` | 15.73 | 30,022 | 0.07 | All-pairs distance evaluation for interdiction cuts |
| 12 | `networkx:...:dijkstra_path_length` | 15.37 | 53,811 | 0.11 | Nominal path length calculations |
| 13 | `robot.py:sense_environment` | 14.17 | 268 | 0.22 | Local edge sensing and hazard belief propagation |
| 14 | `contingency.py:edge_weight_fn` | 6.84 | 3,291,544 | 3.33 | Inner-loop Python callback during Dijkstra traversal |
| 15 | `aca.py:_get_peer_edge_marginals` | 6.39 | 2,451 | 1.83 | Recomputing peer ToM edge marginals during auction |

---

## 2. Analysis of Computational Structure and GPU Suitability

### The GPU Question
The ACA simulation workload is **fundamentally CPU-bound, irregular, and branchy**:
1. **Tiny, Sparse Graph Sizes:** The largest benchmark topology (`road_osmnx`) has 216 nodes and 326 edges; synthetic families have 30–38 nodes. Transferring these tiny adjacency structures across the PCIe bus to GPU memory introduces kernel-launch and memory transfer latency that dwarfs the computation time.
2. **Branchy Sequential Logic:** The simulation consists of discrete sequential auction rounds, per-robot greedy bundle search, and recursive depth-first contingency tree construction. GPUs require dense data-parallel SIMD execution; branch-heavy recursive pointer graphs on 200-node graphs cause thread divergence.
3. **Bit-for-Bit Preregistration Determinism:** GPU floating-point reduction and atomic operations are non-associative and non-deterministic across hardware architectures and driver versions. A preregistered confirmatory protocol strictly requires bit-for-bit reproducible outcomes across seeds.
4. **Statistics Layer Bootstrap Performance:** The 10,000-resample bootstrap over paired contrasts (`experiments/stats.py`) takes **0.118 seconds** on a standard CPU. Since the entire bootstrap across all contrasts finishes in < 5 seconds, offloading to GPU via PyTorch/CUDA is completely unnecessary.

**Conclusion:** Do **not** port the simulator or statistics to GPU. The genuine levers for performance are **safe CPU optimizations** and **multiprocess CPU parallelism**.

---

## 3. High-Impact Safe CPU Speedups

Profiling isolates three specific bottlenecks that can be accelerated without altering algorithmic behavior or determinism:
1. **Static Topology Distance & Betweenness Caching:** Precomputing and caching all-pairs shortest paths and betweenness centrality by graph topology SHA-256 eliminates redundant Dijkstra runs across trials.
2. **Hoisting Invariant Marginal and Interdiction Computations:** During an auction round, `fleet_states` is static. Hoisting `compute_interdiction_cut` and caching peer marginals per tick eliminates > 19 seconds of redundant re-evaluations.
3. **Graph Views for Blocked-Edge Path Queries:** Using lightweight edge exclusion views rather than full graph copies (`nx.Graph.copy()`) avoids graph memory allocation overhead during interdiction cut checks.
4. **BLAS Thread Capping (`OMP_NUM_THREADS=1`):** Preventing worker processes from spawning nested OpenBLAS/MKL threads ensures 100% efficient multi-core CPU utilization without core oversubscription.
