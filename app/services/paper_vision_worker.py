"""Background handwriting OCR for photographed week sheets.

OpenCV slicing happens on the request. This worker reads each cell crop
sequentially through Ollama vision (one VRAM-resident request at a time),
then writes ``CurriculumLesson`` rows on its own tenant session.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db import open_tenant_session
from app.enums import CurriculumPlanStatus
from app.models import CurriculumLesson, CurriculumPlan
from app.services.curriculum_plan_import import plan_dimensions_from_rows

logger = logging.getLogger(__name__)

OLLAMA_VISION_MODEL = "llama3.2-vision"
VISION_PROMPT = (
    "Read the handwriting in this image. Return only a JSON object following "
    'this format: {"text": "the handwritten text"}. If it is blank or only '
    "contains printed hints like 'time' or 'lesson', return {\"text\": \"\"}."
)
_PRINTED_HINTS = frozenset({"time", "lesson", "week", "monday", "tuesday",
                            "wednesday", "thursday", "friday"})
_WEEK_NUMBER_RE = re.compile(r"\d+")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_handwriting_from_slices(
    slices: dict,
    plan_id: int,
    tenant_uuid: str,
    jti: str | None = None,
) -> None:
    """Read cell crops with Ollama and insert lessons. Owns its tenant session."""
    failed = False
    db_session = open_tenant_session(tenant_uuid, jti)
    try:
        try:
            lessons = _lessons_from_slices(slices, plan_id)
            _persist_lessons(db_session, plan_id, lessons)
        except Exception:
            failed = True
            logger.exception("Paper vision failed for plan %s", plan_id)
            try:
                db_session.rollback()
            except Exception:
                logger.exception(
                    "Could not roll back after paper plan %s failed", plan_id
                )
    finally:
        db_session.close()
    if failed:
        _mark_plan_failed(tenant_uuid, jti, plan_id)


def _ollama_chat_url() -> str:
    return f"{settings.ollama_host.rstrip('/')}/api/chat"


def _bare_b64(payload: str) -> str:
    if payload.startswith("data:") and "," in payload:
        return payload.split(",", 1)[1]
    return payload


def _read_handwriting(image_b64: str) -> str:
    """One synchronous vision call. Never overlap these on an 8GB GPU."""
    response = httpx.post(
        _ollama_chat_url(),
        json={
            "model": OLLAMA_VISION_MODEL,
            "format": "json",
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": VISION_PROMPT,
                    "images": [_bare_b64(image_b64)],
                }
            ],
        },
        timeout=120.0,
    )
    response.raise_for_status()
    body = response.json()
    try:
        content = body["message"]["content"]
    except (TypeError, KeyError) as exc:
        raise ValueError("Ollama vision response was missing message content") from exc
    return _parse_text(content)


def _parse_text(content: str) -> str:
    raw = _FENCE_RE.sub("", (content or "").strip())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    text = str(payload.get("text") or "").strip()
    if text.lower() in _PRINTED_HINTS:
        return ""
    return text


def _parse_week_number(text: str) -> int:
    match = _WEEK_NUMBER_RE.search(text)
    if match is None:
        return 1
    value = int(match.group())
    if 1 <= value <= 52:
        return value
    return 1


def _lessons_from_slices(slices: dict, plan_id: int) -> list[CurriculumLesson]:
    week = _parse_week_number(_read_handwriting(slices["week_number_image"]))
    lessons: list[CurriculumLesson] = []
    for row in slices["rows"]:
        time_text = _read_handwriting(row["time_image"]).strip()[:64] or None
        for day_index, day_image in enumerate(row["days"], start=1):
            title = _read_handwriting(day_image).strip()[:255]
            if not title:
                continue
            lessons.append(
                CurriculumLesson(
                    plan_id=plan_id,
                    week_number=week,
                    day_number=day_index,
                    title=title,
                    time_slot=time_text,
                )
            )
    return lessons


def _persist_lessons(
    db_session: Session, plan_id: int, lessons: list[CurriculumLesson]
) -> None:
    plan = db_session.get(CurriculumPlan, plan_id)
    if plan is None:
        logger.warning("Curriculum plan %s disappeared before paper lessons were saved", plan_id)
        return
    if lessons:
        db_session.add_all(lessons)
        frequency_days, total_weeks = plan_dimensions_from_rows(
            [
                {
                    "week_number": lesson.week_number,
                    "day_number": lesson.day_number,
                }
                for lesson in lessons
            ]
        )
        plan.frequency_days = frequency_days
        plan.total_weeks = total_weeks
    plan.status = CurriculumPlanStatus.READY
    db_session.commit()


def _mark_plan_status(
    db_session: Session, plan_id: int, status: CurriculumPlanStatus
) -> None:
    plan = db_session.get(CurriculumPlan, plan_id)
    if plan is None:
        return
    plan.status = status
    db_session.commit()


def _mark_plan_failed(tenant_uuid: str, jti: str | None, plan_id: int) -> None:
    session = open_tenant_session(tenant_uuid, jti)
    try:
        _mark_plan_status(session, plan_id, CurriculumPlanStatus.FAILED)
    except Exception:
        logger.exception("Could not mark curriculum plan %s as failed", plan_id)
    finally:
        session.close()
