"""Named school-year CRUD and the operational-year consolidation.

SchoolYear is the canonical date range. HouseholdSettings keeps weekdays and
exception colors only.
"""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db import _ensure_tenant_schema, _sqlite_table_columns
from app.enums import AssignmentStatus
from app.models import (
    Assignment,
    AssignmentEvidence,
    Household,
    HouseholdSettings,
    SchoolYear,
    Student,
)
from app.services.school_year import load_school_year_settings
from tests.test_pacing import preview_body, seed_book

YEAR_BODY = {
    "name": "2026-2027",
    "start_date": "2026-08-03",
    "end_date": "2027-06-04",
}


class TestSchoolYearCRUD:
    def test_create_retrieve_and_update(self, client: TestClient, db: Session) -> None:
        created = client.post("/api/school-years", json=YEAR_BODY)
        assert created.status_code == 201
        body = created.json()
        year_id = body["id"]
        assert body["name"] == "2026-2027"
        assert body["start_date"] == "2026-08-03"
        assert body["end_date"] == "2027-06-04"

        listed = client.get("/api/school-years")
        assert listed.status_code == 200
        assert any(item["id"] == year_id for item in listed.json())

        fetched = client.get(f"/api/school-years/{year_id}")
        assert fetched.status_code == 200
        assert fetched.json() == body

        patched = client.patch(
            f"/api/school-years/{year_id}",
            json={
                "name": "Our Year",
                "start_date": "2026-08-10",
                "end_date": "2027-05-28",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Our Year"
        assert patched.json()["start_date"] == "2026-08-10"
        assert patched.json()["end_date"] == "2027-05-28"

        again = client.get(f"/api/school-years/{year_id}")
        assert again.json()["name"] == "Our Year"
        assert again.json()["start_date"] == "2026-08-10"

        settings = client.get("/api/settings/school-year")
        assert settings.json()["school_year_id"] == year_id
        assert settings.json()["start_date"] == "2026-08-10"
        assert settings.json()["end_date"] == "2027-05-28"

        stored = db.get(SchoolYear, year_id)
        assert stored is not None
        assert stored.name == "Our Year"
        assert "start_date" not in HouseholdSettings.__table__.c
        assert db.query(HouseholdSettings).count() == 0

    def test_create_rejects_a_reversed_window(self, client: TestClient) -> None:
        response = client.post(
            "/api/school-years",
            json={
                "name": "Backwards",
                "start_date": "2027-06-30",
                "end_date": "2026-08-01",
            },
        )
        assert response.status_code == 400

    def test_update_unknown_year_is_404(self, client: TestClient) -> None:
        response = client.patch("/api/school-years/4242", json={"name": "Missing"})
        assert response.status_code == 404

    def test_empty_update_is_rejected(self, client: TestClient) -> None:
        year_id = client.post("/api/school-years", json=YEAR_BODY).json()["id"]
        response = client.patch(f"/api/school-years/{year_id}", json={})
        assert response.status_code == 422

    def test_creating_a_year_makes_settings_read_its_dates(
        self, client: TestClient
    ) -> None:
        created = client.post("/api/school-years", json=YEAR_BODY).json()
        settings = client.get("/api/settings/school-year").json()
        assert settings["school_year_id"] == created["id"]
        assert settings["start_date"] == created["start_date"]
        assert settings["end_date"] == created["end_date"]
        assert settings["weekdays"] == [0, 1, 2, 3, 4]

    def test_later_year_becomes_operational(
        self, client: TestClient
    ) -> None:
        first = client.post(
            "/api/school-years",
            json={
                "name": "2025-2026",
                "start_date": "2025-08-01",
                "end_date": "2026-06-30",
            },
        ).json()
        second = client.post(
            "/api/school-years",
            json={
                "name": "2026-2027",
                "start_date": "2026-08-01",
                "end_date": "2027-06-30",
            },
        ).json()
        settings = client.get("/api/settings/school-year").json()
        assert settings["school_year_id"] == second["id"]
        assert settings["start_date"] == "2026-08-01"
        assert first["id"] != second["id"]

    def test_earlier_historical_year_does_not_replace_operational_dates(
        self, client: TestClient
    ) -> None:
        current = client.post(
            "/api/school-years",
            json={
                "name": "2026-2027",
                "start_date": "2026-08-01",
                "end_date": "2027-06-30",
            },
        ).json()
        client.post(
            "/api/school-years",
            json={
                "name": "2025-2026",
                "start_date": "2025-08-01",
                "end_date": "2026-06-30",
            },
        )
        settings = client.get("/api/settings/school-year").json()
        assert settings["school_year_id"] == current["id"]
        assert settings["start_date"] == "2026-08-01"

    def test_year_modal_put_does_not_rename_a_wizard_year(
        self, client: TestClient
    ) -> None:
        created = client.post(
            "/api/school-years",
            json={
                "name": "Our Year",
                "start_date": "2026-08-01",
                "end_date": "2027-06-30",
            },
        ).json()
        client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2026-08-03",
                "end_date": "2027-06-04",
                "weekdays": [0, 1, 2, 3, 4],
            },
        )
        again = client.get(f"/api/school-years/{created['id']}").json()
        assert again["name"] == "Our Year"
        assert again["start_date"] == "2026-08-03"
        assert again["end_date"] == "2027-06-04"


class TestSchedulingUsesSchoolYearDates:
    def test_pacing_preview_stays_inside_the_named_year(
        self, client: TestClient, db: Session
    ) -> None:
        book = seed_book(db)
        year = client.post(
            "/api/school-years",
            json={
                "name": "Fall window",
                "start_date": "2026-09-07",
                "end_date": "2026-10-02",
            },
        ).json()
        settings = client.get("/api/settings/school-year").json()
        assert settings["school_year_id"] == year["id"]
        assert settings["start_date"] == year["start_date"]
        assert settings["end_date"] == year["end_date"]

        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(
                book_id=book.id,
                start_date=settings["start_date"],
                target_completion_date=settings["end_date"],
                active_weekdays=settings["weekdays"],
                target_lessons=5,
            ),
        )
        assert response.status_code == 200
        lessons = response.json()["lessons"]
        assert lessons
        for lesson in lessons:
            assert settings["start_date"] <= lesson["scheduled_date"] <= settings["end_date"]

    def test_recalibration_reads_class_days_from_settings(
        self, client: TestClient, db: Session
    ) -> None:
        household = Household(name="Test Household")
        student = Student(household=household, name="Ada")
        db.add(student)
        db.commit()
        db.refresh(student)

        saved = client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2026-08-03",
                "end_date": "2027-06-04",
                "weekdays": [0, 2, 4],
            },
        )
        assert saved.status_code == 200

        response = client.get(f"/api/recalibrate/{student.id}/options")
        assert response.status_code == 200
        assert response.json()["target_days"] == [0, 2, 4]


class TestExceptionsUseSchoolYear:
    def test_toggle_on_the_first_day_of_the_named_year(
        self, client: TestClient
    ) -> None:
        year = client.post("/api/school-years", json=YEAR_BODY).json()
        settings = client.get("/api/settings/school-year").json()
        assert settings["start_date"] == year["start_date"]
        assert settings["end_date"] == year["end_date"]

        toggled = client.post(
            "/api/exceptions/toggle",
            json={"date": year["start_date"]},
        )
        assert toggled.status_code == 200
        assert toggled.json()["excepted"] is True
        assert year["start_date"] in toggled.json()["dates"]


class TestPortfolioUsesSchoolYearDates:
    def test_window_follows_updated_year_dates(
        self, client: TestClient, db: Session
    ) -> None:
        household = Household(name="Test Household")
        student = Student(household=household, name="Ada")
        db.add(student)
        db.commit()
        db.refresh(student)

        year = client.post(
            "/api/school-years",
            json={
                "name": "2026-2027",
                "start_date": "2026-08-01",
                "end_date": "2027-05-31",
            },
        ).json()
        assignment = Assignment(
            student_id=student.id,
            title="June lesson",
            scheduled_date=date(2027, 6, 1),
            status=AssignmentStatus.COMPLETED,
        )
        assignment.evidence.append(AssignmentEvidence(file_path="test/june.webp"))
        db.add(assignment)
        db.commit()

        before = client.get(
            f"/api/portfolios/report?student_id={student.id}"
            f"&school_year_id={year['id']}&report_type=work_samples"
        )
        assert before.status_code == 200
        assert before.json()["assignments"] == []

        updated = client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2026-08-01",
                "end_date": "2027-06-30",
                "weekdays": [0, 1, 2, 3, 4],
            },
        )
        assert updated.json()["school_year_id"] == year["id"]
        assert updated.json()["end_date"] == "2027-06-30"

        named = client.get(f"/api/school-years/{year['id']}").json()
        assert named["end_date"] == "2027-06-30"

        after = client.get(
            f"/api/portfolios/report?student_id={student.id}"
            f"&school_year_id={year['id']}&report_type=work_samples"
        )
        assert after.status_code == 200
        assert [item["title"] for item in after.json()["assignments"]] == ["June lesson"]


class TestLegacyTenantInitialize:
    def test_existing_settings_file_backfills_a_year_and_drops_date_columns(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "tenant_legacy.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE households (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        jurisdiction_id INTEGER,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE household_settings (
                        id INTEGER PRIMARY KEY,
                        household_id INTEGER NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        weekdays VARCHAR(32) NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "INSERT INTO households (id, name, created_at, updated_at) "
                    "VALUES (1, 'Legacy', '2026-01-01', '2026-01-01')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO household_settings "
                    "(id, household_id, start_date, end_date, weekdays, "
                    "created_at, updated_at) "
                    "VALUES (1, 1, '2026-08-03', '2027-06-04', '0,2,4', "
                    "'2026-01-01', '2026-01-01')"
                )
            )

        _ensure_tenant_schema(engine)
        _ensure_tenant_schema(engine)

        with engine.connect() as conn:
            columns = _sqlite_table_columns(conn, "household_settings")
            assert "start_date" not in columns
            assert "end_date" not in columns
            assert "weekdays" in columns
            assert "exception_colors" in columns
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            assert "school_years" in tables
            row = conn.execute(
                text("SELECT weekdays FROM household_settings")
            ).one()
            assert row[0] == "0,2,4"
            year = conn.execute(
                text(
                    "SELECT name, start_date, end_date FROM school_years "
                    "WHERE household_id = 1"
                )
            ).one()
            assert year[0] == "2026-2027"
            assert str(year[1]).startswith("2026-08-03")
            assert str(year[2]).startswith("2027-06-04")

        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = factory()
        try:
            start, end, weekdays, year_id = load_school_year_settings(session)
            assert start == date(2026, 8, 3)
            assert end == date(2027, 6, 4)
            assert weekdays == [0, 2, 4]
            assert year_id is not None
            year = session.get(SchoolYear, year_id)
            assert year is not None
            assert year.name == "2026-2027"
            settings = session.query(HouseholdSettings).one()
            assert settings.weekdays == "0,2,4"
        finally:
            session.close()
            engine.dispose()

    def test_divergent_settings_dates_do_not_overwrite_an_existing_year(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "tenant_divergent.db"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE households (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE school_years (
                        id INTEGER PRIMARY KEY,
                        household_id INTEGER NOT NULL,
                        name VARCHAR(128) NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE household_settings (
                        id INTEGER PRIMARY KEY,
                        household_id INTEGER NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        weekdays VARCHAR(32) NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "INSERT INTO households (id, name, created_at, updated_at) "
                    "VALUES (1, 'Family', '2026-01-01', '2026-01-01')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO school_years "
                    "(id, household_id, name, start_date, end_date, "
                    "created_at, updated_at) "
                    "VALUES (1, 1, 'Named Year', '2026-08-10', '2027-05-28', "
                    "'2026-01-01', '2026-01-01')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO household_settings "
                    "(id, household_id, start_date, end_date, weekdays, "
                    "created_at, updated_at) "
                    "VALUES (1, 1, '2025-08-01', '2026-06-30', '0,2,4', "
                    "'2026-01-01', '2026-01-01')"
                )
            )

        _ensure_tenant_schema(engine)

        with engine.connect() as conn:
            columns = _sqlite_table_columns(conn, "household_settings")
            assert "start_date" not in columns
            assert "end_date" not in columns
            year = conn.execute(
                text("SELECT name, start_date, end_date FROM school_years")
            ).one()
            assert year[0] == "Named Year"
            assert str(year[1]).startswith("2026-08-10")
            assert str(year[2]).startswith("2027-05-28")
            count = conn.execute(text("SELECT COUNT(*) FROM school_years")).scalar()
            assert count == 1
            weekdays = conn.execute(
                text("SELECT weekdays FROM household_settings")
            ).scalar()
            assert weekdays == "0,2,4"

        engine.dispose()
