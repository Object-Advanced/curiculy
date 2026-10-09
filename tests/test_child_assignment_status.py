"""A child may complete their own assignments and nothing else."""

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.enums import AssignmentStatus
from tests.test_auth import bearer, seed_user
from tests.test_kid_auth import _child_token, _login, _parent_ready, _set_pin

pytest_plugins = ["tests.test_auth"]

ANCHOR = date.today().isoformat()


def _add_assignment(
    client: TestClient,
    token: str,
    student_id: int,
    title: str = "Lesson 1",
) -> dict:
    response = client.post(
        "/api/assignments",
        headers=bearer(token),
        json={
            "student_id": student_id,
            "title": title,
            "scheduled_date": ANCHOR,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_parent_can_patch_status_in_their_household(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    assignment = _add_assignment(auth_client, token, student["id"])
    response = auth_client.patch(
        f"/api/assignments/{assignment['id']}/status",
        headers=bearer(token),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert response.status_code == 200
    assert response.json()["status"] == AssignmentStatus.COMPLETED.value
    assert response.json()["title"] == assignment["title"]


def test_child_can_patch_own_assignment_status(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    assignment = _add_assignment(auth_client, token, student["id"], "Fractions")
    child = _child_token(auth_client, student["id"])
    response = auth_client.patch(
        f"/api/assignments/{assignment['id']}/status",
        headers=bearer(child),
        json={"status": AssignmentStatus.IN_PROGRESS.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == AssignmentStatus.IN_PROGRESS.value
    assert body["title"] == "Fractions"
    assert body["scheduled_date"] == ANCHOR
    done = auth_client.patch(
        f"/api/assignments/{assignment['id']}/status",
        headers=bearer(child),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert done.status_code == 200
    assert done.json()["status"] == AssignmentStatus.COMPLETED.value


def test_child_cannot_patch_sibling_assignment_status(auth_client: TestClient) -> None:
    token, ada = _parent_ready(auth_client)
    blaise = auth_client.post(
        "/api/students",
        headers=bearer(token),
        json={"name": "Blaise"},
    ).json()
    _set_pin(auth_client, token, ada["id"])
    siblings_work = _add_assignment(auth_client, token, blaise["id"], "Spelling")
    child = _child_token(auth_client, ada["id"])
    response = auth_client.patch(
        f"/api/assignments/{siblings_work['id']}/status",
        headers=bearer(child),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert response.status_code == 404
    still = auth_client.get(
        f"/api/assignments/{siblings_work['id']}",
        headers=bearer(token),
    )
    assert still.json()["status"] == AssignmentStatus.ASSIGNED.value


def test_child_nonexistent_assignment_is_404(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    response = auth_client.patch(
        "/api/assignments/4242/status",
        headers=bearer(child),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Assignment not found"


def test_child_cannot_change_grades_edit_or_delete(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    assignment = _add_assignment(auth_client, token, student["id"])
    child = bearer(_child_token(auth_client, student["id"]))
    assignment_id = assignment["id"]
    grade = auth_client.put(
        f"/api/assignments/{assignment_id}/grade",
        headers=child,
        json={"score_value": "92"},
    )
    edited = auth_client.put(
        f"/api/assignments/{assignment_id}",
        headers=child,
        json={"scheduled_date": (date.today() + timedelta(days=1)).isoformat()},
    )
    deleted = auth_client.delete(f"/api/assignments/{assignment_id}", headers=child)
    evidence = auth_client.post(
        f"/api/assignments/{assignment_id}/evidence",
        headers=child,
        files={"file": ("page.jpg", b"not-an-image", "image/jpeg")},
    )
    assert grade.status_code == 403
    assert edited.status_code == 403
    assert deleted.status_code == 403
    assert evidence.status_code == 403
    current = auth_client.get(f"/api/assignments/{assignment_id}", headers=bearer(token))
    assert current.status_code == 200
    assert current.json()["title"] == assignment["title"]
    assert current.json()["scheduled_date"] == ANCHOR
    assert current.json()["grade"] is None


def test_wrong_tenant_cannot_patch_assignment_status(auth_client: TestClient) -> None:
    seed_user(email="alpha@example.com", tenant_uuid=str(uuid4()))
    seed_user(email="beta@example.com", tenant_uuid=str(uuid4()))
    alpha = _login(auth_client, "alpha@example.com")
    beta = _login(auth_client, "beta@example.com")
    ada = auth_client.post(
        "/api/students",
        headers=bearer(alpha),
        json={"name": "Ada"},
    ).json()
    assignment = _add_assignment(auth_client, alpha, ada["id"])
    other_child_student = auth_client.post(
        "/api/students",
        headers=bearer(beta),
        json={"name": "Cora"},
    ).json()
    _set_pin(auth_client, beta, other_child_student["id"])
    beta_code = auth_client.get("/api/auth/family-code", headers=bearer(beta)).json()["code"]
    other_child = auth_client.post(
        "/api/auth/student-token",
        json={
            "family_code": beta_code,
            "student_id": other_child_student["id"],
            "pin": "1234",
        },
    ).json()["access_token"]
    as_parent = auth_client.patch(
        f"/api/assignments/{assignment['id']}/status",
        headers=bearer(beta),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    as_child = auth_client.patch(
        f"/api/assignments/{assignment['id']}/status",
        headers=bearer(other_child),
        json={"status": AssignmentStatus.COMPLETED.value},
    )
    assert as_parent.status_code == 404
    assert as_child.status_code == 404
    original = auth_client.get(
        f"/api/assignments/{assignment['id']}",
        headers=bearer(alpha),
    )
    assert original.json()["status"] == AssignmentStatus.ASSIGNED.value
