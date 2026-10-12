"""The Curriculum planner: build a curriculum around a textbook, schedule it,
and share it with the next family."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, ExceptionKind
from app.models import (
    Assignment,
    CalendarException,
    CatalogContribution,
    CommunityCurriculum,
    Course,
    SchoolYear,
    Student,
)
from app.services.households import get_default_household
from app.services.planner import _apportion, _sessions, course_days, page_plan
from tests.test_community import admin  # noqa: F401  (the admin review fixture)

MONDAY = date(2026, 10, 12)


def _add(client: TestClient, **fields) -> dict:
    response = client.post("/api/library", json=fields)
    assert response.status_code == 201, response.text
    return response.json()


def _textbook(client: TestClient, lessons: int = 6, **fields) -> dict:
    details = {"kind": "textbook", "title": "BJU Reading 4", "publisher": "BJU Press", "edition": "4th",
               "subject_code": "english", "grade": "4", "total_pages": 300, "days_per_week": 4}
    item = _add(client, **{**details, **fields})
    body = client.put(
        f"/api/library/{item['id']}/lessons",
        json=[{"number": n, "name": f"Story {n}", "start_page": n * 2 - 1, "end_page": n * 2} for n in range(1, lessons + 1)],
    ).json()
    assert body["ready"] is True, body["readiness"]
    return body


def _workbook(client: TestClient) -> dict:
    item = _add(client, kind="workbook", title="BJU Reading 4 Worktext", subject_code="english", grade="4",
                total_pages=120, answer_key_start_page=101)
    return client.put(f"/api/library/{item['id']}/chapters",
                      json=[{"name": "Unit 1", "start_page": 1}, {"name": "Unit 2", "start_page": 51}]).json()


def _novel(client: TestClient, title: str = "Charlotte's Web") -> dict:
    return _add(client, kind="reading_book", title=title, author="E. B. White", total_pages=184)


def _online(client: TestClient) -> dict:
    return _add(client, kind="online_program", title="IXL Language Arts", website_url="https://www.ixl.com/ela",
                subject_code="english", grade="4", measure="minutes", minutes_per_session=15, days_per_week=2)


def _curriculum(client: TestClient, textbook: dict, *others: tuple[dict, str]) -> dict:
    body = client.post("/api/planner/curricula", json={"textbook_id": textbook["id"]}).json()
    for item, role in others:
        response = client.post(f"/api/planner/curricula/{body['id']}/items",
                               json={"library_item_id": item["id"], "role": role})
        assert response.status_code == 200, response.text
        body = response.json()
    return body


@pytest.fixture
def ada(db: Session) -> int:
    household = get_default_household(db)
    db.add(SchoolYear(household_id=household.id, name="2026–27", start_date=date(2026, 8, 1),
                      end_date=date(2027, 6, 4)))
    student = Student(household_id=household.id, name="Ada")
    db.add(student)
    db.flush()
    return student.id


class TestBuilding:
    def test_starting_from_a_textbook_carries_its_details(self, client: TestClient) -> None:
        body = _curriculum(client, _textbook(client))
        assert (body["name"], body["subject_code"], body["grade"], body["days_per_week"]) == (
            "BJU Reading 4", "english", "4", 4)
        assert [(i["role"], i["role_label"]) for i in body["items"]] == [("textbook", "Textbook")]
        assert body["readiness"]["ready"] is True

    def test_a_curriculum_is_built_around_a_textbook(self, client: TestClient) -> None:
        body = client.post("/api/planner/curricula", json={"name": "Reading 4", "subject_code": "english"}).json()
        [missing] = body["readiness"]["missing"]
        assert missing["field"] == "textbook" and "set the pace" in missing["reason"]

    def test_each_role_fits_its_kind(self, client: TestClient) -> None:
        textbook, workbook = _textbook(client), _workbook(client)
        body = _curriculum(client, textbook)
        add = lambda item, role: client.post(  # noqa: E731
            f"/api/planner/curricula/{body['id']}/items", json={"library_item_id": item["id"], "role": role})
        assert add(workbook, "textbook").status_code == 409
        assert add(_textbook(client, title="Another"), "textbook").status_code == 409
        teacher = _add(client, kind="textbook", title="BJU Reading 4 Teacher's Edition", publisher="BJU Press",
                       edition="4th", subject_code="english", grade="4", total_pages=500, for_parent=True)
        assert add(teacher, "workbook").status_code == 409  # it's a textbook, not a workbook
        assert client.delete(f"/api/planner/curricula/{body['id']}/items/{textbook['id']}").status_code == 200
        as_textbook = add(teacher, "textbook")
        assert as_textbook.status_code == 409 and "For the parent" in as_textbook.json()["detail"]
        assert add(textbook, "textbook").status_code == 200
        assert add(teacher, "teacher").status_code == 200
        assert add(workbook, "workbook").status_code == 200
        assert add(workbook, "workbook").status_code == 409  # already in it
        roles = [i["role"] for i in client.get(f"/api/planner/curricula/{body['id']}").json()["items"]]
        assert roles == ["textbook", "workbook", "teacher"]

    def test_an_unfinished_book_holds_up_scheduling(self, client: TestClient, ada: int) -> None:
        unfinished = _add(client, kind="workbook", title="Spectrum Reading 4")
        body = _curriculum(client, _textbook(client), (unfinished, "workbook"))
        [problem] = body["readiness"]["problems"]
        assert problem["where"] == "Spectrum Reading 4" and "Finish it in your Library" in problem["message"]
        preview = client.post(f"/api/planner/curricula/{body['id']}/schedule/preview",
                              json={"student_ids": [ada], "start_date": MONDAY.isoformat()})
        assert preview.status_code == 409

    def test_removing_an_item_keeps_it_in_the_library(self, client: TestClient) -> None:
        novel = _novel(client)
        body = _curriculum(client, _textbook(client), (novel, "reading"))
        after = client.delete(f"/api/planner/curricula/{body['id']}/items/{novel['id']}").json()
        assert [i["role"] for i in after["items"]] == ["textbook"]
        assert client.get(f"/api/library/{novel['id']}").json()["curriculum_ids"] == []


class TestPacing:
    def _item(self, total: int, chapters: list[int], answer_key: int | None = None):
        return SimpleNamespace(
            total_pages=total, answer_key_start_page=answer_key,
            chapters=[SimpleNamespace(name=f"Ch {i + 1}", start_page=start) for i, start in enumerate(chapters)],
        )

    def test_pages_stay_inside_chapters_and_skip_the_answer_key(self) -> None:
        days = [date(2026, 10, d) for d in (12, 13, 14, 15, 19, 20)]
        plan = page_plan(self._item(120, [1, 51], answer_key=101), days)
        assert [(first, last, name) for _, first, last, name in plan] == [
            (1, 17, "Ch 1"), (18, 34, "Ch 1"), (35, 50, "Ch 1"),
            (51, 67, "Ch 2"), (68, 84, "Ch 2"), (85, 100, "Ch 2"),
        ]

    def test_front_matter_is_skipped_and_tiny_chapters_still_get_a_day(self) -> None:
        days = [date(2026, 10, d) for d in (12, 13, 14, 15)]
        plan = page_plan(self._item(100, [5, 8, 50]), days)
        assert plan[0][1] == 5 and {name for *_, name in plan} == {"Ch 1", "Ch 2", "Ch 3"}

    def test_more_chapters_than_days_shares_days(self) -> None:
        days = [date(2026, 10, 12), date(2026, 10, 13)]
        plan = page_plan(self._item(40, [1, 10, 20, 30]), days)
        assert [(first, last) for _, first, last, _ in plan] == [(1, 20), (21, 40)]

    def test_apportion_and_sessions(self) -> None:
        assert _apportion([50, 50], 6) == [3, 3]
        assert sum(_apportion([300, 20, 5], 10)) == 10 and min(_apportion([300, 20, 5], 10)) >= 1
        days = [date(2026, 10, d) for d in (12, 13, 14, 15, 19, 20, 21)]
        assert _sessions(days, 2) == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 19), date(2026, 10, 20)]

    def test_course_days_skip_days_off(self) -> None:
        days = course_days(MONDAY, [0, 1, 2, 3], {date(2026, 10, 14)}, 4)
        assert days == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 15), date(2026, 10, 19)]


class TestScheduling:
    def _full(self, client: TestClient) -> dict:
        return _curriculum(client, _textbook(client), (_workbook(client), "workbook"), (_online(client), "online"),
                           (_novel(client), "reading"))

    def test_preview_then_schedule(self, client: TestClient, db: Session, ada: int) -> None:
        body = self._full(client)
        request = {"student_ids": [ada], "start_date": MONDAY.isoformat()}
        preview = client.post(f"/api/planner/curricula/{body['id']}/schedule/preview", json=request).json()
        assert preview["weekday_names"] == ["Mon", "Tue", "Wed", "Thu"]  # a 4-day program leaves Friday free
        [kid] = preview["students"]
        assert (kid["finish_date"], kid["lessons"]) == ("2026-10-20", 22)
        assert [(i["role"], i["count"]) for i in kid["items"]] == [
            ("textbook", 6), ("workbook", 6), ("online", 4), ("reading", 6)]
        assert preview["warnings"] == []
        assert db.scalars(select(Assignment)).all() == []  # a preview saves nothing

        result = client.post(f"/api/planner/curricula/{body['id']}/schedule", json=request)
        assert result.status_code == 201
        assert result.json()["lessons_created"] == 22 and "assignments" in result.json()["calendar_url"]
        lessons = db.scalars(select(Assignment).order_by(Assignment.scheduled_date, Assignment.id)).all()
        assert lessons[0].title == "BJU Reading 4 · Lesson 1: Story 1 (pp. 1–2)"
        assert lessons[0].library_lesson_id is not None and lessons[0].course_id is not None
        workbook_titles = [lesson.title for lesson in lessons if "Worktext" in lesson.title]
        assert workbook_titles[0] == "BJU Reading 4 Worktext · pp. 1–17 (Unit 1)"
        assert not any("101" in title for title in workbook_titles)  # never the answer key
        assert client.get(f"/api/planner/curricula/{body['id']}").json()["courses"][0]["lessons_scheduled"] == 22

        again = client.post(f"/api/planner/curricula/{body['id']}/schedule", json=request)
        assert again.status_code == 409
        assert client.delete(f"/api/planner/curricula/{body['id']}").status_code == 409

    def test_days_off_push_lessons_along(self, client: TestClient, db: Session, ada: int) -> None:
        household = get_default_household(db)
        db.add(CalendarException(household_id=household.id, kind=list(ExceptionKind)[0], title="Field trip",
                                 start_date=date(2026, 10, 14), end_date=date(2026, 10, 14)))
        db.add(CalendarException(household_id=household.id, student_id=ada, kind=list(ExceptionKind)[0],
                                 title="Dentist", start_date=date(2026, 10, 19), end_date=date(2026, 10, 19)))
        db.flush()
        body = _curriculum(client, _textbook(client))
        preview = client.post(f"/api/planner/curricula/{body['id']}/schedule/preview",
                              json={"student_ids": [ada], "start_date": MONDAY.isoformat()}).json()
        assert preview["students"][0]["finish_date"] == "2026-10-22"

    def test_finishing_after_the_school_year_warns(self, client: TestClient, ada: int) -> None:
        body = _curriculum(client, _textbook(client, lessons=40))
        preview = client.post(f"/api/planner/curricula/{body['id']}/schedule/preview",
                              json={"student_ids": [ada], "start_date": "2027-05-03"}).json()
        [warning] = preview["warnings"]
        assert "after your school year ends June 4" in warning and "Ada" in warning

    def test_unscheduling_keeps_finished_lessons(self, client: TestClient, db: Session, ada: int) -> None:
        body = _curriculum(client, _textbook(client))
        client.post(f"/api/planner/curricula/{body['id']}/schedule",
                    json={"student_ids": [ada], "start_date": MONDAY.isoformat()})
        first = db.scalars(select(Assignment).order_by(Assignment.scheduled_date)).first()
        first.status = AssignmentStatus.COMPLETED
        first.completion_date = first.scheduled_date
        db.flush()
        course_id = db.scalars(select(Course)).one().id
        result = client.delete(f"/api/planner/courses/{course_id}").json()
        assert result == {"lessons_removed": 5, "lessons_kept": 1}
        assert db.scalars(select(Assignment)).one().course_id is None
        assert client.delete(f"/api/planner/curricula/{body['id']}").status_code == 204


class TestCommunityCurricula:
    def test_a_built_curriculum_helps_the_next_family(self, admin: TestClient, db: Session, as_family) -> None:  # noqa: F811
        textbook, workbook, novel = _textbook(admin), _workbook(admin), _novel(admin)
        mine = _curriculum(admin, textbook, (workbook, "workbook"), (novel, "reading"))
        [shared] = db.scalars(select(CatalogContribution).where(CatalogContribution.kind == "curriculum")).all()
        assert shared.status == "pending" and "items_waiting" in {flag.code for flag in shared.flags}

        early = admin.post(f"/api/admin/community/contributions/{shared.id}/approve", json={})
        assert early.status_code == 409 and "Review its books first" in early.json()["detail"]
        books = db.scalars(select(CatalogContribution).where(CatalogContribution.kind == "item")).all()
        entries = {}
        for book in books:
            entries[book.title] = admin.post(
                f"/api/admin/community/contributions/{book.id}/approve", json={}).json()["entry_id"]
        result = admin.post(f"/api/admin/community/contributions/{shared.id}/approve", json={}).json()
        community_id = result["curriculum_id"]
        assert db.get(CommunityCurriculum, community_id).families_count == 1
        assert admin.get(f"/api/planner/curricula/{mine['id']}").json()["community_curriculum_id"] == community_id

        # The next family adds the same textbook from the catalog...
        with patch("app.services.community.family_of", return_value="next"):
            as_family("next")
            copy = admin.post("/api/library/from-community", json={"entry_id": entries["BJU Reading 4"]}).json()
            suggestions = admin.get("/api/community/suggestions", params={"library_item_id": copy["id"]}).json()
            assert suggestions["message"].startswith("1 family built a curriculum around BJU Reading 4")
            [option] = suggestions["curricula"]
            assert [(i["role"], i["entry"]["title"]) for i in option["items"]] == [
                ("textbook", "BJU Reading 4"), ("workbook", "BJU Reading 4 Worktext"), ("reading", "Charlotte's Web")]
            assert option["items"][0]["library_item_id"] == copy["id"]  # already theirs
            assert [i["entry"]["title"] for i in suggestions["often_used_with"]] == [
                "BJU Reading 4 Worktext", "Charlotte's Web"]

            # ...keeps the textbook and worktext, and picks a different novel.
            theirs = admin.post("/api/planner/curricula/from-community", json={
                "community_curriculum_id": community_id,
                "entry_ids": [entries["BJU Reading 4"], entries["BJU Reading 4 Worktext"]],
            })
            assert theirs.status_code == 201
            body = theirs.json()
            assert [i["item"]["title"] for i in body["items"]] == ["BJU Reading 4", "BJU Reading 4 Worktext"]
            assert body["readiness"]["ready"] is True
            stuart = _novel(admin, title="Stuart Little")
            admin.post(f"/api/planner/curricula/{body['id']}/items",
                       json={"library_item_id": stuart["id"], "role": "reading"})
            as_family("test")
        variant = db.scalars(select(CatalogContribution).where(
            CatalogContribution.kind == "curriculum", CatalogContribution.contributor == "next")).one()
        assert {item["title"] for item in variant.data["items"]} == {
            "BJU Reading 4", "BJU Reading 4 Worktext", "Stuart Little"}

    def test_adopting_it_unchanged_counts_the_family(self, admin: TestClient, db: Session) -> None:  # noqa: F811
        textbook = _textbook(admin)
        _curriculum(admin, textbook, (_novel(admin), "reading"))
        for book in db.scalars(select(CatalogContribution).where(CatalogContribution.kind == "item")).all():
            admin.post(f"/api/admin/community/contributions/{book.id}/approve", json={})
        shared = db.scalars(select(CatalogContribution).where(CatalogContribution.kind == "curriculum")).one()
        community_id = admin.post(f"/api/admin/community/contributions/{shared.id}/approve", json={}).json()["curriculum_id"]
        again = admin.post("/api/planner/curricula/from-community", json={"community_curriculum_id": community_id})
        assert again.status_code == 201
        assert db.get(CommunityCurriculum, community_id).families_count == 2
        open_ones = db.scalars(select(CatalogContribution).where(CatalogContribution.status == "pending")).all()
        assert open_ones == []  # an unchanged copy isn't contributed again
