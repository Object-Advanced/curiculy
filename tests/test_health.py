"""GET /api/health: the process can reach Postgres, and reads no family's data."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "dev_mode": False}


def test_health_needs_no_sign_in_and_uses_the_real_database(committed_db: None) -> None:
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
