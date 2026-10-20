#!/usr/bin/env python3
"""
Single Source of Truth Metrics Exporter.
Delegates to tools.build_result_model and tools.generate_numbers_from_model
to guarantee byte-for-byte consistency across all pipelines.
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import tools.build_result_model as brm
import tools.generate_numbers_from_model as gnm
import experiments.make_tables as mt


def main():
    print("[*] Rebuilding result model and latex numbers...")
    brm.main()
    gnm.generate_numbers()
    mt.main()
    print("[+] Latex numbers and tables exported successfully.")


if __name__ == "__main__":
    main()
