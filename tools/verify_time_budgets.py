"""
Verification V3: Time Budget Assertions.
- Boston single run < 4s
- Paired comparison < 12s
- 20 seeds < 15s (4 workers)
- 38-node warehouse run < 1s
"""

import time
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.demo.runner import (
    run_single_simulation,
    run_paired_comparison,
    run_20_seeds_paired,
    DEFAULT_MAX_STEPS,
)


def verify_budgets():
    print("=================== TIME BUDGET VERIFICATION ===================")
    
    # 1. 38-node warehouse run < 1s
    print("\n[1/4] Running 38-node warehouse single simulation...")
    t0 = time.time()
    res_wh = run_single_simulation(
        graph_family="warehouse_movingai",
        n_nodes=38,
        adversary_str="Reactive (Corridor Interdiction)",
        allocator_str="aca",
        seed=10001,
        max_steps=DEFAULT_MAX_STEPS,
        variant="10-20-10-2-1",
        record_history=True,
    )
    t_wh = time.time() - t0
    print(f"  38-node warehouse duration: {t_wh:.3f}s (budget: < 1.0s)")
    assert t_wh < 1.0, f"38-node warehouse took {t_wh:.3f}s >= 1.0s"

    # 2. Boston single run < 4s
    print("\n[2/4] Running Boston 216-node single simulation...")
    t0 = time.time()
    res_boston = run_single_simulation(
        graph_family="road_osmnx",
        n_nodes=216,
        adversary_str="Reactive (Corridor Interdiction)",
        allocator_str="aca",
        seed=10001,
        max_steps=DEFAULT_MAX_STEPS,
        variant="none",
        record_history=True,
    )
    t_boston = time.time() - t0
    print(f"  Boston single run duration: {t_boston:.3f}s (budget: < 4.0s)")
    assert t_boston < 4.0, f"Boston single run took {t_boston:.3f}s >= 4.0s"

    # 3. Boston paired comparison < 12s
    print("\n[3/4] Running Boston paired comparison (selected vs CBBA-PR+LR, CBBA, CTP Replan)...")
    t0 = time.time()
    res_paired = run_paired_comparison(
        graph_family="road_osmnx",
        n_nodes=216,
        adversary_str="Reactive (Corridor Interdiction)",
        selected_allocator_str="aca",
        seed=10001,
        max_steps=DEFAULT_MAX_STEPS,
        variant="none",
    )
    t_paired = time.time() - t0
    print(f"  Boston paired comparison duration: {t_paired:.3f}s (budget: < 12.0s)")
    assert t_paired < 12.0, f"Boston paired comparison took {t_paired:.3f}s >= 12.0s"

    # 4. Boston 20 seeds < 15s (4 workers)
    print("\n[4/4] Running Boston 20-seed evaluation across 4 workers...")
    t0 = time.time()
    res_20 = run_20_seeds_paired(
        graph_family="road_osmnx",
        n_nodes=216,
        adversary_str="Reactive (Corridor Interdiction)",
        allocator_str="aca",
        seed_start=10001,
        num_seeds=20,
        max_steps=DEFAULT_MAX_STEPS,
        variant="none",
    )
    t_20 = time.time() - t0
    print(f"  Boston 20 seeds duration: {t_20:.3f}s (budget: < 15.0s)")
    print(f"  Verdict: {res_20['verdict']}")
    assert t_20 < 15.0, f"Boston 20 seeds took {t_20:.3f}s >= 15.0s"

    print("\nALL TIME BUDGET ASSERTIONS PASSED!")
    return {
        "warehouse_38_sec": t_wh,
        "boston_single_sec": t_boston,
        "boston_paired_sec": t_paired,
        "boston_20_seeds_sec": t_20,
    }


if __name__ == "__main__":
    verify_budgets()
