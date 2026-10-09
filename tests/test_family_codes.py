"""Kid sign-in by family code instead of the parent's email.

The unauthenticated household lookup used to answer to any parent's email
address with the children's full names and ids.
"""

import pytest
from fastapi.testclient import TestClient

from app.db import open_admin_session
from app.services.family_codes import (
    ALPHABET,
    CODE_LENGTH,
    display_code,
    family_code_for,
    normalize_code,
    rotate_family_code,
    sign_in_names,
    tenant_for_code,
)
from tests.test_auth import bearer, seed_user

pytest_plugins = ["tests.test_auth"]


def _parent_with_kid_login(client: TestClient, name: str = "Ada Lovelace") -> tuple[str, int]:
    seed_user()
    token = client.post(
        "/api/auth/token", data={"username": "parent@example.com", "password": "secret"}
    ).json()["access_token"]
    student = client.post("/api/students", headers=bearer(token), json={"name": name}).json()
    client.post(f"/api/students/{student['id']}/pin", headers=bearer(token), json={"pin": "1234"})
    return token, student["id"]


class TestCodes:
    def test_normalize_accepts_dashes_spaces_and_lowercase(self) -> None:
        assert normalize_code("abcd-2345") == "ABCD2345"
        assert normalize_code(" AB CD 23 45 ") == "ABCD2345"

    @pytest.mark.parametrize("text", [None, "", "ABC-234", "ABCD-23456", "ABCD-0O1I", "parent@example.com"])
    def test_normalize_rejects_anything_else(self, text: str | None) -> None:
        assert normalize_code(text) is None

    def test_display_adds_the_dash(self) -> None:
        assert display_code("ABCD2345") == "ABCD-2345"

    def test_codes_avoid_look_alike_characters(self, auth_client: TestClient) -> None:
        session = open_admin_session()
        try:
            code = family_code_for(session, "family-1").code
        finally:
            session.close()
        assert len(code) == CODE_LENGTH
        assert set(code) <= set(ALPHABET)
        assert not set(code) & set("0O1IL")

    def test_one_stable_code_per_household_until_rotated(self, auth_client: TestClient) -> None:
        session = open_admin_session()
        try:
            first = family_code_for(session, "family-1").code
            assert family_code_for(session, "family-1").code == first
            rotated = rotate_family_code(session, "family-1").code
            assert rotated != first
            assert tenant_for_code(session, first) is None
            assert tenant_for_code(session, rotated) == "family-1"
        finally:
            session.close()


class TestSignInNames:
    def test_first_names_only(self) -> None:
        assert sign_in_names({1: "Ada Lovelace", 2: "Blaise Pascal"}) == {1: "Ada", 2: "Blaise"}

    def test_same_first_name_gets_a_last_initial(self) -> None:
        names = sign_in_names({1: "Sam Rivera", 2: "Sam Okafor", 3: "Maya"})
        assert names == {1: "Sam R.", 2: "Sam O.", 3: "Maya"}


class TestSignInApi:
    def test_parent_email_no_longer_lists_children(self, auth_client: TestClient) -> None:
        _parent_with_kid_login(auth_client)
        response = auth_client.post(
            "/api/auth/student-household", json={"email": "parent@example.com"}
        )
        assert response.status_code == 422
        assert "Ada" not in response.text

    def test_family_code_lists_first_names(self, auth_client: TestClient) -> None:
        token, student_id = _parent_with_kid_login(auth_client)
        code = auth_client.get("/api/auth/family-code", headers=bearer(token)).json()["code"]
        assert len(code) == CODE_LENGTH + 1 and code[4] == "-"

        response = auth_client.post(
            "/api/auth/student-household", json={"family_code": code.lower()}
        )
        assert response.json()["students"] == [{"student_id": student_id, "name": "Ada"}]

    def test_kid_signs_in_with_code_and_pin(self, auth_client: TestClient) -> None:
        token, student_id = _parent_with_kid_login(auth_client)
        code = auth_client.get("/api/auth/family-code", headers=bearer(token)).json()["code"]
        response = auth_client.post(
            "/api/auth/student-token",
            json={"family_code": code, "student_id": student_id, "pin": "1234"},
        )
        assert response.status_code == 200

    def test_wrong_code_cannot_sign_in(self, auth_client: TestClient) -> None:
        _token, student_id = _parent_with_kid_login(auth_client)
        response = auth_client.post(
            "/api/auth/student-token",
            json={"family_code": "ABCD-2345", "student_id": student_id, "pin": "1234"},
        )
        assert response.status_code == 401

    def test_rotating_stops_the_old_code(self, auth_client: TestClient) -> None:
        token, student_id = _parent_with_kid_login(auth_client)
        old = auth_client.get("/api/auth/family-code", headers=bearer(token)).json()["code"]
        new = auth_client.post("/api/auth/family-code/rotate", headers=bearer(token)).json()["code"]
        assert new != old
        assert (
            auth_client.post("/api/auth/student-household", json={"family_code": old}).json()["students"]
            == []
        )
        assert auth_client.get("/api/auth/family-code", headers=bearer(token)).json()["code"] == new

    def test_children_cannot_read_or_rotate_the_code(self, auth_client: TestClient) -> None:
        token, student_id = _parent_with_kid_login(auth_client)
        code = auth_client.get("/api/auth/family-code", headers=bearer(token)).json()["code"]
        child = auth_client.post(
            "/api/auth/student-token",
            json={"family_code": code, "student_id": student_id, "pin": "1234"},
        ).json()["access_token"]
        assert auth_client.get("/api/auth/family-code", headers=bearer(child)).status_code == 403
        assert (
            auth_client.post("/api/auth/family-code/rotate", headers=bearer(child)).status_code
            == 403
        )

    def test_demo_has_no_family_code(self, auth_client: TestClient) -> None:
        token = auth_client.post("/api/auth/demo").json()["access_token"]
        assert auth_client.get("/api/auth/family-code", headers=bearer(token)).status_code == 403
