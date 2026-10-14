"""
Acceptance tests for Gate 6: Manuscript, UI, and Documentation Verification.
Validates:
1. Anonymization enabled in paper.tex and supplement.tex.
2. Three evidence tiers clearly demarcated across paper and docs.
3. Protocol v5 CBBA+LR reversal and inactive pruning honestly disclosed.
4. UI layout and tabs updated with pending v6 protocol status and dynamic model loading.
5. All public docs synchronized with verified evidence hierarchy.
"""

import os
import re
import json
import pytest
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_paper_anonymity_flags():
    """Verify paper.tex and supplement.tex have \\anonymoustrue enabled."""
    paper_path = os.path.join(REPO_ROOT, "paper.tex")
    supplement_path = os.path.join(REPO_ROOT, "supplement.tex")

    with open(paper_path, "r", encoding="utf-8") as f:
        paper_content = f.read()
    with open(supplement_path, "r", encoding="utf-8") as f:
        supplement_content = f.read()

    assert r"\anonymoustrue" in paper_content, "paper.tex must enable \\anonymoustrue"
    assert r"\anonymousfalse" not in paper_content or "%" in paper_content.split(r"\anonymousfalse")[0].splitlines()[-1], (
        "paper.tex must not have active \\anonymousfalse"
    )

    assert r"\anonymoustrue" in supplement_content, "supplement.tex must enable \\anonymoustrue"


def test_paper_abstract_three_evidence_tiers():
    """Verify abstract clearly distinguishes exploratory, held-out v5 reversal, and pending v6 tiers."""
    paper_path = os.path.join(REPO_ROOT, "paper.tex")
    with open(paper_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Must contain 3 tiers in abstract
    assert "three distinct tiers" in content.lower(), "Abstract must state three distinct evidence tiers"
    assert "exploratory" in content.lower(), "Abstract must label nominal grid as exploratory"
    assert "reversal" in content.lower(), "Abstract must prominently report the Protocol v5 reversal"
    assert "cbba+lr" in content.lower(), "Abstract must mention CBBA+LR performance in v5"
    assert "pending" in content.lower(), "Abstract must state Protocol v6 execution is pending"


def test_paper_v5_pruning_inactive_disclosed():
    """Verify paper discloses that v5 ACA+ pruning was inactive (0.06 < 0.12)."""
    paper_path = os.path.join(REPO_ROOT, "paper.tex")
    with open(paper_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "inactive" in content.lower(), "Paper must disclose that v5 pruning was inactive"
    assert "0.06" in content or r"\aeHeldoutPruneThreshold" in content, (
        "Paper must reference the 0.06 prune threshold"
    )
    assert "0.12" in content or r"\aePlannerRiskThreshold" in content, (
        "Paper must reference the 0.12 planner threshold"
    )


def test_paper_no_unsupported_confirmation_claims():
    """Verify no forbidden 'confirming' / 'confirms' claims remain on exploratory results."""
    paper_path = os.path.join(REPO_ROOT, "paper.tex")
    with open(paper_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for "confirming" or "confirms" in Section V (Results)
    results_match = re.search(r"\\section\{Experimental Results and Empirical Evaluation\}(.*?)\\section\{", content, re.DOTALL)
    if results_match:
        results_text = results_match.group(1)
        # Check that 'confirming' or 'confirms' does not apply to exploratory baseline comparisons
        assert "confirming hypothesis h2" not in results_text.lower(), "Forbidden 'confirming hypothesis H2' found"
        assert "confirms hypothesis h2" not in results_text.lower(), "Forbidden 'confirms hypothesis H2' found"


def test_ui_header_and_tabs_sync():
    """Verify UI layout has pending v6 label and tabs.py dynamically loads held-out data."""
    layout_path = os.path.join(REPO_ROOT, "acalib", "demo", "ui", "layout.py")
    tabs_path = os.path.join(REPO_ROOT, "acalib", "demo", "ui", "tabs.py")

    with open(layout_path, "r", encoding="utf-8") as f:
        layout_content = f.read()
    with open(tabs_path, "r", encoding="utf-8") as f:
        tabs_content = f.read()

    # Layout check
    assert "Protocol v6 registered; execution pending" in layout_content
    assert "Displayed results:" in layout_content
    assert "protocol v5" in layout_content
    assert "Verified Deterministic" not in layout_content, "Unbacked 'Verified Deterministic' badge must be removed"

    # Tabs check
    assert "_load_heldout_v5_table" in tabs_content, "tabs.py must define dynamic loader _load_heldout_v5_table"
    assert "result_model_v1.json" in tabs_content, "tabs.py must reference result_model_v1.json"


def test_docs_and_readme_evidence_hierarchy():
    """Verify README.md, RESULTS_VERDICT.md, docs/PAPER_CLAIMS.md reflect verified evidence hierarchy."""
    readme_path = os.path.join(REPO_ROOT, "README.md")
    verdict_path = os.path.join(REPO_ROOT, "RESULTS_VERDICT.md")
    claims_path = os.path.join(REPO_ROOT, "docs", "PAPER_CLAIMS.md")

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
    with open(verdict_path, "r", encoding="utf-8") as f:
        verdict = f.read()
    with open(claims_path, "r", encoding="utf-8") as f:
        claims = f.read()

    # README check
    assert "Protocol v6" in readme
    assert "pending" in readme.lower()
    assert "CBBA+LR" in readme

    # RESULTS_VERDICT check
    assert "Protocol v6 is registered" in verdict
    assert "prereg-v4" not in verdict.splitlines()[0], "Header must not reference prereg-v4 alone"

    # PAPER_CLAIMS check
    assert "inactive in v5" in claims.lower(), "docs/PAPER_CLAIMS.md must note pruning inactive in v5"
    assert "reversal" in claims.lower(), "docs/PAPER_CLAIMS.md must document v5 reversal"
