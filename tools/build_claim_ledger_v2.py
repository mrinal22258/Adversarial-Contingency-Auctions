"""Build and validate audit/CLAIM_LEDGER_V2.csv with non-empty executable queries."""
import os
import sys
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.claims import EmpiricalClaim, compute_file_sha256

CLAIMS_V2_SPEC = [
    {
        "claim_id": "CLAIM-01-V2",
        "claim_text": "ACA outperforms depth-0 ablation by local contingency detour execution on nominal balanced core grid.",
        "source_file": "results/raw_results.csv",
        "executable_filter": "comm_regime == 'nominal' and method in ['aca', 'aca_depth_zero'] and adversary in ['theta_1_stochastic', 'theta_2_reactive', 'theta_4_cyclic_patrol']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Hodges-Lehmann median diff: +4.1 pp completion",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_greater",
        "correction": "Holm-Bonferroni FWER",
        "evidence_tier": "Tier 1: Nominal Core Grid",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-02-V2",
        "claim_text": "In Protocol v5 confirmatory evaluation, CBBA+LR achieves higher completion (94.67% vs 92.40%) and higher welfare (958.9 vs 937.4) than ACA static.",
        "source_file": "results/confirmatory/heldout_v5_results.csv",
        "executable_filter": "method in ['aca', 'cbba_lr']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Mean difference: +2.27 pp completion for CBBA+LR; +21.48 welfare",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_two_sided",
        "correction": "Holm-Bonferroni FWER",
        "evidence_tier": "Tier 3: Protocol v5 Confirmatory",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-03-V2",
        "claim_text": "In Protocol v5 confirmatory evaluation, ACA achieves statistical parity with partial re-auctioning (CBBA-PR+LR: 92.40% vs 93.39%).",
        "source_file": "results/confirmatory/heldout_v5_results.csv",
        "executable_filter": "method in ['aca', 'cbba_partial_lr']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Hodges-Lehmann median diff: -0.99 pp [-2.1, +0.1]",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_two_sided",
        "correction": "Holm-Bonferroni FWER (p = 0.091 unadjusted)",
        "evidence_tier": "Tier 3: Protocol v5 Confirmatory",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-04-V2",
        "claim_text": "Pinsker claim margin reduces safe conflicts by ~10.3 conflicts/trial relative to no-margin ablation (39.66 vs 49.93, p < 0.001) in v5.",
        "source_file": "results/confirmatory/heldout_v5_results.csv",
        "executable_filter": "method in ['aca', 'aca_no_margin']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Mean conflict diff: -10.27 conflicts/trial [-13.4, -7.1]",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_less",
        "correction": "Holm-Bonferroni FWER",
        "evidence_tier": "Tier 3: Protocol v5 Confirmatory",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-05-V2",
        "claim_text": "Pinsker margin incurs a modest non-significant completion cost of ~1.08 pp (92.40% vs 93.48%, p = 0.091) in v5.",
        "source_file": "results/confirmatory/heldout_v5_results.csv",
        "executable_filter": "method in ['aca', 'aca_no_margin']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Mean completion diff: -1.08 pp [-2.3, +0.2]",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_two_sided",
        "correction": "Holm-Bonferroni FWER",
        "evidence_tier": "Tier 3: Protocol v5 Confirmatory",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-06-V2",
        "claim_text": "CTP Replan achieves higher completion than ACA on the balanced core grid (96.4% vs 90.9%) due to continuous reactive replanning without consensus deferrals.",
        "source_file": "results/raw_results.csv",
        "executable_filter": "comm_regime == 'nominal' and method in ['aca', 'ctp_replan'] and adversary in ['theta_1_stochastic', 'theta_2_reactive', 'theta_4_cyclic_patrol']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Mean completion diff: +5.5 pp for CTP Replan",
        "ci_method": "Bootstrap 95% CI",
        "test_method": "paired_wilcoxon_greater",
        "correction": "Holm-Bonferroni FWER",
        "evidence_tier": "Tier 1: Nominal Core Grid",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-07-V2",
        "claim_text": "ACA+ and ACA-Adaptive performance gains observed in Stage 4 pilot (N=60) did not replicate in Protocol v5 confirmatory evaluation (completion 92.44% and 91.29% vs static 92.40%).",
        "source_file": "results/confirmatory/heldout_v5_results.csv",
        "executable_filter": "method in ['aca', 'aca_plus', 'aca_adaptive']",
        "cluster_unit": "graph_family:seed",
        "estimator": "Mean completion diff: +0.04 pp (ACA+) and -1.11 pp (Adaptive)",
        "ci_method": "Cluster-aware bootstrap 95% CI",
        "test_method": "paired_wilcoxon_two_sided",
        "correction": "Holm-Bonferroni FWER (both non-significant)",
        "evidence_tier": "Tier 3: Protocol v5 Confirmatory",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-08-V2",
        "claim_text": "Theorem 1 conflict-freedom is strictly conditional on Assumption 1 (TV <= eta_eff) on a fixed tree; unconditioned safety is an empirical property.",
        "source_file": "results/raw_results.csv",
        "executable_filter": "method == 'aca' and comm_regime == 'nominal'",
        "cluster_unit": "graph_family:seed",
        "estimator": "Analytical conditional implication",
        "ci_method": "Exact proof condition",
        "test_method": "mathematical_deduction",
        "correction": "None",
        "evidence_tier": "Theory: Conditional Scope",
        "expected_verdict": "PASS",
    },
    {
        "claim_id": "CLAIM-09-V2",
        "claim_text": "SITL physics simulation introduces a substantial completion drop of ~18.9 pp; rank invariance fails across discrete and continuous simulation fidelities.",
        "source_file": "results/sitl/analysis/sitl_vs_graph_summary.json",
        "executable_filter": "bland_altman.bias_mean_difference_pp < -15 and not ranking_preservation.ranking_preserved",
        "cluster_unit": "map:seed",
        "estimator": "Hodges-Lehmann median drop: -18.8 pp; Spearman rho = 0.486 (p = 0.328)",
        "ci_method": "Limits of Agreement 95% [-61.0, +17.4]",
        "test_method": "spearman_rank_correlation_test",
        "correction": "None",
        "evidence_tier": "Tier 1: SITL Physics Simulation",
        "expected_verdict": "PASS",
    },
]


def build_claim_ledger_v2(out_path="audit/CLAIM_LEDGER_V2.csv", root_dir="."):
    rows = []
    for spec in CLAIMS_V2_SPEC:
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
        res = claim.evaluate(root_dir=root_dir)
        if res["population_n"] == 0:
            raise ValueError(f"Build failed: Claim {spec['claim_id']} has empty population (n=0)!")
        if res["verdict"] != spec["expected_verdict"]:
            raise ValueError(f"Build failed: Claim {spec['claim_id']} verdict {res['verdict']} != expected {spec['expected_verdict']} ({res['result']})")

        rows.append({
            "claim_id": spec["claim_id"],
            "claim_text": spec["claim_text"],
            "source_file": spec["source_file"],
            "sha256": res["sha256"],
            "executable_filter": spec["executable_filter"],
            "population_n": res["population_n"],
            "cluster_unit": spec["cluster_unit"],
            "estimator": spec["estimator"],
            "ci_method": spec["ci_method"],
            "test_and_correction": f"{spec['test_method']} ({spec['correction']})",
            "evidence_tier": spec["evidence_tier"],
            "result_status": res["status"],
            "verdict": res["verdict"],
        })

    df_v2 = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_v2.to_csv(out_path, index=False, lineterminator="\n")
    print(f"Successfully generated {out_path} with {len(df_v2)} validated, non-empty claims.")
    for idx, r in df_v2.iterrows():
        print(f"  {r['claim_id']:12s} | N={r['population_n']:5d} | Verdict={r['verdict']:4s} | {r['claim_text'][:60]}...")
    return df_v2


if __name__ == "__main__":
    build_claim_ledger_v2()
