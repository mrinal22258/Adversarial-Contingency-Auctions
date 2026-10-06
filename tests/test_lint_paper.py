"""
Unit tests for tools/lint_paper.py linter (Phase G.4).
Verifies that:
1. Hard-coded numbers (+13.0, 0.41, 1200, p=0.88) are flagged.
2. Forbidden hype phrases ('Extensive', 'Theoretical Bound') are flagged.
3. Clean LaTeX with macros and provenance files passes.
"""

import pytest
from tools.lint_paper import check_hardcoded_numbers, check_figure_provenance


def test_linter_detects_forbidden_numbers_and_phrases():
    dirty_tex = r"""
    \begin{abstract}
    Extensive experiments demonstrate +13.0 pp gain over CBBA across 1200 total runs.
    We compare against a Theoretical Bound oracle with p = 0.88 and Cliff's delta = 0.41.
    Approximately 3% safe claims are achieved with 34 messages.
    \end{abstract}
    """
    errors = check_hardcoded_numbers(dirty_tex)
    assert len(errors) >= 5
    assert any("13.0" in e for e in errors)
    assert any("Extensive" in e for e in errors)
    assert any("Theoretical Bound" in e for e in errors)
    assert any("1200" in e for e in errors)


def test_linter_passes_on_clean_macroized_tex():
    clean_tex = r"""
    \begin{abstract}
    Rigorous paired empirical evaluations across controlled communication regimes
    demonstrate \aeGainOverCbba{} percentage points gain over CBBA across \aeTotalTrials{} trials.
    We compare against a Clairvoyant Greedy baseline.
    Phase 1 safe claims achieve \aeSafeClaimRate{} with \aeAcaMsgs{} messages.
    \end{abstract}
    """
    errors = check_hardcoded_numbers(clean_tex)
    assert len(errors) == 0, f"Unexpected errors on clean tex: {errors}"
