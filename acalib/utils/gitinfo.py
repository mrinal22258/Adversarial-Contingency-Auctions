#!/usr/bin/env python3
"""
Consolidated Git Information Helper for ACA.
Guarantees:
1. List-argument subprocess.run without shell invocation.
2. Tries PATH git, with fallback to known Windows paths.
3. Returns GitInfo(commit, is_dirty, source).
4. Without .git, falls back to commit in results/build_provenance.json with source='archive-no-git'.
5. Clean status filtering for transient and log files.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import NamedTuple, Optional, Tuple, List


class GitInfo(NamedTuple):
    commit: str
    is_dirty: bool
    source: str  # "git" | "archive-no-git" | "unknown"


def _find_repo_root(start_dir: Optional[str] = None) -> str:
    """Find repository root by walking up from start_dir."""
    curr = os.path.abspath(start_dir or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(curr, ".git")) or os.path.isfile(os.path.join(curr, ".git")):
            return curr
        if os.path.isfile(os.path.join(curr, "results", "build_provenance.json")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    # Default to directory containing acalib root
    module_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return module_root


def _find_git_binary() -> Optional[str]:
    """Find git executable on PATH or known system paths."""
    git_bin = shutil.which("git")
    if git_bin:
        return git_bin
    known_windows_paths = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    for p in known_windows_paths:
        if os.path.exists(p):
            return p
    return None


def get_git_info(repo_root: Optional[str] = None) -> GitInfo:
    """
    Retrieve Git commit, dirty status, and provenance source.
    Returns:
        GitInfo(commit: str, is_dirty: bool, source: str)
    """
    root = repo_root or _find_repo_root()
    git_dir = os.path.join(root, ".git")

    if os.path.exists(git_dir):
        git_bin = _find_git_binary()
        if git_bin:
            try:
                # 1. Commit hash
                res_head = subprocess.run(
                    [git_bin, "rev-parse", "HEAD"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                commit = res_head.stdout.strip()
                if res_head.returncode == 0 and commit:
                    # 2. Status / Porcelain check
                    res_status = subprocess.run(
                        [git_bin, "status", "--porcelain"],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    dirty_lines = []
                    if res_status.returncode == 0 and res_status.stdout.strip():
                        for line in res_status.stdout.strip().splitlines():
                            # Exclude untracked test logs or local scratch files
                            if (
                                line.startswith("?? results/test_logs")
                                or line.startswith("?? ACA_End_to_End_Audit")
                                or line.startswith("?? .coverage")
                                or line.startswith("?? .pytest_cache")
                            ):
                                continue
                            dirty_lines.append(line)
                    is_dirty = len(dirty_lines) > 0
                    return GitInfo(commit=commit, is_dirty=is_dirty, source="git")
            except Exception:
                pass

        # If git binary failed but .git directory exists, inspect .git/HEAD directly
        head_path = os.path.join(git_dir, "HEAD")
        if os.path.exists(head_path):
            try:
                with open(head_path, "r", encoding="utf-8") as f:
                    ref_or_hash = f.read().strip()
                if ref_or_hash.startswith("ref: "):
                    ref_path = os.path.join(git_dir, ref_or_hash[5:])
                    if os.path.exists(ref_path):
                        with open(ref_path, "r", encoding="utf-8") as rf:
                            commit = rf.read().strip()
                            if commit:
                                return GitInfo(commit=commit, is_dirty=False, source="git")
                elif len(ref_or_hash) == 40:
                    return GitInfo(commit=ref_or_hash, is_dirty=False, source="git")
            except Exception:
                pass

    # No .git directory or unreadable: fallback to build_provenance.json
    prov_path = os.path.join(root, "results", "build_provenance.json")
    if os.path.exists(prov_path):
        try:
            with open(prov_path, "r", encoding="utf-8") as f:
                prov = json.load(f)
            commit = prov.get("git_commit", "")
            if commit and commit != "UNKNOWN":
                return GitInfo(commit=commit, is_dirty=False, source="archive-no-git")
        except Exception:
            pass

    return GitInfo(commit="unknown", is_dirty=True, source="unknown")


def get_git_commit(repo_root: Optional[str] = None) -> str:
    """Retrieve commit hash (or 'unknown')."""
    return get_git_info(repo_root).commit


def check_git_clean(repo_root: Optional[str] = None) -> Tuple[bool, str]:
    """Check if repository working tree is clean. Returns (is_clean, status_msg)."""
    info = get_git_info(repo_root)
    if info.source == "archive-no-git":
        return True, "archive-no-git"
    if info.source == "unknown":
        return False, "git_uninspectable"
    is_clean = not info.is_dirty
    return is_clean, "clean" if is_clean else "dirty"


def check_git_status(repo_root: Optional[str] = None) -> Tuple[bool, str, str]:
    """Returns (is_clean, commit_sha, status_summary)."""
    info = get_git_info(repo_root)
    is_clean = not info.is_dirty
    return is_clean, info.commit, "clean" if is_clean else "dirty"
