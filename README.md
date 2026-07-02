---
title: Adversarial Contingency Auctions
emoji: 🤖
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
python_version: "3.10"
---

# Adversarial Contingency Auctions (ACA)

A decentralized multi-robot task allocation algorithm combining contingency games, inconsistent-belief auction dynamics, and adversarial blockages.

This interactive demo allows you to simulate a fleet of heterogeneous robots (scouts and heavy lifters) completing dynamic tasks in a graph world subject to path-blockages by a strategic adversary.

## Quick Start
1. The left panel allows tuning the robot fleet, grid size, blockage probability, and simulation seed.
2. Click **Run Simulation** to execute the scenario.
3. Use the **Step / Tick** slider under the graph to scrub through simulation ticks and visualize how robots navigate around blocks and complete tasks.
4. Review the metrics dashboard at the bottom for total utility, social welfare, fleet energy status, and out-of-sync allocations.

Original Codebase: [github.com/mrinal22258/Adversarial-Contingency-Auctions](https://github.com/mrinal22258/Adversarial-Contingency-Auctions)
