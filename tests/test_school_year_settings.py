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
        year = db.get(SchoolYear, body["school_year_id"])
        assert year is not None
        assert year.start_date == date(2026, 8, 3)
        assert year.end_date == date(2027, 6, 4)

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

        response = client.get("/api/calendar/exceptions")
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

        response = client.get("/api/calendar/exceptions")
        assert response.json()["dates"] == []


class TestToggleException:
    def test_creates_then_removes_a_day(self, client: TestClient, db: Session) -> None:
        created = client.post(
            "/api/calendar/exceptions/toggle", json={"date": "2026-10-12"}
        )
        assert created.status_code == 200
        assert created.json()["excepted"] is True
        assert created.json()["dates"] == ["2026-10-12"]
        row = db.query(CalendarException).one()
        assert row.start_date == date(2026, 10, 12)
        assert row.end_date == date(2026, 10, 12)
        assert row.student_id is None

        removed = client.post(
            "/api/calendar/exceptions/toggle", json={"date": "2026-10-12"}
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
            "/api/calendar/exceptions/toggle", json={"date": "2026-12-25"}
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
            "/api/calendar/exceptions/import-holidays",
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
            "/api/calendar/exceptions/import-holidays",
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
            "/api/calendar/exceptions/import-holidays",
            json={"country": "US", "subdiv": "FL", "year": 2026},
        )
        assert response.status_code == 200
        assert CHRISTMAS_2026.isoformat() in response.json()["dates"]

    def test_rejects_an_unknown_region(self, client: TestClient) -> None:
        response = client.post(
            "/api/calendar/exceptions/import-holidays",
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
