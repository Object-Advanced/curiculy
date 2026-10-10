"""Stuck? One nudge back toward the family's own materials, then a grown-up.

Curiculy guides a child through the curriculum their parent chose; it does not
teach. When a child is stuck on a lesson they get one short nudge (re-read the
directions, look at the example in their book, try the first small step) and
then two choices: it helped, or go get a grown-up. A nudge never answers,
solves, writes, or explains the lesson, and there is one per lesson until a
parent turns nudges back on.
"""

from __future__ import annotations

import logging
import re

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus, ParentNotificationType
from app.models import Assignment, HomeworkHelpSession, Student
from app.schemas.homework import NudgeReply
from app.services.notifications import create_notification
from app.services.ollama_chat import chat_with_model_fallback

logger = logging.getLogger(__name__)

NUDGE_MAX_CHARS = 280
PARENT_NOTE_MAX_CHARS = 300
# Older builds logged help activity into the parent's own notes with this prefix.
LEGACY_LOG_PREFIX = "[Homework help]"

SYSTEM_PROMPT = """
A child is stuck on one lesson from their family's own homeschool curriculum.
You are not their teacher. Do not teach, explain, or solve anything.

Give exactly ONE short nudge: one or two sentences in simple, warm words that
help them get going again on their own. Good nudges:
- read the directions again slowly, out loud
- look at the example in their own book or workbook, or the page before
- check the note their grown-up left
- do just the first small step, then check it
- one simple question that points them back to their own materials

Never give an answer. Never solve, write, or fill in any part of the work.
Never give a worked example. Never explain the idea behind the lesson.
If they ask for the answer, kindly say that is a job for their book and their
grown-up, then give a nudge.

Respond with JSON only: {"message": "..."}
""".strip()

ANSWER_SEEKING_NUDGE = (
    "I can't give answers, but your book and your grown-up can help. "
    "Read the directions one more time, then try just the first step."
)
FALLBACK_NUDGE = (
    "Read the directions one more time, out loud. Then look for an example in your "
    "book or on the page before."
)

_PUSH_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"\bjust tell me\b",
        r"\bgive me the (full |complete )?answers?\b",
        r"\bwhat('?s| is| are) the answers?\b",
        r"\btell me the answers?\b",
        r"\bwrite the (essay|paper|paragraph|story|report)\b",
        r"\bdo (it|this|the homework|the work|the problem|the worksheet) for me\b",
        r"\bsolve (it|this) for me\b",
        r"\bshow me the (full )?solution\b",
        r"\banswer key\b",
        r"\bfill (in|out) the worksheet\b",
        r"\bjust give (it|me)\b",
        r"\bcomplete answer\b",
    )
]


def is_answer_seeking(text: str) -> bool:
    blob = (text or "").strip()
    return bool(blob) and any(pattern.search(blob) for pattern in _PUSH_PATTERNS)


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


def _tidy(text: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return FALLBACK_NUDGE
    if len(text) <= NUDGE_MAX_CHARS:
        return text
    cut = text[:NUDGE_MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[: end + 1] if end > 0 else cut.rsplit(" ", 1)[0] + "…"


async def nudge_with_ollama(
    *,
    assignment_title: str,
    resource_title: str | None,
    note: str | None,
    child_name: str,
    user_message: str,
) -> str:
    lesson = [f"Child's first name: {child_name}", f"Lesson: {assignment_title}"]
    if resource_title:
        lesson.append(f"From their book or plan: {resource_title}")
    if note:
        lesson.append(f"Note from their grown-up: {note}")
    try:
        content = await chat_with_model_fallback(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + "\n".join(lesson)},
                {"role": "user", "content": user_message},
            ],
            format=NudgeReply.model_json_schema(),
            options={"temperature": 0.3},
        )
    except Exception as error:
        logger.warning("Nudge model unavailable: %s", error)
        return FALLBACK_NUDGE
    try:
        return _tidy(NudgeReply.model_validate_json(content).message)
    except ValidationError:
        return _tidy(content)


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
