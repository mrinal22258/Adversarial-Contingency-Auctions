"""
Test ensuring zero hardcoded numeric literals in narrative templates of RESULTS_VERDICT.md generator.
Verifies that all statistics in generated narrative reports are purely derived from the data.
"""

import ast
import inspect
import re
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from experiments.run_statistical_tests import (
    generate_verdict_markdown,
)


def test_zero_numeric_literals_in_narrative_templates():
    """
    AST inspection of generate_verdict_markdown to ensure narrative template strings
    contain zero hardcoded empirical numbers.
    """
    from experiments import run_statistical_tests

    func_source = inspect.getsource(run_statistical_tests.generate_verdict_markdown)
    tree = ast.parse(func_source)

    # Disallowed statistical empirical numbers that were previously hardcoded in narrative templates
    stale_empirical_numbers = [
        "11,000",
        "0.0463",
        "0.208",
        "+0.19",
        "89.85",
        "89.66",
        "88.42",
        "88.37",
        "87.15",
        "87.03",
        "6,059",
        "85,619",
        "60,263",
        "42,532",
        "277,424",
        "86.71",
        "88.97",
        "90.28",
        "1,972",
        "2,000",
        "98.60",
        "97.99",
        "99.07",
    ]

    for num_str in stale_empirical_numbers:
        assert num_str not in func_source, (
            f"Found hardcoded empirical number '{num_str}' in generate_verdict_markdown source!"
        )

    # Inspect all raw string literals in the AST
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            # Check if this string looks like a narrative sentence containing numbers
            # Disallow hardcoded percentages like '98.6%' or counts like '42 tasks'
            # Allowed: section titles ('1.', '2.', '3.'), hypothesis IDs ('H1', 'H8'), confidence level '95%'
            disallowed_patterns = [
                r"\b\d+\.\d+%\b",               # Hardcoded percentage like 89.85%
                r"\b\d+,\d+\b",                 # Hardcoded comma formatted integer like 11,000
                r"\b\d+\.\d+\s*pp\b",           # Hardcoded percentage points like 0.19 pp
                r"\b\d+\s+total safe-claim\b",   # Hardcoded conflict counts
                r"\b\d+\s+safe conflicts\b",     # Hardcoded conflict counts
                r"\b\d+\s+tasks\b",             # Hardcoded task counts
            ]
            for pat in disallowed_patterns:
                match = re.search(pat, val)
                assert match is None, (
                    f"Found hardcoded empirical literal pattern '{match.group(0)}' in string constant: '{val}'"
                )


def test_narrative_generates_dynamically_from_input_data(tmp_path):
    """
    Verify that varying the input dataframe dynamically updates every figure in the generated report.
    """
    out_file_1 = tmp_path / "verdict_1.md"
    out_file_2 = tmp_path / "verdict_2.md"

    # Minimal mock res_df
    res_df = pd.DataFrame([
        {
            "hypothesis_id": "H1",
            "title": "Recourse Efficacy (ACA vs ACA-d0)",
            "metric": "completion_rate_pct",
            "mean_diff": 5.00,
            "hl_median_diff": 4.50,
            "hl_ci_95": "[3.0, 6.0]",
            "cliffs_delta": 0.300,
            "raw_p_value": 0.0001,
            "adj_p_value": 0.0001,
            "bonferroni_p_value": 0.0001,
            "direction": "greater",
            "significant": True,
            "n_instances": 100,
        },
        {
            "hypothesis_id": "H2",
            "title": "Level Execution (ACA vs cbba_partial_lr)",
            "metric": "completion_rate_pct",
            "mean_diff": 1.25,
            "hl_median_diff": 1.00,
            "hl_ci_95": "[0.2, 1.8]",
            "cliffs_delta": 0.100,
            "raw_p_value": 0.02,
            "adj_p_value": 0.04,
            "bonferroni_p_value": 0.08,
            "direction": "two_sided",
            "significant": True,
            "n_instances": 100,
        },
        {
            "hypothesis_id": "H4",
            "title": "Pinsker Margin Safe Conflict Reduction",
            "metric": "safe_claim_conflicts",
            "mean_diff": -3.00,
            "hl_median_diff": -3.00,
            "hl_ci_95": "[-4.0, -2.0]",
            "cliffs_delta": -0.800,
            "raw_p_value": 1e-10,
            "adj_p_value": 1e-10,
            "direction": "less",
            "significant": True,
            "n_instances": 100,
        },
        {
            "hypothesis_id": "H4_COMPLETION",
            "title": "Pinsker Margin Completion Equivalence (TOST 5pp)",
            "metric": "completion_rate_pct",
            "mean_diff": -0.20,
            "hl_median_diff": -0.20,
            "hl_ci_95": "[-1.0, 0.5]",
            "cliffs_delta": -0.05,
            "raw_p_value": 1e-5,
            "direction": "non_inferiority",
            "significant": True,
            "n_instances": 100,
        },
        {
            "hypothesis_id": "H7",
            "title": "Assumption 1 Empirical TV Adherence",
            "metric": "tv_bound_adherence_rate",
            "mean_aca": 0.75,
            "mean_diff": -0.15,
            "hl_median_diff": 0.75,
            "hl_ci_95": "[0.70, 0.80]",
            "cliffs_delta": 0.0,
            "raw_p_value": 1.0,
            "direction": "greater_or_equal",
            "significant": False,
            "n_instances": 100,
        },
    ])

    # Dataset 1: 50 trials
    raw_df_1 = pd.DataFrame({
        "graph_family": ["rgg"] * 50,
        "seed": list(range(1, 51)),
        "method": ["aca"] * 25 + ["cbba_partial_lr"] * 15 + ["aca_no_margin"] * 10,
        "comm_regime": ["nominal"] * 50,
        "comm_range": [30.0] * 50,
        "p_drop": [0.10] * 50,
        "completion_rate_pct": [85.0] * 50,
        "safe_claim_conflicts": [0] * 50,
        "safe_claims": [10] * 50,
        "total_conflicts": [5] * 50,
        "deferred_claims": [20] * 50,
        "total_claims": [30] * 50,
    })

    # Dataset 2: 120 trials with different values
    raw_df_2 = pd.DataFrame({
        "graph_family": ["warehouse_movingai"] * 120,
        "seed": list(range(1, 121)),
        "method": ["aca"] * 60 + ["cbba_partial_lr"] * 30 + ["aca_no_margin"] * 30,
        "comm_regime": ["nominal"] * 120,
        "comm_range": [30.0] * 120,
        "p_drop": [0.10] * 120,
        "completion_rate_pct": [92.0] * 120,
        "safe_claim_conflicts": [1] * 120,
        "safe_claims": [50] * 120,
        "total_conflicts": [10] * 120,
        "deferred_claims": [5] * 120,
        "total_claims": [55] * 120,
    })

    generate_verdict_markdown(res_df, output_path=str(out_file_1), raw_df=raw_df_1)
    generate_verdict_markdown(res_df, output_path=str(out_file_2), raw_df=raw_df_2)

    content_1 = out_file_1.read_text(encoding="utf-8")
    content_2 = out_file_2.read_text(encoding="utf-8")

    # The two contents must reflect their distinct inputs
    assert "N = 50 executed trials" in content_1
    assert "N = 120 executed trials" in content_2
    assert "ACA 85.00%" in content_1
    assert "ACA 92.00%" in content_2
