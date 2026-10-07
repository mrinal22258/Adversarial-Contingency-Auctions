"""
Statistical Analysis Pipeline for Hypotheses H1-H8 (Phase 3 & Phase 4).
Reads results/raw_results.csv, aggregates to independent instance level (graph_family, seed),
executes paired tests, TOST equivalence tests, bootstrap CIs, and multiple-comparison corrections,
and outputs results/stats/*.csv and RESULTS_VERDICT.md.
"""

import os
import sys
import yaml
import numpy as np
import pandas as pd
import scipy.stats as stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.stats import (
    paired_cohens_dz,
    hodges_lehmann_difference,
    cliffs_delta,
    tost_equivalence_test,
    paired_wilcoxon_test,
    holm_bonferroni_correction,
    benjamini_hochberg_correction,
    bootstrap_ci,
)


def load_and_aggregate_instances(csv_path: str) -> pd.DataFrame:
    """
    Unit of Analysis Rule:
    The independent unit is (graph_family, seed).
    Averages replicate runs inside each instance to prevent pseudo-replication.
    """
    df = pd.read_csv(csv_path)
    metric_cols = [
        "completion_rate_pct",
        "net_welfare",
        "total_travel_distance",
        "total_messages",
        "total_conflicts",
        "distinct_conflicts",
        "safe_claim_conflicts",
        "safe_claims",
        "deferred_claims",
        "reauction_events",
        "mean_tick_runtime_ms",
    ]
    # Keep only available numeric cols
    avail_cols = [c for c in metric_cols if c in df.columns]

    inst_df = df.groupby(["graph_family", "seed", "method"])[avail_cols].mean().reset_index()
    return inst_df, df


def evaluate_hypotheses(inst_df: pd.DataFrame, raw_df: pd.DataFrame, hypotheses_config: dict) -> pd.DataFrame:
    """Evaluate each pre-registered hypothesis H1-H8 on independent instances."""
    results = []

    # Pivot instances by method for paired comparisons
    pivots = {}
    for metric in ["completion_rate_pct", "net_welfare", "total_messages", "safe_claim_conflicts", "reauction_events"]:
        if metric in inst_df.columns:
            pivots[metric] = inst_df.pivot(index=["graph_family", "seed"], columns="method", values=metric)

    # H1: ACA vs ACA-depth-0 (Recourse Efficacy)
    if "aca" in pivots["completion_rate_pct"] and "aca_depth_0" in pivots["completion_rate_pct"]:
        x = pivots["completion_rate_pct"]["aca"].dropna()
        y = pivots["completion_rate_pct"]["aca_depth_0"].dropna()
        common = x.index.intersection(y.index)
        x_c, y_c = x.loc[common], y.loc[common]
        
        stat, p_val = paired_wilcoxon_test(list(x_c), list(y_c), alternative="greater")
        hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c), list(y_c))
        cd, cd_low, cd_high = cliffs_delta(list(x_c), list(y_c))
        dz = paired_cohens_dz(list(x_c), list(y_c))

        results.append({
            "hypothesis_id": "H1",
            "title": "Recourse Efficacy (ACA vs ACA-d0)",
            "metric": "completion_rate_pct",
            "comparison": "aca - aca_depth_0",
            "n_instances": len(common),
            "mean_aca": round(float(x_c.mean()), 2),
            "mean_comparator": round(float(y_c.mean()), 2),
            "mean_diff": round(float((x_c - y_c).mean()), 2),
            "hl_median_diff": round(hl, 2),
            "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
            "cliffs_delta": round(cd, 3),
            "cliffs_ci_95": f"[{round(cd_low, 3)}, {round(cd_high, 3)}]",
            "cohens_dz": round(dz, 3),
            "raw_p_value": p_val,
            "test_type": "paired_wilcoxon_greater",
            "tier": "primary",
        })

    # H2: ACA vs Level Execution Baselines (+LR)
    for baseline_lr in ["cbba_lr", "cbba_partial_lr", "ssi_lr"]:
        if "aca" in pivots["completion_rate_pct"] and baseline_lr in pivots["completion_rate_pct"]:
            x = pivots["completion_rate_pct"]["aca"].dropna()
            y = pivots["completion_rate_pct"][baseline_lr].dropna()
            common = x.index.intersection(y.index)
            x_c, y_c = x.loc[common], y.loc[common]

            stat, p_val = paired_wilcoxon_test(list(x_c), list(y_c), alternative="two-sided")
            hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c), list(y_c))
            cd, cd_low, cd_high = cliffs_delta(list(x_c), list(y_c))
            dz = paired_cohens_dz(list(x_c), list(y_c))

            results.append({
                "hypothesis_id": "H2",
                "title": f"Level Execution (ACA vs {baseline_lr})",
                "metric": "completion_rate_pct",
                "comparison": f"aca - {baseline_lr}",
                "n_instances": len(common),
                "mean_aca": round(float(x_c.mean()), 2),
                "mean_comparator": round(float(y_c.mean()), 2),
                "mean_diff": round(float((x_c - y_c).mean()), 2),
                "hl_median_diff": round(hl, 2),
                "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
                "cliffs_delta": round(cd, 3),
                "cliffs_ci_95": f"[{round(cd_low, 3)}, {round(cd_high, 3)}]",
                "cohens_dz": round(dz, 3),
                "raw_p_value": p_val,
                "test_type": "paired_wilcoxon_two_sided",
                "tier": "primary",
            })

    # H3: Welfare Non-Inferiority vs Best Baseline
    if "aca" in pivots["net_welfare"]:
        # Find best comparator on net welfare
        comparators = [c for c in pivots["net_welfare"].columns if c != "aca"]
        if comparators:
            mean_welfares = {c: pivots["net_welfare"][c].mean() for c in comparators}
            best_c = max(mean_welfares, key=mean_welfares.get)
            x = pivots["net_welfare"]["aca"].dropna()
            y = pivots["net_welfare"][best_c].dropna()
            common = x.index.intersection(y.index)
            x_c, y_c = x.loc[common], y.loc[common]

            # Margin 5% of best baseline mean
            equiv_margin = float(0.05 * abs(y_c.mean()))
            tost_res = tost_equivalence_test(list(x_c), list(y_c), margin=equiv_margin, alpha=0.05)

            results.append({
                "hypothesis_id": "H3",
                "title": f"Welfare Non-Inferiority (ACA vs best {best_c})",
                "metric": "net_welfare",
                "comparison": f"aca - {best_c}",
                "n_instances": len(common),
                "mean_aca": round(float(x_c.mean()), 2),
                "mean_comparator": round(float(y_c.mean()), 2),
                "mean_diff": round(float((x_c - y_c).mean()), 2),
                "hl_median_diff": round(tost_res["mean_diff"], 2),
                "hl_ci_95": f"[{round(tost_res['ci_90_lower'], 2)}, {round(tost_res['ci_90_upper'], 2)}]",
                "cliffs_delta": round(cliffs_delta(list(x_c), list(y_c))[0], 3),
                "cliffs_ci_95": "N/A",
                "cohens_dz": round(paired_cohens_dz(list(x_c), list(y_c)), 3),
                "raw_p_value": tost_res["p_tost"],
                "test_type": "tost_non_inferiority",
                "tier": "primary",
            })

    # H4: Pinsker Margin Conflict Elimination (ACA vs ACA-No-Margin)
    if "aca" in pivots["completion_rate_pct"] and "aca_no_margin" in pivots["completion_rate_pct"]:
        x_c = pivots["completion_rate_pct"]["aca"].dropna()
        y_c = pivots["completion_rate_pct"]["aca_no_margin"].dropna()
        common = x_c.index.intersection(y_c.index)
        
        stat, p_val = paired_wilcoxon_test(list(x_c.loc[common]), list(y_c.loc[common]), alternative="two-sided")
        hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c.loc[common]), list(y_c.loc[common]))
        
        results.append({
            "hypothesis_id": "H4",
            "title": "Margin Conflict Impact (ACA vs ACA-NoMargin)",
            "metric": "completion_rate_pct",
            "comparison": "aca - aca_no_margin",
            "n_instances": len(common),
            "mean_aca": round(float(x_c.loc[common].mean()), 2),
            "mean_comparator": round(float(y_c.loc[common].mean()), 2),
            "mean_diff": round(float((x_c.loc[common] - y_c.loc[common]).mean()), 2),
            "hl_median_diff": round(hl, 2),
            "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
            "cliffs_delta": round(cliffs_delta(list(x_c.loc[common]), list(y_c.loc[common]))[0], 3),
            "cliffs_ci_95": "N/A",
            "cohens_dz": round(paired_cohens_dz(list(x_c.loc[common]), list(y_c.loc[common])), 3),
            "raw_p_value": p_val,
            "test_type": "paired_wilcoxon_two_sided",
            "tier": "primary",
        })

    # H5: Bayesian Inference Advantage (ACA vs ACA-No-Inference)
    if "aca" in pivots["completion_rate_pct"] and "aca_no_inference" in pivots["completion_rate_pct"]:
        x_c = pivots["completion_rate_pct"]["aca"].dropna()
        y_c = pivots["completion_rate_pct"]["aca_no_inference"].dropna()
        common = x_c.index.intersection(y_c.index)
        stat, p_val = paired_wilcoxon_test(list(x_c.loc[common]), list(y_c.loc[common]), alternative="greater")
        hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c.loc[common]), list(y_c.loc[common]))

        results.append({
            "hypothesis_id": "H5",
            "title": "Bayesian Inference Advantage (ACA vs ACA-NoInference)",
            "metric": "completion_rate_pct",
            "comparison": "aca - aca_no_inference",
            "n_instances": len(common),
            "mean_aca": round(float(x_c.loc[common].mean()), 2),
            "mean_comparator": round(float(y_c.loc[common].mean()), 2),
            "mean_diff": round(float((x_c.loc[common] - y_c.loc[common]).mean()), 2),
            "hl_median_diff": round(hl, 2),
            "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
            "cliffs_delta": round(cliffs_delta(list(x_c.loc[common]), list(y_c.loc[common]))[0], 3),
            "cliffs_ci_95": "N/A",
            "cohens_dz": round(paired_cohens_dz(list(x_c.loc[common]), list(y_c.loc[common])), 3),
            "raw_p_value": p_val,
            "test_type": "paired_wilcoxon_greater",
            "tier": "secondary",
        })

    # H6: Communication and Re-Auction Efficiency (ACA vs CBBA)
    if "aca" in pivots["total_messages"] and "cbba" in pivots["total_messages"]:
        x_c = pivots["total_messages"]["aca"].dropna()
        y_c = pivots["total_messages"]["cbba"].dropna()
        common = x_c.index.intersection(y_c.index)
        stat, p_val = paired_wilcoxon_test(list(x_c.loc[common]), list(y_c.loc[common]), alternative="less")
        hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c.loc[common]), list(y_c.loc[common]))

        results.append({
            "hypothesis_id": "H6",
            "title": "Communication Efficiency (ACA vs CBBA)",
            "metric": "total_messages",
            "comparison": "aca - cbba",
            "n_instances": len(common),
            "mean_aca": round(float(x_c.loc[common].mean()), 2),
            "mean_comparator": round(float(y_c.loc[common].mean()), 2),
            "mean_diff": round(float((x_c.loc[common] - y_c.loc[common]).mean()), 2),
            "hl_median_diff": round(hl, 2),
            "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
            "cliffs_delta": round(cliffs_delta(list(x_c.loc[common]), list(y_c.loc[common]))[0], 3),
            "cliffs_ci_95": "N/A",
            "cohens_dz": round(paired_cohens_dz(list(x_c.loc[common]), list(y_c.loc[common])), 3),
            "raw_p_value": p_val,
            "test_type": "paired_wilcoxon_less",
            "tier": "secondary",
        })

    # H7: Assumption 1 Empirical Validity (TV bound adherence rate >= 0.90)
    if "safe_claim_conflicts" in raw_df.columns:
        aca_runs = raw_df[raw_df["method"] == "aca"]
        total_evals = len(aca_runs)
        # Runs with 0 safe claim conflicts satisfy Assumption 1 guarantee
        adhered = int((aca_runs["safe_claim_conflicts"] == 0).sum())
        from scipy.stats import binomtest
        b_res = binomtest(adhered, total_evals, p=0.90, alternative="greater")
        ci = b_res.proportion_ci(confidence_level=0.95)

        results.append({
            "hypothesis_id": "H7",
            "title": "Assumption 1 Empirical Adherence Rate",
            "metric": "tv_bound_adherence_rate",
            "comparison": "adherence_rate vs 0.90",
            "n_instances": total_evals,
            "mean_aca": round(float(adhered / max(1, total_evals)), 4),
            "mean_comparator": 0.90,
            "mean_diff": round(float(adhered / max(1, total_evals) - 0.90), 4),
            "hl_median_diff": round(float(adhered / max(1, total_evals)), 4),
            "hl_ci_95": f"[{round(ci.low, 4)}, {round(ci.high, 4)}]",
            "cliffs_delta": 0.0,
            "cliffs_ci_95": "N/A",
            "cohens_dz": 0.0,
            "raw_p_value": b_res.pvalue,
            "test_type": "exact_binomial_greater",
            "tier": "secondary",
        })

    # H8: Out-of-Model Adversary Robustness (theta_4 Cyclic Patrol)
    t4_df = raw_df[raw_df["adversary"] == "theta_4_cyclic_patrol"]
    if not t4_df.empty:
        t4_inst = t4_df.groupby(["graph_family", "seed", "method"])["completion_rate_pct"].mean().reset_index()
        t4_piv = t4_inst.pivot(index=["graph_family", "seed"], columns="method", values="completion_rate_pct")
        if "aca" in t4_piv:
            other_m = [c for c in t4_piv.columns if c != "aca"]
            best_t4 = max(other_m, key=lambda c: t4_piv[c].mean()) if other_m else None
            if best_t4:
                x_c = t4_piv["aca"].dropna()
                y_c = t4_piv[best_t4].dropna()
                common = x_c.index.intersection(y_c.index)
                stat, p_val = paired_wilcoxon_test(list(x_c.loc[common]), list(y_c.loc[common]), alternative="two-sided")
                hl, hl_low, hl_high = hodges_lehmann_difference(list(x_c.loc[common]), list(y_c.loc[common]))

                results.append({
                    "hypothesis_id": "H8",
                    "title": f"Robustness on theta_4 (ACA vs best {best_t4})",
                    "metric": "completion_rate_pct",
                    "comparison": f"aca - {best_t4}",
                    "n_instances": len(common),
                    "mean_aca": round(float(x_c.loc[common].mean()), 2),
                    "mean_comparator": round(float(y_c.loc[common].mean()), 2),
                    "mean_diff": round(float((x_c.loc[common] - y_c.loc[common]).mean()), 2),
                    "hl_median_diff": round(hl, 2),
                    "hl_ci_95": f"[{round(hl_low, 2)}, {round(hl_high, 2)}]",
                    "cliffs_delta": round(cliffs_delta(list(x_c.loc[common]), list(y_c.loc[common]))[0], 3),
                    "cliffs_ci_95": "N/A",
                    "cohens_dz": round(paired_cohens_dz(list(x_c.loc[common]), list(y_c.loc[common])), 3),
                    "raw_p_value": p_val,
                    "test_type": "paired_wilcoxon_two_sided",
                    "tier": "secondary",
                })

    # Apply Multiple-Comparison Corrections (Holm for primary, BH for secondary)
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        primary_mask = res_df["tier"] == "primary"
        if primary_mask.any():
            primary_p = res_df.loc[primary_mask, "raw_p_value"].tolist()
            holm_res = holm_bonferroni_correction(primary_p, alpha=0.05)
            res_df.loc[primary_mask, "adj_p_value"] = [r[0] for r in holm_res]
            res_df.loc[primary_mask, "significant"] = [r[1] for r in holm_res]

        secondary_mask = res_df["tier"] == "secondary"
        if secondary_mask.any():
            sec_p = res_df.loc[secondary_mask, "raw_p_value"].tolist()
            bh_res = benjamini_hochberg_correction(sec_p, q=0.05)
            res_df.loc[secondary_mask, "adj_p_value"] = [r[0] for r in bh_res]
            res_df.loc[secondary_mask, "significant"] = [r[1] for r in bh_res]

    return res_df


def generate_verdict_markdown(res_df: pd.DataFrame, output_path: str = "RESULTS_VERDICT.md") -> None:
    """Generate the definitive RESULTS_VERDICT.md reporting supported / not supported."""
    lines = [
        "# RESULTS_VERDICT.md: Empirical Verdict for Hypotheses H1-H8",
        "",
        "**Strict Rule R5**: Every claim in the paper maps directly to an entry below.",
        "Generated directly from executed raw runs and independent instance-level tests.",
        "",
        "| ID | Title | Metric | Mean Diff | HL Median [95% CI] | Cliff's Delta | Raw p | Holm Adj p | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for _, row in res_df.iterrows():
        p_raw = f"{row['raw_p_value']:.4e}" if row['raw_p_value'] < 0.001 else f"{row['raw_p_value']:.4f}"
        p_adj = f"{row.get('adj_p_value', row['raw_p_value']):.4e}" if row.get('adj_p_value', 1.0) < 0.001 else f"{row.get('adj_p_value', 1.0):.4f}"
        
        # Dynamically determine verdict based on statistical test type and results
        sig = row.get("significant", False)
        hl_diff = row.get("hl_median_diff", 0.0)
        test_type = row.get("test_type", "")
        p_raw_val = row.get("raw_p_value", 1.0)

        if "tost" in test_type or row["hypothesis_id"] == "H3":
            if p_raw_val <= 0.05:
                verdict = "**NON-INFERIOR (SUPPORTED)**"
            else:
                verdict = "**NOT EQUIVALENT / INCONCLUSIVE**"
        elif "two_sided" in test_type:
            if sig:
                direction = "ACA HIGHER" if hl_diff > 0 else "COMPARATOR HIGHER"
                verdict = f"**SIGNIFICANT DIFFERENCE ({direction})**"
            else:
                verdict = "**PARITY (NO SIGNIFICANT DIFFERENCE)**"
        else: # One-sided / superiority test
            if sig and hl_diff > 0:
                verdict = "**SUPPORTED (ACA SUPERIOR)**"
            elif sig and hl_diff < 0:
                verdict = "**REJECTED (BASELINE SUPERIOR)**"
            else:
                verdict = "**NOT SUPPORTED / PARITY**"

        lines.append(
            f"| {row['hypothesis_id']} | {row['title']} | {row['metric']} | {row['mean_diff']} | "
            f"{row['hl_median_diff']} {row['hl_ci_95']} | {row['cliffs_delta']} | {p_raw} | {p_adj} | {verdict} |"
        )

    lines.extend([
        "",
        "## Key Scientific Findings & Narrative Decision Rule",
        "",
    ])

    for _, row in res_df.iterrows():
        h_id = row['hypothesis_id']
        title = row['title']
        p_adj_str = f"{row.get('adj_p_value', row['raw_p_value']):.4e}" if row.get('adj_p_value', 1.0) < 0.001 else f"{row.get('adj_p_value', 1.0):.4f}"
        sig_str = "statistically significant" if row.get("significant", False) else "not statistically significant"
        n_inst = row.get("n_instances", "N/A")
        
        lines.append(
            f"- **{h_id} ({title})** [n={n_inst}]: {row['metric']} mean difference = {row['mean_diff']:+.2f} "
            f"(HL median diff = {row['hl_median_diff']:+.2f}, 95% CI {row['hl_ci_95']}, "
            f"Cliff's delta = {row['cliffs_delta']:.3f}, adjusted p = {p_adj_str}). "
            f"Result is {sig_str} at alpha=0.05."
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Generated verdict report: {output_path}")


def main():
    csv_path = "results/raw_results.csv"
    if not os.path.exists(csv_path):
        print(f"Raw results file {csv_path} not found.")
        return

    os.makedirs("results/stats", exist_ok=True)
    inst_df, raw_df = load_and_aggregate_instances(csv_path)
    inst_df.to_csv("results/stats/instance_aggregated_results.csv", index=False)

    hypo_path = "experiments/hypotheses.yaml"
    hypo_config = {}
    if os.path.exists(hypo_path):
        with open(hypo_path, "r", encoding="utf-8") as f:
            hypo_config = yaml.safe_load(f) or {}

    res_df = evaluate_hypotheses(inst_df, raw_df, hypo_config)
    res_df.to_csv("results/stats/hypothesis_test_results.csv", index=False)
    print("\nHypothesis Test Results:")
    print(res_df[["hypothesis_id", "title", "mean_diff", "hl_median_diff", "raw_p_value", "adj_p_value", "significant"]].to_string(index=False))

    generate_verdict_markdown(res_df)


if __name__ == "__main__":
    main()
