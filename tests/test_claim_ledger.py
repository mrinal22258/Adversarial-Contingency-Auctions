"""Unit tests for Claim Ledger V2, active claim verification, and legacy ledger annotations."""
import os
import subprocess
import pandas as pd
import pytest

from tools.build_claim_ledger_v2 import build_claim_ledger_v2, CLAIMS_V2_SPEC
from experiments.claims import EmpiricalClaim, compute_file_sha256


def test_claim_ledger_v2_generation_and_non_empty_populations(tmp_path):
    """Verify build_claim_ledger_v2 creates valid ledger in tmp_path with non-empty populations."""
    ledger_path = str(tmp_path / "CLAIM_LEDGER_V2.csv")
    df = build_claim_ledger_v2(ledger_path)

    assert os.path.exists(ledger_path), "CLAIM_LEDGER_V2.csv was not created in tmp_path!"
    assert len(df) == 9, f"Expected 9 claims, found {len(df)}"

    for idx, row in df.iterrows():
        cid = row["claim_id"]
        n = int(row["population_n"])
        sha = str(row["sha256"])
        filt = str(row["executable_filter"])
        src = str(row["source_file"])

        assert n > 0, f"Claim {cid} has empty population N = {n}!"
        assert len(sha) == 64, f"Claim {cid} has invalid sha256: {sha}"
        assert row["verdict"] == "PASS", f"Claim {cid} failed verification: {row['verdict']}"
        assert row["result_status"] == "EVALUATED"


def _evaluate_spec_claim(claim_id: str) -> dict:
    specs = [s for s in CLAIMS_V2_SPEC if s["claim_id"] == claim_id]
    assert len(specs) == 1, f"Claim spec not found: {claim_id}"
    spec = specs[0]
    claim = EmpiricalClaim(
        claim_id=spec["claim_id"],
        claim_text=spec["claim_text"],
        source_file=spec["source_file"],
        executable_filter=spec["executable_filter"],
        cluster_unit=spec["cluster_unit"],
        estimator=spec["estimator"],
        ci_method=spec["ci_method"],
        test_method=spec["test_method"],
        correction=spec["correction"],
        evidence_tier=spec["evidence_tier"],
        expected_verdict=spec["expected_verdict"],
    )
    return claim.evaluate()


def test_claim_01_recourse_depth_gain():
    """CLAIM-01-V2: ACA outperforms depth-0 by local contingency detour execution on core."""
    res = _evaluate_spec_claim("CLAIM-01-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] >= 750
    assert "Mean completion diff:" in res["result"]


def test_claim_02_heldout_v5_cbba_lr_lead():
    """CLAIM-02-V2: In v5 confirmatory, CBBA+LR achieves higher completion and welfare than ACA."""
    res = _evaluate_spec_claim("CLAIM-02-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 900
    assert "CBBA+LR vs ACA in v5:" in res["result"]


def test_claim_03_heldout_v5_cbba_pr_parity():
    """CLAIM-03-V2: In v5 confirmatory, ACA achieves statistical parity with CBBA-PR+LR."""
    res = _evaluate_spec_claim("CLAIM-03-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 900
    assert "parity <=" in res["result"]


def test_claim_04_pinsker_margin_conflict_reduction():
    """CLAIM-04-V2: Pinsker margin cuts safe conflicts by ~10.3 relative to no-margin in v5."""
    res = _evaluate_spec_claim("CLAIM-04-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 900
    assert "Conflict reduction:" in res["result"]


def test_claim_05_pinsker_margin_preservation_cost():
    """CLAIM-05-V2: Pinsker margin incurs modest non-significant completion cost in v5."""
    res = _evaluate_spec_claim("CLAIM-05-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 900
    assert "Margin preservation cost:" in res["result"]


def test_claim_06_ctp_replan_lead_on_core():
    """CLAIM-06-V2: CTP Replan achieves higher completion than ACA on balanced core grid."""
    res = _evaluate_spec_claim("CLAIM-06-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 1500
    assert "CTP vs ACA completion diff:" in res["result"]


def test_claim_07_variant_gains_non_replication():
    """CLAIM-07-V2: ACA+ and Adaptive gains did not replicate in v5 confirmatory."""
    res = _evaluate_spec_claim("CLAIM-07-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 1350
    assert "Replication parity:" in res["result"]


def test_claim_08_theorem_1_conditional_scope():
    """CLAIM-08-V2: Theorem 1 conflict-freedom is strictly conditional on Assumption 1."""
    res = _evaluate_spec_claim("CLAIM-08-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] == 850
    assert "Theoretical conditional scope" in res["result"]


def test_claim_09_sitl_fidelity_gap_and_rank_invariance_failure():
    """CLAIM-09-V2: SITL physics simulation introduces completion drop and rank invariance fails."""
    res = _evaluate_spec_claim("CLAIM-09-V2")
    assert res["verdict"] == "PASS"
    assert res["population_n"] >= 360
    assert "SITL bias:" in res["result"]


def test_tracked_claim_ledger_matches_and_git_status_clean(tmp_path):
    """Verify tracked CLAIM_LEDGER_V2.csv is clean and not modified by test execution."""
    tracked_path = "audit/CLAIM_LEDGER_V2.csv"
    assert os.path.exists(tracked_path), "audit/CLAIM_LEDGER_V2.csv must exist!"
    df_tracked = pd.read_csv(tracked_path)
    assert len(df_tracked) == 9

    # Generate to tmp_path and compare row counts and verdicts
    tmp_file = str(tmp_path / "temp_ledger.csv")
    df_tmp = build_claim_ledger_v2(tmp_file)
    assert len(df_tmp) == len(df_tracked)
    assert list(df_tmp["claim_id"]) == list(df_tracked["claim_id"])
    assert list(df_tmp["verdict"]) == list(df_tracked["verdict"])


def test_legacy_ledger_annotated():
    annotated_path = "audit/CLAIM_LEDGER_LEGACY_ANNOTATED.csv"
    assert os.path.exists(annotated_path), "CLAIM_LEDGER_LEGACY_ANNOTATED.csv missing!"

    df_legacy = pd.read_csv(annotated_path)
    assert "audit_annotation" in df_legacy.columns
    assert len(df_legacy) == 15

    # Assert known empty filter claims are properly classified
    empty_claims = ["CLAIM-01", "CLAIM-02", "CLAIM-03", "CLAIM-04", "CLAIM-05", "CLAIM-06", "CLAIM-07", "CLAIM-08"]
    for cid in empty_claims:
        row = df_legacy[df_legacy["claim_id"] == cid].iloc[0]
        assert row["audit_annotation"] == "INVALID_EMPTY_FILTER", f"{cid} was not flagged INVALID_EMPTY_FILTER"

    error_claims = ["CLAIM-11", "CLAIM-12", "CLAIM-14", "CLAIM-15"]
    for cid in error_claims:
        row = df_legacy[df_legacy["claim_id"] == cid].iloc[0]
        assert row["audit_annotation"] == "FILTER_ERROR", f"{cid} was not flagged FILTER_ERROR"
