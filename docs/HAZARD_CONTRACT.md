# Hazard Event and State Contract (Protocol v6)

## 1. Specification Overview
This contract formally standardizes the hazard event semantics and state observations across the environment, adversary models, perception/sensing filters, and planning algorithms (ACA, CC-CBBA, CBBA+LR) within `acalib`.

Prior to this contract, planning-time valuations evaluated edge marginals and Lipschitz bounds using unpopulated default arguments (`edge_robot_count=0.0`, `is_targeted_by_interdiction=False`), causing reactive and budgeted-interdiction adversary hypotheses to collapse to a baseline value (~0.05). Furthermore, spatial proximity features had divergent implementations between sensor updates and simulation physics.

Under Protocol v6, all modules adhere to a unified hazard event and state contract.

---

## 2. Shared Event Semantics

### 2.1 Spatial Robot Proximity on Edges (`compute_edge_robot_count`)
For a canonical undirected edge $e = (u, v)$ and active fleet state dictionary $S = \{r: s_r\}_{r \in \mathcal{R}}$:
1. **Traversing Contiguity (+1.0):** If robot $r$ is actively in transit between $u$ and $v$ such that `canonical_edge(curr_node, next_node) == canonical_edge(u, v)`, it contributes exactly $+1.0$ to edge $e$.
2. **Endpoint Incident Proximity (+0.5):** If robot $r$ is currently stationed at endpoint node $u$ or $v$ (`curr_node in (u, v)`) without actively traversing a different incident edge, it contributes $+0.5$ proximity weight to edge $e$.

Both the simulator adversary (`ReactiveAdversary.get_onset_hazards`) and the belief filter (`BayesianTypeFilter`, `RobotAgent.get_edge_marginals`, `ACAAllocator`) share the identical functional implementation `compute_fleet_edge_robot_counts(graph, edges, fleet_states)`.

### 2.2 Budgeted Interdiction Cut (`compute_interdiction_cut`)
For an edge set $\mathcal{E}_{\text{risky}}$, budget $k$, and origin-destination pairs defined by active fleet tasks:
1. Interdiction targets are selected via greedy submodular maximization of total shortest-path travel delay across active fleet paths.
2. If fleet has active tasks, shortest-path increases over the current graph determine targeted edges.
3. Fallback under inactive fleet uses edge betweenness centrality over $\mathcal{E}_{\text{risky}}$.
4. An edge $e$ evaluates to `is_targeted_by_interdiction = True` if and only if $e \in \text{targeted\_edges}$.

Both the simulator adversary (`BudgetedInterdictionAdversary`) and the planning-time marginal estimators evaluate the identical cut function `compute_interdiction_cut(graph, risky_edges, fleet_states, budget_k)`.

---

## 3. Planning-Time State Propagation

In all planning and auction methods:
- `ACAAllocator._build_bundle_aca`: queries `robot.get_edge_marginals(fleet_states=fleet_states)`.
- `ACAAllocator._get_peer_edge_marginals`: passes `fleet_states` and passes explicit `edge_robot_count` and `is_targeted_by_interdiction` to `get_hazard_under_type`.
- `ACAAllocator._compute_lipschitz_L_j`: evaluates `hazards_by_type` using explicit `edge_robot_count` and `is_targeted_by_interdiction` derived from current fleet states.
- Zero calls with default `edge_robot_count=0` or `is_targeted_by_interdiction=False` are permitted in planning paths.

---

## 4. Directional Hypothesis Separation

Under equal inputs, given edge $e$ with proximity $c > 0$ and interdiction targeting $T \in \{0, 1\}$:
- **$\theta_1$ (Stochastic):** $h(e) = p_0 = 0.15$ (independent of fleet positions or targeting).
- **$\theta_2$ (Reactive):** $h(e) = \min(1.0, 0.05 + \alpha \cdot c)$ (strictly increases with robot proximity $c$).
- **$\theta_3$ (Budgeted Interdiction):** $h(e) = p_{\text{cut}} = 0.85$ if $T = 1$, else $0.05$ (strictly separates targeted bottleneck edges from non-targeted edges).

This directional separation guarantees that the Bayesian posterior over hypothesis types $\mathcal{T}$ and resulting marginals $\pi_r(e)$ meaningfully inform contingency planning and margin claims.
