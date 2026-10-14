"""Compute and store sha256 hashes for all key input and baseline artifacts."""
import hashlib
import json
import os

files_to_hash = [
    "results/confirmatory/heldout_v5_results.csv",
    "results/confirmatory/heldout_v5_runs.jsonl",
    "results/pilot/stage4_pilot_results.csv",
    "results/pilot/stage4_pilot_runs.jsonl",
    "paper.tex",
    "paper.pdf",
    "results/build_provenance.json",
    "results/numbers.tex",
    "results/table_heldout_v5.tex",
    "results/table_main_results.tex",
    "results/table_main_results.md",
    "results/table_per_condition.csv",
    "results/table_sitl.tex",
    "results/table_sitl.md",
    "results/table_stratified.tex",
    "results/table_stratified.md",
    "results/table_system_params.tex",
    "results/raw_results.csv",
    "results/runs.jsonl",
    "data/maps/manifest.json",
    "data/maps/warehouse-10-20-10-2-1.map",
    "data/maps/warehouse-20-40-10-2-1.map",
    "data/maps/boston_downtown_drive.graphml",
    "data/maps/boston_work_zones.csv",
    "audit/baseline_snapshot/manifest.json",
    "audit/baseline_snapshot/paper.pdf",
    "audit/baseline_snapshot/supplement.pdf",
]

hashes = {}
for relpath in files_to_hash:
    norm = relpath.replace("/", os.sep)
    if os.path.exists(norm):
        h = hashlib.sha256()
        with open(norm, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        hashes[relpath] = {
            "sha256": h.hexdigest(),
            "size_bytes": os.path.getsize(norm),
            "status": "PRESENT",
        }
    else:
        hashes[relpath] = {"status": "MISSING"}

os.makedirs("repro", exist_ok=True)
with open("repro/input_hashes.json", "w", encoding="utf-8") as f:
    json.dump(hashes, f, indent=2)

print(f"Stored {len(hashes)} file hashes in repro/input_hashes.json")
for k, v in hashes.items():
    print(f"  {k}: {v.get('sha256', 'MISSING')[:16]}... ({v.get('size_bytes', 0)} bytes)")
