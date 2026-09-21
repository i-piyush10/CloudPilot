from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_work():
    assert client.get("/healthz").status_code == 200
    response = client.get("/api/work?iterations=100")
    assert response.status_code == 200
    assert response.json()["iterations"] == 100


def test_controlled_failure():
    assert client.get("/api/work?iterations=100&fail=true").status_code == 503


def test_metrics_are_exposed():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "workload_http_requests_total" in response.text

