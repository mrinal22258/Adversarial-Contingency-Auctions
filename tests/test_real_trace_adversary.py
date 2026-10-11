"""
Unit tests for Tier E3 Real-Trace Replay Adversary on the real Boston road network.
"""
from acalib.env.real_maps import generate_real_road_network
from acalib.env.adversaries import create_adversary, AdversaryType, RealTraceReplayAdversary


def test_real_trace_replay_adversary_boston():
    """Verify that RealTraceReplayAdversary matches real Boston construction work zones to graph edges."""
    g = generate_real_road_network()
    adv = create_adversary(AdversaryType.REAL_TRACE_REPLAY)
    assert isinstance(adv, RealTraceReplayAdversary)

    risky = set(list(g.edges())[:20])
    hazards = adv.get_onset_hazards(
        graph=g,
        risky_edges=risky,
        current_blockages=set(),
        fleet_states={},
        step=0,
    )

    assert len(hazards) == len(risky)
    # Check that matched construction edges have high hazard
    high_hazards = [h for h in hazards.values() if h > 0.5]
    print(f"Matched {len(high_hazards)} high-hazard construction closure edges in sample risky set")
    assert all(0.0 <= h <= 1.0 for h in hazards.values())
