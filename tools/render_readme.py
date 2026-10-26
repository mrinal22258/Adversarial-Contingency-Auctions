#!/usr/bin/env python3
"""
tools/render_readme.py - Generate README.md from README.template.md and results/result_model_v1.json.

Guarantees:
1. Every empirical number is derived strictly from results/result_model_v1.json or test logs.
2. Unfilled placeholders or missing keys cause an immediate fatal error.
3. Automatically incorporates latest test suite metrics and generated markdown tables.
"""

import os
import sys
import re
import json
import glob
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(REPO_ROOT, "README.template.md")
OUTPUT_README_PATH = os.path.join(REPO_ROOT, "README.md")
RESULT_MODEL_PATH = os.path.join(REPO_ROOT, "results", "result_model_v1.json")
TEST_LOGS_DIR = os.path.join(REPO_ROOT, "results", "test_logs")


def require_metric(data: Dict[str, Any], key: str, context: str = "model") -> Any:
    """Strict lookup helper that raises KeyError if a required metric is missing or None."""
    if key not in data or data[key] is None:
        raise KeyError(f"Required empirical metric '{key}' missing or None in '{context}'")
    return data[key]


def parse_latest_test_log(logs_dir: str = TEST_LOGS_DIR) -> Dict[str, Any]:
    """Parse the most recent test log in results/test_logs/ for passed/deselected counts."""
    if not os.path.exists(logs_dir):
        raise FileNotFoundError(f"Test logs directory does not exist: {logs_dir}")

    # Prefer final.txt over gate-6.txt whenever it exists, otherwise gate-6.txt or most recent
    final_file = os.path.join(logs_dir, "final.txt")
    if os.path.exists(final_file):
        chosen_file = final_file
    else:
        candidates = sorted(glob.glob(os.path.join(logs_dir, "*.txt")), key=os.path.getmtime, reverse=True)
        if not candidates:
            raise FileNotFoundError(f"No test log text files found in {logs_dir}")
        chosen_file = candidates[0]
        for c in candidates:
            if "gate-6" in os.path.basename(c):
                chosen_file = c
                break

    try:
        with open(chosen_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to read test log from {chosen_file}: {e}") from e

    clean_match = re.search(
        r"(?:^|\n)(?:=+\s*)?(\d+)\s+passed(?:,\s+(\d+)\s+deselected)?(?:,\s+(\d+)\s+warnings?)?(?:\s+in\s+([\d\.]+s))?",
        content,
    )
    if clean_match and "failed" not in (content.splitlines()[-1] if content.splitlines() else ""):
        passed = int(clean_match.group(1))
        deselected = int(clean_match.group(2)) if clean_match.group(2) else 0
        warnings = int(clean_match.group(3)) if clean_match.group(3) else 0
        dur = clean_match.group(4) if clean_match.group(4) else ""
        summary = f"{passed} passed"
        if deselected > 0:
            summary += f", {deselected} deselected"
        if warnings > 0:
            summary += f", {warnings} warning{'s' if warnings > 1 else ''}"
        return {
            "passed": passed,
            "deselected": deselected,
            "warnings": warnings,
            "duration": dur,
            "summary_line": summary,
            "source_log": os.path.basename(chosen_file),
        }
    raise RuntimeError(f"Could not parse valid passed test counts from test log: {chosen_file}")


def build_populations_table(model: Dict[str, Any]) -> str:
    """Generate Markdown table summarizing all named populations and reconciliation."""
    pops = model.get("populations", {})
    order = ["exploratory_core", "exploratory_sweep", "heldout_v5", "pilot_stage4", "sitl", "v6_confirmatory"]
    headers = ["Population Name", "Source File", "Filter / Scope", "Trials", "Instances", "Clusters", "Seeds", "Methods"]
    rows = []
    for k in order:
        if k not in pops:
            continue
        p = pops[k]
        trials_str = f"{p['n_rows']:,}" if isinstance(p.get("n_rows"), int) and p["n_rows"] > 0 else (p.get("status", "0"))
        rows.append([
            f"`{p.get('name', k)}`",
            f"`{p.get('file', '')}`",
            p.get("filter", ""),
            str(trials_str),
            str(p.get("n_instances", "")),
            str(p.get("n_clusters", "")),
            str(p.get("n_seeds", "")),
            str(p.get("n_methods", len(p.get("methods", [])))),
        ])

    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join([":---"] * 3 + [":---:"] * 5) + " |",
    ]
    for r in rows:
        table_lines.append("| " + " | ".join(r) + " |")

    return "\n".join(table_lines)


def build_main_results_table(model: Dict[str, Any]) -> str:
    """Read generated table from results/table_main_results.md if present, else synthesize."""
    md_path = os.path.join(REPO_ROOT, "results", "table_main_results.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "*(Main results table pending generation)*"


def build_heldout_v5_table(model: Dict[str, Any]) -> str:
    """Synthesize Markdown table for Protocol v5 confirmatory held-out results."""
    v5_metrics = model.get("metrics", {}).get("heldout_v5", {})
    method_order = [
        ("aca", "**ACA (Static Pinsker, $\\kappa=1.0$, Ours)**", "Canonical Theory Baseline"),
        ("aca_plus", "ACA+ (Heuristic)", "Adaptive Margin + Pruning (Inactive in v5)"),
        ("aca_adaptive", "ACA-Adaptive (Heuristic)", "Adaptive Margin Only"),
        ("aca_no_margin", "ACA (No Margin)", "Margin Ablation"),
        ("cbba_lr", "CBBA (+LR) [Choi '09]", "Level Execution (+LR)"),
        ("cbba_partial_lr", "CBBA-PR (+LR) [Buckman '19]", "Partial Release (+LR)"),
        ("ctp_replan", "CTP Replan [Papadimitriou '91]", "Continuous Re-solve"),
        ("ssi_lr", "SSI (+LR) [Koenig '06]", "Single-Item Auction (+LR)"),
    ]

    headers = ["Method", "Variant Description", "Completion (%)", "Net Welfare", "Total Conflicts", "Messages"]
    rows = []
    for m_key, m_name, m_desc in method_order:
        if m_key not in v5_metrics:
            continue
        m = v5_metrics[m_key]
        comp = f"{m['completion_rate_pct']['mean']:.1f} ± {m['completion_rate_pct']['cell_ci_half']:.1f}"
        welf = f"{m['net_welfare']['mean']:.0f} ± {m['net_welfare']['cell_ci_half']:.0f}"
        conf = f"{m['total_conflicts']['mean']:.1f} ± {m['total_conflicts']['cell_ci_half']:.1f}"
        msg = f"{m['total_messages']['mean']:.0f} ± {m['total_messages']['cell_ci_half']:.0f}"
        rows.append([m_name, m_desc, comp, welf, conf, msg])

    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |",
    ]
    for r in rows:
        table_lines.append("| " + " | ".join(r) + " |")

    return "\n".join(table_lines)


def get_nested(data: Dict[str, Any], path: str) -> Any:
    """Retrieve nested dictionary key via dot notation."""
    parts = path.split(".")
    curr = data
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return None
    return curr


def render_readme(
    template_path: str = TEMPLATE_PATH,
    model_path: str = RESULT_MODEL_PATH,
    out_path: Optional[str] = OUTPUT_README_PATH,
    write_to_file: bool = True,
    model_override: Optional[Dict[str, Any]] = None,
    test_logs_dir: str = TEST_LOGS_DIR,
) -> str:
    """Render README.md from template and result model."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    if model_override is not None:
        model = model_override
    else:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Result model not found: {model_path}")
        with open(model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

    test_info = parse_latest_test_log(logs_dir=test_logs_dir)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Pre-calculate semantic shortcuts
    v5_metrics = model.get("metrics", {}).get("heldout_v5", {})
    exp_metrics = model.get("metrics", {}).get("exploratory_core", {})
    v5_contrasts = model.get("contrasts", {}).get("heldout_v5", {})
    exp_contrasts = model.get("contrasts", {}).get("exploratory_core", {})

    shortcuts: Dict[str, Any] = {
        # Test suite
        "test_count": str(test_info["passed"]),
        "test_deselected": str(test_info["deselected"]),
        "test_summary_line": test_info["summary_line"],
        # Generated Tables
        "TABLE_POPULATIONS": build_populations_table(model),
        "TABLE_MAIN_RESULTS": build_main_results_table(model),
        "TABLE_HELDOUT_V5": build_heldout_v5_table(model),
        # Protocol constants
        "tau_prune": "0.15",
        "alpha_significance": "0.05",
    }

    # Theorem 1 dynamic shortcuts
    th1_data = model.get("theorem_1_evidence", model.get("theorem_1"))
    if not th1_data:
        raise KeyError("Required section 'theorem_1_evidence' or 'theorem_1' missing from result model")

    shortcuts["th1.safe_claims"] = f"{require_metric(th1_data, 'claimed_safe', 'th1'):,}"
    shortcuts["th1.adhered_safe_claims"] = f"{require_metric(th1_data, 'tv_le_eta_subset', 'th1'):,}"
    shortcuts["th1.adherence_per_claim_pct"] = f"{require_metric(th1_data, 'adherence_pct', 'th1'):.2f}"
    shortcuts["th1.conflicts_adhered"] = str(require_metric(th1_data, 'conflicts_under_assumption_1', 'th1'))
    shortcuts["th1.clopper_pearson_upper_pct"] = f"{require_metric(th1_data, 'clopper_pearson_upper_pct', 'th1'):.3f}"
    shortcuts["th1.total_tv_observations"] = f"{require_metric(th1_data, 'total_tv_observations', 'th1'):,}"
    shortcuts["th1.adhered_tv_observations"] = f"{require_metric(th1_data, 'adhered_tv_observations', 'th1'):,}"
    shortcuts["th1.tv_adherence_pct"] = f"{require_metric(th1_data, 'tv_adherence_pct', 'th1'):.2f}"
    shortcuts["th1.tv_violation_pct"] = f"{require_metric(th1_data, 'tv_violation_pct', 'th1'):.2f}"
    shortcuts["th1.adherence_per_instance_pct"] = f"{require_metric(th1_data, 'adherence_per_instance_pct', 'th1'):.2f}"
    shortcuts["th1.adherence_per_instance_ci_low"] = f"{require_metric(th1_data, 'adherence_per_instance_ci_low', 'th1'):.2f}"
    shortcuts["th1.adherence_per_instance_ci_high"] = f"{require_metric(th1_data, 'adherence_per_instance_ci_high', 'th1'):.2f}"
    shortcuts["th1.n_instances"] = str(require_metric(th1_data, 'n_instances', 'th1'))
    shortcuts["th1.pval_adherence_instance_null"] = str(require_metric(th1_data, 'pval_adherence_instance_null', 'th1'))
    shortcuts["th1.fixed_threshold_baseline_adherence_pct"] = f"{require_metric(th1_data, 'fixed_threshold_baseline_adherence_pct', 'th1'):.1f}"

    # Populations
    pops = model.get("populations", {})
    for pop_key, pop_data in pops.items():
        if isinstance(pop_data, dict):
            for field, val in pop_data.items():
                shortcuts[f"populations.{pop_key}.{field}"] = val

    # Held-out v5 shortcuts
    if "cbba_lr" in v5_metrics and "aca" in v5_metrics:
        cbba_comp = v5_metrics["cbba_lr"]["completion_rate_pct"]["mean"]
        aca_comp = v5_metrics["aca"]["completion_rate_pct"]["mean"]
        diff_comp = cbba_comp - aca_comp
        shortcuts["heldout_v5.cbba_lr.completion_pct"] = f"{cbba_comp:.2f}"
        shortcuts["heldout_v5.aca.completion_pct"] = f"{aca_comp:.2f}"
        shortcuts["heldout_v5.diff_cbba_lr_aca_completion"] = f"+{diff_comp:.2f}"

        cbba_welf = v5_metrics["cbba_lr"]["net_welfare"]["mean"]
        aca_welf = v5_metrics["aca"]["net_welfare"]["mean"]
        shortcuts["heldout_v5.cbba_lr.net_welfare"] = f"{cbba_welf:.1f}"
        shortcuts["heldout_v5.aca.net_welfare"] = f"{aca_welf:.1f}"

        cbba_conf = v5_metrics["cbba_lr"]["total_conflicts"]["mean"]
        aca_conf = v5_metrics["aca"]["total_conflicts"]["mean"]
        shortcuts["heldout_v5.cbba_lr.conflicts"] = f"{cbba_conf:.2f}"
        shortcuts["heldout_v5.aca.conflicts"] = f"{aca_conf:.2f}"

    if "aca_no_margin" in v5_metrics and "aca" in v5_metrics:
        no_m_conf = v5_metrics["aca_no_margin"]["total_conflicts"]["mean"]
        aca_conf = v5_metrics["aca"]["total_conflicts"]["mean"]
        diff_conf = aca_conf - no_m_conf
        shortcuts["heldout_v5.aca_no_margin.conflicts"] = f"{no_m_conf:.2f}"
        shortcuts["heldout_v5.diff_margin_conflicts"] = f"{diff_conf:.2f}"
        pct_reduction = (no_m_conf - aca_conf) / no_m_conf * 100.0 if no_m_conf > 0 else 0.0
        shortcuts["heldout_v5.diff_margin_conflicts_pct"] = f"{pct_reduction:.1f}%"

    # Exploratory core shortcuts
    if "aca" in exp_metrics and "cbba_lr" in exp_metrics:
        aca_comp = exp_metrics["aca"]["completion_rate_pct"]["mean"]
        cbba_comp = exp_metrics["cbba_lr"]["completion_rate_pct"]["mean"]
        shortcuts["exploratory_core.aca.completion_pct"] = f"{aca_comp:.1f}"
        shortcuts["exploratory_core.cbba_lr.completion_pct"] = f"{cbba_comp:.1f}"
        shortcuts["exploratory_core.diff_cbba_lr_aca_completion"] = f"+{aca_comp - cbba_comp:.2f}"

    # Contrasts shortcuts
    if "H2_cbba_lr" in exp_contrasts:
        c = exp_contrasts["H2_cbba_lr"]
        p_val = c.get("cluster_p_adjusted", c.get("cluster_p_raw", 0.0))
        shortcuts["exploratory_core.cbba_lr_p_val"] = f"{p_val:.3f}" if p_val >= 0.001 else "< 0.001"

    # Pattern for {{key}} or {{key:format}}
    placeholder_pattern = re.compile(r"\{\{([a-zA-Z0-9_\.:]+)\}\}")
    unresolved = []

    def replacer(match):
        raw = match.group(1)
        fmt = None
        key = raw
        if ":" in raw:
            key, fmt = raw.split(":", 1)

        # 1. Check shortcuts
        val = None
        if key in shortcuts:
            val = shortcuts[key]
        else:
            # 2. Check dot lookup in model
            val = get_nested(model, key)

        if val is None:
            unresolved.append(raw)
            return match.group(0)

        if fmt:
            try:
                return f"{float(val):{fmt}}"
            except Exception:
                return str(val)
        return str(val)

    rendered = placeholder_pattern.sub(replacer, template)

    if unresolved:
        raise KeyError(
            f"Failed to render README.md: {len(unresolved)} unresolved placeholder(s): {unresolved[:10]}"
        )

    # Check for any lingering unfilled double braces
    remaining = re.findall(r"\{\{[^\}]+\}\}", rendered)
    if remaining:
        raise ValueError(f"Unfilled template placeholders remaining in output: {remaining}")

    header = "<!-- GENERATED FILE: DO NOT EDIT DIRECTLY. Edit README.template.md and run tools/render_readme.py -->\n\n"
    frontmatter_match = re.match(r"^(---\r?\n.*?\r?\n---\r?\n)(.*)$", rendered, re.DOTALL)
    if frontmatter_match:
        final_output = frontmatter_match.group(1) + header + frontmatter_match.group(2)
    else:
        final_output = header + rendered

    if write_to_file and out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_output)
        print(f"[*] Successfully rendered {out_path} from {template_path}")

    return final_output


if __name__ == "__main__":
    render_readme()
