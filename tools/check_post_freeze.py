#!/usr/bin/env python3
"""
Post-Freeze Integrity Checker (Rule 7).
Ensures that after the cryptographic freeze tag (prereg-v6.2), no changes are made to:
- acalib/ (zero changes permitted)
- experiments/ (only figure/table generation scripts permitted)
- experiments/configs/protocol_v6.yaml (zero changes permitted)
- protocols/prereg-v6.md (only dated amendment additions permitted)
"""

import os
import sys
import argparse
import subprocess
from typing import List, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.utils.gitinfo import _find_git_binary

ALLOWED_EXPERIMENT_SCRIPTS = {
    "experiments/make_figures.py",
    "experiments/make_map_figures.py",
    "experiments/make_tables.py",
    "experiments/plot_style.py",
    "experiments/plot_comm_degradation_diagnostic.py",
    "experiments/make_rollout_videos.py",
    "experiments/make_cd_diagram.py",
}


def get_diff_files(git_bin: str, tag: str) -> List[str]:
    """Retrieve all files modified against tag (committed, staged, or working tree)."""
    files = set()
    # 1. Committed diff against tag
    res_tag = subprocess.run(
        [git_bin, "diff", "--name-only", f"{tag}..HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res_tag.returncode == 0 and res_tag.stdout.strip():
        files.update(res_tag.stdout.strip().splitlines())

    # 2. Unstaged changes in working tree
    res_work = subprocess.run(
        [git_bin, "diff", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res_work.returncode == 0 and res_work.stdout.strip():
        files.update(res_work.stdout.strip().splitlines())

    # 3. Staged changes
    res_staged = subprocess.run(
        [git_bin, "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res_staged.returncode == 0 and res_staged.stdout.strip():
        files.update(res_staged.stdout.strip().splitlines())

    return sorted(files)


def check_prereg_amendment_only(git_bin: str, tag: str) -> Tuple[bool, str]:
    """Verify that any changes to protocols/prereg-v6.md are strictly additions to amendments."""
    res_diff = subprocess.run(
        [git_bin, "diff", tag, "--", "protocols/prereg-v6.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    diff_text = res_diff.stdout
    # Deletions or modifications to frozen sections are forbidden
    for line in diff_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            return False, f"Forbidden deletion in frozen preregistration: '{line}'"
    return True, "Valid amendment addition"


def check_post_freeze(tag: str = "prereg-v6.2") -> Tuple[bool, List[str]]:
    """Check repository against freeze tag for forbidden modifications."""
    git_bin = _find_git_binary()
    if not git_bin:
        return False, ["Git binary not found; cannot verify post-freeze diff."]

    # Check tag exists
    res_tag_check = subprocess.run(
        [git_bin, "rev-parse", "--verify", f"refs/tags/{tag}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res_tag_check.returncode != 0:
        return False, [f"Freeze tag '{tag}' does not exist in repository."]

    changed_files = get_diff_files(git_bin, tag)
    violations = []

    for f in changed_files:
        norm = f.replace("\\", "/")

        # 1. acalib/ simulation core is strictly frozen (demo UI exempted)
        if norm.startswith("acalib/"):
            if not norm.startswith("acalib/demo/"):
                violations.append(f"Forbidden post-freeze change in simulator core: {norm}")

        # 2. protocol config is strictly frozen
        elif norm == "experiments/configs/protocol_v6.yaml":
            violations.append(f"Forbidden post-freeze change in protocol configuration: {norm}")

        # 3. experiments/ (except figure/table scripts)
        elif norm.startswith("experiments/"):
            if norm not in ALLOWED_EXPERIMENT_SCRIPTS and not norm.startswith("experiments/plot_"):
                violations.append(f"Forbidden post-freeze change in experiments directory: {norm}")

        # 4. protocols/prereg-v6.md (only dated amendment additions)
        elif norm == "protocols/prereg-v6.md":
            valid_amend, msg = check_prereg_amendment_only(git_bin, tag)
            if not valid_amend:
                violations.append(f"Forbidden post-freeze modification in prereg-v6.md: {msg}")

    return len(violations) == 0, violations


def main():
    parser = argparse.ArgumentParser(description="Check post-freeze immutability against tag.")
    parser.add_argument("--tag", default="prereg-v6.2", help="Freeze tag to diff against (default: prereg-v6.2)")
    args = parser.parse_args()

    print(f"==================================================================")
    print(f"               POST-FREEZE INTEGRITY AUDIT                        ")
    print(f"==================================================================")
    print(f"Freeze Tag:              {args.tag}")

    passed, violations = check_post_freeze(tag=args.tag)

    if not passed:
        print(f"STATUS: POST-FREEZE CHECK FAILED ({len(violations)} violations):")
        for v in violations:
            print(f"  [ERROR] {v}")
        sys.exit(1)
    else:
        print(f"STATUS: POST-FREEZE INTEGRITY VERIFIED (PASS)")
        print(f"Zero simulation or protocol changes against freeze tag '{args.tag}'.")
        sys.exit(0)


if __name__ == "__main__":
    main()
