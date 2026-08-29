"""Guarded homework tutor: hints and examples, never complete answers."""

from __future__ import annotations

import logging
from re import IGNORECASE
from re import compile as regexp

import ollama
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import (
    HomeworkHelpMessageRole,
    HomeworkHelpStatus,
    ParentNotificationType,
)
from app.models import Assignment, HomeworkHelpMessage, HomeworkHelpSession, Student
from app.models.mixins import utcnow
from app.schemas.homework import TutorReply
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)

PUSH_LIMIT = 3
OLLAMA_FALLBACK_MODEL = "mistral"

SYSTEM_PROMPT = """
You are a homeschool homework tutor for a child. Your only job is to help them
learn by demonstrating a SIMILAR example (different numbers, names, or facts)
and by asking guiding questions.

Strict rules:
- Never give the answer to the assigned problem, question, prompt, or worksheet.
- Never write the essay, paragraph, story, lab report, or completed worksheet.
- Never list step-by-step solutions for the exact assigned work.
- If they ask for the answer, refuse briefly and offer a different example or a hint.
- Keep language warm, short, and age-appropriate.
- If they keep demanding the complete answer after you have already refused, set
  redirect to true and tell them to ask a parent.

Respond with JSON only:
{"mode": "hint" | "example" | "socratic" | "redirect", "message": "...", "redirect": false}
""".strip()

_PUSH_PATTERNS = [
    regexp(r"\bjust tell me\b", flags=IGNORECASE),
    regexp(r"\bgive me the (full |complete )?answer\b", flags=IGNORECASE),
    regexp(r"\bwhat('?s| is) the answer\b", flags=IGNORECASE),
    regexp(r"\btell me the answer\b", flags=IGNORECASE),
    regexp(r"\bwrite the (essay|paper|paragraph|story|report)\b", flags=IGNORECASE),
    regexp(r"\bdo (it|this|the homework|the work|the problem|the worksheet) for me\b", flags=IGNORECASE),
    regexp(r"\bsolve (it|this) for me\b", flags=IGNORECASE),
    regexp(r"\bshow me the (full )?solution\b", flags=IGNORECASE),
    regexp(r"\banswer key\b", flags=IGNORECASE),
    regexp(r"\bfill (in|out) the worksheet\b", flags=IGNORECASE),
    regexp(r"\bi (don't|do not) care\b", flags=IGNORECASE),
    regexp(r"\bjust give (it|me)\b", flags=IGNORECASE),
    regexp(r"\bcomplete answer\b", flags=IGNORECASE),
]


def is_answer_seeking(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return False
    return any(pattern.search(blob) for pattern in _PUSH_PATTERNS)


def assignment_is_locked(db: Session, assignment_id: int) -> bool:
    session = (
        db.query(HomeworkHelpSession)
        .filter(
            HomeworkHelpSession.assignment_id == assignment_id,
            HomeworkHelpSession.status == HomeworkHelpStatus.REDIRECTED,
        )
        .order_by(HomeworkHelpSession.id.desc())
        .first()
    )
    return session is not None


def append_assignment_note(assignment: Assignment, line: str) -> None:
    stamp = utcnow().strftime("%Y-%m-%d")
    entry = f"[Homework help] {stamp} — {line}"
    if assignment.notes and assignment.notes.strip():
        assignment.notes = assignment.notes.rstrip() + "\n\n" + entry
    else:
        assignment.notes = entry


def _message_content(response: object) -> str:
    try:
        return response["message"]["content"]
    except (TypeError, KeyError, AttributeError):
        return response.message.content


def _is_missing_model(error: BaseException) -> bool:
    text = str(error).lower()
    return "not found" in text or "does not exist" in text or "404" in text


async def tutor_with_ollama(
    *,
    assignment_title: str,
    student_name: str,
    history: list[HomeworkHelpMessage],
    user_message: str,
) -> TutorReply:
    transcript = []
    for item in history[-12:]:
        role = "user" if item.role == HomeworkHelpMessageRole.USER else "assistant"
        transcript.append({"role": role, "content": item.content})
    transcript.append({"role": "user", "content": user_message})
    prompt = (
        f"Student: {student_name}\n"
        f"Assignment: {assignment_title}\n"
        "Help with this assignment without giving the complete answer."
    )
    client = ollama.AsyncClient(host=settings.ollama_host)
    models = [settings.ollama_model]
    if settings.ollama_model != OLLAMA_FALLBACK_MODEL:
        models.append(OLLAMA_FALLBACK_MODEL)

    last_error: BaseException | None = None
    for model in models:
        try:
            response = await client.chat(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + prompt}, *transcript],
                format=TutorReply.model_json_schema(),
                options={"temperature": 0.3},
            )
            return TutorReply.model_validate_json(_message_content(response))
        except ValidationError:
            raw = _message_content(response)
            return TutorReply(mode="hint", message=raw.strip() or _fallback_hint(), redirect=False)
        except Exception as error:
            last_error = error
            if not _is_missing_model(error):
                logger.warning("Homework tutor failed: %s", error)
                break
            logger.warning("Ollama model %s is unavailable; trying fallback", model)

    if last_error is not None:
        logger.warning("Homework tutor unavailable: %s", last_error)
    return TutorReply(mode="hint", message=_fallback_hint(), redirect=False)


def _fallback_hint() -> str:
    return (
        "I can't reach the tutor right now. Try a similar example with different "
        "numbers or details, then come back to this assignment. Ask a parent if you're stuck."
    )


def session_to_locked_flag(session: HomeworkHelpSession) -> bool:
    return session.status == HomeworkHelpStatus.REDIRECTED


def notify_help_started(db: Session, student: Student, assignment: Assignment) -> None:
    name = student.name
    create_notification(
        db,
        type=ParentNotificationType.HOMEWORK_HELP_STARTED,
        student_id=student.id,
        assignment_id=assignment.id,
        title=f"{name} used homework help",
        body=f"{name} asked for help on “{assignment.title}”.",
    )


def notify_help_redirect(db: Session, student: Student, assignment: Assignment) -> None:
    name = student.name
    create_notification(
        db,
        type=ParentNotificationType.HOMEWORK_HELP_REDIRECT,
        student_id=student.id,
        assignment_id=assignment.id,
        title=f"{name} needs you",
        body=(
            f"{name} kept asking for the complete answer on “{assignment.title}”. "
            "Homework help was stopped. They were told to come to you."
        ),
    )


def unlock_assignment(db: Session, assignment_id: int) -> int:
    rows = (
        db.query(HomeworkHelpSession)
        .filter(
            HomeworkHelpSession.assignment_id == assignment_id,
            HomeworkHelpSession.status == HomeworkHelpStatus.REDIRECTED,
        )
        .all()
    )
    for row in rows:
        row.status = HomeworkHelpStatus.CLOSED
    return len(rows)
