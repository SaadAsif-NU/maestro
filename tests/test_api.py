from __future__ import annotations

from fastapi.testclient import TestClient

from maestro.server.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["brain"] == "simulated"


def test_index_is_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Maestro" in resp.text


def test_static_assets():
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_start_and_get_run():
    resp = client.post("/api/runs", json={"goal": "Ship a product"})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    assert run_id.startswith("run_")
    got = client.get(f"/api/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["goal"] == "Ship a product"


def test_missing_run_is_404():
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_list_runs():
    client.post("/api/runs", json={"goal": "list-me-A"})
    client.post("/api/runs", json={"goal": "list-me-B"})
    runs = client.get("/api/runs").json()["runs"]
    assert len(runs) >= 2
    assert {"run_id", "goal", "status"} <= set(runs[0])


def test_cancel_missing_run_is_404():
    assert client.post("/api/runs/nope/cancel").status_code == 404


def test_cancel_returns_ok():
    run_id = client.post("/api/runs", json={"goal": "cancel-me"}).json()["run_id"]
    resp = client.post(f"/api/runs/{run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] in {"cancelled", "not_running"}


def test_team_size_is_configurable():
    run_id = client.post("/api/runs", json={"goal": "big team", "researchers": 4}).json()["run_id"]
    assert run_id.startswith("run_")


def test_config_lists_providers_with_status():
    cfg = client.get("/api/config").json()
    ids = {p["id"] for p in cfg["providers"]}
    assert {"simulated", "gemini", "openai"} <= ids
    simulated = next(p for p in cfg["providers"] if p["id"] == "simulated")
    assert simulated["configured"] is True and simulated["models"]
    assert "provider" in cfg["default"] and "model" in cfg["default"]


def test_run_with_unconfigured_provider_is_400(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    resp = client.post("/api/runs", json={"goal": "x", "provider": "gemini"})
    assert resp.status_code == 400
    assert "GEMINI_API_KEY" in resp.json()["error"]


def test_run_with_offline_provider_ok():
    resp = client.post("/api/runs", json={"goal": "x", "provider": "simulated"})
    assert resp.status_code == 200


def test_invalid_goal_is_422():
    assert client.post("/api/runs", json={"goal": ""}).status_code == 422


def test_websocket_streams_a_full_run():
    run_id = client.post("/api/runs", json={"goal": "Design a launch plan"}).json()["run_id"]
    types: list[str] = []
    deliverable = None
    with client.websocket_connect(f"/api/runs/{run_id}/events") as ws:
        while True:
            msg = ws.receive_json()
            types.append(msg["type"])
            if msg["type"] == "run_completed":
                deliverable = msg["data"]["deliverable"]
                break
    assert "agent_spawned" in types
    assert "token" in types
    assert deliverable and deliverable.startswith("#")
