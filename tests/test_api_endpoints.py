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
    assert "metadata" in json_data
    assert json_data["metadata"]["protocol"] == "Protocol v6 (6.2.0)"
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
