"""JWT login, demo mode, and tenant routing."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    DEMO_TENANT_UUID,
    DEV_TENANT_UUID,
    create_access_token,
    decode_access_token,
    hash_password,
    user_from_token,
    verify_password,
)
from app.db import get_catalog_db, open_admin_session, tenant_file_url
from app.main import create_app
from app.models.admin import InviteKey, User


@pytest.fixture
def auth_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(
        settings, "jwt_secret", "pytest-auth-jwt-secret-not-used-in-production"
    )
    monkeypatch.setattr(settings, "admin_database_url", f"sqlite:///{tmp_path / 'admin.db'}")
    monkeypatch.setattr(settings, "tenant_database_url", f"sqlite:///{tmp_path / 'tenant.db'}")
    return tmp_path


@pytest.fixture
def auth_client(auth_dir: Path, db: Session) -> Iterator[TestClient]:
    """HTTP client with real ``admin.db`` and ``tenant_{uuid}.db`` under tmp_path.

    Does not override ``get_tenant_db`` or ``get_current_user``. Catalog stays
    on the in-memory ``db`` session. Never writes ``./data``.
    """
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    try:
        yield TestClient(application)
    finally:
        application.dependency_overrides.clear()


def seed_user(
    email: str = "parent@example.com",
    password: str = "secret",
    tenant_uuid: str = "family-1",
    is_admin: bool = False,
) -> User:
    session = open_admin_session()
    try:
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            tenant_uuid=tenant_uuid,
            is_admin=is_admin,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def seed_invite(key: str = "abcd1234") -> InviteKey:
    session = open_admin_session()
    try:
        invite = InviteKey(key=key, tenant_uuid="")
        session.add(invite)
        session.commit()
        session.refresh(invite)
        return invite
    finally:
        session.close()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_hash_and_verify_password() -> None:
    hashed = hash_password("secret")
    assert hashed != "secret"
    assert verify_password("secret", hashed)
    assert not verify_password("other", hashed)


def test_user_from_token_requires_jwt(auth_dir: Path) -> None:
    with pytest.raises(HTTPException) as caught:
        user_from_token(None)
    assert caught.value.status_code == 401


def test_user_from_token_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dev_mode", True)
    user = user_from_token(None)
    assert user.tenant_uuid == DEV_TENANT_UUID
    assert user.email == "dev@local"
    assert user.is_admin is True


def test_create_and_decode_access_token(auth_dir: Path) -> None:
    token = create_access_token(subject="parent@example.com", tenant_uuid="family-1")
    payload = decode_access_token(token)
    assert payload["sub"] == "parent@example.com"
    assert payload["tenant_uuid"] == "family-1"
    assert payload["jti"]
    assert payload["is_admin"] is False


def test_expired_token_is_rejected(auth_dir: Path) -> None:
    token = create_access_token(
        subject="parent@example.com",
        tenant_uuid="family-1",
        expires_delta=timedelta(seconds=-5),
    )
    with pytest.raises(HTTPException) as caught:
        decode_access_token(token)
    assert caught.value.status_code == 401
    assert caught.value.detail == "Token has expired"


def test_tenant_file_url(auth_dir: Path) -> None:
    url = tenant_file_url("family-1")
    assert url.endswith("/tenant_family-1.db")
    assert Path(url.removeprefix("sqlite:///")).name == "tenant_family-1.db"


def test_login_success(auth_client: TestClient) -> None:
    seed_user()
    response = auth_client.post(
        "/api/auth/token",
        data={"username": "parent@example.com", "password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == "parent@example.com"
    assert payload["tenant_uuid"] == "family-1"
    assert payload["is_admin"] is False


def test_login_rejects_bad_password(auth_client: TestClient) -> None:
    seed_user()
    response = auth_client.post(
        "/api/auth/token",
        data={"username": "parent@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_demo_token_uses_demo_tenant(auth_client: TestClient) -> None:
    response = auth_client.post("/api/auth/demo")
    assert response.status_code == 200
    payload = decode_access_token(response.json()["access_token"])
    assert payload["tenant_uuid"] == DEMO_TENANT_UUID
    assert payload["demo"] is True


def test_household_requires_auth(auth_client: TestClient) -> None:
    response = auth_client.get("/api/household")
    assert response.status_code == 401


def test_demo_token_opens_an_empty_tenant(auth_client: TestClient) -> None:
    token = auth_client.post("/api/auth/demo").json()["access_token"]
    household = auth_client.get("/api/household", headers=bearer(token))
    assert household.status_code == 200
    created = auth_client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Ada"},
    )
    assert created.status_code == 201
    students = auth_client.get("/api/students", headers=bearer(token))
    assert [row["name"] for row in students.json()] == ["Ada"]


def test_demo_sessions_do_not_share_data(auth_client: TestClient) -> None:
    first = auth_client.post("/api/auth/demo").json()["access_token"]
    second = auth_client.post("/api/auth/demo").json()["access_token"]
    auth_client.post("/api/students", headers=bearer(first), json={"name": "Ada"})
    other = auth_client.get("/api/students", headers=bearer(second))
    assert other.status_code == 200
    assert other.json() == []


def test_concurrent_requests_to_one_demo_household(auth_client: TestClient) -> None:
    """The SPA loads several things at once. A demo household shared one
    in-memory connection across threads, so parallel reads returned 404s and
    500s ("bad parameter or other API misuse")."""
    token = auth_client.post("/api/auth/demo").json()["access_token"]
    student = auth_client.post(
        "/api/students", headers=bearer(token), json={"name": "Ada"}
    ).json()
    for day in range(1, 6):
        auth_client.post(
            "/api/assignments",
            headers=bearer(token),
            json={
                "student_id": student["id"],
                "title": f"Lesson {day}",
                "scheduled_date": f"2026-10-0{day}",
            },
        )
    paths = [
        f"/api/students/{student['id']}/courses",
        f"/api/students/{student['id']}/assignments?start_date=2026-10-01",
    ] * 30

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(
            pool.map(lambda path: auth_client.get(path, headers=bearer(token)).status_code, paths)
        )

    assert statuses == [200] * len(paths)


def test_only_recent_demo_households_are_kept(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.db as db_module

    monkeypatch.setattr(db_module, "DEMO_HOUSEHOLD_LIMIT", 2)
    monkeypatch.setattr(db_module, "demo_data_dir", lambda: tmp_path)
    for _ in range(3):
        token = auth_client.post("/api/auth/demo").json()["access_token"]
        assert auth_client.get("/api/students", headers=bearer(token)).status_code == 200

    assert len(list(tmp_path.glob("demo_*.db"))) == 2


def test_login_routes_to_tenant_file(auth_client: TestClient, auth_dir: Path) -> None:
    tenant_uuid = str(uuid4())
    seed_user(tenant_uuid=tenant_uuid)
    token = auth_client.post(
        "/api/auth/token",
        data={"username": "parent@example.com", "password": "secret"},
    ).json()["access_token"]
    response = auth_client.get("/api/household", headers=bearer(token))
    assert response.status_code == 200
    tenant_path = auth_dir / f"tenant_{tenant_uuid}.db"
    assert tenant_path.exists()


def _student_names_on_disk(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT name FROM students ORDER BY id").fetchall()
        return [row[0] for row in rows]
    finally:
        connection.close()


def test_physical_tenant_files_persist_and_stay_isolated(
    auth_client: TestClient, auth_dir: Path
) -> None:
    """JWT → admin user → tenant_{uuid}.db; a second connection sees committed rows."""
    seed_user(email="alpha@example.com", tenant_uuid="family-a")
    seed_user(email="beta@example.com", tenant_uuid="family-b")
    alpha = _login(auth_client, "alpha@example.com")
    beta = _login(auth_client, "beta@example.com")

    created_a = auth_client.post(
        "/api/students",
        headers=bearer(alpha),
        json={"name": "Ada"},
    )
    created_b = auth_client.post(
        "/api/students",
        headers=bearer(beta),
        json={"name": "Blaise"},
    )
    assert created_a.status_code == 201
    assert created_b.status_code == 201

    path_a = auth_dir / "tenant_family-a.db"
    path_b = auth_dir / "tenant_family-b.db"
    assert path_a.is_file()
    assert path_b.is_file()
    assert _student_names_on_disk(path_a) == ["Ada"]
    assert _student_names_on_disk(path_b) == ["Blaise"]

    listed_a = auth_client.get("/api/students", headers=bearer(alpha))
    listed_b = auth_client.get("/api/students", headers=bearer(beta))
    assert [row["name"] for row in listed_a.json()] == ["Ada"]
    assert [row["name"] for row in listed_b.json()] == ["Blaise"]


def test_auth_me_for_logged_in_user(auth_client: TestClient) -> None:
    seed_user()
    token = auth_client.post(
        "/api/auth/token",
        data={"username": "parent@example.com", "password": "secret"},
    ).json()["access_token"]
    response = auth_client.get("/api/auth/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {
        "email": "parent@example.com",
        "tenant_uuid": "family-1",
        "is_demo": False,
        "is_admin": False,
        "role": "parent",
        "student_id": None,
        "display_name": "Default household",
    }


def test_health_is_public_and_reports_dev_mode(auth_client: TestClient) -> None:
    response = auth_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["dev_mode"] is False
    assert set(body) == {"status", "database", "dev_mode"}


def _login(client: TestClient, email: str = "parent@example.com", password: str = "secret") -> str:
    return client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    ).json()["access_token"]


def test_register_with_invite_provisions_tenant(auth_client: TestClient, auth_dir: Path) -> None:
    seed_invite("abcd1234")
    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "New.Family@example.com",
            "password": "password1",
            "invite_key": "ABCD1234",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]
    assert isinstance(token, str) and token
    claims = decode_access_token(token)
    assert claims["sub"] == "new.family@example.com"
    tenant_uuid = claims["tenant_uuid"]
    assert (auth_dir / f"tenant_{tenant_uuid}.db").exists()

    session = open_admin_session()
    try:
        invite = session.query(InviteKey).filter(InviteKey.key == "abcd1234").one()
        assert invite.redeemed_at is not None
        assert invite.tenant_uuid == tenant_uuid
        assert invite.email == "new.family@example.com"
        user = session.query(User).filter(User.email == "new.family@example.com").one()
        assert user.tenant_uuid == tenant_uuid
    finally:
        session.close()

    household = auth_client.get("/api/household", headers=bearer(token))
    assert household.status_code == 200
    created = auth_client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Ada"},
    )
    assert created.status_code == 201


def test_register_rejects_used_or_unknown_invite(auth_client: TestClient) -> None:
    seed_invite("abcd1234")
    first = auth_client.post(
        "/api/auth/register",
        json={
            "email": "one@example.com",
            "password": "password1",
            "invite_key": "abcd1234",
        },
    )
    assert first.status_code == 201
    reused = auth_client.post(
        "/api/auth/register",
        json={
            "email": "two@example.com",
            "password": "password1",
            "invite_key": "abcd1234",
        },
    )
    assert reused.status_code == 400
    unknown = auth_client.post(
        "/api/auth/register",
        json={
            "email": "two@example.com",
            "password": "password1",
            "invite_key": "zzzzzzzz",
        },
    )
    assert unknown.status_code == 400


def test_register_rejects_duplicate_email(auth_client: TestClient) -> None:
    seed_invite("abcd1234")
    seed_invite("efgh5678")
    auth_client.post(
        "/api/auth/register",
        json={
            "email": "parent@example.com",
            "password": "password1",
            "invite_key": "abcd1234",
        },
    )
    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "parent@example.com",
            "password": "password1",
            "invite_key": "efgh5678",
        },
    )
    assert response.status_code == 409


def test_register_rejects_short_password(auth_client: TestClient) -> None:
    seed_invite("abcd1234")
    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "parent@example.com",
            "password": "short",
            "invite_key": "abcd1234",
        },
    )
    assert response.status_code == 422


def test_admin_jwt_claim_and_invite_flow(auth_client: TestClient) -> None:
    seed_user(is_admin=True)
    token = _login(auth_client)
    payload = decode_access_token(token)
    assert payload["is_admin"] is True

    created = auth_client.post("/api/admin/invite", headers=bearer(token))
    assert created.status_code == 201
    key = created.json()["key"]
    assert len(key) == 8

    listed = auth_client.get("/api/admin/invites", headers=bearer(token))
    assert listed.status_code == 200
    assert [row["key"] for row in listed.json()] == [key]


def test_non_admin_cannot_create_invites(auth_client: TestClient) -> None:
    seed_user(is_admin=False)
    token = _login(auth_client)
    response = auth_client.post("/api/admin/invite", headers=bearer(token))
    assert response.status_code == 403


def test_demo_cannot_create_invites(auth_client: TestClient) -> None:
    token = auth_client.post("/api/auth/demo").json()["access_token"]
    response = auth_client.post("/api/admin/invite", headers=bearer(token))
    assert response.status_code == 403


def test_admin_me_reports_is_admin(auth_client: TestClient) -> None:
    seed_user(is_admin=True)
    token = _login(auth_client)
    response = auth_client.get("/api/auth/me", headers=bearer(token))
    assert response.json()["is_admin"] is True
