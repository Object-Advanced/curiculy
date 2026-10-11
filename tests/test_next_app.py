"""The React app (frontend/) is served under /next next to the legacy app."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><script type="module" src="/next/assets/app-abc123.js"></script>')
    (dist / "assets" / "app-abc123.js").write_text("console.log('trail')")
    monkeypatch.setattr(settings, "frontend_dist_dir", dist)
    return dist


def test_every_next_url_is_the_app_page(built: Path) -> None:
    client = TestClient(create_app())
    for path in ("/next", "/next/", "/next/trail", "/next/trail?student=3", "/next/some/deep/link"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "app-abc123.js" in response.text
        assert response.headers["cache-control"] == "no-cache"
        assert "default-src 'self'" in response.headers["content-security-policy"]


def test_hashed_assets_are_cached_forever(built: Path) -> None:
    client = TestClient(create_app())
    response = client.get("/next/assets/app-abc123.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    missing = client.get("/next/assets/gone-000.js")
    assert missing.status_code == 404
    assert "immutable" not in missing.headers.get("cache-control", "")


def test_without_a_build_next_is_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_dist_dir", tmp_path / "nothing")
    client = TestClient(create_app())
    assert client.get("/next/trail").status_code == 404
    assert client.get("/").status_code == 200


def test_frontend_api_contract_is_current() -> None:
    """frontend/openapi.json (what the typed client is built from) matches the API."""
    committed = json.loads((ROOT / "frontend" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == create_app().openapi(), (
        "The API changed: regenerate frontend/openapi.json and frontend/src/api/schema.d.ts "
        "(see frontend/README.md)."
    )
