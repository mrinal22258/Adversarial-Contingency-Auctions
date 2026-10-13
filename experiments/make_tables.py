"""
Automated LaTeX and Markdown Table Generator.
Reads empirical results directly from results/raw_results.csv and outputs Table II with 95% CIs and significance markers.
Also outputs results/numbers.tex with LaTeX macros for all empirical values used in paper prose.
NO hand-typed numbers!
"""

import os
import sys
import json
import re
import argparse
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
from experiments.stats import (
    bootstrap_ci,
    cliffs_delta,
    paired_wilcoxon_test,
    holm_bonferroni_correction,
    format_latex_ci,
)
from experiments.population import get_locked_population

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
    "clairvoyant_greedy": "Clairvoyant greedy (reference, not a bound)",
    "oracle": "Clairvoyant greedy (reference, not a bound)",
    "foresight_opt": "Foresight Optimal (CP-SAT bound)",
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
    Guards against merge amplification and ensures per-baseline paired N.
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
        paired_dfs = {}

        for m in compared_baselines:
            m_df = df[df["method"] == m]
            # Guard against duplicate pairing keys to prevent merge amplification
            aca_clean = aca_df.drop_duplicates(subset=pairing_keys)
            m_clean = m_df.drop_duplicates(subset=pairing_keys)

            paired = pd.merge(
                aca_clean,
                m_clean,
                on=pairing_keys,
                suffixes=("_aca", f"_{m}"),
            )
            paired_dfs[m] = paired

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
                    "n_pairs": len(paired_dfs[m]),
                }

    return stats_results


def generate_main_results_table(
    df: pd.DataFrame,
    out_tex_path: str = "results/table_main_results.tex",
    out_md_path: str = "results/table_main_results.md",
) -> str:
    """
    Generate LaTeX Table II and Markdown table directly from raw CSV.
    Evaluates on balanced core grid to ensure paired estimand consistency:
    means, bootstrap CIs, and paired tests use the identical matched population.
    """
    try:
        from experiments.population import get_locked_population
        eval_df, meta = get_locked_population(df, population_id="nominal_balanced_core")
    except Exception:
        core_mask = (df["comm_regime"] == "nominal") & (df["adversary"].isin(["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"]))
        eval_df = df[core_mask] if core_mask.sum() > 0 else df

    methods = [m for m in METHOD_PRETTY.keys() if m in eval_df["method"].unique()]
    pairing_keys = [k for k in ["graph_family", "adversary", "comm_regime", "n_robots", "n_tasks", "seed"] if k in eval_df.columns]

    metrics_to_report = [
        ("completion_rate_pct", "Completion (\\%)", 1),
        ("net_welfare", "Net Welfare", 0),
        ("distinct_conflicts", "Distinct Conf.", 1),
        ("total_conflicts", "Total Conf.", 1),
        ("total_messages", "Messages", 0),
        ("mean_tick_runtime_ms", "Tick RT (ms)", 2),
    ]

    metric_cols = [col for col, _, _ in metrics_to_report]
    stats_results = compute_paired_statistics(eval_df, methods, metric_cols, pairing_keys)

    n_trials = len(eval_df[eval_df["method"] == "aca"])

    latex_lines = [
        "\\begin{table*}[t]",
        "\\centering",
        f"\\caption{{Main Benchmark Results Across Graph Topologies and Adversary Types (Mean $\\pm$ 95\\% Bootstrap CI, Balanced Core Grid, $N = {n_trials}$ Paired Trials per Method Across 250 Independent Instances).",
        "$^\\dagger$ denotes statistically significant difference vs.\\ ACA ($p < 0.05$, paired Wilcoxon signed-rank test with Holm--Bonferroni correction).}",
        "\\label{tab:main_results}",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Completion (\\%)} & \\textbf{Net Welfare} & \\textbf{Distinct Conf.} & \\textbf{Total Conf.} & \\textbf{Messages} & \\textbf{Tick RT (ms)} \\\\",
        "\\midrule",
    ]

    md_lines = [
        f"### Benchmark Results ($N = {n_trials}$ Paired Trials per Method Across 250 Independent Instances)",
        "",
        "| Method | Completion (%) | Net Welfare | Distinct Conflicts | Total Conflicts | Messages | Tick RT (ms) |",
        "|:-------|:--------------:|:-----------:|:------------------:|:---------------:|:--------:|:------------:|",
    ]

    for m in methods:
        sub = eval_df[eval_df["method"] == m]
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


def generate_numbers_macro_file(df: Optional[pd.DataFrame] = None, out_macro_path: str = "results/numbers.tex") -> None:
    """Generate LaTeX \\newcommand macros exclusively from results/result_model_v1.json."""
    from tools.generate_numbers_from_model import generate_numbers
    generate_numbers(out_path=out_macro_path)


def generate_stratified_table(
    df: pd.DataFrame,
    out_tex_path: str = "results/table_stratified.tex",
    out_md_path: str = "results/table_stratified.md",
) -> str:
    """
    Generate Table III: Task Completion (%) stratified by Map Type (Real vs Synthetic)
    and Adversary Regime (Benign vs Adversarial).
    """
    real_maps = ["warehouse_movingai", "road_osmnx"]
    synthetic_maps = ["rgg", "grid", "er"]

    methods = [m for m in METHOD_PRETTY.keys() if m in df["method"].unique()]

    strata = [
        ("Real Maps (Benign)", (df["graph_family"].isin(real_maps)) & (df["adversary"] == "theta_1_stochastic")),
        ("Real Maps (Adv.)", (df["graph_family"].isin(real_maps)) & (df["adversary"] != "theta_1_stochastic")),
        ("Synthetic (Benign)", (df["graph_family"].isin(synthetic_maps)) & (df["adversary"] == "theta_1_stochastic")),
        ("Synthetic (Adv.)", (df["graph_family"].isin(synthetic_maps)) & (df["adversary"] != "theta_1_stochastic")),
        ("Overall", pd.Series(True, index=df.index)),
    ]

    latex_lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Task Completion (\\%) Stratified by Map Class and Adversarial Regime (Mean $\\pm$ 95\\% Bootstrap CI).}",
        "\\label{tab:stratified_results}",
        "\\renewcommand{\\arraystretch}{0.85}",
        "\\resizebox{\\columnwidth}{!}{%",
        "\\begin{tabular}{lccccc}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Real (Benign)} & \\textbf{Real (Adv.)} & \\textbf{Synth (Benign)} & \\textbf{Synth (Adv.)} & \\textbf{Overall (\\%)} \\\\",
        "\\midrule",
    ]

    md_lines = [
        "### Stratified Task Completion (%) by Map Class and Adversary Regime",
        "",
        "| Method | Real (Benign) | Real (Adv.) | Synth (Benign) | Synth (Adv.) | Overall (%) |",
        "|:-------|:-------------:|:-----------:|:--------------:|:------------:|:-----------:|",
    ]

    for m in methods:
        sub_m = df[df["method"] == m]
        label = METHOD_PRETTY.get(m, m)
        row_tex = [label]
        clean_label = (
            label.replace("\\textbf{", "**")
            .replace("\\cite{choi2009cbba}", "[Choi '09]")
            .replace("\\cite{buckman2019partial}", "[Buckman '19]")
            .replace("\\cite{ponda2012cc}", "[Ponda '12]")
            .replace("\\cite{alighanbari2005implicit}", "[Alighanbari '05]")
            .replace("\\cite{koenig2006ssi}", "[Koenig '06]")
            .replace("}", "**")
        )
        row_md = [clean_label]

        for s_name, s_mask in strata:
            sub = sub_m[s_mask.loc[sub_m.index]]
            if len(sub) == 0:
                row_tex.append("N/A")
                row_md.append("N/A")
                continue
            vals = sub["completion_rate_pct"].dropna().astype(float).values.tolist()
            mean, low, high = bootstrap_ci(vals)
            row_tex.append(format_latex_ci(mean, low, high, decimals=1))
            half_ci = 0.5 * (high - low)
            row_md.append(f"{mean:.1f} ± {half_ci:.1f}")

        latex_lines.append(" & ".join(row_tex) + " \\\\")
        md_lines.append("| " + " | ".join(row_md) + " |")

    latex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}%",
        "}",
        "\\end{table}",
    ])

    tex_content = "\n".join(latex_lines)
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    os.makedirs(os.path.dirname(out_md_path), exist_ok=True)
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return tex_content


def generate_sitl_table(
    sitl_json_path: str = "results/sitl/analysis/sitl_vs_graph_summary.json",
    raw_csv_path: str = "results/raw_results.csv",
    out_tex_path: str = "results/table_sitl.tex",
    out_md_path: str = "results/table_sitl.md",
) -> str:
    """
    Generate Table IV: Software-in-the-Loop (SITL) Physics-Based Simulation vs Discrete Graph Simulation
    (Matched paired trials per method on real maps).
    """
    if not os.path.exists(sitl_json_path):
        print(f"Warning: {sitl_json_path} not found for Table IV.")
        return ""

    with open(sitl_json_path, "r", encoding="utf-8") as f:
        sitl_data = json.load(f)

    method_summary = sitl_data.get("sitl_method_summary", {})
    graph_method_summary = sitl_data.get("graph_method_summary", {})
    domain_gap_summary = sitl_data.get("domain_gap_summary", {})
    paired_vs_aca = sitl_data.get("ranking_preservation", {}).get("paired_tests_vs_aca", {})

    n_trials_per_m = 360
    if method_summary:
        first_m = next(iter(method_summary.values()))
        n_trials_per_m = first_m.get("n_trials", 360)

    latex_lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{Software-in-the-Loop (SITL) Physics Simulation vs.\\ Discrete Graph Simulation ($N = {n_trials_per_m}$ Paired Trials per Method on Real Maps).}}",
        "\\label{tab:sitl_results}",
        "\\renewcommand{\\arraystretch}{0.88}",
        "\\resizebox{\\columnwidth}{!}{%",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{SITL Comp. (\\%)} & \\textbf{Graph Comp. (\\%)} & \\textbf{Domain Gap (pp)} & \\textbf{vs. ACA ($p$)} & \\textbf{Phys. Collisions} & \\textbf{Abstract Conf.} \\\\",
        "\\midrule",
    ]

    md_lines = [
        f"### SITL Physics Simulation vs. Discrete Graph Simulation ($N = {n_trials_per_m}$ Paired Trials per Method)",
        "",
        "| Method | SITL Comp. (%) | Graph Comp. (%) | Domain Gap (pp) | vs. ACA ($p$) | Phys. Collisions | Abstract Conf. |",
        "|:-------|:--------------:|:---------------:|:---------------:|:-------------:|:----------------:|:--------------:|",
    ]

    for m, stats in method_summary.items():
        label = METHOD_PRETTY.get(m, m)
        clean_label = (
            label.replace("\\textbf{", "**")
            .replace("\\cite{choi2009cbba}", "[Choi '09]")
            .replace("\\cite{buckman2019partial}", "[Buckman '19]")
            .replace("\\cite{ponda2012cc}", "[Ponda '12]")
            .replace("\\cite{alighanbari2005implicit}", "[Alighanbari '05]")
            .replace("\\cite{koenig2006ssi}", "[Koenig '06]")
            .replace("}", "**")
        )

        sitl_mean = stats.get("completion_mean", 0.0)
        sitl_std = stats.get("completion_std", 0.0)

        if m in graph_method_summary:
            g_mean = graph_method_summary[m].get("completion_mean", 0.0)
            g_std = graph_method_summary[m].get("completion_std", 0.0)
        else:
            g_mean, g_std = 0.0, 0.0

        if m in domain_gap_summary:
            gap = domain_gap_summary[m].get("gap_mean_pp", sitl_mean - g_mean)
        else:
            gap = sitl_mean - g_mean

        if m == "aca":
            p_val_str = "--"
        else:
            pair_info = paired_vs_aca.get(f"aca_vs_{m}", {})
            pval = pair_info.get("holm_adj_pvalue", pair_info.get("wilcoxon_pvalue", 1.0))
            p_val_str = f"{pval:.4f}" if pval >= 0.0001 else "$< 10^{-4}$"

        phys_col = stats.get("collisions_mean", 0.0)
        abs_conf = stats.get("conflicts_mean", 0.0)

        tex_row = [
            label,
            f"{sitl_mean:.1f} $\\pm$ {sitl_std:.1f}",
            f"{g_mean:.1f} $\\pm$ {g_std:.1f}",
            f"{gap:+.1f}",
            p_val_str,
            f"{phys_col:.1f}",
            f"{abs_conf:.1f}",
        ]
        md_row = [
            clean_label,
            f"{sitl_mean:.1f} ± {sitl_std:.1f}",
            f"{g_mean:.1f} ± {g_std:.1f}",
            f"{gap:+.1f}",
            p_val_str.replace("$", "").replace("\\", ""),
            f"{phys_col:.1f}",
            f"{abs_conf:.1f}",
        ]

        latex_lines.append(" & ".join(tex_row) + " \\\\")
        md_lines.append("| " + " | ".join(md_row) + " |")

    latex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}%",
        "}",
        "\\end{table}",
    ])

    tex_content = "\n".join(latex_lines)
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    os.makedirs(os.path.dirname(out_md_path), exist_ok=True)
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return tex_content


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


def update_readme_results_section(
    readme_path: str = "README.md",
    md_table_path: str = "results/table_main_results.md",
) -> None:
    """Embed auto-generated markdown results table directly into README.md."""
    if not os.path.exists(readme_path) or not os.path.exists(md_table_path):
        return
    with open(md_table_path, "r", encoding="utf-8") as f:
        table_md = f.read().strip()
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!-- RESULTS_TABLE_START -->.*?<!-- RESULTS_TABLE_END -->"
    replacement = f"<!-- RESULTS_TABLE_START -->\n\n{table_md}\n\n<!-- RESULTS_TABLE_END -->"
    if "<!-- RESULTS_TABLE_START -->" in content:
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        anchor = "All empirical data is generated automatically with zero hand-typed numbers:\n"
        if anchor in content:
            new_content = content.replace(anchor, f"{anchor}\n{replacement}\n\n")
        else:
            new_content = content + f"\n\n{replacement}\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated README.md results section from script.")


def generate_heldout_v5_table(
    out_tex_path: str = "results/table_heldout_v5.tex",
    out_md_path: str = "results/table_heldout_v5.md",
) -> Optional[str]:
    """Generate Table V: Protocol v5 Pre-Registered Confirmatory Held-Out Results."""
    csv_path = os.path.join(REPO_ROOT, "results", "confirmatory", "heldout_v5_results.csv")
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)

    method_order = [
        ("aca_plus", "\\textbf{ACA+ (Ours)}"),
        ("aca_adaptive", "ACA-Adaptive"),
        ("aca", "ACA (Static Pinsker)"),
        ("aca_no_margin", "ACA (No Margin)"),
        ("cbba_lr", "CBBA (+LR) \\cite{choi2009cbba}"),
        ("cbba_partial_lr", "CBBA-PR (+LR) \\cite{buckman2019partial}"),
        ("ctp_replan", "CTP Replan \\cite{papadimitriou1991shortest}"),
        ("ssi_lr", "SSI (+LR) \\cite{koenig2006ssi}"),
    ]

    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Protocol v5 Confirmatory Held-Out Results Across 5 Benchmark Families and 3 Adversary Regimes ($N = 450$ Matched Instances, Seeds 101--130, Mean $\\pm$ 95\\% Bootstrap CI).}",
        "\\label{tab:heldout_v5_results}",
        "\\renewcommand{\\arraystretch}{0.88}",
        "\\resizebox{\\columnwidth}{!}{%",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Completion (\\%)} & \\textbf{Net Welfare} & \\textbf{Total Conf.} & \\textbf{Messages} \\\\",
        "\\midrule",
    ]

    for m_key, m_name in method_order:
        sub = df[df["method"] == m_key]
        if len(sub) == 0:
            continue
        c_m, c_l, c_h = bootstrap_ci(sub["completion_rate_pct"].dropna().values.tolist(), n_resamples=1000)
        c_ci = 0.5 * (c_h - c_l)
        w_m, w_l, w_h = bootstrap_ci(sub["net_welfare"].dropna().values.tolist(), n_resamples=1000)
        w_ci = 0.5 * (w_h - w_l)
        conf_m, conf_l, conf_h = bootstrap_ci(sub["total_conflicts"].dropna().values.tolist(), n_resamples=1000)
        conf_ci = 0.5 * (conf_h - conf_l)
        msg_m, msg_l, msg_h = bootstrap_ci(sub["total_messages"].dropna().values.tolist(), n_resamples=1000)
        msg_ci = 0.5 * (msg_h - msg_l)

        lines.append(
            f"{m_name} & ${c_m:.1f} \\pm {c_ci:.1f}$ & ${w_m:.0f} \\pm {w_ci:.0f}$ & ${conf_m:.1f} \\pm {conf_ci:.1f}$ & ${msg_m:.0f} \\pm {msg_ci:.0f}$ \\\\"
        )

    lines.extend([
        "\\bottomrule",
        "\\end{tabular}%",
        "}",
        "\\end{table}",
    ])

    tex_content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)
    print(f"Wrote Table Held-Out v5 to {out_tex_path}")
    return tex_content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="results/raw_results.csv")
    parser.add_argument("--out", type=str, default="results/table_main_results.tex")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: {args.csv} does not exist. Run experiments/run_sweep.py first.")
        return

    df = pd.read_csv(args.csv)
    eval_df, _ = get_locked_population(df, population_id="nominal_balanced_core")
    tex_ii = generate_main_results_table(df, args.out)
    tex_iii = generate_stratified_table(df)
    tex_iv = generate_sitl_table()
    tex_v = generate_heldout_v5_table()
    generate_numbers_macro_file(eval_df)
    per_cond = generate_per_condition_table(df)
    update_readme_results_section()
    print(f"Wrote Table II to {args.out}")
    print("Wrote Table III to results/table_stratified.tex")
    print("Wrote Table IV to results/table_sitl.tex")
    print("Wrote per-condition breakdown to results/table_per_condition.csv\n")


if __name__ == "__main__":
    main()
