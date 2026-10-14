#!/usr/bin/env python3
"""
Publication Paper and Supplement Build Script.
Runs the complete pdflatex -> bibtex -> pdflatex -> pdflatex pipeline
for paper.tex and supplement.tex.
"""

import os
import sys
import shutil
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required LaTeX tool '{name}' not found on PATH.")
    return path


def compile_doc(doc_name: str):
    tex_file = f"{doc_name}.tex"
    pdf_file = f"{doc_name}.pdf"
    full_tex = os.path.join(REPO_ROOT, tex_file)
    if not os.path.exists(full_tex):
        raise FileNotFoundError(f"Source file not found: {full_tex}")

    pdflatex = find_tool("pdflatex")
    bibtex = find_tool("bibtex")

    print(f"\n==================================================")
    print(f"  Building {doc_name}.pdf (pdflatex -> bibtex -> 2x pdflatex)")
    print(f"==================================================")

    steps = [
        ("pdflatex (pass 1)", [pdflatex, "-interaction=nonstopmode", tex_file]),
        ("bibtex", [bibtex, doc_name]),
        ("pdflatex (pass 2)", [pdflatex, "-interaction=nonstopmode", tex_file]),
        ("pdflatex (pass 3)", [pdflatex, "-interaction=nonstopmode", tex_file]),
    ]

    for step_name, cmd in steps:
        print(f"Running {step_name}...")
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error during {step_name}:\n{res.stdout[-1500:]}\n{res.stderr}")
            sys.exit(1)

    full_pdf = os.path.join(REPO_ROOT, pdf_file)
    if not os.path.exists(full_pdf):
        raise FileNotFoundError(f"Expected output PDF not created: {full_pdf}")

    # Inspect page count
    try:
        import fitz
        doc = fitz.open(full_pdf)
        pages = len(doc)
        print(f"Successfully generated {pdf_file} ({pages} pages).")
    except Exception:
        print(f"Successfully generated {pdf_file}.")


def main():
    compile_doc("paper")
    compile_doc("supplement")
    print("\n[SUCCESS] Paper and Supplement built successfully.")


if __name__ == "__main__":
    main()
