#!/usr/bin/env python3
"""
Master build script (tools/build_all.py / make all).
Regenerates result model, tables, macros, figures, paper PDF, and build provenance manifest.
"""

import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.build_all_results import run_pipeline

if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
