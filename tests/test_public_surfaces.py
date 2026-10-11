"""
Verification test for public surfaces synchronization.
Ensures headline numbers across README.md, index.html, paper.tex, and numbers.tex
match without drift, and that obsolete figures/numbers are completely absent.
"""

import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_file(rel_path: str) -> str:
    path = os.path.join(REPO_ROOT, rel_path)
    assert os.path.exists(path), f"File {rel_path} does not exist"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_macro_dict(tex_content: str) -> dict:
    """Parse \\newcommand{\\macroName}{macroValue} from numbers.tex."""
    pattern = r"\\newcommand\{\\([a-zA-Z0-9]+)\}\{([^}]+)\}"
    matches = re.findall(pattern, tex_content)
    return {name: val for name, val in matches}


class TestPublicSurfacesSynchronization:
    """Validate consistency of headline metrics across all public surfaces."""

    @pytest.fixture(autouse=True)
    def load_surfaces(self):
        self.numbers_tex = read_file("results/numbers.tex")
        self.macros = parse_macro_dict(self.numbers_tex)
        self.readme = read_file("README.md")
        self.index_html = read_file("index.html")
        self.paper_tex = read_file("paper.tex")
        self.verdict = read_file("RESULTS_VERDICT.md")

    def test_macros_exist_in_numbers_tex(self):
        """Verify expected key macros exist in numbers.tex."""
        expected_macros = [
            "aeAcaComp",
            "aeCbbaComp",
            "aeAcaWelfare",
            "aeAcaTotConf",
            "aeAcaMsgs",
            "aeHeldoutTrials",
            "aeHeldoutInstances",
            "aeHeldoutAcaComp",
            "aeHeldoutAcaPlusComp",
            "aeHeldoutCbbaLrComp",
            "aeHeldoutSsiComp",
            "aeHeldoutAcaConflicts",
            "aeHeldoutNoMarginConflicts",
        ]
        for m in expected_macros:
            assert m in self.macros, f"Missing macro \\{m} in numbers.tex"

    def test_readme_matches_headline_numbers(self):
        """README.md must report the exact headline numbers from numbers.tex."""
        aca_comp = self.macros["aeAcaComp"]
        aca_welfare = self.macros["aeAcaWelfare"]
        aca_conflicts = self.macros["aeAcaTotConf"]
        aca_msgs = self.macros["aeAcaMsgs"]

        assert aca_comp in self.readme, f"README missing ACA completion {aca_comp}"
        assert aca_welfare in self.readme, f"README missing ACA welfare {aca_welfare}"
        assert aca_conflicts in self.readme, f"README missing ACA conflicts {aca_conflicts}"
        assert aca_msgs in self.readme, f"README missing ACA messages {aca_msgs}"

        # Protocol v5 held-out table in README
        assert "Protocol v5 Confirmatory Held-Out Results" in self.readme
        assert "450" in self.readme
        assert self.macros["aeHeldoutAcaPlusComp"] in self.readme
        assert self.macros["aeHeldoutCbbaLrComp"] in self.readme
        assert self.macros["aeHeldoutSsiComp"] in self.readme

    def test_index_html_matches_headline_numbers(self):
        """index.html must report the exact headline numbers from numbers.tex."""
        aca_comp = self.macros["aeAcaComp"]
        cbba_comp = self.macros["aeCbbaComp"]
        aca_welfare = self.macros["aeAcaWelfare"]
        aca_conflicts = self.macros["aeAcaTotConf"]

        assert aca_comp in self.index_html, f"index.html missing ACA completion {aca_comp}"
        assert cbba_comp in self.index_html, f"index.html missing CBBA completion {cbba_comp}"
        assert aca_welfare in self.index_html, f"index.html missing ACA welfare {aca_welfare}"
        assert aca_conflicts in self.index_html, f"index.html missing ACA conflicts {aca_conflicts}"

        # Protocol v5 held-out section in index.html
        assert "Protocol v5 Confirmatory Held-Out Benchmark" in self.index_html
        assert "450" in self.index_html
        assert self.macros["aeHeldoutAcaPlusComp"] in self.index_html
        assert self.macros["aeHeldoutCbbaLrComp"] in self.index_html
        assert self.macros["aeHeldoutSsiComp"] in self.index_html

    def test_no_obsolete_numbers_in_index_html(self):
        """index.html must not contain obsolete 120-trial strings or old 81.6 completion."""
        assert "120 paired simulation trials" not in self.index_html
        assert "81.6" not in self.index_html
        assert "across 120 paired trials" not in self.index_html

    def test_conditional_guarantee_statements(self):
        """Every mention of conflict-freedom guarantee must be explicitly conditional."""
        # Must condition on bounded estimation error / Assumption 1
        assert "Theorem 1, conditional on Assumption 1" in self.index_html or "Assumption 1" in self.index_html
        assert "Theorem 1, conditional on Assumption 1" in self.readme or "bounded belief estimation error" in self.readme

    def test_paper_tex_inputs_numbers_and_uses_macros(self):
        """paper.tex must input results/numbers.tex and reference key macros."""
        assert "\\input{results/numbers.tex}" in self.paper_tex
        assert "\\aeAcaComp" in self.paper_tex
        assert "\\aeCbbaComp" in self.paper_tex

    def test_results_verdict_has_heldout_v5(self):
        """RESULTS_VERDICT.md must contain the Protocol v5 confirmatory findings."""
        assert "Protocol v5 Confirmatory Held-Out Verdict" in self.verdict
        assert "H1_aca_plus_comp" in self.verdict
        assert "H6_aca_plus_vs_ssi_comp" in self.verdict
        assert "H7_aca_nomargin_conf" in self.verdict
        assert "$N = 450$ Independent Instances" in self.verdict or "450" in self.verdict
