"""
Acceptance tests for Gate 5: Protocol Preparation, Verification Tooling, Smoke Run, and CI Configuration.
"""

import os
import sys
import yaml
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.verify_protocol import verify_protocol
from tools.verify_log_integrity import verify_log_integrity


@pytest.mark.core
def test_gate5_protocol_v6_valid():
    """Verify that protocol_v6.yaml passes strict protocol verification."""
    res = verify_protocol(
        config_path="experiments/configs/protocol_v6.yaml",
        prereg_path="protocols/prereg-v6.md",
        strict=False,  # strict git check tested separately
    )
    assert res["valid"], f"Protocol v6 verification failed: {res['errors']}"
    assert res["conf_seeds_count"] == 50
    assert res["dev_seeds_count"] == 15
    assert res["status"] == "REGISTERED_FROZEN"
    assert res["version"] == "6.1.0"


@pytest.mark.core
def test_gate5_protocol_rejection_on_tampered_seeds(tmp_path):
    """Verify that verify_protocol rejects modified seeds or bad thresholds."""
    with open(os.path.join(REPO_ROOT, "experiments", "configs", "protocol_v6.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Tamper with confirmatory seeds
    cfg["evaluation_design"]["confirmatory_phase"]["seeds"][0] = 99999
    bad_cfg_file = tmp_path / "bad_protocol.yaml"
    with open(bad_cfg_file, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f)

    res = verify_protocol(str(bad_cfg_file), prereg_path="protocols/prereg-v6.md", strict=False)
    assert not res["valid"]
    assert any("Confirmatory seeds" in e for e in res["errors"])


@pytest.mark.core
def test_gate5_protocol_rejection_on_inactive_pruning(tmp_path):
    """Verify that verify_protocol rejects aca_plus prune_threshold <= 0.12."""
    with open(os.path.join(REPO_ROOT, "experiments", "configs", "protocol_v6.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Inactive threshold
    cfg["evaluated_methods"]["aca_plus"]["allocator_kwargs"]["prune_threshold"] = 0.06
    bad_cfg_file = tmp_path / "bad_pruning.yaml"
    with open(bad_cfg_file, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f)

    res = verify_protocol(str(bad_cfg_file), prereg_path="protocols/prereg-v6.md", strict=False)
    assert not res["valid"]
    assert any("prune_threshold must be strictly > 0.12" in e for e in res["errors"])


@pytest.mark.core
def test_gate5_smoke_artifacts_integrity():
    """Verify that smoke run output exists, passed log integrity, and has disclaimer."""
    smoke_dir = os.path.join(REPO_ROOT, "results", "smoke")
    csv_path = os.path.join(smoke_dir, "results.csv")
    jsonl_path = os.path.join(smoke_dir, "runs.jsonl")
    readme_path = os.path.join(smoke_dir, "README.md")
    log_path = os.path.join(smoke_dir, "smoke_pipeline.log")

    assert os.path.exists(csv_path), "results/smoke/results.csv missing"
    assert os.path.exists(jsonl_path), "results/smoke/runs.jsonl missing"
    assert os.path.exists(readme_path), "results/smoke/README.md missing"
    assert os.path.exists(log_path), "results/smoke/smoke_pipeline.log missing"

    # Check disclaimer in README
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
    assert "NOT EMPIRICAL EVIDENCE" in readme_content

    # Strict log integrity check on smoke artifacts
    integrity = verify_log_integrity(csv_path, jsonl_path, strict=True, require_record_hashes=True)
    assert integrity["is_clean"]
    assert integrity["csv_rows"] == 4
    assert integrity["jsonl_valid_records"] == 4
    assert integrity["hash_mismatches"] == 0


@pytest.mark.core
def test_gate5_run_v6_and_ci_documentation():
    """Verify that RUN_V6.md and CI workflows exist and specify required commands."""
    run_v6_path = os.path.join(REPO_ROOT, "RUN_V6.md")
    ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
    lock_path = os.path.join(REPO_ROOT, "requirements.lock")

    assert os.path.exists(run_v6_path), "RUN_V6.md missing"
    assert os.path.exists(ci_path), ".github/workflows/ci.yml missing"
    assert os.path.exists(lock_path), "requirements.lock missing"

    with open(run_v6_path, "r", encoding="utf-8") as f:
        run_v6 = f.read()
    assert "tools/verify_protocol.py" in run_v6
    assert "tools/verify_log_integrity.py" in run_v6
    assert "tools/build_all_results.py" in run_v6
    assert "tools/lint_paper.py" in run_v6
    assert "experiments/run_sweep.py --protocol v6" in run_v6

    with open(ci_path, "r", encoding="utf-8") as f:
        ci = f.read()
    assert "tools/verify_protocol.py" in ci
    assert "tools/lint_paper.py" in ci
    assert "requirements.lock" in ci
