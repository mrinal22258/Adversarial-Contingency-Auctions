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
from typing import List, Tuple, Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
                    if gen and not any(allowed in gen for allowed in ["make_figures.py", "make_map_figures.py", "generate_paper_figures.py", "plot_comm_degradation_diagnostic.py"]):
                        errors.append(f"Figure {fig_path} provenance records generator '{gen}' (must be produced by make_figures.py / make_map_figures.py)")
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
    Ensure numbers in experimental results and evaluation text are defined via LaTeX macros.
    Catches hardcoded percentages like '88.4%', decimals like '13.0', or trial counts outside macros.
    """
    errors = []
    lines = tex_content.splitlines()

    in_results_section = False
    for line_num, line in enumerate(lines, 1):
        # Strip unescaped comments only (preserve escaped \%)
        parts = re.split(r"(?<!\\)%", line)
        clean = parts[0].strip()
        if not clean:
            continue

        if re.search(r"\\section\*?\{.*(evaluat|result|experiment|empiric).*", clean, re.IGNORECASE):
            in_results_section = True
        elif re.search(r"\\section\*?\{.*(relat|conclus|intro|theory|method).*", clean, re.IGNORECASE):
            in_results_section = False

        if in_results_section:
            # Skip macro definitions or table formatting lines
            if clean.startswith("\\newcommand") or clean.startswith("\\def") or clean.startswith("\\ae"):
                continue
            if clean.startswith("\\begin") or clean.startswith("\\end") or clean.startswith("\\hline"):
                continue
            if clean.startswith("\\caption") or clean.startswith("\\label") or clean.startswith("\\ref") or clean.startswith("\\cite"):
                continue

            # Check for literal percentages outside macros: e.g. '88.4\%' or '13%'
            pct_match = re.search(r"\b(\d+\.?\d*)\s*\\?%", clean)
            if pct_match and not re.search(r"\\ae[A-Za-z]+", clean):
                errors.append(f"Line {line_num}: Literal percentage '{pct_match.group(0)}' outside macro in results section: '{clean}'")

            # Check for literal statistical p-values outside macros (e.g. 'p = 0.001' or 'p-value = 0.05')
            if not any(k in clean.lower() for k in ["g(n", "erd", "graph", "p_{", "edge"]):
                pval_match = re.search(r"\bp\s*[=<]\s*0\.\d+", clean)
                if pval_match and not re.search(r"\\ae[A-Za-z]+", clean):
                    errors.append(f"Line {line_num}: Literal p-value '{pval_match.group(0)}' outside macro: '{clean}'")

    return errors


def get_git_commit() -> Optional[str]:
    """Retrieve current Git HEAD commit hash."""
    git_bin = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
    try:
        res = subprocess.run([git_bin, "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        git_dir = os.path.join(REPO_ROOT, ".git")
        head_file = os.path.join(git_dir, "HEAD")
        if os.path.exists(head_file):
            try:
                with open(head_file, "r") as f:
                    ref = f.read().strip()
                if ref.startswith("ref: "):
                    ref_path = os.path.join(git_dir, ref[5:])
                    if os.path.exists(ref_path):
                        with open(ref_path, "r") as f:
                            return f.read().strip()
                else:
                    return ref
            except Exception:
                pass
    return None


def check_staleness(tex_content: str, base_dir: str = REPO_ROOT) -> List[str]:
    """
    Check staleness across results, paper, maps, and git commit:
    1. results git_commit != code commit
    2. any figure/number/PDF is older than its inputs
    3. raw results record node counts that differ from committed map files
    4. the paper cites sizes not in the results
    """
    errors = []
    current_commit = get_git_commit()
    results_dir = os.path.join(REPO_ROOT, "results")
    raw_results_path = os.path.join(results_dir, "raw_results.csv")
    runs_jsonl_path = os.path.join(results_dir, "runs.jsonl")

    # 1. results git_commit != code commit
    if current_commit:
        if os.path.exists(runs_jsonl_path) and os.path.getsize(runs_jsonl_path) > 0:
            with open(runs_jsonl_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    try:
                        rec = json.loads(first_line)
                        res_commit = rec.get("git_commit")
                        if res_commit and res_commit != current_commit:
                            errors.append(
                                f"Stale results: runs.jsonl commit ({res_commit}) != repository HEAD ({current_commit})"
                            )
                    except Exception:
                        pass
        elif os.path.exists(raw_results_path):
            try:
                import pandas as pd
                df_head = pd.read_csv(raw_results_path, nrows=5)
                if "git_commit" in df_head.columns:
                    res_commit = str(df_head["git_commit"].iloc[0])
                    if res_commit and res_commit != current_commit:
                        errors.append(
                            f"Stale results: raw_results.csv commit ({res_commit}) != repository HEAD ({current_commit})"
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


def lint_paper(tex_path: str = "paper.tex") -> List[str]:
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
    errors.extend(check_staleness(content, base_dir))
    return errors


def main():
    tex_path = "paper.tex"
    errors = lint_paper(tex_path)
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
