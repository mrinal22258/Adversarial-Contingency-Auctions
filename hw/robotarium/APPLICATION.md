# Georgia Tech Robotarium Remote-Access Experiment Application

> **STATUS DISCLOSURE & PREPARATION NOTICE**:
> **This document contains the drafted application text for future remote physical multi-robot validation on the Georgia Tech Robotarium testbed. Remote real-robot validation is planned; no physical experiments were conducted in this study, and no access to the physical facility is claimed.**

---

## 1. Project Information
- **Project Title:** Adversarial Contingency Auctions (ACA) for Decentralized Multi-Robot Task Allocation under Strategic Path Blockages
- **Principal Investigator:** Kumar Mrinal (IIIT-Delhi, `mrinal22258@iiitd.ac.in`)
- **Target Facility:** Georgia Tech Robotarium Remote-Access Testbed (Pickem et al., 2017)
- **Requested Fleet:** 4 GRITSBot differential-drive mobile robots
- **Estimated Run Time:** 15 minutes across 6 experimental conditions

---

## 2. Scientific Motivation & Experimental Objectives
Multi-robot task allocation in dynamic, contested spatial domains requires robots to commit to spatial targets while subject to unanticipated corridor blockages and lossy communication. While our theoretical contributions (Theorem 1 Pinsker claim margin, Proposition 1 expected recourse cost) and simulation evaluations (PyBullet continuous rigid-body physics) validate the algorithmic mechanism, physical multi-robot deployment is necessary to quantify the sim-to-real reality gap under:
1. Asynchronous wireless packet transmission and physical latency.
2. Unicycle nonholonomic motion constraints and differential-drive wheel slip.
3. Physical Robotarium Control Barrier Functions (CBFs) governing inter-robot collision avoidance during tight bottleneck recourse detours.

---

## 3. Experimental Design & Independent Variables
We plan to evaluate two allocation mechanisms across identical matched topologies on the Robotarium arena ($[-1.6, 1.6] \times [-1.0, 1.0]$ m):
1. **ACA (Ours):** Type-aware expected recourse cost bidding + Pinsker claim margin + zero-message local detour execution.
2. **CBBA+LR (Baseline):** Standard consensus-based bundle algorithm equipped with reactive local recourse.

### Conditions to Test:
- **Map:** 12-waypoint topological corridor environment scaled to the $[-1.4, 1.4] \times [-0.8, 0.8]$ m sub-region.
- **Fleet Size:** $R = 4$ GRITSBots.
- **Task Set:** $M = 8$ spatial waypoints.
- **Interdictions:** 2 simulated virtual obstacles dynamically placed along active transit corridors, triggering local detours.
- **Replications:** 3 paired trials per method with matched initial configurations.

---

## 4. Control Barrier Function (CBF) & Safety Compliance
All robot trajectories will be passed through the standard Robotarium Control Barrier Certificate:
```python
# Enforce formal collision avoidance barrier certificate
uni_barrier_cert = create_unicycle_barrier_certificate(
    barrier_gain=100, 
    safety_radius=0.15, 
    projection_distance=0.05
)
dx_safe = uni_barrier_cert(dx_desired, poses)
```
- **Velocity Clamping:** Linear velocities strictly clamped to $v \in [0, 0.15]$ m/s (below the 0.20 m/s platform limit); angular velocities clamped to $|\omega| \le 1.5$ rad/s.
- **Arena Boundary Enforcement:** Virtual soft wall boundaries enforced at $x \in [-1.45, 1.45]$ m, $y \in [-0.85, 0.85]$ m.
- **Emergency Abort:** Script automatically shuts down robot motors if waypoint position error exceeds 0.20 m or if barrier certificate intervention fails.

---

## 5. Metrics to Extract from Telemetry
From the Robotarium overhead camera logs and robot trajectory telemetry, we will measure:
1. **Task Completion Rate (%):** Fraction of designated spatial tasks visited within the 180-second mission window.
2. **Barrier Certificate Interventions:** Count of CBF velocity corrections per trial as a metric of physical congestion around detour bottlenecks.
3. **Communication Volume:** Total bytes and discrete message count exchanged over the simulated peer-to-peer network layer.
4. **Sim-to-Real Domain Gap:** Direct comparison against the PyBullet SITL baseline metrics reported in Table V of the paper.
