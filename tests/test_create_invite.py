"""Operator invite script: makes the first parent account possible on a fresh install."""


import pytest

from app.db import open_admin_session
from app.models.admin import InviteKey
from app.models.mixins import utcnow
from scripts.create_invite import create_invite, main


@pytest.fixture
def admin_file(committed_db: None) -> None:
    """The script writes through its own session, so rows really commit."""


def _invites() -> list[InviteKey]:
    session = open_admin_session()
    try:
        return session.query(InviteKey).all()
    finally:
        session.close()


def test_random_key_is_stored_unused(admin_file: None) -> None:
    key = create_invite()

    rows = _invites()
    assert [row.key for row in rows] == [key]
    assert len(key) == 8
    assert rows[0].tenant_uuid == ""
    assert rows[0].redeemed_at is None
    assert rows[0].expires_at is None


def test_explicit_key_is_idempotent(admin_file: None) -> None:
    assert create_invite("e2e-invite-key") == "e2e-invite-key"
    assert create_invite("e2e-invite-key") == "e2e-invite-key"

    assert [row.key for row in _invites()] == ["e2e-invite-key"]


def test_expiry_is_optional(admin_file: None) -> None:
    create_invite("expiring-key", expires_days=2)

    assert _invites()[0].expires_at is not None


def test_redeemed_key_is_refused(admin_file: None) -> None:
    create_invite("used-key-123")
    session = open_admin_session()
    try:
        row = session.query(InviteKey).one()
        row.redeemed_at = utcnow()
        session.commit()
    finally:
        session.close()

    with pytest.raises(ValueError, match="already redeemed"):
        create_invite("used-key-123")


@pytest.mark.parametrize("key", ["short", "x" * 65])
def test_key_length_is_checked(admin_file: None, key: str) -> None:
    with pytest.raises(ValueError, match="8-64 characters"):
        create_invite(key)


def test_cli_prints_the_key(admin_file: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--key", "cli-key-1234"]) == 0
    assert capsys.readouterr().out.strip() == "cli-key-1234"


def test_cli_reports_errors(admin_file: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--key", "short"]) == 1
    assert "8-64 characters" in capsys.readouterr().err
