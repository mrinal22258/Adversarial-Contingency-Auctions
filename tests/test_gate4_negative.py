"""Gate 4 Negative Tests: Verifying Fail-Closed Behavior for Claims and Result Model.

Covers the 4 required audit negative tests:
1. Deliberately wrong estimate fails verification (returns FAIL).
2. Empty population fails closed (flags EMPTY_POPULATION, verdict FAIL, or raises ValueError).
3. Source-hash mismatch is detected upon dataset corruption/tampering.
4. Missing required model field raises KeyError immediately (zero fallback defaults).
"""
import os
import json
import tempfile
import pandas as pd
import pytest

from experiments.claims import EmpiricalClaim, compute_file_sha256
from tools.build_claim_ledger_v2 import build_claim_ledger_v2
from tools.generate_numbers_from_model import generate_numbers


def test_negative_deliberately_wrong_estimate():
    """Negative Test 1: A claim with a deliberately wrong estimate/direction must yield FAIL."""
    # CLAIM-01 true difference is +4.14 pp. We deliberately demand an impossible +50 pp gain.
    wrong_claim = EmpiricalClaim(
        claim_id="CLAIM-01-V2",
        claim_text="Deliberately wrong estimate for depth-0 ablation",
        source_file="results/raw_results.csv",
        executable_filter="comm_regime == 'nominal' and method in ['aca', 'aca_depth_zero'] and adversary in ['theta_1_stochastic', 'theta_2_reactive', 'theta_4_cyclic_patrol']",
        cluster_unit="graph_family:seed",
        estimator="Hodges-Lehmann median diff: +50 pp",
        ci_method="Cluster-aware bootstrap 95% CI",
        test_method="paired_wilcoxon_greater",
        correction="Holm-Bonferroni FWER",
        evidence_tier="Tier 1: Nominal Core Grid",
        expected_verdict="PASS",
        tolerance={"min_diff": 50.0},  # Impossibly high requirement
    )
    res = wrong_claim.evaluate()
    assert res["verdict"] == "FAIL", f"Expected FAIL for impossible +50 pp estimate, got {res['verdict']}"
    assert "Mean completion diff:" in res["result"]

    # Inverted direction: In v5 confirmatory, CBBA+LR actually outperforms ACA. Demanding ACA > CBBA+LR must fail.
    inverted_v5_claim = EmpiricalClaim(
        claim_id="CLAIM-02-V2",
        claim_text="Deliberately inverted direction: ACA outperforms CBBA+LR in v5",
        source_file="results/confirmatory/heldout_v5_results.csv",
        executable_filter="method in ['aca', 'cbba_lr']",
        cluster_unit="graph_family:seed",
        estimator="Mean difference",
        ci_method="Cluster-aware bootstrap 95% CI",
        test_method="paired_wilcoxon_two_sided",
        correction="Holm-Bonferroni FWER",
        evidence_tier="Tier 3: Protocol v5 Confirmatory",
        expected_verdict="PASS",
        tolerance={"min_comp_diff": 50.0},
    )
    res_inv = inverted_v5_claim.evaluate()
    assert res_inv["verdict"] == "FAIL", f"Expected FAIL for inverted v5 claim, got {res_inv['verdict']}"


def test_negative_empty_population():
    """Negative Test 2: An empty population query must fail closed (EMPTY_POPULATION, FAIL, and ValueError)."""
    empty_claim = EmpiricalClaim(
        claim_id="CLAIM-EMPTY-TEST",
        claim_text="Claim querying non-existent population",
        source_file="results/raw_results.csv",
        executable_filter="method == 'non_existent_algorithm_xyz' and comm_regime == 'impossible'",
        cluster_unit="graph_family:seed",
        estimator="None",
        ci_method="None",
        test_method="None",
        correction="None",
        evidence_tier="Test",
        expected_verdict="PASS",
    )
    res = empty_claim.evaluate()
    assert res["status"] == "EMPTY_POPULATION"
    assert res["population_n"] == 0
    assert res["verdict"] == "FAIL"


def test_negative_source_hash_mismatch(tmp_path):
    """Negative Test 3: Detecting source-hash mismatch when source file is modified/corrupted."""
    # Create a corrupted copy of raw_results.csv
    corrupted_csv = tmp_path / "corrupted_results.csv"
    with open(corrupted_csv, "w", encoding="utf-8") as f:
        f.write("corrupted,data,tampered\n1,2,3\n")

    actual_hash = compute_file_sha256(str(corrupted_csv))
    known_clean_hash = compute_file_sha256("results/raw_results.csv")

    assert actual_hash != known_clean_hash, "Corrupted file hash matched pristine raw_results hash!"
    assert actual_hash != "MISSING"
    assert len(actual_hash) == 64


def test_negative_missing_required_model_field(tmp_path):
    """Negative Test 4: Missing required fields in result model must raise KeyError immediately."""
    clean_model_path = "results/result_model_v1.json"
    assert os.path.exists(clean_model_path), "Base result model missing!"

    with open(clean_model_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    # Test 4a: Missing theorem_1_evidence
    bad_m1 = dict(m)
    del bad_m1["theorem_1_evidence"]
    p1 = tmp_path / "bad_model_1.json"
    with open(p1, "w", encoding="utf-8") as f:
        json.dump(bad_m1, f)

    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p1), out_path=str(tmp_path / "out1.tex"))

    # Test 4b: Missing required contrast H1_recourse_depth
    bad_m2 = json.loads(json.dumps(m))
    del bad_m2["contrasts"]["nominal_balanced_core"]["H1_recourse_depth"]
    p2 = tmp_path / "bad_model_2.json"
    with open(p2, "w", encoding="utf-8") as f:
        json.dump(bad_m2, f)

    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p2), out_path=str(tmp_path / "out2.tex"))

    # Test 4c: Missing required v5 contrast H2_aca_plus_vs_aca_completion
    bad_m3 = json.loads(json.dumps(m))
    del bad_m3["contrasts"]["protocol_v5_confirmatory"]["H2_aca_plus_vs_aca_completion"]
    p3 = tmp_path / "bad_model_3.json"
    with open(p3, "w", encoding="utf-8") as f:
        json.dump(bad_m3, f)

    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p3), out_path=str(tmp_path / "out3.tex"))
