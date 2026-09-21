from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_empty_status():
    assert client.get("/healthz").status_code == 200
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["service"] == "CloudPilot"


def test_ingest_and_manual_tick():
    for index in range(6):
        response = client.post(
            "/api/telemetry",
            json={
                "timestamp": f"2026-01-01T00:0{index}:00Z",
                "request_rate": 10 + index * 5,
                "cpu_percent": 40,
                "memory_mb": 100,
                "p95_latency_ms": 120,
                "error_rate": 0,
                "restart_count": 0,
            },
        )
        assert response.status_code == 202
    assert client.post("/api/mode", json={"mode": "predictive"}).status_code == 200
    decision = client.post("/api/control/tick")
    assert decision.status_code == 200
    assert decision.json()["predicted_rps"] >= 0


def test_fixed_mode_requires_replica_count():
    response = client.post("/api/mode", json={"mode": "fixed"})
    assert response.status_code == 422


def test_experiment_lifecycle_calculates_measured_results():
    created = client.post(
        "/api/experiments",
        json={"name": "predictive spike run", "scenario": "spike", "mode": "predictive", "duration_seconds": 60},
    )
    assert created.status_code == 201
    experiment_id = created.json()["id"]
    assert client.post(f"/api/experiments/{experiment_id}/start").status_code == 200
    assert client.post(
        "/api/telemetry",
        json={
            "request_rate": 24,
            "cpu_percent": 55,
            "memory_mb": 140,
            "p95_latency_ms": 180,
            "error_rate": 0.01,
            "restart_count": 0,
        },
    ).status_code == 202
    completed = client.post(f"/api/experiments/{experiment_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["result"]["sample_count"] >= 1
    assert completed.json()["result"]["mean_p95_latency_ms"] >= 0
