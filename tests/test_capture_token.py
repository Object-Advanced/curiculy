"""Capture credentials: upload-only tokens for the Chrome extension."""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import (
    CAPTURE_TOKEN_SCOPE,
    create_access_token,
    decode_access_token,
    hash_password,
)
from app.db import open_admin_session
from app.enums import UserRole
from app.models.admin import CaptureToken, User
from app.models.mixins import utcnow
from app.services.child_accounts import child_account_email, token_for_account
from tests.test_auth import bearer, seed_user
from tests.test_evidence_staging_api import jpeg_bytes

pytest_plugins = ["tests.test_auth"]


@pytest.fixture
def capture_dir(auth_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    evidence = auth_dir / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(settings, "evidence_dir", evidence)
    return evidence


def _login(
    client: TestClient,
    email: str = "parent@example.com",
    password: str = "secret",
) -> str:
    return client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    ).json()["access_token"]


def _issue_capture(client: TestClient, parent_token: str) -> str:
    response = client.post("/api/auth/capture-token", headers=bearer(parent_token))
    assert response.status_code == 201
    token = response.json().get("access_token")
    assert isinstance(token, str) and len(token) > 20
    return token


def _stage(client: TestClient, token: str) -> object:
    return client.post(
        "/api/evidence/staging",
        headers=bearer(token),
        files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
    )


def seed_child(*, tenant_uuid: str = "family-1", student_id: int = 1) -> User:
    session = open_admin_session()
    try:
        user = User(
            email=child_account_email(tenant_uuid, student_id),
            hashed_password=hash_password("unused-child-password"),
            tenant_uuid=tenant_uuid,
            role=UserRole.CHILD.value,
            student_id=student_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def test_parent_can_issue_a_capture_credential(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    parent = _login(auth_client)
    response = auth_client.post("/api/auth/capture-token", headers=bearer(parent))
    assert response.status_code == 201
    body = response.json()
    payload = decode_access_token(body["access_token"])
    assert payload["scope"] == CAPTURE_TOKEN_SCOPE
    assert payload["role"] == UserRole.EVIDENCE.value
    assert payload["tenant_uuid"] == "family-1"
    assert payload["is_admin"] is False
    assert str(payload["sub"]).startswith("capture.")
    assert "student_id" not in payload
    status = auth_client.get("/api/auth/capture-token", headers=bearer(parent))
    assert status.status_code == 200
    assert status.json()["active"] is True
    assert "access_token" not in status.json()


def test_valid_capture_credential_can_stage_evidence(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    capture = _issue_capture(auth_client, _login(auth_client))
    response = _stage(auth_client, capture)
    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "family-1"
    assert body["file_path"].startswith("family-1/")
    assert (capture_dir / body["file_path"]).is_file()


def test_parent_jwt_can_still_stage_evidence(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    parent = _login(auth_client)
    response = _stage(auth_client, parent)
    assert response.status_code == 201
    assert response.json()["tenant_id"] == "family-1"


def test_capture_credential_cannot_call_parent_apis(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    capture = _issue_capture(auth_client, _login(auth_client))
    headers = bearer(capture)
    denied = [
        auth_client.get("/api/auth/me", headers=headers),
        auth_client.get("/api/household", headers=headers),
        auth_client.patch("/api/household", headers=headers, json={"name": "Nope"}),
        auth_client.get("/api/students", headers=headers),
        auth_client.get("/api/settings/school-year", headers=headers),
        auth_client.get("/api/curricula", headers=headers),
        auth_client.get("/api/students/1/assignments", headers=headers),
        auth_client.patch(
            "/api/assignments/1/status",
            headers=headers,
            json={"status": "completed"},
        ),
        auth_client.get(
            "/api/portfolios/report",
            headers=headers,
            params={
                "student_id": 1,
                "school_year_id": 1,
                "report_type": "reading_list",
            },
        ),
        auth_client.get("/api/admin/invites", headers=headers),
        auth_client.get("/api/notifications", headers=headers),
        auth_client.get(
            "/api/homework-help/sessions",
            headers=headers,
            params={"assignment_id": 1},
        ),
        auth_client.get("/api/calendar", headers=headers),
        auth_client.get("/api/dashboard/stats", headers=headers),
        auth_client.get("/api/evidence/staging", headers=headers),
        auth_client.post(
            "/api/evidence/link",
            headers=headers,
            json={"evidence_id": 1, "assignment_id": 1},
        ),
        auth_client.get("/api/students/1/spark", headers=headers),
        auth_client.post("/api/auth/capture-token", headers=headers),
        auth_client.get("/api/auth/switchable-users", headers=headers),
        auth_client.get("/api/school-years", headers=headers),
        auth_client.get("/api/enrollments", headers=headers),
    ]
    assert all(row.status_code == 403 for row in denied)
    assert all(
        row.json()["detail"]
        in {
            "This credential can only upload evidence",
            "Parent access required",
            "Admin access required",
        }
        for row in denied
    )


def test_capture_credential_cannot_retrieve_evidence(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    capture = _issue_capture(auth_client, _login(auth_client))
    staged = _stage(auth_client, capture)
    assert staged.status_code == 201
    path = staged.json()["file_path"]
    response = auth_client.get(f"/api/evidence/files/{path}", headers=bearer(capture))
    assert response.status_code == 403
    parent = _login(auth_client)
    allowed = auth_client.get(f"/api/evidence/files/{path}", headers=bearer(parent))
    assert allowed.status_code == 200


def test_invalid_capture_credential_is_rejected(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    missing = auth_client.post(
        "/api/evidence/staging",
        files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
    )
    garbage = auth_client.post(
        "/api/evidence/staging",
        headers=bearer("not-a-jwt"),
        files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
    )
    forged = create_access_token(
        subject="capture.family-1",
        tenant_uuid="family-1",
        extra={"role": UserRole.EVIDENCE.value, "scope": CAPTURE_TOKEN_SCOPE},
    )
    unknown = _stage(auth_client, forged)
    assert missing.status_code == 401
    assert garbage.status_code == 401
    assert unknown.status_code == 401


def test_expired_capture_credential_is_rejected(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    jti = str(uuid4())
    session = open_admin_session()
    try:
        session.add(
            CaptureToken(
                tenant_uuid="family-1",
                jti=jti,
                expires_at=utcnow() - timedelta(minutes=5),
            )
        )
        session.commit()
    finally:
        session.close()
    token = create_access_token(
        subject="capture.family-1",
        tenant_uuid="family-1",
        expires_delta=timedelta(minutes=-5),
        extra={
            "role": UserRole.EVIDENCE.value,
            "scope": CAPTURE_TOKEN_SCOPE,
            "jti": jti,
        },
    )
    response = _stage(auth_client, token)
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_revoked_capture_credential_is_rejected(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    parent = _login(auth_client)
    capture = _issue_capture(auth_client, parent)
    revoked = auth_client.delete("/api/auth/capture-token", headers=bearer(parent))
    assert revoked.status_code == 200
    assert revoked.json()["active"] is False
    response = _stage(auth_client, capture)
    assert response.status_code == 401


def test_new_capture_token_revokes_the_previous_one(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    parent = _login(auth_client)
    first = _issue_capture(auth_client, parent)
    second = _issue_capture(auth_client, parent)
    assert _stage(auth_client, first).status_code == 401
    assert _stage(auth_client, second).status_code == 201


def test_capture_credential_is_scoped_to_its_tenant(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user(email="alpha@example.com", tenant_uuid="family-a")
    seed_user(email="beta@example.com", tenant_uuid="family-b")
    capture_a = _issue_capture(auth_client, _login(auth_client, "alpha@example.com"))
    capture_b = _issue_capture(auth_client, _login(auth_client, "beta@example.com"))
    staged_a = _stage(auth_client, capture_a)
    staged_b = _stage(auth_client, capture_b)
    assert staged_a.status_code == 201
    assert staged_b.status_code == 201
    assert staged_a.json()["tenant_id"] == "family-a"
    assert staged_b.json()["tenant_id"] == "family-b"
    assert staged_a.json()["file_path"].startswith("family-a/")
    assert staged_b.json()["file_path"].startswith("family-b/")
    parent_a = _login(auth_client, "alpha@example.com")
    listed = auth_client.get("/api/evidence/staging", headers=bearer(parent_a))
    assert listed.status_code == 200
    assert [row["tenant_id"] for row in listed.json()] == ["family-a"]
    other_file = auth_client.get(
        f"/api/evidence/files/{staged_b.json()['file_path']}",
        headers=bearer(parent_a),
    )
    assert other_file.status_code == 404


def test_capture_credential_cannot_use_child_assignment_routes(
    auth_client: TestClient, capture_dir: Path
) -> None:
    from app.enums import AssignmentStatus
    from tests.test_kid_auth import _child_token, _parent_ready, _set_pin

    parent, student = _parent_ready(auth_client)
    created = auth_client.post(
        "/api/assignments",
        headers=bearer(parent),
        json={
            "student_id": student["id"],
            "title": "Fractions",
            "scheduled_date": "2026-09-16",
        },
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]
    _set_pin(auth_client, parent, student["id"])
    child = _child_token(auth_client, student["id"])
    capture = _issue_capture(auth_client, parent)

    child_ok = auth_client.patch(
        f"/api/assignments/{assignment_id}/status",
        headers=bearer(child),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert child_ok.status_code == 200

    capture_status = auth_client.patch(
        f"/api/assignments/{assignment_id}/status",
        headers=bearer(capture),
        json={"status": AssignmentStatus.ASSIGNED.value},
    )
    assert capture_status.status_code == 403
    help_denied = auth_client.get(
        "/api/homework-help/sessions",
        headers=bearer(capture),
        params={"assignment_id": assignment_id},
    )
    assert help_denied.status_code == 403


def test_capture_credential_cannot_select_another_tenant_via_claims(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user(email="alpha@example.com", tenant_uuid="family-a")
    seed_user(email="beta@example.com", tenant_uuid="family-b")
    capture_a = _issue_capture(auth_client, _login(auth_client, "alpha@example.com"))
    payload = decode_access_token(capture_a)
    swapped = create_access_token(
        subject=str(payload["sub"]),
        tenant_uuid="family-b",
        extra={
            "role": UserRole.EVIDENCE.value,
            "scope": CAPTURE_TOKEN_SCOPE,
            "jti": payload["jti"],
        },
    )
    response = _stage(auth_client, swapped)
    assert response.status_code == 401
    listed_b = auth_client.get(
        "/api/evidence/staging",
        headers=bearer(_login(auth_client, "beta@example.com")),
    )
    assert listed_b.status_code == 200
    assert listed_b.json() == []


def test_capture_credential_cannot_become_parent_by_changing_role(
    auth_client: TestClient, capture_dir: Path
) -> None:
    seed_user()
    capture = _issue_capture(auth_client, _login(auth_client))
    payload = decode_access_token(capture)
    as_parent = create_access_token(
        subject=str(payload["sub"]),
        tenant_uuid=str(payload["tenant_uuid"]),
        extra={"role": UserRole.PARENT.value, "jti": payload["jti"]},
    )
    household = auth_client.get("/api/household", headers=bearer(as_parent))
    assert household.status_code == 401
    staged = _stage(auth_client, as_parent)
    assert staged.status_code == 401


def test_demo_and_child_cannot_issue_capture_tokens(auth_client: TestClient) -> None:
    demo = auth_client.post("/api/auth/demo").json()["access_token"]
    demo_response = auth_client.post("/api/auth/capture-token", headers=bearer(demo))
    assert demo_response.status_code == 403
    seed_user()
    child = seed_child()
    child_token = token_for_account(child)
    child_response = auth_client.post(
        "/api/auth/capture-token",
        headers=bearer(child_token),
    )
    assert child_response.status_code == 403
