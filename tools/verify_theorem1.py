"""
Verify Theorem 1 and Assumption 1 from per-claim evaluations.
Theorem 1 states: Under Assumption 1 (TV(B_s, \hat{B}_s) <= \eta_{eff}),
the probability of a claim conflict is strictly 0 (conflict rate is strictly 0.0).
"""

import json
import os
import sys
import numpy as np
import pandas as pd

def main():
    jsonl_path = "results/per_claim_evaluations.jsonl"
    if not os.path.exists(jsonl_path):
        print(f"File not found: {jsonl_path}")
        sys.exit(1)

    total_claims = 0
    safe_claims = 0
    tv_adhered_safe_claims = 0
    conflicts_tv_adhered = 0
    total_safe_conflicts = 0

    per_instance_tv_adherence = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            claims = rec.get("claims", [])
            inst_claims = 0
            inst_adhered = 0
            for c in claims:
                total_claims += 1
                if c.get("claimed_safe"):
                    safe_claims += 1
                    inst_claims += 1
                    if c.get("conflicted"):
                        total_safe_conflicts += 1
                    if c.get("tv_le_eta"):
                        inst_adhered += 1
                        tv_adhered_safe_claims += 1
                        if c.get("conflicted"):
                            conflicts_tv_adhered += 1
            if inst_claims > 0:
                per_instance_tv_adherence.append(inst_adhered / inst_claims)

    print("=" * 60)
    print("THEOREM 1 EMPIRICAL VERIFICATION REPORT")
    print("=" * 60)
    print(f"Total Claims Analyzed              : {total_claims:,}")
    print(f"Safe Claims (Margin > Threshold)   : {safe_claims:,}")
    print(f"Claims where TV <= eta_eff         : {tv_adhered_safe_claims:,}")
    print(f"Conflicts among TV <= eta_eff claims: {conflicts_tv_adhered}")
    conflict_rate = conflicts_tv_adhered / max(1, tv_adhered_safe_claims)
    print(f"Empirical Conflict Rate (TV <= eta): {conflict_rate:.6f}")
    assert conflicts_tv_adhered == 0, f"VIOLATION: Found {conflicts_tv_adhered} conflicts when TV <= eta_eff!"
    print(">>> THEOREM 1 HOLDS EMPIRICALLY: Conflict rate is strictly 0.0! <<<")
    print("=" * 60)

    # Independent instance bootstrap for Assumption 1 (H7)
    arr = np.array(per_instance_tv_adherence)
    print(f"Independent Instances with Safe Claims: {len(arr)}")
    print(f"Instance-Level Mean TV Adherence: {np.mean(arr):.4f}")
    rng = np.random.default_rng(42)
    boot_means = [np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(10000)]
    ci_low = np.percentile(boot_means, 2.5)
    ci_high = np.percentile(boot_means, 97.5)
    print(f"Independent Instance Bootstrap 95% CI: [{ci_low:.4f}, {ci_high:.4f}]")

if __name__ == "__main__":
    main()
