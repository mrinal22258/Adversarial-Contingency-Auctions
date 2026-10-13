import json
import hashlib
from pathlib import Path
import pytest

@pytest.mark.core
def test_build_manifest_hashes_match_artifacts():
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "results" / "build_provenance.json"
    
    assert manifest_path.exists(), f"Provenance manifest not found at {manifest_path}"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    assert "artifacts" in manifest, "Manifest missing 'artifacts' key"
    artifacts = manifest["artifacts"]
    assert len(artifacts) >= 10, f"Expected at least 10 artifacts in manifest, got {len(artifacts)}"
    
    # Check that required keys are present
    required_files = [
        "results/raw_results.csv",
        "results/confirmatory/heldout_v5_results.csv",
        "results/result_model_v1.json",
        "results/numbers.tex",
        "results/table_main_results.tex",
        "results/table_heldout_v5.tex",
        "audit/CLAIM_LEDGER.csv",
        "audit/CLAIM_LEDGER_V2.csv",
    ]
    
    for rel_path in required_files:
        assert rel_path in artifacts, f"Required artifact {rel_path} missing from manifest"
        
    for rel_path, meta in artifacts.items():
        file_path = repo_root / rel_path
        assert file_path.exists(), f"Artifact file {file_path} listed in manifest does not exist on disk"
        
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            content = f.read()
            hasher.update(content)
        actual_hash = hasher.hexdigest()
        actual_bytes = len(content)
        
        expected_hash = meta["sha256"]
        expected_bytes = meta["bytes"]
        
        assert actual_bytes == expected_bytes, (
            f"Byte count mismatch for {rel_path}: expected {expected_bytes}, got {actual_bytes}"
        )
        assert actual_hash == expected_hash, (
            f"SHA256 mismatch for {rel_path}: manifest={expected_hash}, disk={actual_hash}"
        )
