"""Background PDF → lesson pipeline for structured pacing guides.

The HTTP handler only creates the ``CurriculumPlan`` row (status ``processing``)
and queues this worker with the tenant identity (not a request Session).
The worker opens, commits or rolls back, and closes its own tenant session.
Text extraction is local; Ollama turns that text into ``AIParsedCurriculum``.
On success the plan is marked ``ready``; extraction, validation, or empty
output marks it ``failed``.
"""

from __future__ import annotations

import logging

import ollama
from sqlalchemy.orm import Session

from app.config import settings
from app.db import open_tenant_session
from app.enums import CurriculumPlanStatus
from app.models import CurriculumLesson, CurriculumPlan
from app.schemas.curriculum_plans import AIParsedCurriculum, AIParsedLesson
from app.services.curriculum_plan_import import plan_dimensions_from_rows
from app.services.pdf_parser import extract_text_from_pdf, is_sparse_curriculum_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert data entry assistant for a homeschool curriculum app.
Your job is to extract the lesson plan schedule from the provided text and output it STRICTLY as JSON.
Do not invent or guess any assignments. If a description is missing, leave it null.
Copy unit titles, week numbers, day numbers, titles, time slots, and page ranges from the source text only.

Classify each PDF as one of two types before you extract:

Type A (Multi-Week Pacing Guide): The text names weeks and days ("Week 1, Day 1"), chapters, lessons, or page numbers across many weeks. Emit one row per dated assignment. Do not copy a day onto other days.

Type B (Daily Routine / Block Schedule): The text is a single typical day — times and subjects such as 8:30-9:00 Bible, 9:00-9:45 Phonics — with no week numbers. Emit every subject block, then replicate that same ordered stack across Week 1 Days 1 through 5 (or the plan's school-day frequency if the text states a different number of days). Put clock times in time_slot. Put the subject name in title and subject. Mark Lunch, Recess, Snack, Rest, and similar breaks as category "Routine/Break". Mark academic blocks as category "Daily Work".

A phrase such as "36 weeks" or "36-week program" is year-length metadata, not a lesson grid. Do not invent Week 1 through Week 36 rows, empty days, or placeholder titles like "Week 1" or "Day 1". If the text has no daily assignments, subjects, times, or page numbers, return {"lessons": []}.

EXAMPLE 1 (Type A Input):
Week 1 - Early America
Day 1: Read Chapter 1 (Pages 4-10)
Day 2: Complete Worksheet A

EXAMPLE 1 (Type A Output):
{
  "lessons": [
    {"unit_title": "Early America", "week_number": 1, "day_number": 1, "title": "Read Chapter 1", "description": null, "pages": "4-10", "time_slot": null, "category": "Daily Work", "subject": null},
    {"unit_title": "Early America", "week_number": 1, "day_number": 2, "title": "Complete Worksheet A", "description": null, "pages": null, "time_slot": null, "category": "Daily Work", "subject": null}
  ]
}

EXAMPLE 2 (Type A Input):
Unit: Fractions
Week 3 Day 1 — Introduce mixed numbers, p. 42-45. Notes: use fraction circles.

EXAMPLE 2 (Type A Output):
{
  "lessons": [
    {"unit_title": "Fractions", "week_number": 3, "day_number": 1, "title": "Introduce mixed numbers", "description": "use fraction circles", "pages": "42-45", "time_slot": null, "category": "Daily Work", "subject": null}
  ]
}

EXAMPLE 3 (Type B Input):
Daily Schedule
8:30-9:00  Bible
9:00-9:45  Phonics
12:00-12:30 Lunch

EXAMPLE 3 (Type B Output):
Replicate the timetable across Week 1, Days 1-5. Day 1 is shown in full; Days 2-5 repeat the same three blocks with the same time_slot, title, subject, and category values and day_number set to 2, 3, 4, then 5.
{
  "lessons": [
    {"unit_title": null, "week_number": 1, "day_number": 1, "title": "Bible", "description": null, "pages": null, "time_slot": "8:30-9:00", "category": "Daily Work", "subject": "Bible"},
    {"unit_title": null, "week_number": 1, "day_number": 1, "title": "Phonics", "description": null, "pages": null, "time_slot": "9:00-9:45", "category": "Daily Work", "subject": "Phonics"},
    {"unit_title": null, "week_number": 1, "day_number": 1, "title": "Lunch", "description": null, "pages": null, "time_slot": "12:00-12:30", "category": "Routine/Break", "subject": "Lunch"},
    {"unit_title": null, "week_number": 1, "day_number": 2, "title": "Bible", "description": null, "pages": null, "time_slot": "8:30-9:00", "category": "Daily Work", "subject": "Bible"},
    {"unit_title": null, "week_number": 1, "day_number": 2, "title": "Phonics", "description": null, "pages": null, "time_slot": "9:00-9:45", "category": "Daily Work", "subject": "Phonics"},
    {"unit_title": null, "week_number": 1, "day_number": 2, "title": "Lunch", "description": null, "pages": null, "time_slot": "12:00-12:30", "category": "Routine/Break", "subject": "Lunch"},
    {"unit_title": null, "week_number": 1, "day_number": 3, "title": "Bible", "description": null, "pages": null, "time_slot": "8:30-9:00", "category": "Daily Work", "subject": "Bible"},
    {"unit_title": null, "week_number": 1, "day_number": 3, "title": "Phonics", "description": null, "pages": null, "time_slot": "9:00-9:45", "category": "Daily Work", "subject": "Phonics"},
    {"unit_title": null, "week_number": 1, "day_number": 3, "title": "Lunch", "description": null, "pages": null, "time_slot": "12:00-12:30", "category": "Routine/Break", "subject": "Lunch"},
    {"unit_title": null, "week_number": 1, "day_number": 4, "title": "Bible", "description": null, "pages": null, "time_slot": "8:30-9:00", "category": "Daily Work", "subject": "Bible"},
    {"unit_title": null, "week_number": 1, "day_number": 4, "title": "Phonics", "description": null, "pages": null, "time_slot": "9:00-9:45", "category": "Daily Work", "subject": "Phonics"},
    {"unit_title": null, "week_number": 1, "day_number": 4, "title": "Lunch", "description": null, "pages": null, "time_slot": "12:00-12:30", "category": "Routine/Break", "subject": "Lunch"},
    {"unit_title": null, "week_number": 1, "day_number": 5, "title": "Bible", "description": null, "pages": null, "time_slot": "8:30-9:00", "category": "Daily Work", "subject": "Bible"},
    {"unit_title": null, "week_number": 1, "day_number": 5, "title": "Phonics", "description": null, "pages": null, "time_slot": "9:00-9:45", "category": "Daily Work", "subject": "Phonics"},
    {"unit_title": null, "week_number": 1, "day_number": 5, "title": "Lunch", "description": null, "pages": null, "time_slot": "12:00-12:30", "category": "Routine/Break", "subject": "Lunch"}
  ]
}
""".strip()

OLLAMA_FALLBACK_MODEL = "mistral"


def _message_content(response: object) -> str:
    """Read chat content from a dict response or an ollama ChatResponse."""
    try:
        return response["message"]["content"]
    except (TypeError, KeyError, AttributeError):
        return response.message.content


def _is_missing_model(error: BaseException) -> bool:
    text = str(error).lower()
    return "not found" in text or "does not exist" in text or "404" in text


async def parse_text_with_ollama(raw_text: str) -> AIParsedCurriculum:
    """Ask the local model to turn PDF text into ``AIParsedCurriculum``."""
    if is_sparse_curriculum_text(raw_text):
        return AIParsedCurriculum(lessons=[])

    client = ollama.AsyncClient(host=settings.ollama_host)
    models = [settings.ollama_model]
    if settings.ollama_model != OLLAMA_FALLBACK_MODEL:
        models.append(OLLAMA_FALLBACK_MODEL)

    last_error: BaseException | None = None
    for model in models:
        try:
            response = await client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                format=AIParsedCurriculum.model_json_schema(),
                options={"temperature": 0.0},
            )
            return AIParsedCurriculum.model_validate_json(_message_content(response))
        except Exception as error:
            last_error = error
            if not _is_missing_model(error):
                raise
            logger.warning("Ollama model %s is unavailable; trying fallback", model)

    assert last_error is not None
    raise last_error


def _mark_plan_status(
    db_session: Session, plan_id: int, status: CurriculumPlanStatus
) -> None:
    plan = db_session.get(CurriculumPlan, plan_id)
    if plan is None:
        return
    plan.status = status
    db_session.commit()


def _lesson_row(plan_id: int, lesson: AIParsedLesson) -> CurriculumLesson:
    title = lesson.title.strip()[:255]
    unit_title = (lesson.unit_title or lesson.subject or "").strip()[:255] or None
    description = (lesson.description or "").strip() or None
    pages = (lesson.pages or "").strip()[:64] or None
    category = (lesson.category or "").strip()[:64] or None
    time_slot = (lesson.time_slot or "").strip()[:64] or None
    return CurriculumLesson(
        plan_id=plan_id,
        unit_title=unit_title,
        week_number=lesson.week_number,
        day_number=lesson.day_number,
        title=title,
        description=description,
        pages=pages,
        category=category,
        time_slot=time_slot,
    )


def _mark_plan_failed(tenant_uuid: str, demo_key: str | None, plan_id: int) -> None:
    """Write ``failed`` on a fresh session so a poisoned worker session cannot block it."""
    session = open_tenant_session(tenant_uuid, demo_key)
    try:
        _mark_plan_status(session, plan_id, CurriculumPlanStatus.FAILED)
    except Exception:
        logger.exception("Could not mark curriculum plan %s as failed", plan_id)
    finally:
        session.close()


def _persist_parsed_plan(
    db_session: Session, plan_id: int, parsed_curriculum: AIParsedCurriculum
) -> None:
    plan = db_session.get(CurriculumPlan, plan_id)
    if plan is None:
        logger.warning(
            "Curriculum plan %s disappeared before lessons were saved", plan_id
        )
        return

    rows = [
        _lesson_row(plan_id, lesson)
        for lesson in parsed_curriculum.lessons
        if lesson.title and lesson.title.strip()
    ]
    if not rows:
        plan.status = CurriculumPlanStatus.FAILED
        plan.total_weeks = 1
        db_session.commit()
        return

    db_session.add_all(rows)
    frequency_days, total_weeks = plan_dimensions_from_rows(
        [
            {
                "week_number": lesson.week_number,
                "day_number": lesson.day_number,
            }
            for lesson in rows
        ]
    )
    plan.frequency_days = frequency_days
    plan.total_weeks = total_weeks
    plan.status = CurriculumPlanStatus.READY
    db_session.commit()


async def process_pdf_curriculum_background(
    plan_id: int,
    file_bytes: bytes,
    tenant_uuid: str,
    demo_key: str | None = None,
) -> None:
    """Extract PDF text, parse it with Ollama, and bulk-insert lessons.

    Opens a tenant session for this job. Does not use the request Session.
    """
    failed = False
    db_session = open_tenant_session(tenant_uuid, demo_key)
    try:
        try:
            raw_text = extract_text_from_pdf(file_bytes)
            logger.info(
                "Extracted %s characters from curriculum PDF for plan %s",
                len(raw_text),
                plan_id,
            )
            parsed_curriculum = await parse_text_with_ollama(raw_text)
            _persist_parsed_plan(db_session, plan_id, parsed_curriculum)
        except Exception:
            failed = True
            logger.exception("PDF curriculum processing failed for plan %s", plan_id)
            try:
                db_session.rollback()
            except Exception:
                logger.exception(
                    "Could not roll back after curriculum plan %s failed", plan_id
                )
    finally:
        db_session.close()
    if failed:
        _mark_plan_failed(tenant_uuid, demo_key, plan_id)
