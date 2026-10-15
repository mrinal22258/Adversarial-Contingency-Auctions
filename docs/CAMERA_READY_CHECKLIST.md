# Camera-Ready Publication Checklist

This checklist tracks human-only and final administrative actions required after the double-blind peer-review phase and prior to official venue/camera-ready publication and public release.

---

## 1. De-Anonymization (Guardrail G3 & Finding F-22)
- [ ] **LaTeX Manuscript (`paper.tex`)**:
  - Switch `\anonymoustrue` to `\anonymousfalse`.
  - Replace placeholder author email (`author@example.com` / `anon@example.com`) with legitimate institutional author names, affiliations, and contact email addresses.
  - Uncomment the acknowledgments / funding grants section if required by venue.
- [ ] **Citation & Attribution (`CITATION.cff`)**:
  - Replace anonymous placeholders with full names, ORCID identifiers, and affiliations of all contributing authors.
- [ ] **Repository Licensing (`LICENSE`)**:
  - Update copyright holder name from anonymous placeholder to the designated authors/institutions.

---

## 2. Methodology & Regularization Notes (Finding F-09)
- [ ] **Supplement / Methodology Section**:
  - Review `docs/METHODOLOGY_NOTES.md`.
  - Confirm whether the numerical regularization bound ($\epsilon = 0.01$, clipping edge marginals to $[0.01, 0.99]$) should be added as a one-sentence clarification in the camera-ready camera appendix or manuscript methodology section:
    > "To preserve numerical stability under Bayesian interdiction updates, edge marginal probabilities are regularized to the open interval $[\epsilon, 1-\epsilon]$ with $\epsilon = 0.01$."
  - Note: During peer review, this was preserved in code without touching frozen LaTeX tables or altering paper numbers.

---

## 3. Release Tagging & Packaging
- [ ] **Git Release Tag**:
  - Ensure all commits on `audit-remediation` are merged to `main`.
  - Tag the release version matching `PROTOCOL_VERSION` (e.g., `git tag -a v6.2.0 -m "Release v6.2.0: Camera-Ready Artifact"`).
  - Push tags upstream: `git push origin --tags`.
- [ ] **Python Packaging (`pip` / PyPI / TestPyPI)**:
  - Build source distribution and binary wheels:
    ```bash
    python -m build
    twine check dist/*
    ```
  - Verify package installation in a clean environment:
    ```bash
    python -m venv test_env
    test_env/bin/pip install dist/*.whl
    test_env/bin/python -c "import acalib; print(acalib.__version__, acalib.PROTOCOL_VERSION)"
    ```

---

## 4. Provenance & Artifact Verification (Guardrail G2)
- [ ] **Final Provenance Manifest**:
  - Run the official provenance verification script:
    ```bash
    python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml
    ```
  - If any final camera-ready text edits modified files tracked in `provenance.json`, regenerate provenance using the repo's official build script:
    ```bash
    python tools/build_all_results.py
    ```
  - Verify that all cryptographic SHA-256 hashes match bit-for-bit before tagging.

---

## 5. Public Archival & DOI Minting
- [ ] **Zenodo / Dryad Archival**:
  - Connect repository GitHub release to Zenodo webhook.
  - Mint DOI and record the minted DOI in `README.md` and `CITATION.cff`.
- [ ] **Preprint / Venue Upload**:
  - Compile final PDF using `tools/build_paper.py` (or `pdflatex paper.tex && bibtex paper && pdflatex paper.tex`).
  - Upload camera-ready bundle (PDF + source files + supplementary video/telemetry) to OpenReview / IEEE / ACM portal or arXiv.
