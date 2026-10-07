"""
Unit tests asserting real map data integrity, SHA-256 hashes, node/edge counts,
and deterministic graph conversion procedures.
"""

import os
import hashlib
import networkx as nx
import pytest

from acalib.env.real_maps import (
    MOVINGAI_WAREHOUSE_HASH,
    OSMNX_ROAD_NETWORK_HASH,
    DATA_MAPS_DIR,
    verify_file_sha256,
    generate_movingai_warehouse,
    generate_real_road_network,
)


def test_movingai_file_hash():
    """Assert actual MovingAI warehouse map file exists and matches its byte-level SHA-256."""
    map_path = os.path.join(DATA_MAPS_DIR, "warehouse-10-20-10-2-1.map")
    assert os.path.exists(map_path), f"File {map_path} must exist"
    
    with open(map_path, "rb") as f:
        data = f.read()
    computed_hash = hashlib.sha256(data).hexdigest()
    assert computed_hash == MOVINGAI_WAREHOUSE_HASH, (
        f"MovingAI hash mismatch: expected {MOVINGAI_WAREHOUSE_HASH}, got {computed_hash}"
    )
    # Ensure it's not the empty string hash
    assert computed_hash != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert len(data) == 10242


def test_osmnx_file_hash():
    """Assert actual OSMnx Boston street network GraphML exists and matches its byte-level SHA-256."""
    graphml_path = os.path.join(DATA_MAPS_DIR, "boston_downtown_drive.graphml")
    assert os.path.exists(graphml_path), f"File {graphml_path} must exist"
    
    with open(graphml_path, "rb") as f:
        data = f.read()
    computed_hash = hashlib.sha256(data).hexdigest()
    assert computed_hash == OSMNX_ROAD_NETWORK_HASH, (
        f"OSMnx GraphML hash mismatch: expected {OSMNX_ROAD_NETWORK_HASH}, got {computed_hash}"
    )
    assert len(data) > 100000


def test_movingai_graph_full_resolution():
    """Assert full-resolution MovingAI graph generation (4-connected, connected component)."""
    g = generate_movingai_warehouse(n_nodes=None)
    assert nx.is_connected(g), "Warehouse graph must be connected"
    assert len(g.nodes()) == 5699, f"Expected 5699 nodes, got {len(g.nodes())}"
    assert len(g.edges()) == 8778, f"Expected 8778 edges, got {len(g.edges())}"
    assert g.graph["sha256"] == MOVINGAI_WAREHOUSE_HASH
    assert g.graph["map_type"] == "MovingAI_Warehouse"


def test_movingai_graph_coarsened():
    """Assert deterministic coarsening produces valid, connected graph of realistic size."""
    g_small = generate_movingai_warehouse(n_nodes=40)
    assert nx.is_connected(g_small)
    assert len(g_small.nodes()) == 38
    assert len(g_small.edges()) == 59

    g_med = generate_movingai_warehouse(n_nodes=56)
    assert nx.is_connected(g_med)
    assert len(g_med.nodes()) == 56
    assert len(g_med.edges()) == 76


def test_osmnx_road_network_graph():
    """Assert OSMnx road network graph has realistic size (>= 100 nodes), valid coordinates, and connectivity."""
    g = generate_real_road_network()
    assert nx.is_connected(g), "Road network must be connected"
    assert len(g.nodes()) >= 100, f"Expected >= 100 nodes, got {len(g.nodes())}"
    assert len(g.nodes()) == 216, f"Expected 216 nodes, got {len(g.nodes())}"
    assert len(g.edges()) == 323, f"Expected 323 edges, got {len(g.edges())}"
    assert g.graph["sha256"] == OSMNX_ROAD_NETWORK_HASH
    assert g.graph["map_type"] == "RealRoadNetwork_OSMNx"
    assert g.graph["city"] == "Boston_Downtown"

    # Check node positions
    for node, data in g.nodes(data=True):
        assert "pos" in data
        x, y = data["pos"]
        assert 0.0 <= x <= 100.0
        assert 0.0 <= y <= 100.0

    # Check edge weights
    for u, v, data in g.edges(data=True):
        assert "weight" in data
        assert data["weight"] > 0
