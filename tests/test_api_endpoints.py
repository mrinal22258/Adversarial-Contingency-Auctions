"""
Unit tests for FastAPI endpoints in app.py.
Tests:
1. /api/simulate returns 200 and valid JSON schema with nodes, edges, summary, events.
2. /api/compare returns 200 and paired comparison metrics table.
3. /api/monte_carlo returns 200 and summary statistics.
4. /api/export_json and /api/export_csv return valid telemetry attachments.
5. /hud redirects to / (307/302).
6. Input validation: invalid parameters return 422 Unprocessable Entity instead of crashing with 500.
"""

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_api_simulate_success(client):
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "adversary": "Reactive (Corridor Interdiction)",
        "numRobots": 2,
        "numTasks": 4,
        "seed": 10001,
        "maxSteps": 20,
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "summary" in data
    assert "nodes" in data
    assert len(data["nodes"]) == 38
    assert "edges" in data
    assert "events" in data
    assert "max_ticks" in data


def test_api_simulate_invalid_input(client):
    # numRobots must be >= 1, test with 0 or string
    resp = client.post("/api/simulate", json={"numRobots": 0})
    assert resp.status_code == 422

    resp = client.post("/api/simulate", json={"topology": "non_existent_map"})
    assert resp.status_code == 422


def test_api_compare_success(client):
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "adversary": "Reactive (Corridor Interdiction)",
        "numRobots": 2,
        "numTasks": 4,
        "seed": 10001,
    }
    resp = client.post("/api/compare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "table" in data
    assert len(data["table"]) > 0


def test_api_export_json_and_csv(client):
    # First ensure simulation has run
    client.post("/api/simulate", json={
        "topology": "warehouse_small",
        "numRobots": 2,
        "numTasks": 4,
        "maxSteps": 15,
        "seed": 10001,
    })

    # Test JSON export
    resp_json = client.get("/api/export_json")
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers["content-type"]
    json_data = resp_json.json()
    from acalib import PROTOCOL_FULL_NAME
    assert json_data["metadata"]["protocol"] == PROTOCOL_FULL_NAME
    assert "history" in json_data
    assert len(json_data["history"]) > 0

    # Test CSV export
    resp_csv = client.get("/api/export_csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    csv_text = resp_csv.text
    assert "tick,completed_tasks,conflicts,messages,travel,welfare" in csv_text
    lines = [line.strip() for line in csv_text.strip().split("\n") if line.strip()]
    assert len(lines) > 1  # Header + rows from real history


def test_hud_redirect(client):
    resp = client.get("/hud", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/"


def test_no_duplicate_routes():
    from starlette.routing import Route
    seen = set()
    duplicates = []
    for route in app.routes:
        if isinstance(route, Route):
            for method in route.methods or []:
                key = (method, route.path)
                if key in seen:
                    duplicates.append(key)
                seen.add(key)
    assert not duplicates, f"Found duplicate (method, path) route registrations: {duplicates}"


def test_protocol_version_consistency():
    from acalib import PROTOCOL_LABEL
    import inspect
    import acalib.demo.ui.layout as layout_module

    layout_source = inspect.getsource(layout_module)
    version_tag = PROTOCOL_LABEL.split()[-1].lower()  # e.g., 'v6'
    assert f">{version_tag}<" in layout_source, f"HUD badge must display {version_tag}"
    assert "Protocol v6 registered" in layout_source, "Protocol notice bar must state Protocol v6 registered"


def test_export_empty_store_returns_404(client):
    from app import _RUN_STORE
    _RUN_STORE.clear()

    resp_json = client.get("/api/export_json")
    assert resp_json.status_code == 404
    assert "No simulation has been run" in resp_json.json()["detail"]

    resp_csv = client.get("/api/export_csv")
    assert resp_csv.status_code == 404
    assert "No simulation has been run" in resp_csv.json()["detail"]


def test_export_by_run_id(client):
    resp = client.post("/api/simulate", json={
        "topology": "warehouse_small",
        "numRobots": 2,
        "numTasks": 4,
        "maxSteps": 15,
        "seed": 20002,
    })
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    assert run_id is not None

    # Export specific run_id
    resp_json = client.get(f"/api/export_json?run_id={run_id}")
    assert resp_json.status_code == 200
    assert resp_json.json()["metadata"]["run_id"] == run_id

    # Non-existent run_id returns 404
    resp_404 = client.get("/api/export_json?run_id=non-existent-uuid")
    assert resp_404.status_code == 404


def test_concurrent_simulation_and_exports(client):
    import concurrent.futures

    def run_sim(seed):
        resp = client.post("/api/simulate", json={
            "topology": "warehouse_small",
            "numRobots": 2,
            "numTasks": 4,
            "maxSteps": 15,
            "seed": seed,
        })
        return resp.json()

    def get_export():
        resp = client.get("/api/export_json")
        if resp.status_code == 200:
            return resp.json()
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        sim_futures = [executor.submit(run_sim, 1000 + i) for i in range(4)]
        export_futures = [executor.submit(get_export) for _ in range(6)]
        _ = [f.result() for f in sim_futures]
        export_results = [f.result() for f in export_futures]

    for export in export_results:
        if export is not None:
            assert "metadata" in export
            assert "summary" in export
            assert "history" in export
            # Verify internal snapshot integrity
            assert len(export["history"]) == export["summary"]["makespan"]
            assert export["metadata"]["run_id"] is not None


def test_api_health_and_version(client):
    from acalib import __version__, PROTOCOL_VERSION, PROTOCOL_FULL_NAME

    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"

    resp_version = client.get("/api/version")
    assert resp_version.status_code == 200
    v_data = resp_version.json()
    assert v_data["version"] == __version__
    assert v_data["protocol_version"] == PROTOCOL_VERSION
    assert v_data["protocol_full_name"] == PROTOCOL_FULL_NAME


def test_security_headers_and_payload_cap(client):
    """P4, F-25: Security headers present and oversized payloads rejected with 413."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"

    # Oversized payload rejected
    large_payload = {"padding": "x" * 1_200_000}
    resp_large = client.post("/api/simulate", json=large_payload)
    assert resp_large.status_code == 413


def test_rate_limiter_429(client, monkeypatch):
    """F-25: Exceeding ACA_RATE_LIMIT_PER_MIN returns HTTP 429 with Retry-After header."""
    from app import _RATE_LIMITER
    _RATE_LIMITER.reset()
    monkeypatch.setenv("ACA_RATE_LIMIT_PER_MIN", "2")

    payload = {
        "topology": "warehouse_small",
        "numRobots": 2,
        "numTasks": 2,
        "maxSteps": 10,
        "seed": 10001,
    }

    # Request 1: allowed
    r1 = client.post("/api/simulate", json=payload)
    assert r1.status_code == 200

    # Request 2: allowed
    r2 = client.post("/api/simulate", json=payload)
    assert r2.status_code == 200

    # Request 3: rate limited
    r3 = client.post("/api/simulate", json=payload)
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert int(r3.headers["Retry-After"]) >= 1
    assert "Rate limit" in r3.json()["detail"]

    # Reset limiter for subsequent tests
    _RATE_LIMITER.reset()


def test_monte_carlo_pydantic_bounds(client):
    """F-25: Monte Carlo trial count bounded via Pydantic Field(ge=1, le=50)."""
    # Over max 50
    r_over = client.post("/api/monte_carlo", json={"numTrials": 100})
    assert r_over.status_code == 422

    # Under min 1
    r_under = client.post("/api/monte_carlo", json={"numTrials": 0})
    assert r_under.status_code == 422


def test_api_simulate_depth_zero(client):
    """Verify depth=0 ablation can be requested and executed cleanly without crashing."""
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "numRobots": 2,
        "numTasks": 3,
        "seed": 10001,
        "maxSteps": 15,
        "depth": 0,
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["summary"]["makespan"] > 0


def test_api_simulate_blocked_edges(client):
    """Verify programmatic obstacle injection via blockedEdges."""
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "numRobots": 2,
        "numTasks": 3,
        "seed": 10001,
        "maxSteps": 15,
        "blockedEdges": [[0, 1]],
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["blocked_edges"]) > 0


def test_api_compare_with_custom_parameters(client):
    """Verify /api/compare respects maxSteps, depth, commRange, and pDrop."""
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "adversary": "Reactive (Corridor Interdiction)",
        "numRobots": 2,
        "numTasks": 3,
        "seed": 10001,
        "maxSteps": 15,
        "depth": 0,
        "commRange": 40.0,
        "pDrop": 0.05,
    }
    resp = client.post("/api/compare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["table"]) >= 5


def test_api_monte_carlo_execution(client):
    """Verify /api/monte_carlo returns real summary with comparison records and verdict."""
    payload = {
        "topology": "warehouse_small",
        "allocator": "ACA (Ours)",
        "adversary": "Reactive (Corridor Interdiction)",
        "numRobots": 2,
        "numTasks": 2,
        "numTrials": 2,
        "maxSteps": 10,
        "seedBase": 10001,
    }
    resp = client.post("/api/monte_carlo", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    summary = data["summary"]
    assert "n_seeds" in summary
    assert summary["n_seeds"] == 2
    assert "main_method" in summary
    assert "verdict" in summary
    assert "comparisons" in summary
    assert isinstance(summary["comparisons"], list)


def test_blocked_edges_validation_audit_cases(client):
    """Verify all 4 audit cases of invalid blockedEdges are rejected with HTTP 422."""
    base_payload = {
        "topology": "warehouse_small",
        "numRobots": 2,
        "numTasks": 2,
        "maxSteps": 10,
        "seed": 10001,
    }

    # Case 1: single element list
    r1 = client.post("/api/simulate", json={**base_payload, "blockedEdges": [[1]]})
    assert r1.status_code == 422

    # Case 2: 3-element list
    r2 = client.post("/api/simulate", json={**base_payload, "blockedEdges": [[1, 2, 3]]})
    assert r2.status_code == 422

    # Case 3: string endpoints
    r3 = client.post("/api/simulate", json={**base_payload, "blockedEdges": [["x", "y"]]})
    assert r3.status_code == 422

    # Case 4: non-existent edge in graph topology
    r4 = client.post("/api/simulate", json={**base_payload, "blockedEdges": [[999, 1000]]})
    assert r4.status_code == 422


def test_streaming_payload_cap_without_content_length(client):
    """Verify streaming body-size enforcement rejects >1MB payload even when Content-Length is spoofed or absent."""
    oversized_data = b"x" * 1_200_000

    # Spoofed understated Content-Length header
    resp_spoofed = client.post(
        "/api/simulate",
        content=oversized_data,
        headers={"content-type": "application/json", "content-length": "10"},
    )
    assert resp_spoofed.status_code == 413
    assert resp_spoofed.headers.get("x-content-type-options") == "nosniff"
    assert resp_spoofed.headers.get("x-frame-options") == "DENY"

    # Normal health check still returns 200 with security headers
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    assert resp_health.headers.get("x-content-type-options") == "nosniff"
    assert resp_health.headers.get("x-frame-options") == "DENY"


def test_unknown_adversary_and_allocator_rejected_422(client):
    """Verify that unknown adversary and unknown allocator names return HTTP 422 across endpoints."""
    # /api/simulate
    r_sim_adv = client.post("/api/simulate", json={"adversary": "DefinitelyNotAnAdversary"})
    assert r_sim_adv.status_code == 422, f"Expected 422, got {r_sim_adv.status_code}"

    r_sim_alloc = client.post("/api/simulate", json={"allocator": "DefinitelyNotAnAllocator"})
    assert r_sim_alloc.status_code == 422, f"Expected 422, got {r_sim_alloc.status_code}"

    # /api/compare
    r_comp_adv = client.post("/api/compare", json={"adversary": "DefinitelyNotAnAdversary"})
    assert r_comp_adv.status_code == 422, f"Expected 422, got {r_comp_adv.status_code}"

    r_comp_alloc = client.post("/api/compare", json={"allocator": "DefinitelyNotAnAllocator"})
    assert r_comp_alloc.status_code == 422, f"Expected 422, got {r_comp_alloc.status_code}"

    # /api/monte-carlo and /api/monte_carlo
    r_mc_adv = client.post("/api/monte-carlo", json={"adversary": "DefinitelyNotAnAdversary"})
    assert r_mc_adv.status_code == 422, f"Expected 422, got {r_mc_adv.status_code}"

    r_mc_alloc = client.post("/api/monte-carlo", json={"allocator": "DefinitelyNotAnAllocator"})
    assert r_mc_alloc.status_code == 422, f"Expected 422, got {r_mc_alloc.status_code}"

    r_mc_adv2 = client.post("/api/monte_carlo", json={"adversary": "DefinitelyNotAnAdversary"})
    assert r_mc_adv2.status_code == 422, f"Expected 422, got {r_mc_adv2.status_code}"

    r_mc_alloc2 = client.post("/api/monte_carlo", json={"allocator": "DefinitelyNotAnAllocator"})
    assert r_mc_alloc2.status_code == 422, f"Expected 422, got {r_mc_alloc2.status_code}"







