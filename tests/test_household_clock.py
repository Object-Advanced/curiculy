"""'Today' follows the household's wall clock, not the server's UTC clock.

The bug this guards: at 5:30pm in California the server (UTC) is already on
tomorrow, so the dashboard, spark, and recalibrate's overdue cutoff all moved
a day early every evening.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import ConfigurationError, Settings, settings, validate_runtime_configuration
from app.db import TenantBase
from app.enums import AssignmentStatus
from app.models import Assignment, Household, Student
from app.schema_patches import apply_tenant_schema, sqlite_table_columns
from app.services import clock

# 00:30 UTC on 9 October is still the evening of 8 October in California.
EVENING_IN_CALIFORNIA = datetime(2026, 10, 9, 0, 30, tzinfo=timezone.utc)


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    monkeypatch.setattr(clock, "_now", lambda: EVENING_IN_CALIFORNIA)
    return EVENING_IN_CALIFORNIA


def _household(db: Session, tz: str | None) -> Household:
    household = Household(name="The Rivera family", timezone=tz)
    db.add(household)
    db.commit()
    return household


class TestHouseholdToday:
    def test_uses_the_household_zone(self, db: Session, frozen_now: datetime) -> None:
        _household(db, "America/Los_Angeles")
        assert clock.household_today(db) == date(2026, 10, 8)

    def test_east_of_utc_is_already_tomorrow(self, db: Session, frozen_now: datetime) -> None:
        _household(db, "Asia/Tokyo")
        assert clock.household_today(db) == date(2026, 10, 9)

    def test_falls_back_to_default_timezone(
        self, db: Session, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _household(db, None)
        monkeypatch.setattr(settings, "default_timezone", "America/Chicago")
        assert clock.household_today(db) == date(2026, 10, 8)

    def test_unknown_stored_zone_is_ignored(
        self, db: Session, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _household(db, "Mars/Olympus_Mons")
        monkeypatch.setattr(settings, "default_timezone", "America/New_York")
        assert clock.household_today(db) == date(2026, 10, 8)

    def test_without_any_zone_uses_the_server_clock(
        self, db: Session, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "default_timezone", None)
        assert clock.household_today(db) == frozen_now.astimezone().date()


class TestDefaultTimezoneSetting:
    def test_invalid_zone_refuses_to_start(self) -> None:
        config = Settings(dev_mode=True, default_timezone="Central Time")
        with pytest.raises(ConfigurationError, match="DEFAULT_TIMEZONE"):
            validate_runtime_configuration(config)

    def test_valid_zone_is_accepted(self) -> None:
        validate_runtime_configuration(Settings(dev_mode=True, default_timezone="America/Denver"))


class TestHouseholdTimezoneApi:
    def test_patch_stores_a_known_zone(self, client: TestClient) -> None:
        response = client.patch("/api/household", json={"timezone": "America/Chicago"})
        assert response.status_code == 200
        assert response.json()["timezone"] == "America/Chicago"
        assert client.get("/api/household").json()["timezone"] == "America/Chicago"

    def test_patch_refuses_an_unknown_zone(self, client: TestClient) -> None:
        response = client.patch("/api/household", json={"timezone": "Central Time"})
        assert response.status_code == 422

    def test_new_households_have_no_zone_yet(self, client: TestClient) -> None:
        assert client.get("/api/household").json()["timezone"] is None


class TestEndpointsUseHouseholdToday:
    def test_dashboard_today_is_the_familys_today(
        self, client: TestClient, db: Session, frozen_now: datetime
    ) -> None:
        household = _household(db, "America/Los_Angeles")
        student = Student(household_id=household.id, name="Sam")
        db.add(student)
        db.flush()
        db.add_all(
            [
                Assignment(
                    student_id=student.id,
                    title="Thursday math",
                    scheduled_date=date(2026, 10, 8),
                    status=AssignmentStatus.COMPLETED,
                ),
                Assignment(
                    student_id=student.id,
                    title="Friday math",
                    scheduled_date=date(2026, 10, 9),
                ),
            ]
        )
        db.commit()

        body = client.get("/api/dashboard/stats").json()

        assert body["today"] == "2026-10-08"
        assert body["today_progress"][0]["total"] == 1
        assert body["today_progress"][0]["completed"] == 1

    def test_calendar_period_anchors_on_the_familys_today(
        self, client: TestClient, db: Session, frozen_now: datetime
    ) -> None:
        household = _household(db, "America/Los_Angeles")
        student = Student(household_id=household.id, name="Sam")
        db.add(student)
        db.commit()

        body = client.get(f"/api/students/{student.id}/assignments?period=day").json()

        assert body["start_date"] == body["end_date"] == "2026-10-08"


class TestSchemaPatch:
    def test_old_households_table_gains_timezone(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'tenant_old.db'}")
        try:
            TenantBase.metadata.create_all(engine)
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE households DROP COLUMN timezone"))
                conn.execute(
                    text(
                        "INSERT INTO households (id, name, created_at, updated_at) "
                        "VALUES (1, 'Kept', datetime('now'), datetime('now'))"
                    )
                )

            apply_tenant_schema(engine)
            apply_tenant_schema(engine)

            with engine.connect() as conn:
                assert "timezone" in sqlite_table_columns(conn, "households")
                assert conn.execute(text("SELECT name FROM households")).scalar() == "Kept"
        finally:
            engine.dispose()
