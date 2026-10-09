"""Attempt limits on the sign-in endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.rate_limit import RateLimiter
from tests.test_auth import seed_user

pytest_plugins = ["tests.test_auth"]


class TestRateLimiter:
    def test_allows_up_to_the_limit_then_reports_the_wait(self) -> None:
        limiter = RateLimiter()
        for second in range(3):
            assert limiter.hit("login", "1.2.3.4", 3, 60, now=100.0 + second) is None
        assert limiter.hit("login", "1.2.3.4", 3, 60, now=103.0) == pytest.approx(57.0)

    def test_the_window_slides(self) -> None:
        limiter = RateLimiter()
        for second in range(3):
            limiter.hit("login", "1.2.3.4", 3, 60, now=100.0 + second)
        assert limiter.hit("login", "1.2.3.4", 3, 60, now=160.5) is None

    def test_buckets_and_clients_are_separate(self) -> None:
        limiter = RateLimiter()
        assert limiter.hit("login", "a", 1, 60, now=1.0) is None
        assert limiter.hit("login", "b", 1, 60, now=1.0) is None
        assert limiter.hit("demo", "a", 1, 60, now=1.0) is None
        assert limiter.hit("login", "a", 1, 60, now=1.0) is not None

    def test_memory_is_bounded(self) -> None:
        limiter = RateLimiter(max_keys=2)
        for key in "abc":
            limiter.hit("login", key, 1, 60, now=1.0)
        assert limiter.hit("login", "a", 1, 60, now=1.0) is None


def _wrong_login(client: TestClient):
    return client.post(
        "/api/auth/token", data={"username": "parent@example.com", "password": "nope"}
    )


def test_eleventh_login_in_a_minute_is_refused(auth_client: TestClient) -> None:
    seed_user()
    statuses = [_wrong_login(auth_client).status_code for _ in range(10)]
    assert statuses == [401] * 10

    refused = _wrong_login(auth_client)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) >= 1


def test_kid_lookups_are_limited(auth_client: TestClient) -> None:
    statuses = [
        auth_client.post("/api/auth/student-household", json={"family_code": "ABCD-2345"}).status_code
        for _ in range(21)
    ]
    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_limits_can_be_switched_off_for_test_rigs(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limits_enabled", False)
    seed_user()
    assert {_wrong_login(auth_client).status_code for _ in range(15)} == {401}
