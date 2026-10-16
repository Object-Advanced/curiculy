"""Cross-family probe: Family A can't read, change or delete anything of Family B's.

Runs on the production path (real sign-in, row-level security on):

1. Every API route that takes a record id is called as Family A with Family
   B's ids, in every method it accepts.
2. The routes that take ids in their request body are called with B's ids.
3. Every list and page is read as Family A and searched for B's data.

No response may contain B's data, nothing may fail with a server error, and
B's data must be exactly the same afterwards. New routes are covered
automatically; a new kind of record id fails the test until it's added to
``ID_PARAMS``.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.config import settings
from app.db import open_family_session
from app.enums import AttendanceStatus, CurriculumPlanStatus, ExceptionKind, ParentNotificationType
from app.main import create_app
from app.models import (
    Activity,
    ActivityEvidence,
    ActivityStudent,
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    Attendance,
    CalendarException,
    Course,
    Curriculum,
    CurriculumLesson,
    CurriculumPlan,
    Enrollment,
    EvidenceStaging,
    HomeworkHelpSession,
    Household,
    LibraryChapter,
    LibraryItem,
    LibraryLesson,
    ParentNotification,
    PlannedCurriculum,
    PlannedCurriculumItem,
    ReadingListEntry,
    SchoolYear,
    Student,
    StudentSubject,
)
from app.services.family_data import export_family
from tests.test_auth import bearer, seed_user

pytest_plugins = ["tests.test_auth"]

SECRET = "Bsecret"
# Path parameters that name a family's record, and the seeded record they take.
ID_PARAMS = {
    "student_id": "student",
    "assignment_id": "assignment",
    "curriculum_id": "curriculum",
    "plan_id": "plan",
    "school_year_id": "school_year",
    "enrollment_id": "enrollment",
    "notification_id": "notification",
    "session_id": "session",
    "subject_id": "student_subject",
    "item_id": "library_item",
    "planned_curriculum_id": "planned_curriculum",
    "course_id": "course",
    "file_path": "file_path",
    "reading_id": "reading",
    "activity_id": "activity",
    "activity_evidence_id": "activity_evidence",
}
# Path parameters that aren't a family's record (shared book cache and
# community catalog, static files).
NOT_FAMILY_PARAMS = {"book_id", "isbn", "path", "state_code", "entry_id", "contribution_id"}

# Request bodies for writes, so they get past validation to the ownership check.
BODIES = {
    ("PUT", "/api/students/{student_id}"): {"name": "Hacked"},
    ("POST", "/api/students/{student_id}/pin"): {"pin": "4321"},
    ("PUT", "/api/assignments/{assignment_id}"): {"status": "completed"},
    ("PATCH", "/api/assignments/{assignment_id}/status"): {"status": "completed"},
    ("PUT", "/api/assignments/{assignment_id}/grade"): {"score_value": "F"},
    ("PATCH", "/api/school-years/{school_year_id}"): {"name": "Hacked"},
    ("PUT", "/api/curriculum/plans/{plan_id}"): {"title": "Hacked"},
    ("POST", "/api/homework-help/sessions/{session_id}/outcome"): {"outcome": "resolved"},
    ("POST", "/api/recalibrate/{student_id}/execute"): {"strategy": "extend"},
    ("PATCH", "/api/planner/curricula/{planned_curriculum_id}"): {"name": "Hacked"},
    ("POST", "/api/planner/curricula/{planned_curriculum_id}/items"): {"library_item_id": 1, "role": "reading"},
    ("POST", "/api/planner/curricula/{planned_curriculum_id}/schedule/preview"): {
        "student_ids": [1], "start_date": "2026-10-13"},
    ("POST", "/api/planner/curricula/{planned_curriculum_id}/schedule"): {
        "student_ids": [1], "start_date": "2026-10-13"},
    ("POST", "/api/library/{item_id}/schedule/preview"): {"student_ids": [1], "start_date": "2026-10-13"},
    ("POST", "/api/library/{item_id}/schedule"): {"student_ids": [1], "start_date": "2026-10-13"},
    ("PUT", "/api/school-years/{school_year_id}/terms"): [
        {"name": "Hacked", "start_date": "2026-08-01", "end_date": "2026-12-31"}],
    ("PATCH", "/api/reading-list/{reading_id}"): {"status": "finished"},
    ("PATCH", "/api/activities/{activity_id}"): {"title": "Hacked"},
}


def _seed(tenant_id: str, prefix: str, evidence_dir: Path) -> dict:
    """A family with one of everything; every title starts with ``prefix``."""
    session = open_family_session(tenant_id)
    try:
        household = Household(name=f"{prefix} household")
        session.add(household)
        session.flush()
        student = Student(household_id=household.id, name=f"{prefix} child")
        year = SchoolYear(
            household_id=household.id,
            name=f"{prefix} year",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 6, 30),
        )
        curriculum = Curriculum(title=f"{prefix} book")
        plan = CurriculumPlan(title=f"{prefix} plan", status=CurriculumPlanStatus.READY)
        session.add_all([student, year, curriculum, plan])
        session.flush()
        session.add(CurriculumLesson(plan_id=plan.id, day_number=1, title=f"{prefix} plan lesson"))
        assignment = Assignment(
            student_id=student.id,
            title=f"{prefix} lesson",
            notes=f"{prefix} note on the lesson",
            scheduled_date=date(2026, 10, 12),
        )
        session.add(assignment)
        session.flush()
        file_path = f"{tenant_id}/{prefix.lower()}-page.webp"
        (evidence_dir / tenant_id).mkdir(parents=True, exist_ok=True)
        (evidence_dir / file_path).write_bytes(f"{prefix} photo bytes".encode())
        enrollment = Enrollment(student_id=student.id, curriculum_id=curriculum.id, school_year_id=year.id)
        help_session = HomeworkHelpSession(student_id=student.id, assignment_id=assignment.id)
        notification = ParentNotification(
            type=ParentNotificationType.CURRICULUM_PLAN_FAILED,
            title=f"{prefix} notice",
            body=f"{prefix} notice body",
        )
        staged = EvidenceStaging(file_path=f"{tenant_id}/{prefix.lower()}-staged.webp")
        student_subject = StudentSubject(
            student_id=student.id,
            school_year_id=year.id,
            subject_code=None,
            name=f"{prefix} subject",
            kind="own",
            objective=f"{prefix} objective",
        )
        library_item = LibraryItem(
            kind="reading_book", title=f"{prefix} library book", author=f"{prefix} author", total_pages=99,
            chapters=[LibraryChapter(position=0, name=f"{prefix} chapter", start_page=1)],
        )
        textbook = LibraryItem(
            kind="textbook", title=f"{prefix} textbook", publisher=f"{prefix} press", edition="1",
            subject_code="math", grade="4", total_pages=20,
            lessons=[LibraryLesson(position=0, number=1, name=f"{prefix} first lesson", start_page=1, end_page=2)],
        )
        planned = PlannedCurriculum(name=f"{prefix} curriculum", subject_code="math", grade="4")
        session.add_all([textbook, planned])
        session.flush()
        planned.items.append(PlannedCurriculumItem(library_item_id=textbook.id, role="textbook", position=0))
        course = Course(
            curriculum_id=planned.id, student_id=student.id, school_year_id=year.id,
            start_date=date(2026, 10, 12), end_date=date(2026, 10, 12), weekdays="0,1,2,3,4",
        )
        session.add(course)
        session.flush()
        session.add(Assignment(
            student_id=student.id, title=f"{prefix} course lesson", scheduled_date=date(2026, 10, 12),
            course_id=course.id, library_item_id=textbook.id,
        ))
        session.add(library_item)
        session.flush()
        reading = ReadingListEntry(student_id=student.id, library_item_id=library_item.id, school_year_id=year.id)
        activity = Activity(
            title=f"{prefix} activity", on_date=date(2026, 10, 10), notes=f"{prefix} activity notes",
            subject_codes=["pe"], students=[ActivityStudent(student_id=student.id)],
        )
        activity.evidence.append(ActivityEvidence(
            file_path=file_path, captured_at=datetime(2026, 10, 10, tzinfo=timezone.utc)))
        session.add_all([reading, activity])
        session.flush()
        session.add_all(
            [
                library_item,
                student_subject,
                enrollment,
                help_session,
                notification,
                staged,
                AssignmentGrade(assignment_id=assignment.id, score_value=f"{prefix} grade"),
                AssignmentEvidence(
                    assignment_id=assignment.id,
                    file_path=file_path,
                    captured_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
                ),
                Attendance(student_id=student.id, date=date(2026, 10, 12), status=AttendanceStatus.PRESENT),
                CalendarException(
                    household_id=household.id,
                    student_id=student.id,
                    kind=list(ExceptionKind)[0],
                    title=f"{prefix} holiday",
                    start_date=date(2026, 11, 26),
                    end_date=date(2026, 11, 27),
                ),
            ]
        )
        session.commit()
        return {
            "student": student.id,
            "assignment": assignment.id,
            "curriculum": curriculum.id,
            "plan": plan.id,
            "school_year": year.id,
            "enrollment": enrollment.id,
            "notification": notification.id,
            "session": help_session.id,
            "staged": staged.id,
            "student_subject": student_subject.id,
            "library_item": library_item.id,
            "textbook": textbook.id,
            "planned_curriculum": planned.id,
            "course": course.id,
            "file_path": file_path,
            "reading": reading.id,
            "activity": activity.id,
            "activity_evidence": activity.evidence[0].id,
        }
    finally:
        session.close()


def _export(tenant_id: str) -> dict:
    session = open_family_session(tenant_id)
    try:
        return export_family(session)
    finally:
        session.close()


@pytest.fixture
def probe(auth_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    evidence = auth_dir / "evidence"
    monkeypatch.setattr(settings, "evidence_dir", evidence)
    monkeypatch.setattr(settings, "ollama_host", "http://127.0.0.1:9")  # no AI calls leave the test
    a_ids = _seed("family-a", "Afamily", evidence)
    b_ids = _seed("family-b", SECRET, evidence)
    seed_user(email="alpha@example.com", tenant_uuid="family-a")
    client = TestClient(create_app())
    token = client.post(
        "/api/auth/token", data={"username": "alpha@example.com", "password": "secret"}
    ).json()["access_token"]
    return {"client": client, "headers": bearer(token), "a": a_ids, "b": b_ids}


def _id_routes() -> list[tuple[str, str, list[str]]]:
    routes = []
    for route in create_app().routes:
        if not isinstance(route, APIRoute):
            continue
        params = re.findall(r"{([^}:]+)(?::[^}]+)?}", route.path)
        if not params or set(params) & NOT_FAMILY_PARAMS:
            continue
        for method in sorted(route.methods):
            routes.append((method, route.path, params))
    return routes


def _fill(path: str, ids: dict) -> str:
    def replace(match: re.Match) -> str:
        return str(ids[ID_PARAMS[match.group(1)]])

    return re.sub(r"{([^}:]+)(?::[^}]+)?}", replace, path)


def _assert_clean(response, where: str) -> None:
    assert response.status_code < 500, f"{where} failed with {response.status_code}: {response.text[:300]}"
    assert SECRET.encode() not in response.content, f"{where} returned Family B's data"


def test_every_id_route_refuses_another_familys_records(probe: dict) -> None:
    client, headers, b = probe["client"], probe["headers"], probe["b"]
    before = _export("family-b")
    unknown = sorted(
        {param for _, _, params in _id_routes() for param in params} - set(ID_PARAMS)
    )
    assert not unknown, f"Add these path parameters to ID_PARAMS: {unknown}"

    called = 0
    for method, path, _ in _id_routes():
        url = _fill(path, b)
        body = BODIES.get((method, path), {})
        response = client.request(method, url, headers=headers, json=body if method in {"POST", "PUT", "PATCH"} else None)
        _assert_clean(response, f"{method} {url}")
        called += 1

    assert called == len(_id_routes()) >= 30
    assert _export("family-b") == before


def test_ids_inside_request_bodies_refuse_another_familys_records(probe: dict) -> None:
    client, headers, a, b = probe["client"], probe["headers"], probe["a"], probe["b"]
    before = _export("family-b")
    attempts = [
        ("POST", "/api/assignments", {"student_id": b["student"], "title": "x", "scheduled_date": "2026-10-13"}),
        ("POST", "/api/attendance", {"student_id": b["student"], "date": "2026-10-13", "status": "present"}),
        ("POST", "/api/evidence/link", {"evidence_id": b["staged"], "assignment_id": a["assignment"]}),
        ("POST", "/api/evidence/link", {"evidence_id": b["staged"], "assignment_id": b["assignment"]}),
        ("POST", "/api/homework-help/sessions", {"assignment_id": b["assignment"]}),
        (
            "POST",
            "/api/enrollments",
            {"student_id": b["student"], "curriculum_id": a["curriculum"], "school_year_id": a["school_year"]},
        ),
        (
            "POST",
            "/api/enrollments",
            {"student_id": a["student"], "curriculum_id": b["curriculum"], "school_year_id": b["school_year"]},
        ),
        (
            "POST",
            "/api/exceptions",
            {"student_id": b["student"], "kind": list(ExceptionKind)[0].value, "title": "x",
             "start_date": "2026-12-01", "end_date": "2026-12-01"},
        ),
        ("POST", f"/api/curriculum/plans/{a['plan']}/apply", {"student_id": b["student"], "start_date": "2026-10-13"}),
        ("POST", "/api/portfolios/preview", {"student_ids": [b["student"]]}),
        ("POST", "/api/portfolios/preview", {"student_id": b["student"]}),
        ("POST", "/api/auth/switch", {"student_id": b["student"]}),
        ("POST", "/api/planner/curricula", {"textbook_id": b["textbook"]}),
        ("POST", f"/api/planner/curricula/{a['planned_curriculum']}/items",
         {"library_item_id": b["library_item"], "role": "reading"}),
        ("POST", f"/api/planner/curricula/{a['planned_curriculum']}/schedule/preview",
         {"student_ids": [b["student"]], "start_date": "2026-10-13"}),
        ("POST", f"/api/planner/curricula/{a['planned_curriculum']}/schedule",
         {"student_ids": [b["student"]], "start_date": "2026-10-13"}),
        ("GET", f"/api/community/suggestions?library_item_id={b['textbook']}", None),
        ("POST", f"/api/library/{a['library_item']}/schedule/preview",
         {"student_ids": [b["student"]], "start_date": "2026-10-13"}),
        ("POST", f"/api/library/{a['library_item']}/schedule",
         {"student_ids": [b["student"]], "start_date": "2026-10-13"}),
        ("POST", "/api/reading-list", {"student_id": b["student"], "library_item_id": a["library_item"]}),
        ("POST", "/api/reading-list", {"student_id": a["student"], "library_item_id": b["library_item"]}),
        ("GET", f"/api/reading-list?student_id={b['student']}", None),
        ("GET", f"/api/reading-list?library_item_id={b['library_item']}", None),
        ("POST", "/api/activities", {"title": "x", "on_date": "2026-10-13", "student_ids": [b["student"]]}),
        ("POST", "/api/activities", {"title": "x", "on_date": "2026-10-13",
                                     "student_ids": [a["student"], b["student"]]}),
        ("PATCH", f"/api/activities/{a['activity']}", {"student_ids": [b["student"]]}),
        ("GET", f"/api/activities?student_id={b['student']}", None),
        ("POST", "/api/attendance/confirm", {"marks": [
            {"student_id": b["student"], "date": "2026-10-12", "status": "Absent"}]}),
        ("POST", "/api/attendance/confirm", {"marks": [
            {"student_id": a["student"], "date": "2026-10-12", "status": "Present"},
            {"student_id": b["student"], "date": "2026-10-12", "status": "Absent"}]}),
        ("GET", f"/api/attendance/days?student_id={b['student']}", None),
        ("GET", "/api/attendance/days?start_date=2026-10-12&end_date=2026-10-12", None),
        ("GET", "/api/attendance/summary", None),
    ]
    for method, url, body in attempts:
        response = client.request(method, url, headers=headers, json=body)
        _assert_clean(response, f"{method} {url} {body}")
    assert _export("family-b") == before


def test_lists_and_pages_never_show_another_familys_data(probe: dict) -> None:
    client, headers, a = probe["client"], probe["headers"], probe["a"]
    query = {
        "student_id": a["student"],
        "school_year_id": a["school_year"],
        "start_date": "2026-08-01",
        "end_date": "2027-06-30",
    }
    read = 0
    for route in create_app().routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods:
            continue
        if not route.path.startswith("/api/") or route.path.startswith("/api/books"):
            continue
        params = re.findall(r"{([^}:]+)(?::[^}]+)?}", route.path)
        if set(params) & NOT_FAMILY_PARAMS:
            continue
        url = _fill(route.path, a) if params else route.path
        response = client.get(url, headers=headers, params=query)
        _assert_clean(response, f"GET {url}")
        read += 1
    assert read >= 30
