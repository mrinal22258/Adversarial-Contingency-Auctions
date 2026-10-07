# Robotarium Remote-Access Deployment Preparation

> **DISCLAIMER & CURRENT STATUS**:
> **Prepared for future remote-robot evaluation; NOT executed.**
> No physical experiments were performed. No hardware was deployed.
> No access to the Georgia Tech Robotarium facility is claimed.
> All results reported in this paper are purely from software simulation.

## 1. Overview
This directory contains the remote-access deployment scaffolding prepared for validating
the Adversarial Contingency Auctions (ACA) decentralized allocator on physical differential-drive
robots (GRITSBots) via the Georgia Tech Robotarium remote-access facility (Pickem et al., 2017).

## 2. System Architecture & Command Mapping
Robotarium accepts single-integrator or unicycle control inputs bounded by:
- Arena dimensions: $[-1.6, 1.6] \times [-1.0, 1.0]$ meters.
- Linear velocity limit: $v \le 0.20$ m/s.
- Angular velocity limit: $\omega \le \pi$ rad/s.
- Inter-robot safety distance: $d_{\min} \ge 0.15$ m (enforced via Control Barrier Functions).

### Command Mapping from SITL Diff-Drive to Robotarium:
In `experiments/sitl/robot.py`:
$$v = \frac{r (v_R + v_L)}{2}, \quad \omega = \frac{r (v_R - v_L)}{L}$$
In Robotarium Python API:
```python
# Unicycle dynamics mapping:
dx = np.array([v * np.cos(theta), v * np.sin(theta)])
# Passed to create_si_to_uni_dynamics() and barrier certificates
```

## 3. Pre-Flight Safety Checklist
- [ ] Spatial scale normalization: Map scaled to fit within $[-1.5, 1.5] \times [-0.9, 0.9]$ m.
- [ ] Barrier certificates: Integrated `create_unicycle_barrier_certificate` to prevent collisions.
- [ ] Safe claim margin verification: $\delta_j \ge L_C \eta_{\text{eff}} + \text{drift}$ before task commit.
- [ ] Lossy communication simulation: Comm drops emulated client-side via `SITLCommunicationLayer`.
- [ ] Recourse pivot boundary: Robots must pivot within safe radius if dynamic obstacles are sensed.
- [ ] Emergency stop: Script terminates if tracking error exceeds $0.10$ m or timeout reached.

## 4. Execution Plan (Future Work Only)
1. Submit Python script via Robotarium web interface.
2. Verify simulator pre-check passes without barrier violations.
3. Fetch overhead camera logs and raw telemetry.
4. Compute empirical reality gap vs PyBullet SITL simulation.
