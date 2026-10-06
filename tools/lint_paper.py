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


FORBIDDEN_NUMERIC_PATTERNS = [
    (r"\+?13\.0", "Hand-typed '13.0' found (must use \\ae... macro)"),
    (r"\b0\.41\b", "Hand-typed '0.41' found (must use \\ae... macro)"),
    (r"p\s*=\s*0\.88", "Hand-typed 'p = 0.88' found (must use \\ae... macro)"),
    (r"p\s*=\s*0\.62", "Hand-typed 'p = 0.62' found (must use \\ae... macro)"),
    (r"\b1200\s+total\b", "Hand-typed '1200 total' found (must use \\aeTotalTrials macro)"),
    (r"34\s+messages", "Hand-typed '34 messages' found (must use \\ae... macro)"),
    (r"(?:~|\approx)?\s*3\s*%\s*safe", "Hand-typed '~3% safe' found (must use \\ae... macro)"),
    (r"10\s+seeds", "Hand-typed '10 seeds' found (must be consistent with actual sweep seeds)"),
]

FORBIDDEN_PHRASES = [
    (r"\bExtensive\b", "Forbidden hype word 'Extensive' found (be specific about protocol)"),
    (r"\bTheoretical Bound\b", "Forbidden phrase 'Theoretical Bound' for greedy oracle found (must be 'Clairvoyant Greedy')"),
]


def check_hardcoded_numbers(tex_content: str) -> list:
    """Check entire paper for hand-typed numbers and forbidden misleading phrases."""
    errors = []
    # Strip comments
    lines = [line.split("%")[0] for line in tex_content.splitlines()]
    clean_text = "\n".join(lines)

    for pat, msg in FORBIDDEN_NUMERIC_PATTERNS:
        if re.search(pat, clean_text, re.IGNORECASE):
            errors.append(msg)

    for pat, msg in FORBIDDEN_PHRASES:
        if re.search(pat, clean_text):
            errors.append(msg)

    # Check for physical hardware claims (Tier A is simulation only)
    # Allows "hardware" only when discussing future physical work or hardware limitations
    hw_matches = re.finditer(r"\bhardware\b", clean_text, re.IGNORECASE)
    for m in hw_matches:
        snippet = clean_text[max(0, m.start() - 50): min(len(clean_text), m.end() + 50)].lower()
        if not any(allowed in snippet for allowed in ["future", "limitation", "physical", "scope", "not", "tier a"]):
            errors.append(f"Unsubstantiated 'hardware' claim without physical robot trial: '...{snippet.strip()}...'")

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
    errors.extend(check_hardcoded_numbers(content))

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
