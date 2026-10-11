"""
Create audit/baseline_snapshot/ with all generated artifacts, manifests, and system state.
"""

import os
import sys
import shutil
import hashlib
import json
import datetime
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIT_DIR = os.path.join(REPO_ROOT, "audit")
SNAPSHOT_DIR = os.path.join(AUDIT_DIR, "baseline_snapshot")


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_artifacts():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    manifest = {}

    # Target generated artifacts to snapshot
    artifact_patterns = [
        "results/numbers.tex",
        "results/table_main_results.tex",
        "results/table_main_results.md",
        "results/table_sitl.tex",
        "results/table_sitl.md",
        "results/table_stratified.tex",
        "results/table_stratified.md",
        "results/table_per_condition.csv",
        "results/run_metadata.json",
        "results/config_used.yaml",
        "results/power_analysis.csv",
        "results/demo_baseline_20seeds.json",
        "paper.pdf",
        "supplement.pdf",
    ]

    for p in artifact_patterns:
        src = os.path.join(REPO_ROOT, p)
        if os.path.exists(src):
            dst = os.path.join(SNAPSHOT_DIR, p.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            manifest[p] = {
                "sha256": file_sha256(src),
                "size_bytes": os.path.getsize(src),
                "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(src), tz=datetime.timezone.utc).isoformat()
            }

    # Snapshot results/figures and docs/screenshots
    for folder in ["results/figures", "docs/screenshots", "results/sitl/vision"]:
        src_folder = os.path.join(REPO_ROOT, folder)
        if os.path.exists(src_folder):
            for fname in os.listdir(src_folder):
                src_file = os.path.join(src_folder, fname)
                if os.path.isfile(src_file):
                    rel = f"{folder}/{fname}".replace("\\", "/")
                    dst_file = os.path.join(SNAPSHOT_DIR, folder.replace("/", os.sep), fname)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    manifest[rel] = {
                        "sha256": file_sha256(src_file),
                        "size_bytes": os.path.getsize(src_file),
                        "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(src_file), tz=datetime.timezone.utc).isoformat()
                    }

    manifest_path = os.path.join(SNAPSHOT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Snapshotted {len(manifest)} generated artifacts to {SNAPSHOT_DIR}")
    return manifest


def inventory_repository():
    inventory = {}
    scan_dirs = ["acalib", "experiments", "results", "data", "tests", "tools", "docs"]
    top_files = [
        "app.py", "generate_paper_figures.py", "index.html", "paper.tex",
        "supplement.tex", "references.bib", "Makefile", "requirements.txt",
        "requirements-demo.txt", "README.md", "RESULTS_VERDICT.md", "CHANGELOG_APP.md",
        "CHANGELOG_FIX.md"
    ]

    for tf in top_files:
        p = os.path.join(REPO_ROOT, tf)
        if os.path.exists(p):
            inventory[tf] = {
                "sha256": file_sha256(p),
                "size_bytes": os.path.getsize(p),
                "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(p), tz=datetime.timezone.utc).isoformat()
            }

    for sd in scan_dirs:
        root_dir = os.path.join(REPO_ROOT, sd)
        if not os.path.exists(root_dir):
            continue
        for r, _, files in os.walk(root_dir):
            for f in files:
                full_p = os.path.join(r, f)
                rel_p = os.path.relpath(full_p, REPO_ROOT).replace("\\", "/")
                # Skip massive data files from full sha if needed, but here files are reasonably sized
                # runs.jsonl is 14MB, raw_results.csv is 4.7MB - we can hash them fine
                if "per_claim_evaluations.jsonl" in f:
                    # 18MB, still fast to hash
                    pass
                inventory[rel_p] = {
                    "sha256": file_sha256(full_p),
                    "size_bytes": os.path.getsize(full_p),
                    "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(full_p), tz=datetime.timezone.utc).isoformat()
                }

    inv_path = os.path.join(AUDIT_DIR, "repository_inventory.json")
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)
    print(f"Inventoried {len(inventory)} repository files to {inv_path}")
    return inventory


if __name__ == "__main__":
    snapshot_artifacts()
    inventory_repository()
