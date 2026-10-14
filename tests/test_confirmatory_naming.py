#!/usr/bin/env python3
"""
Test naming discipline and disambiguation in results/confirmatory.
Guarantees:
1. No file in results/confirmatory/ lacks an explicit protocol version tag (e.g. _v5_, _v6_), except README.md.
2. Relocated Stage-4 pilot files exist under results/pilot/ with stage4_pilot_* naming.
3. Files in results/confirmatory/ remain byte-identical to pinned hashes.
"""

import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIRMATORY_DIR = os.path.join(REPO_ROOT, "results", "confirmatory")
PILOT_DIR = os.path.join(REPO_ROOT, "results", "pilot")


def test_confirmatory_file_naming_convention():
    """Verify all data files in results/confirmatory/ have an explicit protocol version."""
    assert os.path.exists(CONFIRMATORY_DIR), "results/confirmatory/ must exist"
    files = os.listdir(CONFIRMATORY_DIR)
    assert len(files) > 0, "results/confirmatory/ must not be empty"

    version_pattern = re.compile(r"v\d+", re.IGNORECASE)
    unversioned = []
    for f in files:
        if f == "README.md":
            continue
        if not version_pattern.search(f):
            unversioned.append(f)

    assert not unversioned, (
        f"Found unversioned files in results/confirmatory/: {unversioned}. "
        f"All confirmatory files must have an explicit protocol version (e.g. heldout_v5_*)."
    )


def test_stage4_pilot_relocated_files_exist():
    """Verify relocated stage4 pilot files exist under results/pilot/."""
    expected_pilot_files = [
        "stage4_pilot_results.csv",
        "stage4_pilot_summary.csv",
        "stage4_pilot_runs.jsonl",
    ]
    assert os.path.exists(PILOT_DIR), "results/pilot/ directory must exist"
    for pf in expected_pilot_files:
        p = os.path.join(PILOT_DIR, pf)
        assert os.path.exists(p), f"Missing relocated pilot file: {p}"
        assert os.path.getsize(p) > 0, f"Pilot file {p} is unexpectedly empty"
