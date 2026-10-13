"""
Tests for Protocol v6 Seed Disjointness and Integrity (Section 8 / Gate 11).
Asserts that v6 seeds are strictly disjoint from all historical seeds across:
- Sweep v1-v4 (1..30)
- Protocol v5 held-out (101..130)
- Stage4 pilot (1000..1060)
- SITL physics trials (20000..20359)
- Demo/ablation seeds (10001..10010)
"""

import os
import re
import ast
import hashlib
import yaml
import numpy as np
import pytest

# Frozen historical seed sets
V1_V4_SEEDS = set(range(1, 31))
V5_HELDOUT_SEEDS = set(range(101, 131))
STAGE4_PILOT_SEEDS = set(range(1000, 1061))
SITL_SEEDS = set(range(20000, 20360))
DEMO_SEEDS = set(range(10001, 10011))

ALL_HISTORICAL_SEEDS = V1_V4_SEEDS | V5_HELDOUT_SEEDS | STAGE4_PILOT_SEEDS | SITL_SEEDS | DEMO_SEEDS

EXPECTED_V6_SHA256 = "09638b69b6d331eb3738023b4ad7502116e7d4768405235cf396d76bc3eea5cb"
EXPECTED_DEV_SHA256 = "19a8aabd61d3f15800164feae865f285ec0d8b4ccc13619534a940d57d63417c"


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


def generate_dev_seeds(n_seeds: int = 15, rng_seed: int = 9992026) -> list[int]:
    """Deterministically generate development seeds disjoint from historical runs."""
    dev_rng = np.random.default_rng(rng_seed)
    candidates = dev_rng.choice(np.arange(40000, 45000), size=n_seeds * 2, replace=False)
    dev_seeds = []
    for s in candidates:
        int_s = int(s)
        if int_s not in ALL_HISTORICAL_SEEDS:
            dev_seeds.append(int_s)
        if len(dev_seeds) == n_seeds:
            break
    return sorted(dev_seeds)


def parse_seeds_from_prereg_md(filepath: str = "protocols/prereg-v6.md") -> list[int]:
    """Parse the confirmatory seed list from prereg-v6.md."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"Confirmatory Seeds.*?`(\[[0-9,\s]+\])`", content, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find confirmatory seeds list in {filepath}")
    return ast.literal_eval(match.group(1))


def parse_seeds_from_yaml(filepath: str = "experiments/configs/protocol_v6.yaml") -> list[int]:
    """Parse the confirmatory seed list from protocol_v6.yaml."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["evaluation_design"]["confirmatory_phase"]["seeds"]


@pytest.mark.core
def test_v6_seed_disjointness():
    v6_seeds = generate_v6_seeds(n_seeds=50)
    assert len(v6_seeds) == 50
    assert len(set(v6_seeds)) == 50

    overlap = set(v6_seeds).intersection(ALL_HISTORICAL_SEEDS)
    assert len(overlap) == 0, f"Protocol v6 seeds overlap with historical seeds: {overlap}"

    dev_seeds = generate_dev_seeds(n_seeds=15)
    assert len(dev_seeds) == 15
    assert len(set(dev_seeds).intersection(set(v6_seeds))) == 0
    assert len(set(dev_seeds).intersection(ALL_HISTORICAL_SEEDS)) == 0


@pytest.mark.core
def test_v6_seed_exact_protocol_matching():
    """Assert exact equality between generated seeds, protocol YAML, and prereg markdown."""
    gen_seeds = generate_v6_seeds(n_seeds=50)
    yaml_seeds = parse_seeds_from_yaml()
    md_seeds = parse_seeds_from_prereg_md()

    assert yaml_seeds == gen_seeds, "protocol_v6.yaml does not match generated seeds"
    assert md_seeds == gen_seeds, "protocols/prereg-v6.md does not match generated seeds"

    # Verify SHA-256 matches frozen hash
    v6_hash = hashlib.sha256(str(gen_seeds).encode()).hexdigest()
    assert v6_hash == EXPECTED_V6_SHA256, f"v6 seed hash {v6_hash} does not match {EXPECTED_V6_SHA256}"

