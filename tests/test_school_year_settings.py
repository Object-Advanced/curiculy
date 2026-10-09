"""School-year settings, day toggles, and public-holiday import."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import ExceptionKind
from app.models import CalendarException, Household, HouseholdSettings, SchoolYear

CHRISTMAS_2026 = date(2026, 12, 25)
THANKSGIVING_2026 = date(2026, 11, 26)


def _household(db: Session) -> Household:
    household = Household(name="Test Household")
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


class TestSchoolYearSettings:
    def test_defaults_to_an_august_june_year(self, client: TestClient) -> None:
        response = client.get("/api/settings/school-year")
        assert response.status_code == 200
        body = response.json()
        assert body["weekdays"] == [0, 1, 2, 3, 4]
        assert body["start_date"] < body["end_date"]
        assert body["start_date"].endswith("-08-01")
        assert body["end_date"].endswith("-06-30")
        assert body["school_year_id"] is None
        assert set(body) == {"start_date", "end_date", "weekdays", "school_year_id"}

    def test_falls_back_to_the_latest_school_year(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        year = SchoolYear(
            household_id=household.id,
            name="2026-2027",
            start_date=date(2026, 8, 10),
            end_date=date(2027, 5, 28),
        )
        db.add(year)
        db.commit()

        response = client.get("/api/settings/school-year")
        assert response.status_code == 200
        body = response.json()
        assert body["start_date"] == "2026-08-10"
        assert body["end_date"] == "2027-05-28"
        assert body["school_year_id"] == year.id
        assert body["weekdays"] == [0, 1, 2, 3, 4]

    def test_put_persists_bounds_and_class_days(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2026-08-03",
                "end_date": "2027-06-04",
                "weekdays": [0, 2, 4],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["start_date"] == "2026-08-03"
        assert body["end_date"] == "2027-06-04"
        assert body["weekdays"] == [0, 2, 4]
        assert body["school_year_id"] is not None

        stored = db.query(HouseholdSettings).one()
        assert stored.weekdays == "0,2,4"
        assert "start_date" not in HouseholdSettings.__table__.c
        assert "end_date" not in HouseholdSettings.__table__.c
        from sqlalchemy import inspect as sa_inspect

        physical = {
            column["name"]
            for column in sa_inspect(db.get_bind()).get_columns("household_settings")
        }
        assert "start_date" not in physical
        assert "end_date" not in physical
        year = db.get(SchoolYear, body["school_year_id"])
        assert year is not None
        assert year.start_date == date(2026, 8, 3)
        assert year.end_date == date(2027, 6, 4)

        named = client.get(f"/api/school-years/{body['school_year_id']}")
        assert named.status_code == 200
        assert named.json()["start_date"] == "2026-08-03"
        assert named.json()["end_date"] == "2027-06-04"

        again = client.get("/api/settings/school-year")
        assert again.json() == body

    def test_put_rejects_an_empty_weekday_list(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2026-08-01",
                "end_date": "2027-06-30",
                "weekdays": [],
            },
        )
        assert response.status_code == 422

    def test_settings_dates_are_not_the_read_source_when_a_year_exists(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        year = SchoolYear(
            household_id=household.id,
            name="2026-2027",
            start_date=date(2026, 8, 10),
            end_date=date(2027, 5, 28),
        )
        db.add(year)
        db.add(
            HouseholdSettings(
                household_id=household.id,
                weekdays="0,2,4",
            )
        )
        db.commit()

        response = client.get("/api/settings/school-year")
        assert response.status_code == 200
        body = response.json()
        assert body["start_date"] == "2026-08-10"
        assert body["end_date"] == "2027-05-28"
        assert body["school_year_id"] == year.id
        assert body["weekdays"] == [0, 2, 4]

        stored = db.query(HouseholdSettings).one()
        db.refresh(stored)
        assert stored.weekdays == "0,2,4"
        assert "start_date" not in HouseholdSettings.__table__.c
        assert "end_date" not in HouseholdSettings.__table__.c

    def test_weekdays_only_settings_do_not_invent_a_named_year(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        db.add(
            HouseholdSettings(
                household_id=household.id,
                weekdays="5,6",
            )
        )
        db.commit()
        assert db.query(SchoolYear).count() == 0

        response = client.get("/api/settings/school-year")
        assert response.status_code == 200
        body = response.json()
        assert body["weekdays"] == [5, 6]
        assert body["school_year_id"] is None
        assert body["start_date"].endswith("-08-01")
        assert body["end_date"].endswith("-06-30")
        assert db.query(SchoolYear).count() == 0

    def test_put_rejects_a_reversed_window(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/school-year",
            json={
                "start_date": "2027-06-30",
                "end_date": "2026-08-01",
                "weekdays": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 422


class TestCalendarExceptionDates:
    def test_lists_expanded_household_dates(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        db.add(
            CalendarException(
                household_id=household.id,
                kind=ExceptionKind.VACATION,
                title="Break",
                start_date=date(2026, 12, 24),
                end_date=date(2026, 12, 26),
            )
        )
        db.commit()

        response = client.get("/api/exceptions/dates")
        assert response.status_code == 200
        assert response.json()["dates"] == [
            "2026-12-24",
            "2026-12-25",
            "2026-12-26",
        ]

    def test_ignores_student_specific_rows(
        self, client: TestClient, db: Session
    ) -> None:
        from app.models import Student

        household = _household(db)
        student = Student(household_id=household.id, name="Ada")
        db.add(student)
        db.commit()
        db.add(
            CalendarException(
                household_id=household.id,
                student_id=student.id,
                kind=ExceptionKind.SICK,
                title="Flu",
                start_date=date(2026, 9, 14),
                end_date=date(2026, 9, 14),
            )
        )
        db.commit()

        response = client.get("/api/exceptions/dates")
        assert response.json()["dates"] == []


class TestToggleException:
    def test_creates_then_removes_a_day(self, client: TestClient, db: Session) -> None:
        created = client.post(
            "/api/exceptions/toggle", json={"date": "2026-10-12"}
        )
        assert created.status_code == 200
        assert created.json()["excepted"] is True
        assert created.json()["dates"] == ["2026-10-12"]
        row = db.query(CalendarException).one()
        assert row.start_date == date(2026, 10, 12)
        assert row.end_date == date(2026, 10, 12)
        assert row.student_id is None

        removed = client.post(
            "/api/exceptions/toggle", json={"date": "2026-10-12"}
        )
        assert removed.status_code == 200
        assert removed.json()["excepted"] is False
        assert removed.json()["dates"] == []
        assert db.query(CalendarException).count() == 0

    def test_punches_a_day_out_of_a_range(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        db.add(
            CalendarException(
                household_id=household.id,
                kind=ExceptionKind.VACATION,
                title="Break",
                start_date=date(2026, 12, 20),
                end_date=date(2026, 12, 26),
            )
        )
        db.commit()

        response = client.post(
            "/api/exceptions/toggle", json={"date": "2026-12-25"}
        )
        assert response.status_code == 200
        assert "2026-12-25" not in response.json()["dates"]
        assert "2026-12-24" in response.json()["dates"]
        assert "2026-12-26" in response.json()["dates"]

        rows = db.query(CalendarException).order_by(CalendarException.start_date).all()
        assert [(row.start_date, row.end_date) for row in rows] == [
            (date(2026, 12, 20), date(2026, 12, 24)),
            (date(2026, 12, 26), date(2026, 12, 26)),
        ]


class TestImportHolidays:
    def test_imports_us_federal_holidays(self, client: TestClient) -> None:
        response = client.post(
            "/api/exceptions/import-holidays",
            json={"country": "US", "year": 2026},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["imported"] > 0
        assert body["skipped"] == 0
        assert CHRISTMAS_2026.isoformat() in body["dates"]
        assert THANKSGIVING_2026.isoformat() in body["dates"]

    def test_skips_dates_already_on_the_calendar(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        db.add(
            CalendarException(
                household_id=household.id,
                kind=ExceptionKind.HOLIDAY,
                title="Christmas Day",
                start_date=CHRISTMAS_2026,
                end_date=CHRISTMAS_2026,
            )
        )
        db.commit()

        response = client.post(
            "/api/exceptions/import-holidays",
            json={"country": "US", "subdiv": None, "year": 2026},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["skipped"] >= 1
        christmas_rows = (
            db.query(CalendarException)
            .filter(
                CalendarException.start_date == CHRISTMAS_2026,
                CalendarException.end_date == CHRISTMAS_2026,
            )
            .count()
        )
        assert christmas_rows == 1

    def test_accepts_a_state_subdivision(self, client: TestClient) -> None:
        response = client.post(
            "/api/exceptions/import-holidays",
            json={"country": "US", "subdiv": "FL", "year": 2026},
        )
        assert response.status_code == 200
        assert CHRISTMAS_2026.isoformat() in response.json()["dates"]

    def test_rejects_an_unknown_region(self, client: TestClient) -> None:
        response = client.post(
            "/api/exceptions/import-holidays",
            json={"country": "ZZ", "year": 2026},
        )
        assert response.status_code == 400
        assert "ZZ" in response.json()["detail"]


class TestExceptionColors:
    def test_returns_the_default_scheme(self, client: TestClient) -> None:
        response = client.get("/api/settings/exception-colors")
        assert response.status_code == 200
        assert response.json() == {
            "holiday": "#c2410c",
            "vacation": "#2563eb",
            "sick": "#7c3aed",
            "appointment": "#0f766e",
            "other": "#dc2626",
        }

    def test_put_persists_a_custom_color(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.put(
            "/api/settings/exception-colors",
            json={"other": "#ff8800"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["other"] == "#ff8800"
        assert body["holiday"] == "#c2410c"
        stored = db.query(HouseholdSettings).one()
        assert "#ff8800" in stored.exception_colors

        again = client.get("/api/settings/exception-colors")
        assert again.json()["other"] == "#ff8800"

    def test_rejects_a_bad_hex(self, client: TestClient) -> None:
        response = client.put(
            "/api/settings/exception-colors",
            json={"holiday": "red"},
        )
        assert response.status_code == 422


class TestExceptionRecords:
    def test_list_returns_full_records_not_a_date_envelope(
        self, client: TestClient, db: Session
    ) -> None:
        household = _household(db)
        db.add(
            CalendarException(
                household_id=household.id,
                kind=ExceptionKind.VACATION,
                title="Break",
                start_date=date(2026, 12, 24),
                end_date=date(2026, 12, 26),
            )
        )
        db.commit()

        listed = client.get("/api/exceptions")
        assert listed.status_code == 200
        body = listed.json()
        assert isinstance(body, list)
        assert body[0]["title"] == "Break"
        assert body[0]["start_date"] == "2026-12-24"
        assert body[0]["end_date"] == "2026-12-26"

        dates = client.get("/api/exceptions/dates")
        assert dates.json()["dates"] == [
            "2026-12-24",
            "2026-12-25",
            "2026-12-26",
        ]

    def test_create_titled_range(self, client: TestClient) -> None:
        response = client.post(
            "/api/exceptions",
            json={
                "kind": "sick",
                "title": "Flu",
                "student_id": None,
                "start_date": "2026-09-14",
                "end_date": "2026-09-16",
                "notes": None,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Flu"
        assert body["kind"] == "sick"
        assert body["start_date"] == "2026-09-14"
        assert body["end_date"] == "2026-09-16"
        assert body["student_id"] is None

        listed = client.get("/api/exceptions")
        assert any(row["title"] == "Flu" for row in listed.json())

    def test_old_calendar_exceptions_prefix_is_gone(self, client: TestClient) -> None:
        assert client.get("/api/calendar/exceptions").status_code == 404
        assert (
            client.post(
                "/api/calendar/exceptions/toggle", json={"date": "2026-10-12"}
            ).status_code
            == 404
        )
