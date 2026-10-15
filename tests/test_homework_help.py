"""Stuck? nudges: one nudge per lesson back to the family's materials, then a grown-up.

No AI talks to children (decided 2026-10-13): the nudge is built from the
lesson itself, and the child types nothing.
"""

import inspect
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Assignment, LibraryItem, LibraryLesson, Student
from app.routers import homework_help as homework_router
from app.services import homework_help as homework_service
from app.services.homework_help import FALLBACK_NUDGE, NUDGE_MAX_CHARS, nudge_for
from app.services.households import get_default_household
from tests.test_auth import bearer
from tests.test_kid_auth import _child_token, _parent_ready, _set_pin

pytest_plugins = ["tests.test_auth"]

NOTE = "Parent reminder: use fraction circles."
NOTED_NUDGE = f"{FALLBACK_NUDGE} Your grown-up left a note: “{NOTE}”"


def _assignment(client: TestClient, token: str, student_id: int, title: str = "Fractions p. 42") -> dict:
    return client.post(
        "/api/assignments",
        headers=bearer(token),
        json={
            "student_id": student_id,
            "title": title,
            "scheduled_date": date.today().isoformat(),
            "notes": NOTE,
        },
    ).json()


def _ready(client: TestClient) -> tuple[str, dict, dict, str]:
    token, student = _parent_ready(client)
    _set_pin(client, token, student["id"])
    work = _assignment(client, token, student["id"])
    return token, student, work, _child_token(client, student["id"])


def _start(client: TestClient, child: str, assignment_id: int):
    return client.post("/api/homework-help/sessions", headers=bearer(child), json={"assignment_id": assignment_id})


def _ask(client: TestClient, child: str, session_id: int):
    return client.post(f"/api/homework-help/sessions/{session_id}/nudge", headers=bearer(child))


def _outcome(client: TestClient, token: str, session_id: int, outcome: str):
    return client.post(
        f"/api/homework-help/sessions/{session_id}/outcome",
        headers=bearer(token),
        json={"outcome": outcome},
    )


def _inbox(client: TestClient, token: str) -> list[dict]:
    return client.get("/api/notifications", headers=bearer(token)).json()["notifications"]


def test_one_nudge_then_the_parent_sees_exactly_what_was_said(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    started = _start(auth_client, child, work["id"])
    assert started.status_code == 201
    assert started.json()["status"] == "active"
    assert started.json()["nudged"] is False
    assert _inbox(auth_client, token) == []

    response = _ask(auth_client, child, started.json()["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["nudged"] is True
    assert [(row["role"], row["content"]) for row in body["messages"]] == [
        ("user", "I'm stuck."),
        ("assistant", NOTED_NUDGE),
    ]

    [note] = _inbox(auth_client, token)
    assert note["type"] == "homework_help_started"
    assert note["title"] == "Ada asked for a nudge"
    assert NOTED_NUDGE in note["body"]
    # The parent's own notes are left alone.
    saved = auth_client.get(f"/api/assignments/{work['id']}", headers=bearer(token)).json()
    assert saved["notes"] == NOTE

    second = _ask(auth_client, child, body["id"])
    assert second.status_code == 403
    assert "ask a grown-up" in second.json()["detail"]


def test_parent_cannot_ask_for_a_nudge(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    work = _assignment(auth_client, token, student["id"])
    assert _start(auth_client, token, work["id"]).status_code == 403


def test_helped_uses_up_the_nudge_until_a_parent_allows_another(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    assert _outcome(auth_client, child, session["id"], "helped").status_code == 409  # no nudge yet
    _ask(auth_client, child, session["id"])

    helped = _outcome(auth_client, child, session["id"], "helped")
    assert helped.status_code == 200
    assert helped.json()["status"] == "helped"
    # Coming back to the lesson shows the same, used nudge; no second one.
    again = _start(auth_client, child, work["id"])
    assert again.json()["id"] == session["id"]
    assert _ask(auth_client, child, session["id"]).status_code == 403

    assert auth_client.post(
        f"/api/homework-help/assignments/{work['id']}/unlock", headers=bearer(child)
    ).status_code == 403
    allowed = auth_client.post(f"/api/homework-help/assignments/{work['id']}/unlock", headers=bearer(token))
    assert allowed.status_code == 200
    assert allowed.json()[0]["status"] == "closed"
    fresh = _start(auth_client, child, work["id"])
    assert fresh.status_code == 201
    assert fresh.json()["id"] != session["id"]
    assert fresh.json()["nudged"] is False


def test_still_stuck_sends_them_to_a_grown_up_and_tells_the_parent(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    _ask(auth_client, child, session["id"])

    stuck = _outcome(auth_client, child, session["id"], "ask_grown_up")
    assert stuck.status_code == 200
    body = stuck.json()
    assert body["status"] == "redirected"
    assert body["locked"] is True
    assert body["messages"][-1]["role"] == "system"
    assert "find a grown-up" in body["messages"][-1]["content"]
    titles = [row["title"] for row in _inbox(auth_client, token)]
    assert "Ada needs you" in titles

    assert _start(auth_client, child, work["id"]).status_code == 403
    assert _outcome(auth_client, child, session["id"], "ask_grown_up").status_code == 409


def test_a_child_can_go_straight_to_a_grown_up(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    stuck = _outcome(auth_client, child, session["id"], "ask_grown_up")
    assert stuck.status_code == 200
    assert stuck.json()["nudged"] is False
    assert [row["type"] for row in _inbox(auth_client, token)] == ["homework_help_redirect"]


def test_only_the_child_acts_on_their_own_nudge(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    assert _outcome(auth_client, token, session["id"], "ask_grown_up").status_code == 403
    assert _outcome(auth_client, child, session["id"] + 99, "helped").status_code == 404
    assert _outcome(auth_client, child, session["id"], "solve_it").status_code == 422


def test_mark_notifications_read(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    _ask(auth_client, child, _start(auth_client, child, work["id"]).json()["id"])
    note_id = _inbox(auth_client, token)[0]["id"]
    read = auth_client.post(f"/api/notifications/{note_id}/read", headers=bearer(token))
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    assert auth_client.get("/api/notifications", headers=bearer(token)).json()["unread_count"] == 0
    assert auth_client.get("/api/notifications", headers=bearer(child)).status_code == 403


def test_no_ai_is_reached_from_anything_a_child_does(auth_client: TestClient) -> None:
    """A tripwire on every way the app reaches a model: the whole flow still works."""
    _token, _student, work, child = _ready(auth_client)

    def tripwire(*_args, **_kwargs):
        raise AssertionError("A child's request reached the AI")

    with (
        patch("ollama.AsyncClient", side_effect=tripwire),
        patch("ollama.Client", side_effect=tripwire),
        patch("app.services.ollama_chat.chat_with_model_fallback", side_effect=tripwire),
    ):
        session = _start(auth_client, child, work["id"]).json()
        assert _ask(auth_client, child, session["id"]).status_code == 200
        assert _outcome(auth_client, child, session["id"], "ask_grown_up").status_code == 200
    for module in (homework_router, homework_service):
        assert "ollama" not in inspect.getsource(module).lower()


# --- Where the nudge points ---------------------------------------------------

def _student(db: Session) -> Student:
    student = Student(household_id=get_default_household(db).id, name="Ada Okafor")
    db.add(student)
    db.flush()
    return student


def _lesson(db: Session, student: Student, title: str, **links) -> Assignment:
    lesson = Assignment(student_id=student.id, title=title, scheduled_date=date(2026, 10, 19), **links)
    db.add(lesson)
    db.flush()
    return lesson


def test_a_textbook_lesson_points_to_its_pages(db: Session) -> None:
    book = LibraryItem(kind="textbook", title="Saxon Math 5/4", total_pages=600)
    book.lessons.append(LibraryLesson(position=0, number=12, name="Fractions", start_page=45, end_page=49))
    db.add(book)
    db.flush()
    lesson = _lesson(db, _student(db), "Saxon Math 5/4 · Lesson 12: Fractions (pp. 45–49)",
                     library_item_id=book.id, library_lesson_id=book.lessons[0].id)
    assert nudge_for(db, lesson) == (
        "Open Saxon Math 5/4 to pages 45–49 and read the directions again, out loud. "
        "Look for an example on the page or the page before."
    )


def test_workbook_and_reading_lessons_point_to_their_pages(db: Session) -> None:
    student = _student(db)
    workbook = LibraryItem(kind="workbook", title="Spectrum Math 4", total_pages=160)
    novel = LibraryItem(kind="reading_book", title="Charlotte's Web", total_pages=184)
    db.add_all([workbook, novel])
    db.flush()
    pages = _lesson(db, student, "Spectrum Math 4 · pp. 18–20 (Unit 1)", library_item_id=workbook.id)
    one = _lesson(db, student, "Read Charlotte's Web, p. 41", library_item_id=novel.id)
    assert nudge_for(db, pages).startswith("Open Spectrum Math 4 to pages 18–20 and read the directions")
    assert nudge_for(db, one).startswith("Open Charlotte's Web to page 41 and read")


def test_an_online_lesson_points_back_to_the_site(db: Session) -> None:
    site = LibraryItem(kind="online_program", title="IXL Math", website_url="https://www.ixl.com")
    db.add(site)
    db.flush()
    lesson = _lesson(db, _student(db), "IXL Math · 20 minutes", library_item_id=site.id)
    assert nudge_for(db, lesson) == "Go back to IXL Math and look at its example or hint, then try the first one again."


def test_older_lessons_use_their_book_title_and_the_parents_note(db: Session) -> None:
    student = _student(db)
    lesson = _lesson(db, student, "Fractions worksheet", notes="Use the blue workbook.\n[Homework help] old log line")
    assert nudge_for(db, lesson, resource_title="Saxon Math 5/4") == (
        "Look in Saxon Math 5/4 and read the directions again, out loud. Look for an example on the page "
        "or the page before. Your grown-up left a note: “Use the blue workbook.”"
    )
    bare = _lesson(db, student, "Free writing")
    assert nudge_for(db, bare) == FALLBACK_NUDGE


def test_a_long_note_is_trimmed_to_fit_a_nudge(db: Session) -> None:
    lesson = _lesson(db, _student(db), "Essay", notes="Remember the outline we made together. " * 10)
    nudge = nudge_for(db, lesson)
    assert len(nudge) <= NUDGE_MAX_CHARS
    assert nudge.startswith(FALLBACK_NUDGE) and nudge.endswith("…”")
