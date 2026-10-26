"""
tests/test_readme_and_numbers_linter.py - Tests for README Generation and Number Integrity.

Tests:
1. Valid README rendering matches current README.md byte-for-byte.
2. Missing field in result model causes render_readme to fail.
3. Injected/tampered number in README.md causes linter to fail.
4. Injected number outside generated blocks in index.html / docs causes linter to fail.
5. Current repository state passes lint_all_numbers with 0 violations.
"""

import os
import copy
import pytest
from pathlib import Path

from tools.render_readme import render_readme, get_nested
from tools.lint_numbers import lint_all_numbers, check_readme_sync, check_file_empirical_literals

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.core
def test_readme_matches_render_output():
    """Verify that README.md on disk is 100% in sync with render_readme()."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md must exist on disk"
    with open(readme_path, "r", encoding="utf-8") as f:
        disk_content = f.read()

    rendered = render_readme(write_to_file=False)
    assert disk_content == rendered, "README.md on disk diverged from rendered template output"


@pytest.mark.core
def test_missing_model_field_fails_rendering(tmp_path):
    """Verify that deleting a required metric like tv_adherence_pct causes render_readme to fail."""
    import json
    model_path = REPO_ROOT / "results" / "result_model_v1.json"
    with open(model_path, "r", encoding="utf-8") as f:
        full_model = json.load(f)

    bad_model = copy.deepcopy(full_model)
    th1_sec = bad_model.get("theorem_1_evidence", bad_model.get("theorem_1", {}))
    assert "tv_adherence_pct" in th1_sec, "Baseline result model must contain tv_adherence_pct"
    del th1_sec["tv_adherence_pct"]

    with pytest.raises(KeyError) as exc_info:
        render_readme(model_override=bad_model, write_to_file=False)
    assert "tv_adherence_pct" in str(exc_info.value)


@pytest.mark.core
def test_missing_or_invalid_test_log_fails_rendering(tmp_path):
    """Verify that missing or unparseable test logs cause render_readme / parse_latest_test_log to fail."""
    from tools.render_readme import parse_latest_test_log

    # Empty directory with no test log files
    empty_dir = tmp_path / "empty_logs"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        parse_latest_test_log(logs_dir=str(empty_dir))

    # Invalid directory with garbage text log
    bad_log_dir = tmp_path / "bad_logs"
    bad_log_dir.mkdir()
    (bad_log_dir / "final.txt").write_text("Corrupted log without pass line\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        parse_latest_test_log(logs_dir=str(bad_log_dir))


@pytest.mark.core
def test_tampered_number_in_readme_fails_sync(tmp_path, monkeypatch):
    """Verify that a tampered or injected empirical number in README.md is caught by sync check."""
    fake_readme = tmp_path / "README.md"
    fake_readme.write_text("Tampered README with fake number 99.9% completion\n", encoding="utf-8")

    import tools.lint_numbers as ln
    monkeypatch.setattr(ln, "REPO_ROOT", str(tmp_path))

    errors = check_readme_sync()
    assert len(errors) > 0, "Expected sync check to fail on tampered README.md"
    assert "tampered" in errors[0].lower() or "diverged" in errors[0].lower() or "not match" in errors[0].lower()


@pytest.mark.core
def test_injected_empirical_literal_outside_block_fails(tmp_path):
    """Verify that injecting an un-macroed percentage or p-value outside a generated block fails."""
    bad_html = tmp_path / "index.html"
    bad_html.write_text(
        "<html><body><p>Our method achieves 99.4% task completion with p = 0.0001.</p></body></html>",
        encoding="utf-8",
    )

    errors = check_file_empirical_literals(str(bad_html))
    assert len(errors) >= 2, f"Expected both percentage and p-value errors, got: {errors}"
    assert any("percentage" in e.lower() for e in errors)
    assert any("p-value" in e.lower() for e in errors)


@pytest.mark.core
def test_full_repository_numbers_lint_clean():
    """Verify that the repository currently passes the strict empirical numbers linter."""
    errors = lint_all_numbers()
    assert len(errors) == 0, f"Empirical numbers linter failed with violations: {errors}"
