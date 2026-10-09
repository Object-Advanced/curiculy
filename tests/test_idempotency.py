"""Idempotency keys: a replayed write is answered, not applied twice."""

import asyncio
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.idempotency import IdempotencyMiddleware, purge_expired_records
from app.core.security import create_access_token
from app.db import open_admin_session
from app.models.admin import IdempotencyRecord
from app.models.mixins import utcnow
from tests.test_auth import bearer, seed_user

pytest_plugins = ["tests.test_auth"]


def _token(client: TestClient, email: str = "parent@example.com") -> str:
    return client.post(
        "/api/auth/token", data={"username": email, "password": "secret"}
    ).json()["access_token"]


def _headers(token: str, key: str) -> dict[str, str]:
    return {**bearer(token), "Idempotency-Key": key}


class TestThroughTheApi:
    def test_a_replayed_write_is_answered_not_repeated(self, auth_client: TestClient) -> None:
        seed_user()
        token = _token(auth_client)
        first = auth_client.post(
            "/api/students", headers=_headers(token, "key-00000001"), json={"name": "Ada"}
        )
        again = auth_client.post(
            "/api/students", headers=_headers(token, "key-00000001"), json={"name": "Ada"}
        )

        assert first.status_code == again.status_code == 201
        assert again.json() == first.json()
        assert again.headers["idempotent-replayed"] == "true"
        names = [row["name"] for row in auth_client.get("/api/students", headers=bearer(token)).json()]
        assert names == ["Ada"]

    def test_writes_without_a_key_are_untouched(self, auth_client: TestClient) -> None:
        seed_user()
        token = _token(auth_client)
        for _ in range(2):
            auth_client.post("/api/students", headers=bearer(token), json={"name": "Ada"})
        assert len(auth_client.get("/api/students", headers=bearer(token)).json()) == 2

    def test_a_key_reused_for_another_request_is_refused(self, auth_client: TestClient) -> None:
        seed_user()
        token = _token(auth_client)
        auth_client.post("/api/students", headers=_headers(token, "key-00000002"), json={"name": "Ada"})
        clash = auth_client.patch(
            "/api/household", headers=_headers(token, "key-00000002"), json={"name": "Home"}
        )
        assert clash.status_code == 422

    def test_keys_are_scoped_to_the_household(self, auth_client: TestClient) -> None:
        seed_user("alpha@example.com", tenant_uuid="family-a")
        seed_user("beta@example.com", tenant_uuid="family-b")
        alpha, beta = _token(auth_client, "alpha@example.com"), _token(auth_client, "beta@example.com")

        auth_client.post("/api/students", headers=_headers(alpha, "shared-key-1"), json={"name": "Ada"})
        other = auth_client.post(
            "/api/students", headers=_headers(beta, "shared-key-1"), json={"name": "Cora"}
        )

        assert other.status_code == 201
        assert "idempotent-replayed" not in other.headers
        assert [row["name"] for row in auth_client.get("/api/students", headers=bearer(beta)).json()] == ["Cora"]

    def test_refusals_are_replayed_too(self, auth_client: TestClient) -> None:
        seed_user()
        token = _token(auth_client)
        first = auth_client.post("/api/students", headers=_headers(token, "key-00000003"), json={})
        again = auth_client.post("/api/students", headers=_headers(token, "key-00000003"), json={})
        assert first.status_code == again.status_code == 422
        assert again.headers["idempotent-replayed"] == "true"

    def test_malformed_keys_are_refused(self, auth_client: TestClient) -> None:
        seed_user()
        response = auth_client.post(
            "/api/students", headers=_headers(_token(auth_client), "no spaces!"), json={"name": "Ada"}
        )
        assert response.status_code == 400

    def test_old_records_are_purged(self, auth_client: TestClient) -> None:
        seed_user()
        token = _token(auth_client)
        auth_client.post("/api/students", headers=_headers(token, "key-00000004"), json={"name": "Ada"})
        session = open_admin_session()
        try:
            session.query(IdempotencyRecord).update({"created_at": utcnow() - timedelta(days=3)})
            session.commit()
        finally:
            session.close()

        assert purge_expired_records() == 1


def _counting_app(statuses: list[int]) -> tuple[IdempotencyMiddleware, list[int]]:
    calls: list[int] = []

    async def write(_request: Request) -> JSONResponse:
        calls.append(1)
        await asyncio.sleep(0.05)
        return JSONResponse({"call": len(calls)}, status_code=statuses[min(len(calls), len(statuses)) - 1])

    app = Starlette(routes=[Route("/api/thing", write, methods=["POST"])])
    return IdempotencyMiddleware(app), calls


@pytest.fixture
def signed_headers(auth_dir) -> dict[str, str]:
    token = create_access_token(subject="parent@example.com", tenant_uuid="family-1")
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": "race-key-0001"}


async def test_simultaneous_copies_run_once(signed_headers: dict[str, str]) -> None:
    app, calls = _counting_app([201])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        responses = await asyncio.gather(
            *(client.post("/api/thing", headers=signed_headers) for _ in range(5))
        )
    assert len(calls) == 1
    assert {response.json()["call"] for response in responses} == {1}


async def test_server_errors_are_not_stored(signed_headers: dict[str, str]) -> None:
    app, calls = _counting_app([500, 201])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        failed = await client.post("/api/thing", headers=signed_headers)
        retried = await client.post("/api/thing", headers=signed_headers)
    assert failed.status_code == 500
    assert retried.status_code == 201
    assert len(calls) == 2
