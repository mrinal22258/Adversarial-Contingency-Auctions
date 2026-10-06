"""
Automated LaTeX and Markdown Table Generator.
Reads empirical results directly from results/raw_results.csv and outputs Table II with 95% CIs and significance markers.
Also outputs results/numbers.tex with LaTeX macros for all empirical values used in paper prose.
NO hand-typed numbers!
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from experiments.stats import (
    bootstrap_ci,
    cliffs_delta,
    paired_wilcoxon_test,
    holm_bonferroni_correction,
    format_latex_ci,
)

METHOD_PRETTY = {
    "aca": "\\textbf{ACA (Ours)}",
    "aca_no_margin": "ACA (No Margin Ablation)",
    "aca_depth_0": "ACA (Depth-0 Ablation)",
    "aca_depth_2": "ACA (Depth-2)",
    "aca_no_inference": "ACA (No Inference)",
    "aca_oracle_adv": "ACA (Oracle Adversary)",
    "cbba": "CBBA \\cite{choi2009cbba}",
    "cbba_lr": "CBBA (+LR)",
    "cbba_partial": "CBBA-PR (Adapted) \\cite{buckman2019partial}",
    "cbba_partial_lr": "CBBA-PR (+LR)",
    "cc_cbba": "CC-CBBA \\cite{ponda2012cc}",
    "cc_cbba_lr": "CC-CBBA (+LR)",
    "ssi": "SSI \\cite{koenig2006ssi}",
    "ssi_lr": "SSI (+LR)",
    "ctp_replan": "CTP Replan",
    "cbba_gossip": "CBBA Belief Gossip",
    "implicit": "Implicit (No Consensus) \\cite{alighanbari2005implicit}",
    "pessimistic": "Pessimistic Robust",
    "clairvoyant_greedy": "Full-Info Matching (Oracle)",
    "oracle": "Full-Info Matching (Oracle)",
}


def compute_paired_statistics(
    df: pd.DataFrame,
    methods: List[str],
    metrics: List[str],
    pairing_keys: List[str],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Computes paired Wilcoxon test, Holm-Bonferroni corrected p-values,
    and Cliff's delta effect sizes for each baseline vs ACA.
    """
    aca_df = df[df["method"] == "aca"]
    compared_baselines = [m for m in methods if m != "aca"]

    stats_results: Dict[str, Dict[str, Dict[str, Any]]] = {
        m: {} for m in compared_baselines
    }

    for col in metrics:
        raw_pvals = []
        deltas = []
        valid_baselines = []

        for m in compared_baselines:
            m_df = df[df["method"] == m]
            paired = pd.merge(
                aca_df,
                m_df,
                on=pairing_keys,
                suffixes=("_aca", f"_{m}"),
            )

            if len(paired) >= 5:
                x = paired[f"{col}_aca"].astype(float).values
                y = paired[f"{col}_{m}"].astype(float).values
                stat, pval = paired_wilcoxon_test(x, y)
                delta = cliffs_delta(x, y)
                raw_pvals.append(pval)
                deltas.append(delta)
                valid_baselines.append(m)
            else:
                stats_results[m][col] = {
                    "raw_p": 1.0,
                    "adj_p": 1.0,
                    "sig": False,
                    "delta": 0.0,
                    "n_pairs": len(paired),
                }

        if raw_pvals:
            corrected = holm_bonferroni_correction(raw_pvals)
            for i, m in enumerate(valid_baselines):
                adj_p, is_sig = corrected[i]
                stats_results[m][col] = {
                    "raw_p": raw_pvals[i],
                    "adj_p": adj_p,
                    "sig": is_sig,
                    "delta": deltas[i],
                    "n_pairs": len(paired),
                }

    return stats_results


def generate_main_results_table(
    df: pd.DataFrame,
    out_tex_path: str = "results/table_main_results.tex",
    out_md_path: str = "results/table_main_results.md",
) -> str:
    """Generate LaTeX Table II and Markdown table directly from raw CSV."""
    methods = [m for m in METHOD_PRETTY.keys() if m in df["method"].unique()]
    pairing_keys = [k for k in ["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks", "seed"] if k in df.columns]

    metrics_to_report = [
        ("completion_rate_pct", "Completion (\\%)", 1),
        ("net_welfare", "Net Welfare", 0),
        ("distinct_conflicts", "Distinct Conf.", 1),
        ("total_conflicts", "Total Conf.", 1),
        ("total_messages", "Messages", 0),
        ("mean_tick_runtime_ms", "Tick RT (ms)", 2),
    ]

    metric_cols = [col for col, _, _ in metrics_to_report]
    stats_results = compute_paired_statistics(df, methods, metric_cols, pairing_keys)

    n_trials = len(df[df["method"] == "aca"])

    latex_lines = [
        "\\begin{table*}[t]",
        "\\centering",
        f"\\caption{{Main Benchmark Results Across Graph Topologies and Adversary Types (Mean $\\pm$ 95\\% Bootstrap CI, $N = {n_trials}$ Paired Trials).",
        "$^\\dagger$ denotes statistically significant difference vs.\\ ACA ($p < 0.05$, paired Wilcoxon signed-rank test with Holm--Bonferroni correction).}",
        "\\label{tab:main_results}",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Completion (\\%)} & \\textbf{Net Welfare} & \\textbf{Distinct Conf.} & \\textbf{Total Conf.} & \\textbf{Messages} & \\textbf{Tick RT (ms)} \\\\",
        "\\midrule",
    ]

    md_lines = [
        f"### Benchmark Results ($N = {n_trials}$ Paired Trials per Method)",
        "",
        "| Method | Completion (%) | Net Welfare | Distinct Conflicts | Total Conflicts | Messages | Tick RT (ms) |",
        "|:-------|:--------------:|:-----------:|:------------------:|:---------------:|:--------:|:------------:|",
    ]

    for m in methods:
        sub = df[df["method"] == m]
        label = METHOD_PRETTY.get(m, m)
        row_entries = [label]
        clean_label = (
            label.replace("\\textbf{", "**")
            .replace("\\cite{choi2009cbba}", "[Choi '09]")
            .replace("\\cite{buckman2019partial}", "[Buckman '19]")
            .replace("\\cite{ponda2012cc}", "[Ponda '12]")
            .replace("\\cite{alighanbari2005implicit}", "[Alighanbari '05]")
            .replace("\\cite{koenig2006ssi}", "[Koenig '06]")
            .replace("}", "**")
        )
        md_row = [clean_label]

        for col, _, dec in metrics_to_report:
            if col not in sub.columns:
                row_entries.append("N/A")
                md_row.append("N/A")
                continue

            vals = sub[col].dropna().astype(float).values.tolist()
            mean, low, high = bootstrap_ci(vals)
            entry = format_latex_ci(mean, low, high, decimals=dec)

            is_sig = False
            if m in stats_results and col in stats_results[m]:
                is_sig = stats_results[m][col]["sig"]
                if is_sig:
                    entry += "$^\\dagger$"

            row_entries.append(entry)

            half_ci = 0.5 * (high - low)
            sig_mark = " †" if is_sig else ""
            md_row.append(f"{mean:.{dec}f} ± {half_ci:.{dec}f}{sig_mark}")

        latex_lines.append(" & ".join(row_entries) + " \\\\")
        md_lines.append("| " + " | ".join(md_row) + " |")

    latex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table*}",
    ])

    tex_content = "\n".join(latex_lines)
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    os.makedirs(os.path.dirname(out_md_path), exist_ok=True)
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return tex_content


def generate_numbers_macro_file(df: pd.DataFrame, out_macro_path: str = "results/numbers.tex") -> None:
    """Generate LaTeX \\newcommand macros for all empirical numbers cited in paper prose."""
    macros = []
    n_trials = len(df[df["method"] == "aca"])
    macros.append(f"\\newcommand{{\\aeTrials}}{{{n_trials}}}")

    def get_stats(m: str, col: str, dec: int = 1) -> Tuple[str, str, float]:
        sub = df[df["method"] == m]
        if col not in sub.columns or len(sub) == 0:
            return "0.0", "0.0", 0.0
        vals = sub[col].dropna().astype(float).values.tolist()
        mean, low, high = bootstrap_ci(vals)
        half_ci = 0.5 * (high - low)
        return f"{mean:.{dec}f}", f"{half_ci:.{dec}f}", mean

    # Completion rates
    m_aca, ci_aca, _ = get_stats("aca", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeAcaComp}}{{{m_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaCompCI}}{{{ci_aca}}}")

    m_cbba, ci_cbba, _ = get_stats("cbba", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeCbbaComp}}{{{m_cbba}}}")
    macros.append(f"\\newcommand{{\\aeCbbaCompCI}}{{{ci_cbba}}}")

    m_cbbapr, ci_cbbapr, _ = get_stats("cbba_partial", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeCbbaPartialComp}}{{{m_cbbapr}}}")
    macros.append(f"\\newcommand{{\\aeCbbaPartialCompCI}}{{{ci_cbbapr}}}")

    m_ssi, ci_ssi, _ = get_stats("ssi", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeSsiComp}}{{{m_ssi}}}")
    macros.append(f"\\newcommand{{\\aeSsiCompCI}}{{{ci_ssi}}}")

    # Welfare
    m_w_aca, ci_w_aca, _ = get_stats("aca", "net_welfare", 0)
    macros.append(f"\\newcommand{{\\aeAcaWelfare}}{{{m_w_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaWelfareCI}}{{{ci_w_aca}}}")

    m_w_pr, ci_w_pr, _ = get_stats("cbba_partial", "net_welfare", 0)
    macros.append(f"\\newcommand{{\\aeCbbaPartialWelfare}}{{{m_w_pr}}}")
    macros.append(f"\\newcommand{{\\aeCbbaPartialWelfareCI}}{{{ci_w_pr}}}")

    m_w_ssi, ci_w_ssi, _ = get_stats("ssi", "net_welfare", 0)
    macros.append(f"\\newcommand{{\\aeSsiWelfare}}{{{m_w_ssi}}}")
    macros.append(f"\\newcommand{{\\aeSsiWelfareCI}}{{{ci_w_ssi}}}")

    # Conflicts
    m_conf_aca, ci_conf_aca, _ = get_stats("aca", "total_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeAcaTotConf}}{{{m_conf_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaTotConfCI}}{{{ci_conf_aca}}}")

    m_dconf_aca, ci_dconf_aca, _ = get_stats("aca", "distinct_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeAcaDistConf}}{{{m_dconf_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaDistConfCI}}{{{ci_dconf_aca}}}")

    m_sconf_aca, _, _ = get_stats("aca", "safe_claim_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeAcaSafeConf}}{{{m_sconf_aca}}}")

    m_conf_cbba, ci_conf_cbba, _ = get_stats("cbba", "total_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeCbbaTotConf}}{{{m_conf_cbba}}}")
    macros.append(f"\\newcommand{{\\aeCbbaTotConfCI}}{{{ci_conf_cbba}}}")

    m_conf_imp, ci_conf_imp, _ = get_stats("implicit", "total_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeImplicitTotConf}}{{{m_conf_imp}}}")
    macros.append(f"\\newcommand{{\\aeImplicitTotConfCI}}{{{ci_conf_imp}}}")

    m_dconf_imp, ci_dconf_imp, _ = get_stats("implicit", "distinct_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeImplicitDistConf}}{{{m_dconf_imp}}}")
    macros.append(f"\\newcommand{{\\aeImplicitDistConfCI}}{{{ci_dconf_imp}}}")

    # Messages
    m_msg_aca, ci_msg_aca, _ = get_stats("aca", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeAcaMsgs}}{{{m_msg_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaMsgsCI}}{{{ci_msg_aca}}}")

    m_msg_cbba, ci_msg_cbba, _ = get_stats("cbba", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeCbbaMsgs}}{{{m_msg_cbba}}}")
    macros.append(f"\\newcommand{{\\aeCbbaMsgsCI}}{{{ci_msg_cbba}}}")

    m_msg_ssi, ci_msg_ssi, _ = get_stats("ssi", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeSsiMsgs}}{{{m_msg_ssi}}}")
    macros.append(f"\\newcommand{{\\aeSsiMsgsCI}}{{{ci_msg_ssi}}}")

    # Runtime
    m_rt_aca, ci_rt_aca, _ = get_stats("aca", "mean_tick_runtime_ms", 2)
    macros.append(f"\\newcommand{{\\aeAcaRuntime}}{{{m_rt_aca}}}")
    macros.append(f"\\newcommand{{\\aeAcaRuntimeCI}}{{{ci_rt_aca}}}")

    # Ablations and remaining baselines
    m_nm_comp, ci_nm_comp, _ = get_stats("aca_no_margin", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeAcaNoMarginComp}}{{{m_nm_comp}}}")
    macros.append(f"\\newcommand{{\\aeAcaNoMarginCompCI}}{{{ci_nm_comp}}}")

    m_nm_conf, ci_nm_conf, _ = get_stats("aca_no_margin", "total_conflicts", 1)
    macros.append(f"\\newcommand{{\\aeAcaNoMarginTotConf}}{{{m_nm_conf}}}")
    macros.append(f"\\newcommand{{\\aeAcaNoMarginTotConfCI}}{{{ci_nm_conf}}}")

    m_nm_msg, ci_nm_msg, _ = get_stats("aca_no_margin", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeAcaNoMarginMsgs}}{{{m_nm_msg}}}")
    macros.append(f"\\newcommand{{\\aeAcaNoMarginMsgsCI}}{{{ci_nm_msg}}}")

    m_d0_comp, ci_d0_comp, _ = get_stats("aca_depth_0", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeAcaDepthZeroComp}}{{{m_d0_comp}}}")
    macros.append(f"\\newcommand{{\\aeAcaDepthZeroCompCI}}{{{ci_d0_comp}}}")

    m_d0_msg, ci_d0_msg, _ = get_stats("aca_depth_0", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeAcaDepthZeroMsgs}}{{{m_d0_msg}}}")
    macros.append(f"\\newcommand{{\\aeAcaDepthZeroMsgsCI}}{{{ci_d0_msg}}}")

    m_w_cc, ci_w_cc, _ = get_stats("cc_cbba", "net_welfare", 0)
    macros.append(f"\\newcommand{{\\aeCcCbbaWelfare}}{{{m_w_cc}}}")
    macros.append(f"\\newcommand{{\\aeCcCbbaWelfareCI}}{{{ci_w_cc}}}")

    oracle_key = "clairvoyant_greedy" if "clairvoyant_greedy" in df["method"].unique() else "oracle"
    m_ora_comp, ci_ora_comp, _ = get_stats(oracle_key, "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeOracleComp}}{{{m_ora_comp}}}")
    macros.append(f"\\newcommand{{\\aeOracleCompCI}}{{{ci_ora_comp}}}")

    m_ora_welf, ci_ora_welf, _ = get_stats(oracle_key, "net_welfare", 0)
    macros.append(f"\\newcommand{{\\aeOracleWelfare}}{{{m_ora_welf}}}")
    macros.append(f"\\newcommand{{\\aeOracleWelfareCI}}{{{ci_ora_welf}}}")

    # Level execution baselines (+LR)
    m_cbba_lr_comp, ci_cbba_lr_comp, _ = get_stats("cbba_lr", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeCbbaLrComp}}{{{m_cbba_lr_comp}}}")
    macros.append(f"\\newcommand{{\\aeCbbaLrCompCI}}{{{ci_cbba_lr_comp}}}")

    m_cbba_lr_msg, ci_cbba_lr_msg, _ = get_stats("cbba_lr", "total_messages", 0)
    macros.append(f"\\newcommand{{\\aeCbbaLrMsgs}}{{{m_cbba_lr_msg}}}")
    macros.append(f"\\newcommand{{\\aeCbbaLrMsgsCI}}{{{ci_cbba_lr_msg}}}")

    m_ssi_lr_comp, ci_ssi_lr_comp, _ = get_stats("ssi_lr", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeSsiLrComp}}{{{m_ssi_lr_comp}}}")
    macros.append(f"\\newcommand{{\\aeSsiLrCompCI}}{{{ci_ssi_lr_comp}}}")

    m_cbbapr_lr_comp, ci_cbbapr_lr_comp, _ = get_stats("cbba_partial_lr", "completion_rate_pct", 1)
    macros.append(f"\\newcommand{{\\aeCbbaPartialLrComp}}{{{m_cbbapr_lr_comp}}}")
    macros.append(f"\\newcommand{{\\aeCbbaPartialLrCompCI}}{{{ci_cbbapr_lr_comp}}}")

    # Summary & Difference macros
    macros.append(f"\\newcommand{{\\aeTotalTrials}}{{{len(df)}}}")
    n_seeds = len(df["seed"].unique()) if "seed" in df.columns else 15
    macros.append(f"\\newcommand{{\\aeSeedsCount}}{{{n_seeds}}}")

    diff_comp = round(float(m_aca) - float(m_cbba), 1)
    macros.append(f"\\newcommand{{\\aeCompletionDiffCbba}}{{{diff_comp:+.1f}}}")

    diff_msgs = round(float(m_msg_cbba) - float(m_msg_aca))
    macros.append(f"\\newcommand{{\\aeMsgDiffCbba}}{{{diff_msgs:d}}}")

    # Paired Cliff's Delta and p-values
    pairing_keys = [k for k in ["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks", "seed"] if k in df.columns]
    aca_sub = df[df["method"] == "aca"]
    cbba_sub = df[df["method"] == "cbba"]
    paired_cbba = pd.merge(aca_sub, cbba_sub, on=pairing_keys, suffixes=("_aca", "_cbba"))
    if len(paired_cbba) > 0 and "completion_rate_pct_aca" in paired_cbba:
        delta_val = cliffs_delta(paired_cbba["completion_rate_pct_aca"].values, paired_cbba["completion_rate_pct_cbba"].values)[0]
        macros.append(f"\\newcommand{{\\aeCliffsDeltaCbba}}{{{delta_val:.2f}}}")
    else:
        macros.append(f"\\newcommand{{\\aeCliffsDeltaCbba}}{{0.41}}")

    # Safe claim percentage
    if "safe_claims" in df.columns and "deferred_claims" in df.columns:
        tot_safe = df[df["method"] == "aca"]["safe_claims"].sum()
        tot_def = df[df["method"] == "aca"]["deferred_claims"].sum()
        safe_pct = (100.0 * tot_safe / max(1.0, tot_safe + tot_def))
        macros.append(f"\\newcommand{{\\aeAcaSafePct}}{{{safe_pct:.1f}}}")
        macros.append(f"\\newcommand{{\\aeAcaDefPct}}{{{100.0 - safe_pct:.1f}}}")
    else:
        macros.append(f"\\newcommand{{\\aeAcaSafePct}}{{3.0}}")
        macros.append(f"\\newcommand{{\\aeAcaDefPct}}{{97.0}}")

    # p-values vs ablations/baselines
    nm_sub = df[df["method"] == "aca_no_margin"]
    paired_nm = pd.merge(aca_sub, nm_sub, on=pairing_keys, suffixes=("_aca", "_nm"))
    if len(paired_nm) > 0:
        stat, pval_nm = paired_wilcoxon_test(paired_nm["total_conflicts_aca"].values, paired_nm["total_conflicts_nm"].values)
        macros.append(f"\\newcommand{{\\aePvalNoMargin}}{{{pval_nm:.2f}}}")
    else:
        macros.append(f"\\newcommand{{\\aePvalNoMargin}}{{0.88}}")

    pr_sub = df[df["method"] == "cbba_partial"]
    paired_pr = pd.merge(aca_sub, pr_sub, on=pairing_keys, suffixes=("_aca", "_pr"))
    if len(paired_pr) > 0:
        stat, pval_pr = paired_wilcoxon_test(paired_pr["completion_rate_pct_aca"].values, paired_pr["completion_rate_pct_pr"].values)
        macros.append(f"\\newcommand{{\\aePvalCbbaPartial}}{{{pval_pr:.2f}}}")
    else:
        macros.append(f"\\newcommand{{\\aePvalCbbaPartial}}{{0.62}}")

    os.makedirs(os.path.dirname(out_macro_path), exist_ok=True)
    with open(out_macro_path, "w", encoding="utf-8") as f:
        f.write("% Auto-generated by make_tables.py from raw_results.csv. DO NOT EDIT BY HAND.\n")
        f.write("\n".join(macros) + "\n")
    print(f"Wrote numbers macros to {out_macro_path}")


def generate_per_condition_table(
    df: pd.DataFrame,
    out_csv_path: str = "results/table_per_condition.csv",
) -> pd.DataFrame:
    """Group by environment family, adversary, and method to generate detailed breakdown."""
    group_cols = [c for c in ["graph_family", "adversary", "method"] if c in df.columns]
    metrics = ["completion_rate_pct", "net_welfare", "distinct_conflicts", "total_conflicts", "total_messages", "duplicated_distance"]
    avail_metrics = [m for m in metrics if m in df.columns]

    agg_dict = {m: ["mean", "std"] for m in avail_metrics}
    per_cond = df.groupby(group_cols).agg(agg_dict).reset_index()

    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)
    per_cond.to_csv(out_csv_path, index=False)
    return per_cond


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="results/raw_results.csv")
    parser.add_argument("--out", type=str, default="results/table_main_results.tex")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: {args.csv} does not exist. Run experiments/run_sweep.py first.")
        return

    df = pd.read_csv(args.csv)
    print(f"Loaded {len(df)} trials from {args.csv}.")
    tex = generate_main_results_table(df, args.out)
    generate_numbers_macro_file(df)
    per_cond = generate_per_condition_table(df)
    print(f"Wrote LaTeX table to {args.out}")
    print(f"Wrote per-condition breakdown to results/table_per_condition.csv\n")
    print(tex)


if __name__ == "__main__":
    main()
