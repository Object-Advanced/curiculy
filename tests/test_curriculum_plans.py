"""Structured pacing-guide CSV import and catalog listing."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CurriculumLesson, CurriculumPlan

PACING_CSV = """Unit,Week,Day,Title,Description,Pages
Multiplication,1,1,Lesson 1,Skip counting,7-10
Multiplication,1,2,Lesson 2,Facts of 2,11-14
Division,2,1,Lesson 3,Equal groups,15-18
"""

ALIASED_CSV = """unit_title,week_number,day_number,lesson_title,notes,page_range
Geometry,3,1,Lesson 4,Shapes,20-22
"""


def _import(client: TestClient, content: str, filename: str = "Saxon Math.csv"):
    return client.post(
        "/api/curriculum/import-csv",
        files={"file": (filename, content, "text/csv")},
    )


class TestImportCurriculumCsv:
    def test_creates_a_plan_titled_from_the_filename(
        self, client: TestClient, db: Session
    ) -> None:
        response = _import(client, PACING_CSV, "Saxon Math 5-4.csv")

        assert response.status_code == 201
        plan_id = response.json()["id"]
        plan = db.get(CurriculumPlan, plan_id)
        assert plan is not None
        assert plan.title == "Saxon Math 5-4"
        lessons = (
            db.query(CurriculumLesson)
            .filter(CurriculumLesson.plan_id == plan_id)
            .order_by(CurriculumLesson.id)
            .all()
        )
        assert [lesson.title for lesson in lessons] == [
            "Lesson 1",
            "Lesson 2",
            "Lesson 3",
        ]
        assert lessons[0].unit_title == "Multiplication"
        assert lessons[0].week_number == 1
        assert lessons[0].day_number == 1
        assert lessons[0].description == "Skip counting"
        assert lessons[0].pages == "7-10"
        assert lessons[2].unit_title == "Division"
        assert lessons[2].week_number == 2

    def test_accepts_aliased_headers(self, client: TestClient, db: Session) -> None:
        response = _import(client, ALIASED_CSV, "geometry.csv")

        assert response.status_code == 201
        plan_id = response.json()["id"]
        lesson = db.query(CurriculumLesson).filter_by(plan_id=plan_id).one()
        assert lesson.unit_title == "Geometry"
        assert lesson.week_number == 3
        assert lesson.day_number == 1
        assert lesson.title == "Lesson 4"
        assert lesson.description == "Shapes"
        assert lesson.pages == "20-22"

    def test_imports_time_slots_and_marks_lunch_as_routine(
        self, client: TestClient, db: Session
    ) -> None:
        csv_body = """Title,Week,Day,Time,Category
8:30-9:00 Bible,1,1,8:30-9:00,Daily Work
Lunch,1,1,12:00-12:30,
"""
        response = _import(client, csv_body, "abeka-day.csv")
        assert response.status_code == 201
        plan_id = response.json()["id"]
        lessons = (
            db.query(CurriculumLesson)
            .filter_by(plan_id=plan_id)
            .order_by(CurriculumLesson.id)
            .all()
        )
        assert [lesson.title for lesson in lessons] == ["Bible", "Lunch"]
        assert lessons[0].time_slot == "8:30-9:00"
        assert lessons[1].time_slot == "12:00-12:30"
        assert lessons[1].category == "Routine/Break"

    def test_defaults_day_number_when_the_column_is_omitted(
        self, client: TestClient, db: Session
    ) -> None:
        csv_body = "Title,Week\nLesson A,1\nLesson B,1\n"
        response = _import(client, csv_body, "days.csv")

        assert response.status_code == 201
        plan_id = response.json()["id"]
        days = [
            lesson.day_number
            for lesson in db.query(CurriculumLesson)
            .filter_by(plan_id=plan_id)
            .order_by(CurriculumLesson.id)
        ]
        assert days == [1, 2]

    def test_empty_file_is_rejected(self, client: TestClient, db: Session) -> None:
        response = _import(client, "", "empty.csv")

        assert response.status_code == 400
        assert db.query(CurriculumPlan).count() == 0

    def test_missing_title_column_is_rejected(
        self, client: TestClient, db: Session
    ) -> None:
        response = _import(client, "Week,Day\n1,1\n", "no-title.csv")

        assert response.status_code == 400
        assert "Title" in response.json()["detail"]
        assert db.query(CurriculumPlan).count() == 0

    def test_header_only_csv_is_rejected(self, client: TestClient, db: Session) -> None:
        response = _import(client, "Unit,Week,Day,Title\n", "headers-only.csv")

        assert response.status_code == 400
        assert db.query(CurriculumPlan).count() == 0
        assert db.query(CurriculumLesson).count() == 0

    def test_blank_title_on_a_row_is_rejected(
        self, client: TestClient, db: Session
    ) -> None:
        response = _import(client, "Title,Day\n,1\n", "blank-title.csv")

        assert response.status_code == 400
        assert db.query(CurriculumPlan).count() == 0


class TestCurriculumPlanRoutes:
    def test_list_includes_lesson_count_and_subject(
        self, client: TestClient, db: Session
    ) -> None:
        created = _import(client, PACING_CSV, "Math-U-See Gamma.csv")
        plan_id = created.json()["id"]
        plan = db.get(CurriculumPlan, plan_id)
        assert plan is not None
        plan.subject = "Mathematics"
        plan.publisher = "Math-U-See"
        db.commit()

        response = client.get("/api/curriculum/plans")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == plan_id
        assert payload[0]["title"] == "Math-U-See Gamma"
        assert payload[0]["publisher"] == "Math-U-See"
        assert payload[0]["subject"] == "Mathematics"
        assert payload[0]["lesson_count"] == 3
        assert payload[0]["status"] == "ready"

    def test_detail_returns_lessons_in_week_and_day_order(
        self, client: TestClient
    ) -> None:
        shuffled = """Unit,Week,Day,Title
B,2,1,Second
A,1,2,Middle
A,1,1,First
"""
        created = _import(client, shuffled, "order.csv")
        plan_id = created.json()["id"]

        response = client.get(f"/api/curriculum/plans/{plan_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "order"
        assert [lesson["title"] for lesson in body["lessons"]] == [
            "First",
            "Middle",
            "Second",
        ]
        assert body["lessons"][0]["unit_title"] == "A"
        assert body["lessons"][0]["week_number"] == 1
        assert body["lessons"][0]["day_number"] == 1

    def test_unknown_plan_is_not_found(self, client: TestClient) -> None:
        response = client.get("/api/curriculum/plans/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Curriculum plan not found"

    def test_import_infers_frequency_and_weeks(
        self, client: TestClient, db: Session
    ) -> None:
        created = _import(client, PACING_CSV, "inferred.csv")
        plan = db.get(CurriculumPlan, created.json()["id"])
        assert plan is not None
        assert plan.frequency_days == 2
        assert plan.total_weeks == 2
        assert plan.is_archived is False


def _create_plan(client: TestClient, body: dict | None = None) -> dict:
    payload = {
        "title": "Saxon Math 3",
        "subject": "Math",
        "grade_level": "3",
        "frequency_days": 3,
        "total_weeks": 1,
        "grading_weights": {"Daily Work": 40, "Quiz": 30, "Test": 30},
        "lessons": [
            {
                "week_number": 1,
                "day_number": 1,
                "title": "Lesson A",
                "category": "Daily Work",
                "notes": "Skip counting",
                "resources": ["https://example.com/a"],
            },
            {
                "week_number": 1,
                "day_number": 3,
                "title": "Lesson C",
                "category": "Quiz",
            },
        ],
    }
    if body:
        payload.update(body)
    response = client.post("/api/curriculum/plans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestCurriculumPlanBuilderApi:
    def test_create_returns_nested_lessons_and_weights(
        self, client: TestClient
    ) -> None:
        body = _create_plan(client)

        assert body["title"] == "Saxon Math 3"
        assert body["subject"] == "Math"
        assert body["grade_level"] == "3"
        assert body["frequency_days"] == 3
        assert body["total_weeks"] == 1
        assert body["grading_weights"] == {
            "Daily Work": 40.0,
            "Quiz": 30.0,
            "Test": 30.0,
        }
        assert body["is_archived"] is False
        assert body["status"] == "ready"
        assert [lesson["title"] for lesson in body["lessons"]] == [
            "Lesson A",
            "Lesson C",
        ]
        assert body["lessons"][0]["notes"] == "Skip counting"
        assert body["lessons"][0]["resources"] == ["https://example.com/a"]
        assert body["lessons"][0]["category"] == "Daily Work"
        assert body["lessons"][0]["time_slot"] is None

    def test_lunch_is_stored_as_routine_break_with_a_time_slot(
        self, client: TestClient
    ) -> None:
        body = _create_plan(
            client,
            {
                "frequency_days": 1,
                "total_weeks": 1,
                "lessons": [
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "8:30-9:00 Bible",
                        "category": "Daily Work",
                    },
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Lunch",
                    },
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Bible",
                        "time_slot": "8:30-9:00",
                        "category": "Daily Work",
                    },
                ],
            },
        )
        lessons = body["lessons"]
        assert [lesson["title"] for lesson in lessons] == ["Bible", "Lunch"]
        assert lessons[0]["time_slot"] == "8:30-9:00"
        assert lessons[0]["category"] == "Daily Work"
        assert lessons[1]["title"] == "Lunch"
        assert lessons[1]["category"] == "Routine/Break"

    def test_empty_grid_cells_are_not_stored(self, client: TestClient) -> None:
        body = _create_plan(
            client,
            {
                "lessons": [
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Keep",
                    },
                    {
                        "week_number": 1,
                        "day_number": 2,
                        "title": "  ",
                        "notes": "",
                    },
                ]
            },
        )
        assert [lesson["title"] for lesson in body["lessons"]] == ["Keep"]

    def test_put_syncs_update_insert_and_delete(self, client: TestClient) -> None:
        created = _create_plan(client)
        first_id = created["lessons"][0]["id"]
        second_id = created["lessons"][1]["id"]

        response = client.put(
            f"/api/curriculum/plans/{created['id']}",
            json={
                "title": "Saxon Math 3 revised",
                "subject": "Mathematics",
                "frequency_days": 3,
                "total_weeks": 1,
                "lessons": [
                    {
                        "id": first_id,
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Lesson A edited",
                        "category": "Daily Work",
                    },
                    {
                        "week_number": 1,
                        "day_number": 2,
                        "title": "Lesson B new",
                    },
                ],
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == "Saxon Math 3 revised"
        assert body["subject"] == "Mathematics"
        titles = [lesson["title"] for lesson in body["lessons"]]
        assert titles == ["Lesson A edited", "Lesson B new"]
        assert body["lessons"][0]["id"] == first_id
        assert second_id not in [lesson["id"] for lesson in body["lessons"]]

    def test_put_rejects_a_lesson_from_another_plan(self, client: TestClient) -> None:
        first = _create_plan(client)
        second = _create_plan(client, {"title": "Other plan"})
        foreign_id = first["lessons"][0]["id"]

        response = client.put(
            f"/api/curriculum/plans/{second['id']}",
            json={
                "title": "Other plan",
                "frequency_days": 3,
                "total_weeks": 1,
                "lessons": [
                    {
                        "id": foreign_id,
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Stolen",
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"]

    def test_list_hides_archived_plans_by_default(self, client: TestClient) -> None:
        created = _create_plan(client)
        plan_id = created["id"]

        archived = client.post(
            f"/api/curriculum/plans/{plan_id}/archive",
            json={"is_archived": True},
        )
        assert archived.status_code == 200
        assert archived.json()["is_archived"] is True

        hidden = client.get("/api/curriculum/plans")
        assert hidden.status_code == 200
        assert hidden.json() == []

        shown = client.get("/api/curriculum/plans?archived=true")
        assert shown.status_code == 200
        assert len(shown.json()) == 1
        assert shown.json()[0]["id"] == plan_id

        restored = client.post(
            f"/api/curriculum/plans/{plan_id}/archive",
            json={"is_archived": False},
        )
        assert restored.json()["is_archived"] is False
        listed = client.get("/api/curriculum/plans")
        assert [item["id"] for item in listed.json()] == [plan_id]

    def test_delete_removes_the_plan_and_lessons(
        self, client: TestClient, db: Session
    ) -> None:
        created = _create_plan(client)
        plan_id = created["id"]

        response = client.delete(f"/api/curriculum/plans/{plan_id}")
        assert response.status_code == 204
        assert db.get(CurriculumPlan, plan_id) is None
        assert db.query(CurriculumLesson).filter_by(plan_id=plan_id).count() == 0


class TestApplyCurriculumPlan:
    def test_preserves_empty_slots_and_stacks_same_day_lessons(
        self, client: TestClient, db: Session
    ) -> None:
        student_id = client.post("/api/students", json={"name": "Ada"}).json()["id"]
        created = _create_plan(
            client,
            {
                "frequency_days": 3,
                "total_weeks": 1,
                "lessons": [
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Lesson A",
                        "notes": "Do the facts",
                        "resources": ["https://example.com/a"],
                    },
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Lesson A extra",
                    },
                    {
                        "week_number": 1,
                        "day_number": 3,
                        "title": "Lesson C",
                    },
                ],
            },
        )

        response = client.post(
            f"/api/curriculum/plans/{created['id']}/apply",
            json={
                "student_id": student_id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["assignments_created"] == 3
        assert body["first_scheduled_date"] == "2026-08-31"
        assert body["last_scheduled_date"] == "2026-09-02"

        from app.models import Assignment

        rows = (
            db.query(Assignment)
            .filter(Assignment.student_id == student_id)
            .order_by(Assignment.scheduled_date, Assignment.id)
            .all()
        )
        assert [(row.title, row.scheduled_date.isoformat()) for row in rows] == [
            ("Lesson A", "2026-08-31"),
            ("Lesson A extra", "2026-08-31"),
            ("Lesson C", "2026-09-02"),
        ]
        assert "Do the facts" in (rows[0].notes or "")
        assert "https://example.com/a" in (rows[0].notes or "")
        from app.models import Curriculum

        curriculum = (
            db.query(Curriculum).filter(Curriculum.title == created["title"]).one()
        )
        assert {row.curriculum_id for row in rows} == {curriculum.id}

    def test_skips_routine_break_blocks_like_lunch(
        self, client: TestClient, db: Session
    ) -> None:
        student_id = client.post("/api/students", json={"name": "Ada"}).json()["id"]
        created = _create_plan(
            client,
            {
                "frequency_days": 1,
                "total_weeks": 1,
                "lessons": [
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Bible",
                        "time_slot": "8:30-9:00",
                    },
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Lunch",
                        "time_slot": "12:00-12:30",
                    },
                    {
                        "week_number": 1,
                        "day_number": 1,
                        "title": "Math",
                        "time_slot": "12:30-1:15",
                    },
                ],
            },
        )

        response = client.post(
            f"/api/curriculum/plans/{created['id']}/apply",
            json={
                "student_id": student_id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["assignments_created"] == 2

        from app.models import Assignment

        rows = (
            db.query(Assignment)
            .filter(Assignment.student_id == student_id)
            .order_by(Assignment.id)
            .all()
        )
        assert [row.title for row in rows] == ["Bible", "Math"]
        assert rows[0].notes == "8:30-9:00"

    def test_skips_weekends_and_calendar_exceptions(
        self, client: TestClient, db: Session
    ) -> None:
        student = client.post("/api/students", json={"name": "Ada"}).json()
        student_id = student["id"]
        from datetime import date

        from app.enums import ExceptionKind
        from app.models import CalendarException, Student

        db_student = db.get(Student, student_id)
        assert db_student is not None
        db.add(
            CalendarException(
                household_id=db_student.household_id,
                student_id=student_id,
                kind=ExceptionKind.HOLIDAY,
                title="Labor Day",
                start_date=date(2026, 9, 7),
                end_date=date(2026, 9, 7),
            )
        )
        db.commit()

        created = _create_plan(
            client,
            {
                "frequency_days": 3,
                "total_weeks": 1,
                "lessons": [
                    {"week_number": 1, "day_number": 1, "title": "Friday work"},
                    {"week_number": 1, "day_number": 2, "title": "Next school day"},
                    {"week_number": 1, "day_number": 3, "title": "After the holiday"},
                ],
            },
        )
        # Friday 4 Sep, then skip weekend, Monday 7 Sep is a holiday, so
        # Day 2 lands Tuesday 8 Sep and Day 3 Wednesday 9 Sep.
        response = client.post(
            f"/api/curriculum/plans/{created['id']}/apply",
            json={
                "student_id": student_id,
                "start_date": "2026-09-04",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["first_scheduled_date"] == "2026-09-04"
        assert response.json()["last_scheduled_date"] == "2026-09-09"

        from app.models import Assignment

        dates = [
            row.scheduled_date.isoformat()
            for row in db.query(Assignment)
            .filter(Assignment.student_id == student_id)
            .order_by(Assignment.scheduled_date)
        ]
        assert dates == ["2026-09-04", "2026-09-08", "2026-09-09"]

    def test_unknown_student_is_not_found(self, client: TestClient) -> None:
        created = _create_plan(client)
        response = client.post(
            f"/api/curriculum/plans/{created['id']}/apply",
            json={
                "student_id": 999,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_plan_without_titles_is_rejected(self, client: TestClient) -> None:
        student_id = client.post("/api/students", json={"name": "Ada"}).json()["id"]
        created = client.post(
            "/api/curriculum/plans",
            json={
                "title": "Empty days",
                "frequency_days": 1,
                "total_weeks": 1,
                "lessons": [
                    {"week_number": 1, "day_number": 1, "title": "", "notes": "only notes"}
                ],
            },
        )
        assert created.status_code == 201
        response = client.post(
            f"/api/curriculum/plans/{created.json()['id']}/apply",
            json={
                "student_id": student_id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 400
        assert "no assignments" in response.json()["detail"]

    def test_processing_plan_cannot_be_applied(
        self, client: TestClient, db: Session
    ) -> None:
        student_id = client.post("/api/students", json={"name": "Ada"}).json()["id"]
        created = _create_plan(client)
        plan = db.get(CurriculumPlan, created["id"])
        assert plan is not None
        plan.status = "processing"
        db.commit()

        response = client.post(
            f"/api/curriculum/plans/{created['id']}/apply",
            json={
                "student_id": student_id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 400
        assert "still being processed" in response.json()["detail"]

