"""
Tests for Protocol v6 Seed Disjointness and Integrity (Section 8 / Gate 11).
Asserts that v6 seeds are strictly disjoint from all historical seeds across:
- Sweep v1-v4 (1..30)
- Protocol v5 held-out (101..130)
- Stage4 pilot (1000..1060)
- SITL physics trials (20000..20359)
- Demo/ablation seeds (10001..10010)
"""

import numpy as np
import pytest

# Frozen historical seed sets
V1_V4_SEEDS = set(range(1, 31))
V5_HELDOUT_SEEDS = set(range(101, 131))
STAGE4_PILOT_SEEDS = set(range(1000, 1061))
SITL_SEEDS = set(range(20000, 20360))
DEMO_SEEDS = set(range(10001, 10011))

ALL_HISTORICAL_SEEDS = V1_V4_SEEDS | V5_HELDOUT_SEEDS | STAGE4_PILOT_SEEDS | SITL_SEEDS | DEMO_SEEDS


def generate_v6_seeds(n_seeds: int = 50, rng_seed: int = 20261013) -> list[int]:
    """Deterministically generate Protocol v6 confirmatory seeds disjoint from historical runs."""
    rng = np.random.default_rng(rng_seed)
    candidates = rng.choice(np.arange(50000, 60000), size=n_seeds * 2, replace=False)
    v6_seeds = []
    for s in candidates:
        int_s = int(s)
        if int_s not in ALL_HISTORICAL_SEEDS:
            v6_seeds.append(int_s)
        if len(v6_seeds) == n_seeds:
            break
    return sorted(v6_seeds)


@pytest.mark.core
def test_v6_seed_disjointness():
    v6_seeds = generate_v6_seeds(n_seeds=50)
    assert len(v6_seeds) == 50
    assert len(set(v6_seeds)) == 50

    overlap = set(v6_seeds).intersection(ALL_HISTORICAL_SEEDS)
    assert len(overlap) == 0, f"Protocol v6 seeds overlap with historical seeds: {overlap}"

    # Also assert dev tuning seeds are disjoint from confirmatory v6 seeds
    dev_rng = np.random.default_rng(9992026)
    dev_seeds = [int(s) for s in dev_rng.choice(np.arange(40000, 45000), size=15, replace=False)]
    assert len(set(dev_seeds).intersection(set(v6_seeds))) == 0
    assert len(set(dev_seeds).intersection(ALL_HISTORICAL_SEEDS)) == 0
