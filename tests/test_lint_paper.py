"""
Unit tests for tools/lint_paper.py (Step 0.4).
Verifies that the linter strictly catches:
- 'strictly 0' claims
- 'Theoretical bound' claims
- Unsubstantiated 'hardware' / 'Gazebo' claims
- Unsubstantiated 'MovingAI' / 'OSMnx' claims without real data
- Literal numbers in results sections outside macros
"""

import os
import pytest
from tools.lint_paper import (
    check_strict_claims,
    check_unmacroed_literal_numbers,
    check_figure_provenance,
    check_staleness,
    lint_paper,
)


BAD_PAPER_TEX = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
We evaluate our method on real hardware in Gazebo and real DDS middleware.
Our algorithm guarantees strictly 0 conflicts in Phase 1.
We compare against the theoretical bound provided by the Oracle.

\section{Experimental Evaluation}
Our algorithm achieved 88.4\% completion rate compared to 79.8\% for CBBA.
The p-value was statistically significant with p = 0.0012.
A total of 17100 trials were conducted.

\includegraphics{static/images/missing_figure.pdf}

\end{document}
"""

CLEAN_SNIPPET = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
We evaluate our multi-robot auction mechanism in simulated environments.
Safe-claim conflicts are strictly bounded under Assumption 1.
We compare against Clairvoyant greedy (reference, not a bound).
We note that physical hardware validation remains future work.

\section{Experimental Evaluation}
Our algorithm achieved \aeAcaCompletion\% completion rate.
The difference was statistically significant (\aePVal).
A total of \aeTotalTrials\ trials were conducted.

\end{document}
"""


def test_linter_catches_bad_claims():
    """Verify that linter catches all prohibited claims on a deliberately bad paper."""
    errors = check_strict_claims(BAD_PAPER_TEX)
    
    # Must catch strictly 0
    assert any("strictly 0" in e.lower() for e in errors), "Must catch 'strictly 0' claim"
    
    # Must catch Theoretical bound
    assert any("theoretical bound" in e.lower() for e in errors), "Must catch 'Theoretical bound' claim"
    
    # Must catch Gazebo
    assert any("gazebo" in e.lower() for e in errors), "Must catch 'Gazebo' claim"

    # Must catch hardware without physical data
    assert any("hardware" in e.lower() for e in errors), "Must catch 'hardware' claim"


def test_linter_catches_literal_numbers():
    """Verify that linter catches unmacroed numbers in results section."""
    errors = check_unmacroed_literal_numbers(BAD_PAPER_TEX)
    
    # Must catch 88.4% or 79.8%
    assert any("88.4" in e or "79.8" in e for e in errors), "Must catch literal percentage numbers"
    
    # Must catch p = 0.0012
    assert any("p-value" in e.lower() or "0.0012" in e for e in errors), "Must catch literal p-value"


def test_linter_catches_missing_figure_provenance():
    """Verify that linter catches figures missing .provenance.json sidecar."""
    errors = check_figure_provenance(BAD_PAPER_TEX, base_dir=".")
    assert any("missing_figure" in e for e in errors), "Must catch missing figure provenance"


def test_clean_snippet_passes():
    """Verify that clean text adhering to all rules produces zero errors."""
    claim_errors = check_strict_claims(CLEAN_SNIPPET)
    num_errors = check_unmacroed_literal_numbers(CLEAN_SNIPPET)
    assert len(claim_errors) == 0, f"Unexpected claim errors: {claim_errors}"
    assert len(num_errors) == 0, f"Unexpected number errors: {num_errors}"


def test_linter_catches_staleness():
    """Verify that linter catches staleness issues (e.g. outdated map node sizes in raw_results)."""
    # BAD_PAPER_TEX with mismatched node citation
    tex_bad_sizes = r"MovingAI ($n = 999$) and Boston ($n = 999$)"
    errors = check_staleness(tex_bad_sizes)
    # The current repo state has stale commit or stale node counts from previous run
    assert len(errors) > 0, "check_staleness must report violations on stale data or mismatched map citations"


def test_linter_fails_on_deliberately_typed_number_paper_including_abstract():
    """
    Verify that the linter strictly fails on a deliberately typed-number paper
    with violations across abstract, body text, captions, and tables (Rule R1, STEP 2).
    """
    dirty_paper = r"""
\documentclass{article}
\begin{document}

\begin{abstract}
Our method achieves a +1.90 percentage point lead and 0 conflicts across 32 seeds.
\end{abstract}

\section{Introduction}
We evaluate navigation across 38 nodes with 10 robots.

\section{Results}
Our algorithm achieved 88.4\% completion across 1,466,999 observations.

\begin{figure}
\caption{Benchmark results over 32 seeds showing 0 conflicts.}
\end{figure}

\begin{table}
\caption{Quantitative ablation metrics across 50 trials.}
45.2 & 12.3 \\
\end{table}

\end{document}
"""
    errors = check_unmacroed_literal_numbers(dirty_paper)
    assert len(errors) >= 5, f"Expected multiple number violations, got: {errors}"
    
    # Check abstract violations
    assert any("+1.90" in e or "1.90" in e for e in errors), "Must catch '+1.90' in abstract"
    assert any("32" in e for e in errors), "Must catch '32' in abstract/captions"
    assert any("0" in e for e in errors), "Must catch '0' in abstract/captions"
    
    # Check body violations
    assert any("38" in e for e in errors), "Must catch '38' map nodes in body"
    assert any("88.4" in e for e in errors), "Must catch '88.4' percentage in body"
    assert any("1,466,999" in e or "1466999" in e for e in errors), "Must catch '1,466,999' in body"
    
    # Check table / caption violations
    assert any("45.2" in e for e in errors), "Must catch '45.2' in table"
    assert any("12.3" in e for e in errors), "Must catch '12.3' in table"
    assert any("50" in e for e in errors), "Must catch '50' trials in caption"


def test_clean_paper_tex_has_zero_unmacroed_numbers():
    """Verify that actual paper.tex in repository contains 0 unmacroed literal numbers."""
    paper_tex_path = os.path.join(os.path.dirname(__file__), "..", "paper.tex")
    if os.path.exists(paper_tex_path):
        with open(paper_tex_path, "r", encoding="utf-8") as f:
            content = f.read()
        errors = check_unmacroed_literal_numbers(content)
        assert len(errors) == 0, f"paper.tex has unmacroed literal numbers: {errors}"


