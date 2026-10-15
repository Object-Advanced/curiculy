"""Stuck? One nudge back toward the family's own materials, then a grown-up.

Curiculy guides a child through the curriculum their parent chose; it does not
teach, and **no AI talks to children** (decided 2026-10-13). When a child is
stuck on a lesson they tap Stuck? and get one short nudge, built from the
lesson itself: the book and pages to open ("Open BJU Reading 4 to pages
45–49 and read the directions again, out loud"), and the note their grown-up
left. Then two choices: it helped, or go get a grown-up (which tells the
parent). There is one nudge per lesson until a parent turns nudges back on.
The child types nothing, so nothing they write is collected.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus, ParentNotificationType
from app.models import Assignment, HomeworkHelpSession, LibraryItem, LibraryLesson, Student
from app.services.notifications import create_notification

NUDGE_MAX_CHARS = 280
PARENT_NOTE_MAX_CHARS = 300
# Older builds logged help activity into the parent's own notes with this prefix.
LEGACY_LOG_PREFIX = "[Homework help]"
# What the child "says" in the thread the parent sees: they tapped Stuck?.
STUCK_MESSAGE = "I'm stuck."
FALLBACK_NUDGE = (
    "Read the directions one more time, out loud. Then look for an example in your "
    "book or on the page before."
)
# The Curriculum planner writes pages into workbook and reading lessons' titles.
_PAGES_IN_TITLE = re.compile(r"\bpp?\. (\d+)(?:–(\d+))?")


def has_nudge(session: HomeworkHelpSession) -> bool:
    return any(item.role == HomeworkHelpMessageRole.ASSISTANT for item in session.messages)


def parent_note(assignment: Assignment) -> str | None:
    """The parent's own note on the lesson, without older help-log lines."""
    lines = [
        line.strip()
        for line in (assignment.notes or "").splitlines()
        if line.strip() and not line.strip().startswith(LEGACY_LOG_PREFIX)
    ]
    text = " ".join(lines)
    return text[:PARENT_NOTE_MAX_CHARS] or None


def first_name(name: str | None) -> str:
    return (name or "").strip().split(" ")[0] or "Your child"


def _pages(first: int, last: int | None) -> str:
    return f"page {first}" if last in (None, first) else f"pages {first}–{last}"


def where_to_look(db: Session, assignment: Assignment, resource_title: str | None = None) -> tuple[str | None, bool]:
    """(what to open, whether it's a website), most specific first."""
    if assignment.library_lesson_id:
        lesson = db.get(LibraryLesson, assignment.library_lesson_id)
        book = db.get(LibraryItem, lesson.item_id) if lesson else None
        if book is not None:
            if lesson.start_page:
                return f"Open {book.title} to {_pages(lesson.start_page, lesson.end_page)}", False
            return f"Open {book.title} to today's lesson", False
    if assignment.library_item_id:
        book = db.get(LibraryItem, assignment.library_item_id)
        if book is not None:
            if book.kind == "online_program":
                return f"Go back to {book.title}", True
            match = _PAGES_IN_TITLE.search(assignment.title or "")
            if match:
                first, last = int(match.group(1)), int(match.group(2)) if match.group(2) else None
                return f"Open {book.title} to {_pages(first, last)}", False
            return f"Open {book.title} to today's pages", False
    if resource_title:
        return f"Look in {resource_title}", False
    return None, False


def nudge_for(db: Session, assignment: Assignment, resource_title: str | None = None) -> str:
    """One short nudge back to the family's own materials. Never an answer."""
    place, online = where_to_look(db, assignment, resource_title)
    if place and online:
        nudge = f"{place} and look at its example or hint, then try the first one again."
    elif place:
        nudge = f"{place} and read the directions again, out loud. Look for an example on the page or the page before."
    else:
        nudge = FALLBACK_NUDGE
    note = parent_note(assignment)
    if note:
        room = NUDGE_MAX_CHARS - len(nudge) - len(" Your grown-up left a note: “”")
        if room >= 20:
            if len(note) > room:
                note = note[: room - 1].rsplit(" ", 1)[0] + "…"
            nudge += f" Your grown-up left a note: “{note}”"
    return nudge


def latest_session(db: Session, assignment_id: int, student_id: int) -> HomeworkHelpSession | None:
    return (
        db.query(HomeworkHelpSession)
        .filter(
            HomeworkHelpSession.assignment_id == assignment_id,
            HomeworkHelpSession.student_id == student_id,
        )
        .order_by(HomeworkHelpSession.id.desc())
        .first()
    )


def notify_nudge(db: Session, student: Student, assignment: Assignment, nudge: str) -> None:
    name = first_name(student.name)
    create_notification(
        db,
        type=ParentNotificationType.HOMEWORK_HELP_STARTED,
        student_id=student.id,
        assignment_id=assignment.id,
        title=f"{name} asked for a nudge",
        body=f"{name} got stuck on “{assignment.title}” and was told: “{nudge}”",
    )


def notify_grown_up(db: Session, student: Student, assignment: Assignment) -> None:
    name = first_name(student.name)
    create_notification(
        db,
        type=ParentNotificationType.HOMEWORK_HELP_REDIRECT,
        student_id=student.id,
        assignment_id=assignment.id,
        title=f"{name} needs you",
        body=f"{name} is stuck on “{assignment.title}” and is coming to find you.",
    )


def allow_another_nudge(db: Session, assignment_id: int) -> int:
    rows = (
        db.query(HomeworkHelpSession)
        .filter(
            HomeworkHelpSession.assignment_id == assignment_id,
            HomeworkHelpSession.status.in_([HomeworkHelpStatus.REDIRECTED, HomeworkHelpStatus.HELPED]),
        )
        .all()
    )
    for row in rows:
        row.status = HomeworkHelpStatus.CLOSED
    return len(rows)
