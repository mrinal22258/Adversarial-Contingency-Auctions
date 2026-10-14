# Double-Blind Peer Review Release & Anonymity Guidelines

This repository and all associated distribution artifacts are prepared under strict **double-blind peer review** protocols for submission to IEEE Robotics and Automation Letters (RA-L) / ICRA.

---

## 1. Golden Rules for Double-Blind Reviewers and Authors

1. **Never Share Real Repository URL or Local Paths:**
   - Do not provide direct links to author-associated GitHub/GitLab usernames or repositories during review.
   - For review access, provide the sanitized release bundle (`release/aca_review_archive.zip`) or host via an anonymous mirror service (such as [Anonymous GitHub / 4open](https://anonymous.4open.science/)).

2. **No Git History in Distribution:**
   - The distribution archive generated via `make release` (or `python tools/make_release.py`) is produced using `git archive` from the freeze tag/commit.
   - It contains zero `.git` metadata, eliminating commit logs, author email stamps, and local author directory paths.

3. **Scrubbed Source Files & PDFs:**
   - `paper.tex` and `supplement.tex` are compiled with `\anonymoustrue`. Both rendered PDFs (`paper.pdf`, `supplement.pdf`) contain zero author names, institutional affiliations, or contact emails.
   - All code files, UI templates, documentation, licenses, and scripts are stripped of personal and institutional identity strings.

4. **Executable Verification:**
   - To verify anonymity locally or in CI, run:
     ```bash
     make release-check
     # or
     python tools/check_anonymity.py
     ```
   - This executes a multi-pattern regex scan across all repository files and extracts PDF text and metadata using PyMuPDF to guarantee zero leaks.

---

## 2. Generating the Clean Review Archive

To package the double-blind submission bundle:
```bash
make release
# or
python tools/make_release.py --ref HEAD
```

This performs the following automated steps:
1. Exports a clean snapshot via `git archive --worktree-attributes`.
2. Honors `.gitattributes` `export-ignore` to omit `.git`, heavy raw JSONL logs, temporary directories, and developer worklogs.
3. Unpacks the archive into an isolated sandbox and runs `tools/check_anonymity.py`.
4. Confirms the resulting `.zip` and `.tar.gz` payloads are compact (< 35 MB) and ready for submission.
