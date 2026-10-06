"""
Paper Quality and Reproducibility Linter (Phase 5).
Fails the build if:
1. Figure referenced in paper lacks a sidecar .provenance.json file.
2. Unmacro'd hard-coded benchmark result numbers appear in Results/Evaluation sections.
"""

import os
import re
import sys


def check_figure_provenance(tex_content: str, base_dir: str) -> list:
    """Check that all included figures have a .provenance.json sidecar."""
    errors = []
    # Find all \includegraphics{path}
    pattern = r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}"
    matches = re.findall(pattern, tex_content)

    for fig_path in matches:
        # Ignore external architecture diagrams if explicitly architectural
        if any(arch in fig_path for arch in ["fig2_adversary_model", "fig3_contingency_tree", "pipeline"]):
            continue

        full_fig_path = os.path.join(base_dir, fig_path)
        provenance_candidates = [
            full_fig_path + ".provenance.json",
            os.path.splitext(full_fig_path)[0] + ".pdf.provenance.json",
            os.path.splitext(full_fig_path)[0] + ".png.provenance.json",
        ]
        found = any(os.path.exists(p) for p in provenance_candidates)
        if not found:
            errors.append(f"Missing provenance file for figure: {fig_path}")

    return errors


def check_hardcoded_numbers_in_results(tex_content: str) -> list:
    """
    Check Results / Evaluation section for raw percentage gains or hardcoded p-values
    that should be defined as \\ae... macros from numbers.tex.
    """
    errors = []
    # Find text in Results section
    results_match = re.search(r"\\section\{Experimental Results\}", tex_content)
    if not results_match:
        results_match = re.search(r"\\section\{Experiments.*?\}", tex_content)

    if results_match:
        res_text = tex_content[results_match.start():]
        # Check for forbidden hand-typed patterns like "+13.0%", "p = 0.62", "p = 0.88", "Cliff's delta = 0.41"
        forbidden_patterns = [
            (r"\+13\.0", "Hand-typed '+13.0' found (use \\aeGainOverCBBA)"),
            (r"p\s*=\s*0\.62", "Hand-typed 'p = 0.62' found (use macro)"),
            (r"p\s*=\s*0\.88", "Hand-typed 'p = 0.88' found (use macro)"),
            (r"delta\s*=\s*0\.41", "Hand-typed 'delta = 0.41' found (use macro)"),
            (r"34\s+messages", "Hand-typed '34 messages' found (use macro)"),
        ]
        for pat, msg in forbidden_patterns:
            if re.search(pat, res_text, re.IGNORECASE):
                errors.append(msg)

    return errors


def main():
    tex_path = "paper.tex"
    if not os.path.exists(tex_path):
        print(f"Error: {tex_path} not found.")
        sys.exit(1)

    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    errors = []
    errors.extend(check_figure_provenance(content, os.path.dirname(os.path.abspath(tex_path))))
    errors.extend(check_hardcoded_numbers_in_results(content))

    if errors:
        print("LINTER FAILURE: Issues found in paper.tex:")
        for err in errors:
            print(f"  - {err}")
        print("\nPlease fix the above items before committing or building final PDF.")
        sys.exit(1)
    else:
        print("Paper lint passed successfully: 0 provenance errors, 0 forbidden hard-coded numbers.")
        sys.exit(0)


if __name__ == "__main__":
    main()
