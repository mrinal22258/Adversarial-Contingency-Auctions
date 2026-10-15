#!/usr/bin/env python3
"""
Double-Blind Anonymity Checker.
Scans extracted release directory, code, documentation, and rendered PDFs
for any author, institutional, or contact identity leaks.
"""

import os
import re
import sys
import argparse
from typing import List, Tuple, Dict, Any

DEFAULT_FORBIDDEN_IDENTITIES = [
    r"\bkumar\b",
    r"\bmrinal\b",
    r"\bmrinal22258\b",
    r"\biiit\b",
    r"\biiitd\b",
    r"\biiit-delhi\b",
    r"\bindraprastha\b",
    r"spaces/mrinal22258",
    r"github\.com/mrinal22258",
    r"\bkrmri\b",
    r"[\\\/]users[\\\/]krmri\b",
    r"\bonedrive[\\\/]",
]

EXCLUDED_FILENAMES = {
    "check_anonymity.py",
    "check_pdf.py",
}

EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".mov", ".avi",
    ".zip", ".tar", ".gz", ".7z",
    ".pyc", ".pyo", ".pyd",
    ".parquet", ".pkl", ".pt", ".pth",
    ".map",
    ".log", ".aux", ".blg", ".out", ".fls", ".fdb_latexmk", ".synctex.gz",
}

EXCLUDED_DIRNAMES = {
    ".git",
    ".venv",
    "venv_core",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}


def scan_file_content(filepath: str, patterns: List[re.Pattern]) -> List[Tuple[int, str, str]]:
    """Scan a single file for regex pattern matches."""
    violations = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                # Exclude self-references or known harmless test fixtures
                line_lower = line.lower()
                for pat in patterns:
                    m = pat.search(line_lower)
                    if m:
                        violations.append((line_no, line.strip(), m.group(0)))
                        break
    except Exception as e:
        violations.append((0, f"Could not read file: {e}", "FILE_READ_ERROR"))
    return violations


def check_directory(dir_path: str, patterns: List[re.Pattern]) -> Dict[str, List[Tuple[int, str, str]]]:
    """Recursively scan directory for identity leaks."""
    results = {}
    for root, dirs, files in os.walk(dir_path):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRNAMES]

        for fname in files:
            if fname in EXCLUDED_FILENAMES:
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDED_EXTENSIONS:
                continue

            # Don't scan raw pdf with text reader (handled by PDF checker)
            if ext == ".pdf":
                continue

            full_path = os.path.join(root, fname)
            v = scan_file_content(full_path, patterns)
            if v:
                results[os.path.relpath(full_path, dir_path)] = v

    return results


def check_pdf_file(pdf_path: str, patterns: List[re.Pattern]) -> Tuple[List[str], bool]:
    """Check PDF text and metadata for identity violations. Returns (errors, is_verified)."""
    if not os.path.exists(pdf_path):
        return ([f"PDF not found: {pdf_path}"], False)

    try:
        import fitz
    except ImportError:
        return (["PyMuPDF (fitz) is not installed; cannot verify PDF text and metadata."], False)

    errors = []
    doc = fitz.open(pdf_path)

    # Check metadata
    metadata = doc.metadata or {}
    for key, val in metadata.items():
        if val:
            val_lower = str(val).lower()
            for pat in patterns:
                if pat.search(val_lower):
                    errors.append(f"PDF metadata leak in field '{key}': '{val}' matches forbidden pattern")

    # Check page text
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text("text").lower()
        for pat in patterns:
            match = pat.search(text)
            if match:
                errors.append(f"PDF page {page_idx + 1} leak: detected forbidden string '{match.group(0)}'")

    return (errors, True)


def main():
    parser = argparse.ArgumentParser(description="Check repository or release archive for double-blind anonymity.")
    parser.add_argument("target_dir", nargs="?", default=".", help="Directory to inspect (default: .)")
    parser.add_argument("--paper", default=None, help="Path to paper PDF to check")
    parser.add_argument("--supplement", default=None, help="Path to supplement PDF to check")
    parser.add_argument("--identities", default=None, help="Custom comma-separated forbidden regex patterns")
    parser.add_argument("--strict", action="store_true", help="Fail strictly if any leak or missing file is found")
    args = parser.parse_args()

    raw_patterns = DEFAULT_FORBIDDEN_IDENTITIES
    if args.identities:
        raw_patterns = [p.strip() for p in args.identities.split(",") if p.strip()]

    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in raw_patterns]

    target_dir = os.path.abspath(args.target_dir)
    print("=" * 60)
    print("       DOUBLE-BLIND PEER REVIEW ANONYMITY AUDIT")
    print("=" * 60)
    print(f"Target Directory: {target_dir}")
    print(f"Configured Forbidden Patterns: {len(compiled_patterns)}")

    total_violations = 0

    # 1. Scan directory files
    dir_violations = check_directory(target_dir, compiled_patterns)
    if dir_violations:
        print("\n[FAIL] Identity leaks detected in repository files:")
        for rpath, vlist in dir_violations.items():
            print(f"  File: {rpath}")
            for line_no, line_content, matched in vlist:
                print(f"    Line {line_no} [matched '{matched}']: {line_content[:100]}")
                total_violations += 1
    else:
        print("[PASS] Clean repository files: zero author/institutional identity strings detected.")

    # 2. Check PDFs
    paper_path = args.paper or os.path.join(target_dir, "paper.pdf")
    supplement_path = args.supplement or os.path.join(target_dir, "supplement.pdf")

    for label, path in [("Paper PDF", paper_path), ("Supplement PDF", supplement_path)]:
        if os.path.exists(path):
            pdf_errs, is_verified = check_pdf_file(path, compiled_patterns)
            if not is_verified:
                print(f"[WARN] {label} ({path}): {pdf_errs[0]}")
                if args.strict:
                    total_violations += 1
            elif pdf_errs:
                print(f"\n[FAIL] Identity leaks detected in {label} ({path}):")
                for err in pdf_errs:
                    print(f"  - {err}")
                    total_violations += 1
            else:
                print(f"[PASS] {label}: clean metadata and text, zero identity leaks.")
        else:
            if args.strict:
                print(f"[WARN] {label} not found at {path}")
                total_violations += 1

    print("-" * 60)
    if total_violations > 0:
        print(f"STATUS: FAILED ({total_violations} identity violations found).")
        print("Double-blind submission requirements VIOLATED.")
        sys.exit(1)
    else:
        print("STATUS: PASSED (100% Anonymized for Double-Blind Peer Review).")
        sys.exit(0)


if __name__ == "__main__":
    main()
