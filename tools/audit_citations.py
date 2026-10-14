#!/usr/bin/env python3
r"""
Comprehensive BibTeX and LaTeX Citation Audit Tool.
Verifies:
1. Every cite in paper.tex and supplement.tex (and all \input files) exists in references.bib.
2. Every bib entry is cited in either paper.tex or supplement.tex (no unused entries).
3. No bib entry contains placeholder fields (e.g., TODO, FIXME, ???, empty fields).
"""

import os
import re
import sys
from typing import Set, Dict, List

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_tex_inputs(file_path: str, base_dir: str, visited: Set[str] = None) -> str:
    """Recursively read a LaTeX document and expand all \\input{...} and \\include{...}."""
    if visited is None:
        visited = set()
    full_path = os.path.normpath(os.path.join(base_dir, file_path))
    if not full_path.endswith(".tex"):
        full_path += ".tex"
    if full_path in visited or not os.path.exists(full_path):
        return ""
    visited.add(full_path)

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find inputs
    def replace_input(match):
        rel = match.group(1).strip()
        return find_tex_inputs(rel, base_dir, visited)

    content = re.sub(r"\\(?:input|include)\{([^}]+)\}", replace_input, content)
    return content


def extract_cites(tex_content: str) -> Set[str]:
    """Extract all citation keys cited via \\cite{...}."""
    cites = set()
    # Strip comments
    clean_lines = [re.sub(r"(?<!\\)%.*", "", line) for line in tex_content.splitlines()]
    clean_tex = "\n".join(clean_lines)
    for m in re.finditer(r"\\cite(?:\[.*?\])?\{([^}]+)\}", clean_tex):
        for k in m.group(1).split(","):
            k_clean = k.strip()
            if k_clean:
                cites.add(k_clean)
    return cites


def parse_bibtex(bib_path: str):
    """Parse bib file into dictionary of entries and raw content."""
    with open(bib_path, "r", encoding="utf-8") as f:
        bib_txt = f.read()

    entries = {}
    pattern = r"@(\w+)\s*\{\s*([^,]+),([^@]*)"
    for m in re.finditer(pattern, bib_txt):
        entry_type = m.group(1).lower()
        key = m.group(2).strip()
        body = m.group(3)
        entries[key] = {"type": entry_type, "body": body}
    return entries, bib_txt


def audit_citations():
    paper_path = os.path.join(REPO_ROOT, "paper.tex")
    supp_path = os.path.join(REPO_ROOT, "supplement.tex")
    bib_path = os.path.join(REPO_ROOT, "references.bib")

    full_paper = find_tex_inputs("paper.tex", REPO_ROOT)
    full_supp = find_tex_inputs("supplement.tex", REPO_ROOT)

    cites_paper = extract_cites(full_paper)
    cites_supp = extract_cites(full_supp)
    all_cites = cites_paper | cites_supp

    bib_entries, bib_raw = parse_bibtex(bib_path)
    bib_keys = set(bib_entries.keys())

    errors = []

    # 1. Missing keys
    missing_cites = all_cites - bib_keys
    if missing_cites:
        errors.append(f"Citations missing from references.bib: {sorted(missing_cites)}")

    # 2. Unused bib entries
    unused_keys = bib_keys - all_cites
    if unused_keys:
        errors.append(f"Unused keys in references.bib: {sorted(unused_keys)}")

    # 3. Check for placeholder fields in bibtex
    placeholder_patterns = [
        (r"\bTODO\b", "TODO marker"),
        (r"\bFIXME\b", "FIXME marker"),
        (r"\?\?\?", "??? placeholder"),
        (r"=\s*[\"']\s*[\"']", "empty string attribute"),
        (r"=\s*\{\s*\}", "empty bracket attribute"),
    ]
    for key, data in bib_entries.items():
        for pat, desc in placeholder_patterns:
            if re.search(pat, data["body"], re.IGNORECASE):
                errors.append(f"Entry '{key}' contains {desc}")

    print("==================================================")
    print("           BIBTEX CITATION AUDIT REPORT           ")
    print("==================================================")
    print(f"Total bib entries:    {len(bib_keys)}")
    print(f"Cited in paper:       {len(cites_paper)}")
    print(f"Cited in supplement:  {len(cites_supp)}")
    print(f"Total unique cites:   {len(all_cites)}")

    if errors:
        print("\n[FAIL] Citation audit found errors:")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("\n[PASS] All citations exist, no unused entries, no placeholders.")
        return True


if __name__ == "__main__":
    success = audit_citations()
    sys.exit(0 if success else 1)
