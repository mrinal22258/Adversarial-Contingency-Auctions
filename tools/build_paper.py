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


def compile_doc(doc_name: str, target_rotation: int = 0):
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
            log_file = os.path.join(REPO_ROOT, f"{doc_name}.log")
            has_fatal = False
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="latin-1") as f_log:
                    content = f_log.read()
                    if "\n!" in content:
                        has_fatal = True
            if has_fatal:
                print(f"Error during {step_name}:\n{res.stdout[-1500:]}\n{res.stderr}")
                sys.exit(1)
            else:
                print(f"[NOTE] Non-fatal notification during {step_name}; proceeding.")

    full_pdf = os.path.join(REPO_ROOT, pdf_file)
    if not os.path.exists(full_pdf):
        raise FileNotFoundError(f"Expected output PDF not created: {full_pdf}")

    # Inspect page count and orientation
    try:
        import fitz
        doc = fitz.open(full_pdf)
        pages = len(doc)
        rotations = [doc[i].rotation for i in range(pages)]
        doc.close()
        print(f"Successfully generated {pdf_file} ({pages} pages, rotation={rotations[0]}°).")
    except Exception:
        print(f"Successfully generated {pdf_file}.")

    # Enforce rotation if required
    ensure_pdf_rotation(full_pdf, target_rotation=target_rotation)


def ensure_pdf_rotation(pdf_path: str, target_rotation: int = 0):
    """
    Guarantees every page of the given PDF has the target rotation (default: 0 degrees).
    Ensures that compilations across all PDF viewers and duplex print drivers
    strictly maintain the required orientation.
    """
    if target_rotation is None:
        return
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        needs_update = False
        for page in reader.pages:
            rot = page.get("/Rotate", 0)
            if rot is None:
                rot = 0
            if rot != target_rotation:
                needs_update = True
                break

        if needs_update:
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                rot = page.get("/Rotate", 0)
                if rot is None:
                    rot = 0
                diff = (target_rotation - rot) % 360
                if diff != 0:
                    page.rotate(diff)
                writer.add_page(page)
            with open(pdf_path, "wb") as f:
                writer.write(f)
            print(f"-> Enforced {target_rotation}° rotation on all pages of {os.path.basename(pdf_path)}.")
        else:
            print(f"-> Verified {os.path.basename(pdf_path)} pages are correctly oriented at {target_rotation}°.")
    except Exception as e:
        print(f"[WARNING] Could not enforce PDF rotation on {pdf_path}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publication Paper and Supplement Build Script")
    parser.add_argument("--rotate", type=int, default=int(os.environ.get("ACA_PAPER_ROTATE", "0")),
                        choices=[0, 90, 180, 270], help="Target rotation in degrees (default: 0 or ACA_PAPER_ROTATE)")
    parser.add_argument("--docs", nargs="+", default=["paper", "supplement"],
                        help="Documents to compile (default: paper supplement)")
    args = parser.parse_args()

    for doc_name in args.docs:
        compile_doc(doc_name, target_rotation=args.rotate)

    print("\n[SUCCESS] Paper and Supplement built successfully with orientation verified.")


if __name__ == "__main__":
    main()
