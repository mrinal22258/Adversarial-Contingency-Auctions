#!/usr/bin/env python3
"""
Strict PDF Integrity and Venue Compliance Checker.

Fails if:
1. Any '[?]' or '??' appears in extracted text of paper.pdf or supplement.pdf.
2. 'References' heading is missing from paper.pdf.
3. Page count exceeds venue limits (paper.pdf <= 8 pages).
4. The corresponding .log file contains:
   - 'undefined' citations or references
   - 'Overfull \\hbox' wider than 10 pt
   - 'Missing character'
5. PDF metadata contains an author name when built in anonymous mode.
6. Extracted PDF text or metadata contains identity strings (Kumar, Mrinal, IIIT, IIIT-Delhi, etc.).
"""

import os
import re
import sys
import argparse
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_FORBIDDEN_IDENTITIES = [
    r"\bkumar\b",
    r"\bmrinal\b",
    r"\bmrinal22258\b",
    r"\biiit\b",
    r"\biiitd\b",
    r"\biiit-delhi\b",
    r"\bindraprastha\b",
]


def check_pdf(pdf_path: str, max_pages: int = None, is_paper: bool = False, forbidden_identities: List[str] = None) -> List[str]:
    errors = []
    if not os.path.exists(pdf_path):
        return [f"PDF file not found: {pdf_path}"]

    if forbidden_identities is None:
        forbidden_identities = DEFAULT_FORBIDDEN_IDENTITIES

    import fitz

    doc = fitz.open(pdf_path)
    page_count = len(doc)

    # 1. Page count check
    if max_pages is not None and page_count > max_pages:
        errors.append(f"{os.path.basename(pdf_path)} page count ({page_count}) exceeds limit of {max_pages}")

    # 2. Extract full text
    full_text = ""
    for page_num in range(page_count):
        page_text = doc[page_num].get_text()
        full_text += f"\n--- Page {page_num + 1} ---\n" + page_text

        # 3. Check for [?] or ??
        if "[?]" in page_text:
            errors.append(f"Unresolved citation '[?]' found on page {page_num + 1} of {os.path.basename(pdf_path)}")
        if "??" in page_text:
            # Avoid flagging ??? if in math or intentional comments, but flag '??' cross-references
            ref_q = re.findall(r"(?:Figure|Table|Section|Eq\.|Equation|Proposition|Theorem|Lemma)\s*\?\?", page_text, re.IGNORECASE)
            if ref_q or " ??" in page_text:
                errors.append(f"Unresolved reference '??' found on page {page_num + 1} of {os.path.basename(pdf_path)}")

    # 4. Check for References heading
    if is_paper and not re.search(r"\bReferences\b", full_text, re.IGNORECASE):
        errors.append(f"Missing 'References' section heading in {os.path.basename(pdf_path)}")

    # 5. Metadata checks
    meta = doc.metadata or {}
    meta_author = meta.get("author", "").strip()
    if meta_author and meta_author.lower() not in ["anonymous", "anonymous authors", ""]:
        errors.append(f"PDF metadata 'author' contains non-anonymous author: '{meta_author}'")

    # 6. Identity leak check in text and metadata
    search_blob = full_text + "\n" + str(meta)
    for pat in forbidden_identities:
        matches = re.findall(pat, search_blob, re.IGNORECASE)
        if matches:
            errors.append(f"Identity leak matching pattern '{pat}' in {os.path.basename(pdf_path)}: found {matches[:3]}")

    # 7. Check .log file
    log_path = os.path.splitext(pdf_path)[0] + ".log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
            log_content = lf.read()

        # Undefined references/citations
        if re.search(r"LaTeX Warning:\s*Citation\s+`[^']+'\s+undefined", log_content):
            errors.append(f"Log {os.path.basename(log_path)} contains undefined citation warnings")
        if re.search(r"LaTeX Warning:\s*Reference\s+`[^']+'\s+undefined", log_content):
            errors.append(f"Log {os.path.basename(log_path)} contains undefined reference warnings")
        if re.search(r"LaTeX Warning:\s*There were undefined references", log_content):
            errors.append(f"Log {os.path.basename(log_path)} records 'There were undefined references'")

        # Missing character
        if "Missing character:" in log_content:
            missing_chars = re.findall(r"Missing character:.*", log_content)
            errors.append(f"Log {os.path.basename(log_path)} contains Missing character: {missing_chars[:3]}")

        # Overfull \hbox > 10 pt
        overfull_matches = re.findall(r"Overfull \\hbox \(([0-9.]+)pt too wide\)", log_content)
        for pts_str in overfull_matches:
            pts = float(pts_str)
            if pts > 10.0:
                errors.append(f"Log {os.path.basename(log_path)} contains severe Overfull \\hbox ({pts:.1f}pt too wide > 10pt limit)")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Strict PDF Integrity and Venue Compliance Checker")
    parser.add_argument("pdfs", nargs="*", default=["paper.pdf", "supplement.pdf"], help="PDF files to check")
    parser.add_argument("--paper-max-pages", type=int, default=8, help="Maximum allowed pages for paper.pdf (default: 8)")
    parser.add_argument("--supplement-max-pages", type=int, default=10, help="Maximum allowed pages for supplement.pdf (default: 10)")
    args = parser.parse_args()

    all_errors = []
    print("==================================================")
    print("           STRICT PDF INTEGRITY AUDIT             ")
    print("==================================================")

    for pdf_arg in args.pdfs:
        full_pdf = os.path.join(REPO_ROOT, pdf_arg) if not os.path.isabs(pdf_arg) else pdf_arg
        base_name = os.path.basename(full_pdf).lower()
        is_paper = "paper" in base_name and "supplement" not in base_name
        max_p = args.paper_max_pages if is_paper else args.supplement_max_pages

        errs = check_pdf(full_pdf, max_pages=max_p, is_paper=is_paper)
        if errs:
            print(f"\n[FAIL] {os.path.basename(full_pdf)} failed audit:")
            for e in errs:
                print(f"  - {e}")
            all_errors.extend(errs)
        else:
            print(f"[PASS] {os.path.basename(full_pdf)}: clean text, no [?], citations resolved, references intact.")

    if all_errors:
        print(f"\nTotal violations: {len(all_errors)}")
        sys.exit(1)
    else:
        print("\nAll PDF integrity checks PASSED successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
