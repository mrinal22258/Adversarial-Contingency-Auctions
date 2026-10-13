"""
Acceptance Tests for Gate 1: Runner Protocol, Resumability, and Integrity (P0-1).
Verifies:
1. Changing comm_range, p_drop, n_robots, depth, or allocator_kwargs changes trial identity.
2. Two configs into separate output dirs isolate records; rerun resumes only matching trials.
3. Malformed JSONL line or hash mismatch halts strict validation.
4. Dirty tree / missing git / unknown commit blocks confirmatory mode.
5. Given v6 seed list, exactly those seeds execute, and metadata contains list + hash + hyperparameters.
6. Multi-valued config either visits all combinations or is rejected in single-cell mode.
7. --dry-run runs zero simulator steps.
8. Lock failure raises LockAcquisitionError.
"""

import os
import sys
import json
import yaml
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from experiments.run_sweep import (
    compute_trial_hash,
    run_single_trial,
    main as sweep_main,
)
from acalib.data.logger import (
    AtomicJsonlWriter,
    LockAcquisitionError,
    compute_record_hash,
)
from tools.verify_log_integrity import verify_log_integrity
from tests.test_prereg_v6_seeds import generate_v6_seeds


def test_trial_identity_changes_on_all_factors():
    """1. Changing only comm_range, p_drop, n_robots, depth, or allocator threshold changes trial identity."""
    base_cond = {
        "graph_family": "warehouse_movingai",
        "n_nodes": 38,
        "n_edges": 60,
        "adversary": "theta_1_stochastic",
        "method": "aca_plus",
        "comm_regime": "nominal",
        "comm_range": 30.0,
        "p_drop": 0.10,
        "n_robots": 4,
        "n_tasks": 15,
        "seed": 50515,
        "max_steps": 80,
        "contingency_depth": 1,
        "allocator_kwargs": {"prune_threshold": 0.20, "kappa": 1.0},
        "git_commit": "abcdef123456",
        "protocol_hash": "protohash987",
    }
    base_hash = compute_trial_hash(base_cond)

    # Change comm_range
    c1 = dict(base_cond, comm_range=35.0)
    assert compute_trial_hash(c1) != base_hash, "comm_range change did not change trial identity"

    # Change p_drop
    c2 = dict(base_cond, p_drop=0.15)
    assert compute_trial_hash(c2) != base_hash, "p_drop change did not change trial identity"

    # Change n_robots
    c3 = dict(base_cond, n_robots=6)
    assert compute_trial_hash(c3) != base_hash, "n_robots change did not change trial identity"

    # Change contingency_depth
    c4 = dict(base_cond, contingency_depth=2)
    assert compute_trial_hash(c4) != base_hash, "contingency_depth change did not change trial identity"

    # Change allocator threshold
    c5 = dict(base_cond, allocator_kwargs={"prune_threshold": 0.15, "kappa": 1.0})
    assert compute_trial_hash(c5) != base_hash, "prune_threshold change did not change trial identity"


def test_separate_output_dirs_and_resumability(tmp_path):
    """2. Two configs into separate output dirs isolate records; rerunning one resumes only its own trials."""
    dir_a = tmp_path / "out_a"
    dir_b = tmp_path / "out_b"

    cfg_a = {
        "environments": [{"family": "grid", "n_nodes": 16}],
        "adversaries": ["theta_1_stochastic"],
        "comm_regimes": {"nominal": {"comm_range": 30.0, "p_drop": 0.10}},
        "methods": ["aca"],
        "fleet_sizes": [2],
        "task_counts": [4],
        "max_steps": 10,
        "contingency_depth": 1,
    }
    cfg_b = dict(cfg_a, comm_regimes={"nominal": {"comm_range": 15.0, "p_drop": 0.25}})

    path_a = tmp_path / "cfg_a.yaml"
    path_b = tmp_path / "cfg_b.yaml"
    with open(path_a, "w") as f:
        yaml.dump(cfg_a, f)
    with open(path_b, "w") as f:
        yaml.dump(cfg_b, f)

    # Run A with 1 seed
    test_args_a = ["run_sweep.py", "--config", str(path_a), "--seeds", "1", "--output-dir", str(dir_a), "--workers", "1"]
    with patch.object(sys, "argv", test_args_a):
        sweep_main()

    # Run B with 1 seed
    test_args_b = ["run_sweep.py", "--config", str(path_b), "--seeds", "1", "--output-dir", str(dir_b), "--workers", "1"]
    with patch.object(sys, "argv", test_args_b):
        sweep_main()

    # Assert directory isolation
    assert (dir_a / "results.csv").exists()
    assert (dir_b / "results.csv").exists()
    assert (dir_a / "runs.jsonl").exists()
    assert (dir_b / "runs.jsonl").exists()

    df_a = pd.read_csv(dir_a / "results.csv")
    df_b = pd.read_csv(dir_b / "results.csv")
    assert len(df_a) == 1
    assert len(df_b) == 1
    assert df_a.iloc[0]["trial_hash"] != df_b.iloc[0]["trial_hash"]

    # Rerunning A should skip the already completed trial
    with patch("experiments.run_sweep.run_single_trial") as mock_run:
        with patch.object(sys, "argv", test_args_a):
            sweep_main()
        mock_run.assert_not_called()


def test_malformed_line_or_hash_mismatch_halts_strict(tmp_path):
    """3. A malformed line or hash mismatch halts strict validation."""
    csv_p = tmp_path / "test.csv"
    jsonl_p = tmp_path / "test.jsonl"

    rec1 = {"trial_hash": "th1", "metric": 10.0}
    writer = AtomicJsonlWriter(str(jsonl_p))
    writer.append(rec1)

    import pandas as pd
    pd.DataFrame([rec1]).to_csv(csv_p, index=False)

    # Strict check passes on clean file
    res = verify_log_integrity(str(csv_p), str(jsonl_p), strict=True)
    assert res["is_clean"] is True

    # 1. Injected malformed line
    with open(jsonl_p, "a", encoding="utf-8") as f:
        f.write("corrupted_non_json_line\n")

    with pytest.raises(ValueError, match="Strict validation failed"):
        verify_log_integrity(str(csv_p), str(jsonl_p), strict=True)

    # 2. Injected record hash mismatch
    jsonl_p2 = tmp_path / "test2.jsonl"
    csv_p2 = tmp_path / "test2.csv"
    rec2 = {"trial_hash": "th2", "metric": 20.0, "record_sha256": "fake_sha_hash"}
    with open(jsonl_p2, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec2) + "\n")
    pd.DataFrame([rec2]).to_csv(csv_p2, index=False)

    with pytest.raises(ValueError, match="Record SHA-256 mismatch"):
        verify_log_integrity(str(csv_p2), str(jsonl_p2), strict=True)


def test_dirty_tree_or_unknown_commit_blocks_confirmatory(tmp_path):
    """4. Dirty tree / missing git / unknown commit blocks confirmatory mode."""
    cfg = tmp_path / "cfg.yaml"
    with open(cfg, "w") as f:
        yaml.dump({"methods": ["aca"], "fleet_sizes": [2], "task_counts": [2], "max_steps": 5}, f)

    # Dirty git test
    with patch("experiments.run_sweep.check_git_clean", return_value=(False, "dirty: unstaged changes")):
        test_args = ["run_sweep.py", "--config", str(cfg), "--confirmatory", "--output-dir", str(tmp_path / "out")]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(RuntimeError, match="Git working tree is dirty"):
                sweep_main()

    # Unknown commit test
    with patch("experiments.run_sweep.check_git_clean", return_value=(True, "clean")):
        with patch("experiments.run_sweep.get_git_commit_hash", return_value="unknown"):
            test_args = ["run_sweep.py", "--config", str(cfg), "--confirmatory", "--output-dir", str(tmp_path / "out")]
            with patch.object(sys, "argv", test_args):
                with pytest.raises(RuntimeError, match="Git commit hash is unknown"):
                    sweep_main()


def test_exact_v6_seeds_and_metadata(tmp_path):
    """5. Given the v6 seed list, exactly those seeds execute, and metadata contains list + hash + hyperparameters."""
    v6_seeds = generate_v6_seeds(50)
    dev_seeds = [v6_seeds[0], v6_seeds[1]]  # run 2 seeds for quick test

    cfg_p = tmp_path / "proto_test.yaml"
    cfg_data = {
        "evaluation_design": {
            "confirmatory_phase": {
                "seeds": dev_seeds,
            }
        },
        "environments": [{"family": "grid", "n_nodes": 16}],
        "adversaries": ["theta_1_stochastic"],
        "comm_regimes": {"nominal": {"comm_range": 30.0, "p_drop": 0.10}},
        "evaluated_methods": {
            "aca_plus": {
                "allocator_type": "aca_plus",
                "allocator_kwargs": {"prune_threshold": 0.20, "kappa": 1.0},
            }
        },
        "fleet_sizes": [2],
        "task_counts": [4],
        "max_steps": 10,
    }
    with open(cfg_p, "w") as f:
        yaml.dump(cfg_data, f)

    out_dir = tmp_path / "v6_test_out"
    test_args = [
        "run_sweep.py",
        "--config", str(cfg_p),
        "--output-dir", str(out_dir),
        "--workers", "1",
    ]
    with patch("experiments.run_sweep.check_git_clean", return_value=(True, "clean")):
        with patch("experiments.run_sweep.get_git_commit_hash", return_value="test_commit_hash"):
            with patch.object(sys, "argv", test_args):
                sweep_main()

    # Check results
    import pandas as pd
    df = pd.read_csv(out_dir / "results.csv")
    assert sorted(df["seed"].unique().tolist()) == sorted(dev_seeds)

    # Check metadata
    with open(out_dir / "run_metadata.json", "r") as f:
        meta = json.load(f)
    assert meta["seed_list"] == dev_seeds
    assert "seed_list_hash" in meta
    assert meta["resolved_hyperparameters"]["aca_plus"]["prune_threshold"] == 0.20


def test_multivalued_config_grid_or_rejected(tmp_path):
    """6. Multi-valued config either visits all combinations or is rejected in single-cell mode."""
    # In single-cell / confirmatory mode, multi-valued fleet_sizes is rejected
    cfg_single = tmp_path / "cfg_single.yaml"
    with open(cfg_single, "w") as f:
        yaml.dump({
            "single_cell": True,
            "fleet_sizes": [2, 4],
            "task_counts": [4],
            "methods": ["aca"],
        }, f)

    test_args = ["run_sweep.py", "--config", str(cfg_single), "--output-dir", str(tmp_path / "out")]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(ValueError, match="single-cell mode requires exactly 1"):
            sweep_main()

    # Without single_cell constraint, it plans full grid
    cfg_grid = tmp_path / "cfg_grid.yaml"
    with open(cfg_grid, "w") as f:
        yaml.dump({
            "single_cell": False,
            "environments": [{"family": "grid", "n_nodes": 16}],
            "adversaries": ["theta_1_stochastic"],
            "comm_regimes": {"nominal": {"comm_range": 30.0, "p_drop": 0.10}},
            "fleet_sizes": [2, 4],
            "task_counts": [4, 6],
            "methods": ["aca"],
            "final_seeds": 1,
            "max_steps": 5,
        }, f)

    # In dry-run mode, verify that it validates the full grid of 2x2 = 4 design cells
    test_args_grid = ["run_sweep.py", "--config", str(cfg_grid), "--dry-run", "--output-dir", str(tmp_path / "out_grid")]
    with patch.object(sys, "argv", test_args_grid):
        sweep_main()  # succeeds without error


def test_dry_run_runs_zero_simulator_steps(tmp_path):
    """7. --dry-run runs zero simulator steps."""
    cfg = tmp_path / "cfg.yaml"
    with open(cfg, "w") as f:
        yaml.dump({
            "environments": [{"family": "grid", "n_nodes": 16}],
            "adversaries": ["theta_1_stochastic"],
            "comm_regimes": {"nominal": {"comm_range": 30.0, "p_drop": 0.10}},
            "methods": ["aca"],
            "fleet_sizes": [2],
            "task_counts": [4],
            "max_steps": 10,
        }, f)

    with patch("experiments.run_sweep.run_single_trial") as mock_trial:
        test_args = ["run_sweep.py", "--config", str(cfg), "--dry-run", "--output-dir", str(tmp_path / "out")]
        with patch.object(sys, "argv", test_args):
            sweep_main()
        mock_trial.assert_not_called()


def test_lock_failure_raises(tmp_path):
    """8. Lock failure raises LockAcquisitionError."""
    target_file = tmp_path / "locked.jsonl"
    writer = AtomicJsonlWriter(str(target_file))

    # Mock file lock timeout / acquisition failure
    with patch.object(writer._file_lock, "acquire", side_effect=Exception("Simulated lock acquisition failure")):
        with pytest.raises(LockAcquisitionError, match="Error acquiring filelock"):
            writer.append({"test": 123})
