#!/usr/bin/env python3
"""
Unit tests for acalib/utils/gitinfo.py and shell=True elimination.
Guarantees:
1. Helper works with and without .git (temp copy fallback to build_provenance.json).
2. Forbids shell=True under acalib/, experiments/, tools/, app.py.
3. Confirmatory mode fail-closed: refuses unknown commit, dirty tree, and archive-no-git source.
"""

import os
import re
import sys
import json
import pytest
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from acalib.utils.gitinfo import get_git_info, get_git_commit, check_git_clean, GitInfo
from experiments.run_sweep import main as sweep_main


def test_gitinfo_live_repository():
    """Verify get_git_info in active git repository returns valid commit and 'git' source."""
    info = get_git_info(REPO_ROOT)
    assert info.source == "git", f"Expected source 'git', got '{info.source}'"
    assert len(info.commit) == 40, f"Expected 40-char SHA commit, got '{info.commit}'"
    assert isinstance(info.is_dirty, bool)


def test_gitinfo_fallback_without_git(tmp_path):
    """Verify get_git_info falls back to build_provenance.json when .git is absent."""
    fake_commit = "1234567890abcdef1234567890abcdef12345678"
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    prov_file = results_dir / "build_provenance.json"
    with open(prov_file, "w", encoding="utf-8") as f:
        json.dump({"git_commit": fake_commit, "protocol": "v6"}, f)

    # In tmp_path there is no .git directory
    info = get_git_info(str(tmp_path))
    assert info.source == "archive-no-git"
    assert info.commit == fake_commit
    assert info.is_dirty is False


def test_gitinfo_no_git_no_provenance(tmp_path):
    """Verify get_git_info handles completely uninspectable directory gracefully."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    info = get_git_info(str(empty_dir))
    assert info.commit == "unknown"
    assert info.is_dirty is True
    assert info.source == "unknown"


def test_no_shell_true_in_codebase():
    """Verify that shell=True is forbidden under acalib/, experiments/, tools/, and app.py."""
    search_dirs = [
        os.path.join(REPO_ROOT, "acalib"),
        os.path.join(REPO_ROOT, "experiments"),
        os.path.join(REPO_ROOT, "tools"),
    ]
    target_files = [os.path.join(REPO_ROOT, "app.py")]

    for d in search_dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".py"):
                    target_files.append(os.path.join(root, f))

    pattern = re.compile(r"\bshell\s*=\s*True\b")
    violations = []
    for filepath in target_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                if pattern.search(line):
                    violations.append(f"{os.path.relpath(filepath, REPO_ROOT)}:{line_no}: {line.strip()}")

    assert not violations, f"Forbidden shell=True detected in:\n" + "\n".join(violations)


def test_confirmatory_mode_refuses_archive_fallback(tmp_path):
    """Verify confirmatory mode fails closed if git source is archive-no-git."""
    import yaml
    cfg = tmp_path / "cfg.yaml"
    with open(cfg, "w", encoding="utf-8") as f:
        yaml.dump({"methods": ["aca"], "fleet_sizes": [2], "task_counts": [2], "max_steps": 5}, f)

    fake_info = GitInfo(commit="1234567890abcdef1234567890abcdef12345678", is_dirty=False, source="archive-no-git")
    with patch("experiments.run_sweep.get_git_info", return_value=fake_info):
        with patch("experiments.run_sweep.check_git_clean", return_value=(True, "clean")):
            with patch("experiments.run_sweep.get_git_commit_hash", return_value=fake_info.commit):
                test_args = ["run_sweep.py", "--config", str(cfg), "--confirmatory", "--output-dir", str(tmp_path / "out")]
                with patch.object(sys, "argv", test_args):
                    with pytest.raises(RuntimeError, match="Must run within a live Git repository"):
                        sweep_main()


def test_confirmatory_mode_refuses_unknown_commit(tmp_path):
    """Verify confirmatory mode fails closed if commit is unknown."""
    import yaml
    cfg = tmp_path / "cfg.yaml"
    with open(cfg, "w", encoding="utf-8") as f:
        yaml.dump({"methods": ["aca"], "fleet_sizes": [2], "task_counts": [2], "max_steps": 5}, f)

    fake_info = GitInfo(commit="unknown", is_dirty=False, source="git")
    with patch("experiments.run_sweep.get_git_info", return_value=fake_info):
        with patch("experiments.run_sweep.check_git_clean", return_value=(True, "clean")):
            with patch("experiments.run_sweep.get_git_commit_hash", return_value="unknown"):
                test_args = ["run_sweep.py", "--config", str(cfg), "--confirmatory", "--output-dir", str(tmp_path / "out")]
                with patch.object(sys, "argv", test_args):
                    with pytest.raises(RuntimeError, match="Git commit hash is unknown"):
                        sweep_main()
