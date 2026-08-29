"""App shell and service worker are served from the API origin."""

from fastapi.testclient import TestClient


def test_service_worker_script(client: TestClient) -> None:
    response = client.get("/sw.js")
    assert response.status_code == 200
    body = response.text
    assert "curiculy-sync" in body
    assert "outbox" in body
    assert "sync-outbox" in body
    assert response.headers.get("service-worker-allowed") == "/"
    assert "javascript" in response.headers.get("content-type", "")
