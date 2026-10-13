"""Unit tests for Claim Ledger V2 and legacy ledger annotations."""
import os
import pandas as pd
import pytest

from tools.build_claim_ledger_v2 import build_claim_ledger_v2


def test_claim_ledger_v2_generation_and_non_empty_populations():
    ledger_path = "audit/CLAIM_LEDGER_V2.csv"
    df = build_claim_ledger_v2(ledger_path)
    
    assert os.path.exists(ledger_path), "CLAIM_LEDGER_V2.csv was not created!"
    assert len(df) >= 8, f"Expected >= 8 claims, found {len(df)}"
    
    # Check each claim has non-empty population and valid sha256
    for idx, row in df.iterrows():
        cid = row["claim_id"]
        n = int(row["population_n"])
        sha = str(row["sha256"])
        filt = str(row["executable_filter"])
        src = str(row["source_file"])
        
        assert n > 0, f"Claim {cid} has empty population N = {n}!"
        assert len(sha) == 64, f"Claim {cid} has invalid sha256: {sha}"
        assert row["verdict"] in ["PASS", "FAIL"], f"Claim {cid} has invalid verdict: {row['verdict']}"
        
        # Verify filter actually executes on source file
        src_df = pd.read_csv(src)
        matched = src_df.query(filt)
        assert len(matched) == n, f"Filter count mismatch for {cid}: expected {n}, got {len(matched)}"


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
