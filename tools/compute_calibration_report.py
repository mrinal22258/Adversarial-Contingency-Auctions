#!/usr/bin/env python3
"""
Held-Out Probability Calibration Report Generator (Protocol v6 / Gate 3).
Evaluates the calibration of Bayesian edge blockage marginals against true environment states:
- Reliability diagram bins (predicted probability vs empirical blockage frequency)
- Brier score (overall and per adversary type)
- Expected Calibration Error (ECE)
Writes report to results/calibration/calibration_report.json and results/calibration/calibration_summary.md.
"""

import os
import sys
import json
import argparse
import numpy as np
import networkx as nx
from typing import Dict, Any, List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.agents.belief import (
    BayesianTypeFilter,
    compute_brier_score,
    compute_reliability_curve,
)
from acalib.agents.robot import RobotAgent
from acalib.env.adversaries import (
    AdversaryType,
    create_adversary,
    canonical_edge,
    compute_edge_robot_count,
    compute_interdiction_cut,
)
from acalib.env.blockage_process import PersistentBlockageProcess
from acalib.env.graph_families import generate_graph


def run_calibration_eval(
    seeds: List[int],
    adversary_types: List[str],
    graph_families: List[str],
    steps_per_trial: int = 30,
) -> Dict[str, Any]:
    """
    Run paired simulation rollouts tracking marginal forecasts vs realized edge blockages.
    """
    forecasts_all: List[float] = []
    outcomes_all: List[float] = []
    by_adversary: Dict[str, Dict[str, List[float]]] = {
        (adv.value if hasattr(adv, "value") else str(adv)): {"forecasts": [], "outcomes": []}
        for adv in adversary_types
    }

    for seed in seeds:
        rng = np.random.default_rng(seed)
        for g_fam in graph_families:
            G = generate_graph(g_fam, n_nodes=30, seed=seed)
            risky_edges = {canonical_edge(u, v) for u, v in G.edges()}

            for adv_name in adversary_types:
                adv_key = adv_name.value if hasattr(adv_name, "value") else str(adv_name)
                adv = create_adversary(adv_name, seed=seed)
                blockage_process = PersistentBlockageProcess(G, adv, seed=seed)

                # Initialize fleet
                fleet_ids = [0, 1]
                robots = {
                    r_id: RobotAgent(r_id, r_id % len(G), G, fleet_ids=fleet_ids)
                    for r_id in fleet_ids
                }

                for step in range(steps_per_trial):
                    fleet_states = {r_id: r.get_state_summary() for r_id, r in robots.items()}
                    blockage_process.step(fleet_states, current_step=step)

                    for r_id, robot in robots.items():
                        robot.sense_environment(blockage_process, fleet_states, step=step)
                        marginals = robot.get_edge_marginals(fleet_states=fleet_states)

                        for e, pi in marginals.items():
                            is_blocked = 1.0 if blockage_process.is_blocked(e[0], e[1]) else 0.0
                            forecasts_all.append(float(pi))
                            outcomes_all.append(is_blocked)
                            by_adversary[adv_key]["forecasts"].append(float(pi))
                            by_adversary[adv_key]["outcomes"].append(is_blocked)

    forecasts_arr = np.array(forecasts_all, dtype=float)
    outcomes_arr = np.array(outcomes_all, dtype=float)

    brier_overall = compute_brier_score(forecasts_arr, outcomes_arr)
    centers, freqs, counts = compute_reliability_curve(forecasts_arr, outcomes_arr, n_bins=10)

    # Compute Expected Calibration Error (ECE) over occupied bins
    total_samples = len(forecasts_arr)
    ece = float(sum((counts[i] / total_samples) * abs(freqs[i] - centers[i]) for i in range(len(centers)) if counts[i] > 0))

    adv_metrics = {}
    for adv, data in by_adversary.items():
        f_arr = np.array(data["forecasts"], dtype=float)
        o_arr = np.array(data["outcomes"], dtype=float)
        adv_brier = compute_brier_score(f_arr, o_arr) if len(f_arr) > 0 else 0.0
        adv_metrics[adv] = {
            "n_samples": len(f_arr),
            "brier_score": float(adv_brier),
            "mean_forecast": float(np.mean(f_arr)) if len(f_arr) > 0 else 0.0,
            "empirical_rate": float(np.mean(o_arr)) if len(o_arr) > 0 else 0.0,
        }

    return {
        "n_samples": total_samples,
        "overall_brier_score": float(brier_overall),
        "expected_calibration_error": float(ece),
        "reliability_bins": [
            {
                "bin_center": float(centers[i]),
                "empirical_freq": float(freqs[i]) if counts[i] > 0 else 0.0,
                "count": int(counts[i]),
            }
            for i in range(len(centers))
        ],
        "by_adversary": adv_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate probability calibration report")
    parser.add_argument("--output", type=str, default="results/calibration", help="Output directory")
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 102], help="Evaluation seeds")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    report = run_calibration_eval(
        seeds=args.seeds,
        adversary_types=[
            AdversaryType.STOCHASTIC,
            AdversaryType.REACTIVE,
            AdversaryType.BUDGETED_INTERDICTION,
        ],
        graph_families=["er", "rgg"],
        steps_per_trial=15,
    )

    json_path = os.path.join(args.output, "calibration_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    md_path = os.path.join(args.output, "calibration_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Bayesian Belief Probability Calibration Report\n\n")
        f.write(f"- **Evaluated Samples:** {report['n_samples']:,}\n")
        f.write(f"- **Overall Brier Score:** {report['overall_brier_score']:.4f}\n")
        f.write(f"- **Expected Calibration Error (ECE):** {report['expected_calibration_error']:.4f}\n\n")
        f.write("## Adversary-Specific Calibration Breakdown\n\n")
        f.write("| Adversary Type | Samples | Brier Score | Mean Forecast | Realized Blockage Rate |\n")
        f.write("|---|---|---|---|---|\n")
        for adv, m in report["by_adversary"].items():
            f.write(f"| `{adv}` | {m['n_samples']:,} | {m['brier_score']:.4f} | {m['mean_forecast']:.4f} | {m['empirical_rate']:.4f} |\n")
        f.write("\n## Reliability Diagram Bins\n\n")
        f.write("| Bin Center | Empirical Frequency | Observation Count |\n")
        f.write("|---|---|---|\n")
        for b in report["reliability_bins"]:
            f.write(f"| {b['bin_center']:.2f} | {b['empirical_freq']:.4f} | {b['count']:,} |\n")

    print(f"Calibration report written to {json_path} and {md_path}")
    print(f"Overall Brier Score: {report['overall_brier_score']:.4f}, ECE: {report['expected_calibration_error']:.4f}")


if __name__ == "__main__":
    main()
