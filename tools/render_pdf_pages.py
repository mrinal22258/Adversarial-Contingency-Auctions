#!/usr/bin/env python3
"""
Renders each page of paper.pdf and supplement.pdf to high-resolution PNG (150 dpi)
for visual inspection of layout, fonts, diagrams, tables, and spacing.
"""

import os
import sys
import fitz

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_DIR = os.path.join(REPO_ROOT, "results", "figures", "rendered_pages")
os.makedirs(RENDER_DIR, exist_ok=True)


def render_pages():
    total_rendered = 0
    for doc_name in ["paper", "supplement"]:
        pdf_path = os.path.join(REPO_ROOT, f"{doc_name}.pdf")
        if not os.path.exists(pdf_path):
            print(f"Skipping missing {pdf_path}")
            continue

        doc = fitz.open(pdf_path)
        print(f"Rendering {doc_name}.pdf ({len(doc)} pages) at 150 dpi...")
        for idx in range(len(doc)):
            page = doc[idx]
            pix = page.get_pixmap(dpi=150)
            out_file = os.path.join(RENDER_DIR, f"{doc_name}_p{idx+1}.png")
            pix.save(out_file)
            print(f"  - Page {idx+1}: {out_file} ({pix.width}x{pix.height} px)")
            total_rendered += 1

    print(f"\nSuccessfully rendered {total_rendered} pages into {RENDER_DIR}")


if __name__ == "__main__":
    render_pages()
