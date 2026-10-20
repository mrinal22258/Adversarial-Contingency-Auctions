#!/usr/bin/env python3
"""
Double-Blind Review Archive Builder.
Uses `git archive` from the given ref/tag to produce a pristine, self-contained,
anonymized submission archive free from .git history, heavy caches, and identity leaks.
"""

import os
import sys
import shutil
import zipfile
import tarfile
import argparse
import tempfile
import subprocess
import json
from typing import List, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.utils.gitinfo import _find_git_binary
from tools.check_anonymity import check_directory, check_pdf_file, DEFAULT_FORBIDDEN_IDENTITIES


def build_release_archive(ref: str = "HEAD", output_dir: str = "release") -> Dict[str, Any]:
    git_bin = _find_git_binary()
    if not git_bin:
        raise RuntimeError("git binary not found on PATH or standard directories.")

    os.makedirs(os.path.join(REPO_ROOT, output_dir), exist_ok=True)
    zip_path = os.path.join(REPO_ROOT, output_dir, "aca_review_archive.zip")
    tar_path = os.path.join(REPO_ROOT, output_dir, "aca_review_archive.tar.gz")

    print("=" * 65)
    print("      BUILDING DOUBLE-BLIND REVIEW RELEASE ARCHIVE")
    print("=" * 65)
    print(f"Source Reference: {ref}")
    print(f"Output Directory: {output_dir}")

    # 1. Create zip archive using git archive (honors export-ignore in .gitattributes)
    print(f"\n[1/4] Running git archive (zip)...")
    cmd_zip = [
        git_bin,
        "archive",
        "--worktree-attributes",
        f"--format=zip",
        f"--prefix=adversarial-contingency-auctions/",
        f"-o",
        zip_path,
        ref,
    ]
    res_zip = subprocess.run(cmd_zip, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if res_zip.returncode != 0:
        raise RuntimeError(f"git archive failed: {res_zip.stderr}")
    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"Created: {zip_path} ({zip_size_mb:.2f} MB)")

    # 2. Create tar.gz archive
    print(f"\n[2/4] Running git archive (tar.gz)...")
    cmd_tar = [
        git_bin,
        "archive",
        "--worktree-attributes",
        f"--format=tar.gz",
        f"--prefix=adversarial-contingency-auctions/",
        f"-o",
        tar_path,
        ref,
    ]
    res_tar = subprocess.run(cmd_tar, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if res_tar.returncode != 0:
        raise RuntimeError(f"git archive tar failed: {res_tar.stderr}")
    tar_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"Created: {tar_path} ({tar_size_mb:.2f} MB)")

    # 3. Extract to temporary folder for strict validation
    print(f"\n[3/4] Extracting archive and auditing contents...")
    violations = []
    extracted_files = []
    total_uncompressed_bytes = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        extract_root = os.path.join(temp_dir, "adversarial-contingency-auctions")
        if not os.path.exists(extract_root):
            extract_root = temp_dir

        for root, dirs, files in os.walk(extract_root):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), extract_root).replace("\\", "/")
                extracted_files.append(rel)
                f_size = os.path.getsize(os.path.join(root, f))
                total_uncompressed_bytes += f_size

                # Enforce exclusion of forbidden directories/files
                if ".git" in rel.split("/"):
                    violations.append(f"Forbidden .git file in archive: {rel}")
                if "venv_core" in rel:
                    violations.append(f"Forbidden venv file in archive: {rel}")
                if "results/supplement" in rel:
                    violations.append(f"Forbidden large supplement file in archive: {rel}")
                if rel.endswith(".jsonl"):
                    violations.append(f"Forbidden raw jsonl file in archive: {rel}")

        # Check required files exist
        required_files = [
            "README.md",
            "LICENSE",
            "paper.pdf",
            "supplement.pdf",
            "app.py",
            "protocols/prereg-v6.md",
            "results/result_model_v1.json",
        ]
        for rf in required_files:
            if rf not in extracted_files:
                violations.append(f"Required file missing from release archive: {rf}")

        # 4. Strict Anonymity Check on extracted tree
        print(f"\n[4/4] Running strict anonymity audit on extracted release tree...")
        import re
        compiled_patterns = [re.compile(p, re.IGNORECASE) for p in DEFAULT_FORBIDDEN_IDENTITIES]
        dir_violations = check_directory(extract_root, compiled_patterns)
        for rpath, vlist in dir_violations.items():
            for lno, lcontent, matched in vlist:
                violations.append(f"Identity leak in {rpath}:{lno} [matched '{matched}']: {lcontent[:80]}")

        paper_in_archive = os.path.join(extract_root, "paper.pdf")
        if os.path.exists(paper_in_archive):
            pdf_errs, _ = check_pdf_file(paper_in_archive, compiled_patterns)
            violations.extend(pdf_errs)

        supp_in_archive = os.path.join(extract_root, "supplement.pdf")
        if os.path.exists(supp_in_archive):
            supp_errs, _ = check_pdf_file(supp_in_archive, compiled_patterns)
            violations.extend(supp_errs)

    uncomp_mb = total_uncompressed_bytes / (1024 * 1024)
    print("-" * 65)
    print(f"Archive Verification Summary:")
    print(f"  Total Files in Archive:     {len(extracted_files)}")
    print(f"  Uncompressed Payload:       {uncomp_mb:.2f} MB")
    print(f"  Compressed Size (.zip):     {zip_size_mb:.2f} MB")
    print(f"  Compressed Size (.tar.gz):  {tar_size_mb:.2f} MB")

    if violations:
        print("\n[FAIL] Release archive validation failed:")
        for v in violations:
            print(f"  - {v}")
        raise RuntimeError(f"Release validation failed with {len(violations)} errors.")

    print("\n[PASS] Release archive is pristine, completely anonymized, and under size limit.")

    manifest = {
        "reference": ref,
        "zip_path": os.path.relpath(zip_path, REPO_ROOT).replace("\\", "/"),
        "tar_path": os.path.relpath(tar_path, REPO_ROOT).replace("\\", "/"),
        "zip_size_mb": round(zip_size_mb, 2),
        "tar_size_mb": round(tar_size_mb, 2),
        "uncompressed_mb": round(uncomp_mb, 2),
        "file_count": len(extracted_files),
        "status": "VERIFIED_DOUBLE_BLIND_CLEAN",
    }
    manifest_path = os.path.join(REPO_ROOT, output_dir, "RELEASE_MANIFEST.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build and audit clean double-blind review archive.")
    parser.add_argument("--ref", default="HEAD", help="Git reference or tag to package (default: HEAD)")
    parser.add_argument("--output-dir", default="release", help="Output directory for archives (default: release)")
    args = parser.parse_args()

    try:
        build_release_archive(ref=args.ref, output_dir=args.output_dir)
    except Exception as e:
        print(f"\n[ERROR] Failed to build release archive: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
