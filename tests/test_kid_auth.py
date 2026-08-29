"""Child PIN logins, role-scoped APIs, and household user switching."""

from datetime import date

from fastapi.testclient import TestClient

from app.core.security import decode_access_token
from app.db import open_admin_session
from app.enums import AssignmentStatus, UserRole
from app.models.admin import User
from tests.test_auth import bearer, seed_user

pytest_plugins = ["tests.test_auth"]


def _login(client: TestClient, email: str = "parent@example.com", password: str = "secret") -> str:
    return client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    ).json()["access_token"]


def _parent_ready(client: TestClient) -> tuple[str, dict]:
    seed_user()
    token = _login(client)
    student = client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Ada"},
    ).json()
    return token, student


def _set_pin(client: TestClient, token: str, student_id: int, pin: str = "1234") -> dict:
    response = client.post(
        f"/api/students/{student_id}/pin",
        headers=bearer(token),
        json={"pin": pin},
    )
    assert response.status_code == 200
    return response.json()


def _child_token(client: TestClient, student_id: int, pin: str = "1234") -> str:
    response = client.post(
        "/api/auth/student-token",
        json={
            "email": "parent@example.com",
            "student_id": student_id,
            "pin": pin,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_parent_login_includes_role(auth_client: TestClient) -> None:
    seed_user()
    token = _login(auth_client)
    payload = decode_access_token(token)
    assert payload["role"] == UserRole.PARENT.value
    assert "student_id" not in payload or payload.get("student_id") in (None, 0)


def test_set_pin_and_student_household(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    body = _set_pin(auth_client, token, student["id"])
    assert body["has_login"] is True
    listed = auth_client.get("/api/students", headers=bearer(token)).json()
    assert listed[0]["has_login"] is True
    household = auth_client.post(
        "/api/auth/student-household",
        json={"email": "parent@example.com"},
    )
    assert household.status_code == 200
    assert household.json()["students"] == [{"student_id": student["id"], "name": "Ada"}]


def test_unknown_household_email_lists_no_students(auth_client: TestClient) -> None:
    seed_user()
    response = auth_client.post(
        "/api/auth/student-household",
        json={"email": "nobody@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["students"] == []


def test_student_pin_login(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"], "2468")
    child = _child_token(auth_client, student["id"], "2468")
    payload = decode_access_token(child)
    assert payload["role"] == UserRole.CHILD.value
    assert payload["student_id"] == student["id"]
    me = auth_client.get("/api/auth/me", headers=bearer(child))
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "child"
    assert body["student_id"] == student["id"]
    assert body["display_name"] == "Ada"
    assert body["email"] == ""


def test_child_cannot_use_parent_password_login(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"], "1234")
    session = open_admin_session()
    try:
        child = (
            session.query(User)
            .filter(User.role == UserRole.CHILD.value, User.student_id == student["id"])
            .one()
        )
        email = child.email
    finally:
        session.close()
    response = auth_client.post(
        "/api/auth/token",
        data={"username": email, "password": "1234"},
    )
    assert response.status_code == 401


def test_pin_lockout(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"], "1234")
    details = []
    for _ in range(5):
        response = auth_client.post(
            "/api/auth/student-token",
            json={
                "email": "parent@example.com",
                "student_id": student["id"],
                "pin": "0000",
            },
        )
        assert response.status_code == 401
        details.append(response.json()["detail"])
    assert details[-1] == "Too many attempts. Try again later."
    locked = auth_client.post(
        "/api/auth/student-token",
        json={
            "email": "parent@example.com",
            "student_id": student["id"],
            "pin": "1234",
        },
    )
    assert locked.status_code == 401
    assert locked.json()["detail"] == "Too many attempts. Try again later."


def test_child_cannot_access_parent_routes_or_siblings(auth_client: TestClient) -> None:
    token, ada = _parent_ready(auth_client)
    blaise = auth_client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Blaise"},
    ).json()
    _set_pin(auth_client, token, ada["id"])
    ada_work = auth_client.post(
        "/api/assignments",
        headers=bearer(token),
        json={
            "student_id": ada["id"],
            "title": "Fractions",
            "scheduled_date": date.today().isoformat(),
        },
    ).json()
    blaise_work = auth_client.post(
        "/api/assignments",
        headers=bearer(token),
        json={
            "student_id": blaise["id"],
            "title": "Spelling",
            "scheduled_date": date.today().isoformat(),
        },
    ).json()
    child = _child_token(auth_client, ada["id"])
    headers = bearer(child)
    assert auth_client.get("/api/household", headers=headers).status_code == 403
    assert auth_client.get("/api/students", headers=headers).status_code == 403
    assert auth_client.get("/api/dashboard/stats", headers=headers).status_code == 403
    own = auth_client.get(f"/api/students/{ada['id']}/assignments", headers=headers)
    assert own.status_code == 200
    assert [row["id"] for row in own.json()["assignments"]] == [ada_work["id"]]
    other = auth_client.get(f"/api/students/{blaise['id']}/assignments", headers=headers)
    assert other.status_code == 404
    assert auth_client.get(f"/api/assignments/{blaise_work['id']}", headers=headers).status_code == 404
    sibling_status = auth_client.patch(
        f"/api/assignments/{blaise_work['id']}/status",
        headers=headers,
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert sibling_status.status_code == 404
    mine = auth_client.get(f"/api/assignments/{ada_work['id']}", headers=headers)
    assert mine.status_code == 200
    completed = auth_client.patch(
        f"/api/assignments/{ada_work['id']}/status",
        headers=headers,
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == AssignmentStatus.COMPLETED.value
    assert completed.json()["id"] == ada_work["id"]


def test_parent_switches_to_child_without_password(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    switched = auth_client.post(
        "/api/auth/switch",
        headers=bearer(token),
        json={"student_id": student["id"]},
    )
    assert switched.status_code == 200
    payload = decode_access_token(switched.json()["access_token"])
    assert payload["role"] == "child"
    assert payload["student_id"] == student["id"]


def test_child_switch_requires_parent_password(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    denied = auth_client.post(
        "/api/auth/switch",
        headers=bearer(child),
        json={"student_id": None},
    )
    assert denied.status_code == 401
    still_child = auth_client.post(
        "/api/auth/switch",
        headers=bearer(child),
        json={"student_id": None, "parent_password": "wrong"},
    )
    assert still_child.status_code == 401
    back = auth_client.post(
        "/api/auth/switch",
        headers=bearer(child),
        json={"student_id": None, "parent_password": "secret"},
    )
    assert back.status_code == 200
    payload = decode_access_token(back.json()["access_token"])
    assert payload["role"] == "parent"


def test_delete_student_removes_child_login(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    assert (
        auth_client.delete(f"/api/students/{student['id']}", headers=bearer(token)).status_code
        == 204
    )
    household = auth_client.post(
        "/api/auth/student-household",
        json={"email": "parent@example.com"},
    )
    assert household.json()["students"] == []
    session = open_admin_session()
    try:
        leftover = (
            session.query(User)
            .filter(User.role == UserRole.CHILD.value, User.student_id == student["id"])
            .one_or_none()
        )
        assert leftover is None
    finally:
        session.close()


def test_demo_switch_keeps_the_same_tenant(auth_client: TestClient) -> None:
    token = auth_client.post("/api/auth/demo").json()["access_token"]
    created = auth_client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Maya"},
    )
    assert created.status_code == 201
    student_id = created.json()["id"]
    switched = auth_client.post(
        "/api/auth/switch",
        headers=bearer(token),
        json={"student_id": student_id},
    )
    assert switched.status_code == 200
    child = switched.json()["access_token"]
    me = auth_client.get("/api/auth/me", headers=bearer(child))
    assert me.json()["role"] == "child"
    assert me.json()["display_name"] == "Maya"
    listed = auth_client.get(
        f"/api/students/{student_id}/assignments",
        headers=bearer(child),
    )
    assert listed.status_code == 200
    back = auth_client.post(
        "/api/auth/switch",
        headers=bearer(child),
        json={"student_id": None},
    )
    assert back.status_code == 200
    students = auth_client.get("/api/students", headers=bearer(back.json()["access_token"]))
    assert [row["name"] for row in students.json()] == ["Maya"]


def test_clear_pin_disables_login(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    cleared = auth_client.delete(
        f"/api/students/{student['id']}/pin",
        headers=bearer(token),
    )
    assert cleared.status_code == 200
    assert cleared.json()["has_login"] is False
    denied = auth_client.post(
        "/api/auth/student-token",
        json={
            "email": "parent@example.com",
            "student_id": student["id"],
            "pin": "1234",
        },
    )
    assert denied.status_code == 401
