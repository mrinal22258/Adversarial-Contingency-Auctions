"""
Test result model integrity and build provenance manifest.
"""

import os
import json
import hashlib
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.mark.core
def test_result_model_structure_and_hashes():
    model_path = os.path.join(REPO_ROOT, "results", "result_model_v1.json")
    assert os.path.exists(model_path), "results/result_model_v1.json must exist"

    with open(model_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    assert "version" in model
    assert "populations" in model
    assert "metrics" in model
    assert "contrasts" in model
    assert "input_hashes" in model

    # Check input hashes match current raw data
    raw_csv = os.path.join(REPO_ROOT, "results", "raw_results.csv")
    v5_csv = os.path.join(REPO_ROOT, "results", "confirmatory", "heldout_v5_results.csv")

    assert model["input_hashes"]["raw_results.csv"] == compute_sha256(raw_csv)
    assert model["input_hashes"]["heldout_v5_results.csv"] == compute_sha256(v5_csv)

    # Check populations
    assert "nominal_balanced_core" in model["populations"]
    assert "protocol_v5_confirmatory" in model["populations"]
    assert model["populations"]["nominal_balanced_core"]["instances"] == 750
    assert model["populations"]["protocol_v5_confirmatory"]["cell_N"] == 3600
    assert model["populations"]["protocol_v5_confirmatory"]["instances"] == 450

    # Check contrasts exist and have both cell and cluster p-values
    v5_contrasts = model["contrasts"]["protocol_v5_confirmatory"]
    assert len(v5_contrasts) >= 7
    for cid, cdata in v5_contrasts.items():
        assert "mean_diff" in cdata
        assert "cell_p_raw" in cdata
        assert "cluster_p_raw" in cdata
        assert "cell_p_adjusted" in cdata
        assert "cluster_p_adjusted" in cdata
        assert "cell_sig" in cdata
        assert "cluster_sig" in cdata


@pytest.mark.core
def test_numbers_macro_completeness():
    numbers_path = os.path.join(REPO_ROOT, "results", "numbers.tex")
    paper_path = os.path.join(REPO_ROOT, "paper.tex")

    assert os.path.exists(numbers_path)
    assert os.path.exists(paper_path)

    import re
    with open(paper_path, "r", encoding="utf-8") as f:
        paper_text = f.read()
    with open(numbers_path, "r", encoding="utf-8") as f:
        numbers_text = f.read()

    used = set(re.findall(r'\\(ae[A-Za-z0-9]+)', paper_text))
    defined = set(re.findall(r'\\newcommand{\\([A-Za-z0-9]+)}', numbers_text))

    missing = [m for m in used if m not in defined]
    assert len(missing) == 0, f"Macros used in paper.tex but missing from numbers.tex: {missing}"


@pytest.mark.core
def test_generate_numbers_fails_on_missing_key(tmp_path):
    from tools.generate_numbers_from_model import generate_numbers
    model_path = os.path.join(REPO_ROOT, "results", "result_model_v1.json")
    with open(model_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    # 1. Test deleting pval_adherence_instance_null raises KeyError
    m1 = json.loads(json.dumps(model))
    del m1["theorem_1_evidence"]["pval_adherence_instance_null"]
    p1 = tmp_path / "model1.json"
    p1.write_text(json.dumps(m1), encoding="utf-8")
    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p1), out_path=str(tmp_path / "out1.tex"))

    # 2. Test deleting adherence_pct raises KeyError
    m2 = json.loads(json.dumps(model))
    del m2["theorem_1_evidence"]["adherence_pct"]
    p2 = tmp_path / "model2.json"
    p2.write_text(json.dumps(m2), encoding="utf-8")
    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p2), out_path=str(tmp_path / "out2.tex"))

    # 3. Test deleting claimed_safe raises KeyError
    m3 = json.loads(json.dumps(model))
    del m3["theorem_1_evidence"]["claimed_safe"]
    p3 = tmp_path / "model3.json"
    p3.write_text(json.dumps(m3), encoding="utf-8")
    with pytest.raises(KeyError):
        generate_numbers(model_path=str(p3), out_path=str(tmp_path / "out3.tex"))

