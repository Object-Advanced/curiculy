"""Operator password reset for parents who are locked out."""

import io

import pytest
from fastapi.testclient import TestClient

from app.db import open_admin_session
from app.models.admin import User
from scripts.reset_password import main, reset_password
from tests.test_auth import seed_user

pytest_plugins = ["tests.test_auth"]


def _login(client: TestClient, password: str) -> int:
    return client.post(
        "/api/auth/token", data={"username": "parent@example.com", "password": password}
    ).status_code


def test_generated_password_replaces_the_old_one(auth_client: TestClient) -> None:
    seed_user()
    new = reset_password("Parent@Example.com")

    assert len(new) >= 8
    assert _login(auth_client, new) == 200
    assert _login(auth_client, "secret") == 401


def test_chosen_password_from_stdin(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seed_user()
    monkeypatch.setattr("sys.stdin", io.StringIO("a-much-longer-password\n"))

    assert main(["parent@example.com", "--password-stdin"]) == 0
    assert "Password updated" in capsys.readouterr().out
    assert _login(auth_client, "a-much-longer-password") == 200


def test_unknown_email_is_an_error(auth_client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["nobody@example.com"]) == 1
    assert "No parent account" in capsys.readouterr().err


def test_short_password_is_refused(auth_client: TestClient) -> None:
    seed_user()
    with pytest.raises(ValueError, match="8-72 characters"):
        reset_password("parent@example.com", "short")
    assert _login(auth_client, "secret") == 200


def test_child_accounts_are_not_reset(auth_client: TestClient) -> None:
    seed_user()
    session = open_admin_session()
    try:
        session.add(
            User(
                email="child.family-1.1@kid.local",
                hashed_password="x",
                tenant_uuid="family-1",
                role="child",
                student_id=1,
            )
        )
        session.commit()
    finally:
        session.close()

    with pytest.raises(ValueError, match="No parent account"):
        reset_password("child.family-1.1@kid.local")
