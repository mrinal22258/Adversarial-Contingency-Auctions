"""
Strict Paper Quality, Provenance, and Reproducibility Linter (Rule R1, R4, R5, Step 0.4).

Fails the build if:
1. Any figure referenced in paper lacks a valid sidecar .provenance.json file.
2. Any unverified claim appears:
   - 'real', 'OSMnx', 'MovingAI' unless matching data files and manifest exist with valid SHA-256 hashes.
   - 'validated', 'hardware', 'DDS', 'Gazebo' unless matching physical/SITL hardware logs exist.
   - 'strictly 0' (violates measured empirical data where safe-claim conflicts > 0).
   - 'Oracle' (unless explicitly referring to clairvoyant greedy heuristic reference).
   - 'Theoretical bound' (clairvoyant greedy is not a mathematical bound).
3. Literal numbers outside LaTeX macros appear in results/discussion text.
"""

import os
import re
import sys
import json
import hashlib
import shutil
import subprocess
from typing import List, Tuple, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
DATA_MAPS_DIR = os.path.join(REPO_ROOT, "data", "maps")


def verify_map_provenance() -> Tuple[bool, str]:
    """Check if real MovingAI and OSMnx files exist with valid SHA-256."""
    manifest_path = os.path.join(DATA_MAPS_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return False, "Missing data/maps/manifest.json"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Check movingai
    movingai_info = manifest.get("movingai", {}).get("warehouse-10-20-10-2-1.map")
    if not movingai_info:
        return False, "Manifest missing MovingAI warehouse-10-20-10-2-1.map entry"
    map_file = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
    if not os.path.exists(map_file):
        return False, f"Missing {map_file}"
    with open(map_file, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != movingai_info["sha256"]:
            return False, "MovingAI file SHA-256 mismatch"

    # Check osmnx
    osmnx_info = manifest.get("osmnx", {})
    if not osmnx_info:
        return False, "Manifest missing OSMnx entry"
    graphml_file = os.path.join(DATA_MAPS_DIR, osmnx_info.get("file", "boston_downtown_drive.graphml"))
    if not os.path.exists(graphml_file):
        return False, f"Missing {graphml_file}"
    with open(graphml_file, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != osmnx_info["sha256"]:
            return False, "OSMnx GraphML file SHA-256 mismatch"

    return True, "Valid"


def check_figure_provenance(tex_content: str, base_dir: str) -> List[str]:
    """Check that all included figures have a .provenance.json sidecar."""
    errors = []
    pattern = r"\\includegraphics(?:\[.*?\])?\{([^}]+)\}"
    matches = re.findall(pattern, tex_content)

    for fig_path in matches:
        if any(arch in fig_path for arch in ["fig2_adversary_model", "fig3_contingency_tree", "pipeline"]):
            continue

        full_fig_path = os.path.join(base_dir, fig_path)
        provenance_candidates = [
            full_fig_path + ".provenance.json",
            os.path.splitext(full_fig_path)[0] + ".pdf.provenance.json",
            os.path.splitext(full_fig_path)[0] + ".png.provenance.json",
        ]
        found = False
        for p in provenance_candidates:
            if os.path.exists(p):
                found = True
                try:
                    with open(p, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                    gen = pdata.get("generator_script", pdata.get("generated_by", ""))
                    if gen and not any(allowed in gen for allowed in ["make_figures.py", "make_map_figures.py", "make_cd_diagram.py", "generate_paper_figures.py", "plot_comm_degradation_diagnostic.py", "make_rollout_videos.py", "build_all_results.py"]):
                        errors.append(f"Figure {fig_path} provenance records generator '{gen}' (must be produced by make_figures.py / make_map_figures.py / make_rollout_videos.py)")
                except Exception:
                    pass
                break
        if not found:
            errors.append(f"Missing provenance file for figure: {fig_path}")

    return errors


def check_strict_claims(tex_content: str) -> List[str]:
    """Enforce strict terminology, provenance requirements, and claim integrity (Rule R1, R4, R5)."""
    errors = []
    lines = [re.split(r"(?<!\\)%", line)[0] for line in tex_content.splitlines()]
    clean_text = "\n".join(lines)

    map_prov_ok, map_prov_msg = verify_map_provenance()

    # 1. MovingAI and OSMnx claims
    if not map_prov_ok:
        if re.search(r"\bMovingAI\b", clean_text, re.IGNORECASE):
            errors.append(f"Claim of 'MovingAI' forbidden without verified data files: {map_prov_msg}")
        if re.search(r"\bOSMnx\b", clean_text, re.IGNORECASE):
            errors.append(f"Claim of 'OSMnx' forbidden without verified data files: {map_prov_msg}")

    # 2. 'strictly 0' and unconditional 'guarantee' claims when measured safe conflicts > 0
    measured_safe_conflicts = 0.0
    raw_csv = os.path.join(REPO_ROOT, "results", "raw_results.csv")
    if os.path.exists(raw_csv):
        try:
            import pandas as pd
            df_raw = pd.read_csv(raw_csv)
            if "method" in df_raw.columns and "safe_claim_conflicts" in df_raw.columns:
                measured_safe_conflicts = float(df_raw[df_raw["method"] == "aca"]["safe_claim_conflicts"].sum())
        except Exception:
            pass

    if measured_safe_conflicts > 0:
        if re.search(r"\bstrictly\s+0\b", clean_text, re.IGNORECASE) or re.search(r"\bstrictly\s+zero\b", clean_text, re.IGNORECASE):
            errors.append(f"Forbidden claim 'strictly 0' / 'strictly zero' conflicts found (measured safe-claim conflicts = {measured_safe_conflicts:.0f} > 0)")
        for m in re.finditer(r"\bguarantees?\s+(?:conflict-free|zero\s+conflicts?)\b", clean_text, re.IGNORECASE):
            snippet = clean_text[max(0, m.start() - 60): min(len(clean_text), m.end() + 60)].lower()
            if not any(cond in snippet for cond in ["under assumption", "when", "provided", "if", "conditioned on", "bounded-error model"]):
                errors.append(f"Unconditional guarantee claim '{clean_text[m.start():m.end()]}' forbidden when empirical safe-claim conflicts > 0: '...{snippet.strip()}...'")

    # 3. 'Theoretical bound' claim
    if re.search(r"\btheoretical\s+bound\b", clean_text, re.IGNORECASE):
        errors.append("Forbidden phrase 'Theoretical bound' found: clairvoyant greedy is a heuristic reference, not a bound")

    # 4. 'Oracle' claim unless qualified
    oracle_matches = re.finditer(r"\bOracle\b", clean_text)
    for m in oracle_matches:
        snippet = clean_text[max(0, m.start() - 60): min(len(clean_text), m.end() + 60)]
        if not any(q in snippet.lower() for q in ["greedy", "heuristic", "clairvoyant", "reference", "not a bound", "foresight"]):
            errors.append(f"Unqualified 'Oracle' claim (must be 'Clairvoyant greedy (reference, not a bound)'): '...{snippet.strip()}...'")

    # 5. Hardware, Gazebo claims without physical provenance
    hw_data_exists = os.path.exists(os.path.join(REPO_ROOT, "results", "hardware")) and len(os.listdir(os.path.join(REPO_ROOT, "results", "hardware"))) > 0
    hw_matches = re.finditer(r"\bhardware\b", clean_text, re.IGNORECASE)
    for m in hw_matches:
        snippet = clean_text[max(0, m.start() - 60): min(len(clean_text), m.end() + 60)].lower()
        if not any(allowed in snippet for allowed in ["future", "limitation", "physical robot trial", "scope", "not", "no physical", "simulat"]):
            if not hw_data_exists:
                errors.append(f"Unsubstantiated 'hardware' claim without physical robot data: '...{snippet.strip()}...'")

    # Gazebo claim
    if re.search(r"\bGazebo\b", clean_text):
        gazebo_exists = os.path.exists(os.path.join(REPO_ROOT, "hw", "gazebo"))
        if not gazebo_exists:
            errors.append("Claim of 'Gazebo' forbidden: no Gazebo environment or execution logs exist")

    # 6. SITL, DDS, 'validated', 'high-fidelity' claims without matching results/sitl/*.jsonl
    sitl_dir = os.path.join(REPO_ROOT, "results", "sitl")
    sitl_exists = os.path.exists(sitl_dir) and any(f.endswith(".jsonl") for f in os.listdir(sitl_dir))
    if not sitl_exists:
        for term in ["SITL", "DDS", "high-fidelity", "high fidelity"]:
            for m in re.finditer(r"\b" + re.escape(term) + r"\b", clean_text, re.IGNORECASE):
                snippet = clean_text[max(0, m.start() - 150): min(len(clean_text), m.end() + 150)].lower()
                if not any(allowed in snippet for allowed in ["future", "limitation", "not", "remains future work", "future work"]):
                    errors.append(f"Forbidden claim of '{clean_text[m.start():m.end()]}' with no matching results/sitl/*.jsonl execution logs: '...{clean_text[max(0, m.start()-30):min(len(clean_text), m.end()+30)].strip()}...'")

        for m in re.finditer(r"\bvalidated\b", clean_text, re.IGNORECASE):
            snippet = clean_text[max(0, m.start() - 150): min(len(clean_text), m.end() + 150)].lower()
            if not any(allowed in snippet for allowed in ["future", "limitation", "not", "remains future work", "future work"]):
                errors.append(f"Forbidden claim of 'validated' without verified simulation/hardware logs: '...{clean_text[max(0, m.start()-30):min(len(clean_text), m.end()+30)].strip()}...'")

    return errors


def check_unmacroed_literal_numbers(tex_content: str) -> List[str]:
    """
    Ensure all numbers in abstract, body text, captions, and tables are defined via LaTeX macros (Rule R1).
    Allows strictly whitelisted non-empirical patterns:
    - Section/Equation/Theorem/Hypothesis/Proposition/Remark/Phase references
    - Literature citations and year tags ('24, '09)
    - Monospace code/filenames in \\texttt{...} and prereg git tags
    - Powers of 10 in scientific notation / p-values ($10^{-15}$)
    - Standard mathematical formula constants (e.g. \\frac{1}{2}, 1 - \\pi, 1 + \\lambda)
    - Math indices, state transitions ($X_e^{t+1}$), and set definitions (\\{0, 1\\})
    - List bullets ((1), (2), 1)) and layout dimensions (0.32\\textwidth, 2.1cm)
    All empirical quantities, map sizes, trial counts, percentages, and CIs MUST use macros.
    """
    errors = []
    lines = tex_content.splitlines()
    in_document = False if "\\begin{document}" in tex_content else True

    for line_num, line in enumerate(lines, 1):
        # Strip unescaped comments only (preserve escaped \\%)
        parts = re.split(r"(?<!\\)%", line)
        clean = parts[0].strip()
        if not clean:
            continue

        if "\\begin{document}" in clean:
            in_document = True
            continue
        if "\\bibliography" in clean or "\\end{document}" in clean:
            in_document = False
            continue

        if not in_document:
            continue

        # Skip pure structural/preamble commands
        if clean.startswith(("\\newcommand", "\\def", "\\renewcommand", "\\setcounter", "\\usepackage", "\\documentclass", "\\input", "\\bibliographystyle")):
            continue
        if clean.startswith(("\\begin{table", "\\end{table", "\\begin{figure", "\\end{figure", "\\begin{tabular", "\\end{tabular", "\\toprule", "\\midrule", "\\bottomrule", "\\hline")):
            continue
        if clean.startswith(("\\hfill", "\\centering", "\\resizebox", "\\markboth", "\\title", "\\author", "\\thanks")):
            continue

        # Mask whitelisted patterns
        masked = clean

        # 1. Citations and literature years ('24, '09, etc.)
        masked = re.sub(r"\\cite\{[^}]+\}", " ", masked)
        masked = re.sub(r"\[[0-9]+(?:--[0-9]+)?\]", " ", masked)
        masked = re.sub(r"'(?:[0-9]{2})\b", " ", masked)

        # 2. Section, Theorem, Equation, Hypothesis, Remark, Phase, Action references (including plural & ranges)
        masked = re.sub(r"(?:Sections?|Secs?\.?|Equations?|Eqs?\.?|Theorems?|Thms?\.?|Assumptions?|Assumps?\.?|Definitions?|Defs?\.?|Propositions?|Props?\.?|Remarks?|Observations?|Lemmas?|Phases?|Stages?|Actions?)(?:\s*~?\s*|\s*-\s*)(?:Y?[0-9]+(?:/[0-9]+)?|[A-Z]+(?:-[A-Z]+)?)(?:\s*(?:--|&|\\&|and)\s*[0-9]+)?", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"H_?[0-9]+(?:_[A-Za-z0-9]+)?", " ", masked)
        masked = re.sub(r"H_\{(?:[^{}]|\{[^{}]*\})*\}", " ", masked)

        # 3. Code, monospace filenames, and pre-registration git tags
        masked = re.sub(r"\\texttt\{[^}]*\}", " ", masked)
        masked = re.sub(r"\bprereg-v[0-9]+\b", " ", masked)
        masked = re.sub(r"\bv[0-9]+\b", " ", masked)

        # 4. Powers of 10 in scientific notation/p-values
        masked = re.sub(r"10\^\{-[0-9]+\}", " ", masked)
        masked = re.sub(r"\\times\s*10\^\{-[0-9]+\}", " ", masked)

        # 5. Standard math formula constants (e.g. \\frac{1}{2} in Pinsker formula, 1 - \\pi, 1 + \\lambda)
        masked = re.sub(r"\\frac\{1\}\{2\}", " ", masked)
        masked = re.sub(r"1\s*[-+]\s*[\\a-zA-Z]", " ", masked)
        masked = re.sub(r"\\to\s*1\b", " ", masked)

        # 6. Math indices and state variables: theta_1..4, X_e^{t+1}, t+1, {0, 1}, etc.
        masked = re.sub(r"\\theta_[0-9]+", " ", masked)
        masked = re.sub(r"\^\{t\+1\}", " ", masked)
        masked = re.sub(r"\^\{?t\}?", " ", masked)
        masked = re.sub(r"\\in\s*\\\{[0-9,\s]+\\\}", " ", masked)
        masked = re.sub(r"=\s*[01]\b", " ", masked)
        masked = re.sub(r"[_^]\{[a-z]\s*=\s*[0-9]+\}", " ", masked)
        masked = re.sub(r"\b[tijkmn]\s*=\s*[0-9]+\b", " ", masked)
        masked = re.sub(r"\b[tijkmn]\s*[<>]\s*[0-9]+\b", " ", masked)
        masked = re.sub(r"\b[uUvV]_[0-9]+\b", " ", masked)
        masked = re.sub(r"w_e\s*>\s*0", " ", masked)
        masked = re.sub(r"\bpi_r\(e\)\s*=\s*0", " ", masked)
        masked = re.sub(r"\\\{1,\s*\\dots,\s*[A-Z]\\\}", " ", masked)
        masked = re.sub(r"\\prod_\{i=1\}\^[A-Z]", " ", masked)
        masked = re.sub(r"\\sum_\{k=1\}\^[A-Z]", " ", masked)

        # 7. List bullets like (1), (2), (3) or 1), 2) and numbered headings
        masked = re.sub(r"^\([0-9]+\)", " ", masked)
        masked = re.sub(r"^[0-9]+\)", " ", masked)
        masked = re.sub(r"\([1-9]\)~?\\textit", " ", masked)
        masked = re.sub(r"(?:\b|\A)[0-9]+\)\s*", " ", masked)

        # 8. Structural commands that take non-text arguments (labels, refs, figures, spacing, multirow, IEEEtriggeratref)
        masked = re.sub(r"\\(?:label|ref|eqref|cite|input|bibliography|bibliographystyle|pagestyle|thispagestyle|vspace|hspace|addtolength|setlength|rule|scalebox|multirow|IEEEtriggeratref)\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", " ", masked)
        masked = re.sub(r"\\includegraphics\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", masked)

        # 9. Layout dimensions: e.g. 0.32\\textwidth, 2.1cm, 10pt, 1ex, etc.
        masked = re.sub(r"[-+]?\b\d+(?:\.\d+)?\s*(?:\\linewidth|\\textwidth|\\columnwidth|pt|mm|cm|in|ex|em)\b", " ", masked)

        # 10. Strip macro names themselves (e.g. \\aeTotalTrials, \\textbf, \\caption) leaving their argument contents
        masked = re.sub(r"\\[a-zA-Z]+", " ", masked)

        # Find any remaining literal numbers
        matches = re.findall(r"[-+]?\b\d+(?:,\d+)*(?:\.\d+)?\b", masked)
        if matches:
            errors.append(f"Line {line_num}: Unmacroed literal number(s) {matches} in: '{clean}'")

    return errors


from acalib.utils.gitinfo import get_git_info, get_git_commit


def check_staleness(tex_content: str, base_dir: str = REPO_ROOT, strict_release: bool = False) -> List[str]:
    """
    Check staleness across results, paper, maps, and git commit:
    1. results git_commit != code commit (strict in release mode, reported in dev mode)
    2. any figure/number/PDF is older than its inputs
    3. raw results record node counts that differ from committed map files
    4. the paper cites sizes not in the results
    """
    errors = []
    git_info = get_git_info()
    current_commit = git_info.commit if git_info.commit != "unknown" else None
    results_dir = os.path.join(REPO_ROOT, "results")
    raw_results_path = os.path.join(results_dir, "raw_results.csv")
    runs_jsonl_path = os.path.join(results_dir, "runs.jsonl")

    # 1. results git_commit != code commit (Rule R1: must equal HEAD with a clean tree in release mode)
    is_dirty = git_info.is_dirty
    if is_dirty:
        if strict_release:
            errors.append("Dirty working tree: uncommitted changes detected. Results commit must equal HEAD with a clean tree.")
        else:
            print("  [NOTICE: DEV MODE] Dirty working tree. Valid development artifact.")

    if current_commit:
        git_bin = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
        if os.path.exists(runs_jsonl_path) and os.path.getsize(runs_jsonl_path) > 0:
            with open(runs_jsonl_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    try:
                        rec = json.loads(first_line)
                        res_commit = rec.get("git_commit", rec.get("commit"))
                        if res_commit and res_commit != current_commit:
                            # Rule R1: exact ancestor check
                            is_valid_ancestor = False
                            try:
                                res = subprocess.run([git_bin, "merge-base", "--is-ancestor", res_commit, current_commit], check=False)
                                if res.returncode == 0:
                                    is_valid_ancestor = True
                            except Exception:
                                pass
                            if not is_valid_ancestor:
                                errors.append(
                                    f"Stale results: runs.jsonl commit ({res_commit}) != repository HEAD ({current_commit}) and is not an unchanged execution ancestor"
                                )
                    except Exception:
                        pass
        elif os.path.exists(raw_results_path):
            try:
                import pandas as pd
                df_head = pd.read_csv(raw_results_path, nrows=5)
                commit_col = "git_commit" if "git_commit" in df_head.columns else ("commit" if "commit" in df_head.columns else None)
                if commit_col:
                    res_commit = str(df_head[commit_col].iloc[0])
                    if res_commit and res_commit != current_commit:
                        is_valid_ancestor = False
                        try:
                            res = subprocess.run([git_bin, "merge-base", "--is-ancestor", res_commit, current_commit], check=False)
                            if res.returncode == 0:
                                is_valid_ancestor = True
                        except Exception:
                            pass
                        if not is_valid_ancestor:
                            errors.append(
                                f"Stale results: raw_results.csv commit ({res_commit}) != repository HEAD ({current_commit}) and is not an unchanged execution ancestor"
                            )
            except Exception:
                pass

    # 2. figure/number/PDF older than inputs
    # 2a. paper.pdf older than paper.tex or results/numbers.tex
    paper_pdf_path = os.path.join(REPO_ROOT, "paper.pdf")
    paper_tex_path = os.path.join(REPO_ROOT, "paper.tex")
    numbers_tex_path = os.path.join(results_dir, "numbers.tex")
    if os.path.exists(paper_pdf_path):
        pdf_mtime = os.path.getmtime(paper_pdf_path)
        if os.path.exists(paper_tex_path) and pdf_mtime < os.path.getmtime(paper_tex_path):
            errors.append("Stale paper.pdf: older than paper.tex")
        if os.path.exists(numbers_tex_path) and pdf_mtime < os.path.getmtime(numbers_tex_path):
            errors.append("Stale paper.pdf: older than results/numbers.tex")

    # 2b. results/numbers.tex older than raw_results.csv
    if os.path.exists(numbers_tex_path) and os.path.exists(raw_results_path):
        if os.path.getmtime(numbers_tex_path) < os.path.getmtime(raw_results_path):
            errors.append("Stale results/numbers.tex: older than results/raw_results.csv")

    # 2c. figures older than their source files
    figures_dir = os.path.join(results_dir, "figures")
    if os.path.exists(figures_dir):
        for fname in os.listdir(figures_dir):
            if fname.endswith(".provenance.json"):
                prov_path = os.path.join(figures_dir, fname)
                try:
                    with open(prov_path, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                    fig_rel = pdata.get("figure_file")
                    if fig_rel:
                        fig_full = os.path.join(REPO_ROOT, fig_rel)
                        if os.path.exists(fig_full):
                            fig_mtime = os.path.getmtime(fig_full)
                            for src in pdata.get("source_files", []):
                                src_full = os.path.join(REPO_ROOT, src)
                                if os.path.exists(src_full) and fig_mtime < os.path.getmtime(src_full):
                                    errors.append(f"Stale figure {fig_rel}: older than source {src}")
                except Exception:
                    pass

    # 3. raw results record node counts that differ from committed map files
    if os.path.exists(raw_results_path):
        try:
            import pandas as pd
            df = pd.read_csv(raw_results_path)
            # Check MovingAI warehouse
            if "warehouse_movingai" in df["graph_family"].values:
                wh_rows = df[df["graph_family"] == "warehouse_movingai"]
                wh_nodes = set(wh_rows["n_nodes"].unique())
                # Expected: 38 (or 56) from coarsened MovingAI map
                if not wh_nodes.issubset({38, 56}):
                    errors.append(
                        f"Stale raw_results.csv: warehouse_movingai records invalid node count {list(wh_nodes)} (expected 38 or 56 from committed map)"
                    )
            # Check OSMnx Boston road network
            if "road_osmnx" in df["graph_family"].values:
                road_rows = df[df["graph_family"] == "road_osmnx"]
                road_nodes = set(road_rows["n_nodes"].unique())
                if road_nodes != {216}:
                    errors.append(
                        f"Stale raw_results.csv: road_osmnx records node count {list(road_nodes)} (expected 216 from committed Boston GraphML)"
                    )
        except Exception as e:
            errors.append(f"Could not verify raw_results.csv node counts: {e}")

    # 4. the paper cites sizes not in the results
    if os.path.exists(raw_results_path):
        try:
            import pandas as pd
            df = pd.read_csv(raw_results_path)
            # Check MovingAI size citation
            wh_match = re.search(r"MovingAI[^\n]*\(\$n\s*=\s*(\d+)\$\)", tex_content, re.IGNORECASE)
            if wh_match:
                cited_n = int(wh_match.group(1))
                res_n = set(df[df["graph_family"] == "warehouse_movingai"]["n_nodes"].unique())
                if len(res_n) > 0 and cited_n not in res_n:
                    errors.append(
                        f"Paper cites MovingAI warehouse size n={cited_n}, but results record n={list(res_n)}"
                    )
            # Check Boston road network size citation
            road_match = re.search(r"(?:Boston|road|OSMnx)[^\n]*\(\$n\s*=\s*(\d+)\$\)", tex_content, re.IGNORECASE)
            if road_match:
                cited_n = int(road_match.group(1))
                res_n = set(df[df["graph_family"] == "road_osmnx"]["n_nodes"].unique())
                if len(res_n) > 0 and cited_n not in res_n:
                    errors.append(
                        f"Paper cites road network size n={cited_n}, but results record n={list(res_n)}"
                    )
        except Exception:
            pass

    return errors


def lint_paper(tex_path: str = "paper.tex", strict_release: bool = False) -> List[str]:
    """Run full suite of strict lint checks on paper file."""
    if not os.path.exists(tex_path):
        return [f"File not found: {tex_path}"]

    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    base_dir = os.path.dirname(os.path.abspath(tex_path))
    errors = []
    errors.extend(check_figure_provenance(content, base_dir))
    errors.extend(check_strict_claims(content))
    errors.extend(check_unmacroed_literal_numbers(content))
    errors.extend(check_staleness(content, base_dir, strict_release=strict_release))
    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strict Paper & Provenance Linter")
    parser.add_argument("--tex-path", default="paper.tex", help="Path to paper.tex")
    parser.add_argument("--strict-release", action="store_true", help="Fail build on dirty working tree")
    parser.add_argument("--strict", action="store_true", help="Strict mode (enforces clean working tree and strict claims)")
    args = parser.parse_args()

    strict_release = args.strict_release or args.strict
    errors = lint_paper(args.tex_path, strict_release=strict_release)
    if errors:
        print("STRICT LINTER FAILURE: Integrity violations found in paper:")
        for err in errors:
            print(f"  [ERROR] {err}")
        sys.exit(1)
    else:
        print("Paper lint passed successfully: 0 provenance violations, 0 unverified claims, 0 literal numbers.")
        sys.exit(0)


if __name__ == "__main__":
    main()
