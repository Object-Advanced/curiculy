"""Import a structured pacing guide from a flat CSV.

The spreadsheet is a day-by-day guide — Unit, Week, Day, Title — not the nested
program tree ``curriculum_import`` writes for Auto-schedule. One file becomes one
``CurriculumPlan`` plus its lessons; a bad row rejects the whole upload so the
catalog never shows a half-imported guide.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import CurriculumLesson, CurriculumPlan
from app.schemas.curriculum_plans import (
    extract_time_slot,
    normalize_lesson_category,
    split_title_time_slot,
)

CSV_COLUMNS: dict[str, tuple[str, ...]] = {
    "unit_title": ("unit", "unit_title", "chapter"),
    "week_number": ("week", "week_number"),
    "day_number": ("day", "day_number"),
    "title": ("title", "lesson", "lesson_title"),
    "description": ("description", "desc", "notes"),
    "pages": ("pages", "page", "page_range"),
    "time_slot": ("time_slot", "time", "timeslot", "period"),
    "category": ("category", "type"),
}

_ALIAS_TO_COLUMN = {
    alias: column for column, aliases in CSV_COLUMNS.items() for alias in aliases
}

DEFAULT_PLAN_TITLE = "Imported curriculum"


class CurriculumPlanImportError(ValueError):
    """The CSV could not be imported; nothing was written."""


def plan_title_from_filename(filename: str | None) -> str:
    """Use the uploaded file's stem as a temporary plan title."""
    stem = Path(filename or "").stem.strip()
    return stem or DEFAULT_PLAN_TITLE


def _normalize_header(name: str) -> str:
    return " ".join(name.strip().lower().replace("-", " ").split()).replace(" ", "_")


def _map_headers(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise CurriculumPlanImportError("the CSV payload is empty")
    columns: dict[str, str] = {}
    for original in fieldnames:
        if original is None or not str(original).strip():
            continue
        alias = _normalize_header(str(original))
        column = _ALIAS_TO_COLUMN.get(alias)
        if column and column not in columns:
            columns[column] = original
    if "title" not in columns:
        raise CurriculumPlanImportError("the CSV is missing a Title column")
    return columns


def _cell(row: dict[str, str | None], original: str | None) -> str:
    if original is None:
        return ""
    value = row.get(original)
    return "" if value is None else str(value).strip()


def _optional_int(value: str, field: str, row_number: int) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise CurriculumPlanImportError(
            f"row {row_number}: {field} must be a whole number"
        ) from error


def _blank_row(row: dict[str, str | None]) -> bool:
    return not any((value or "").strip() for value in row.values() if value is not None)


def parse_pacing_csv(text: str) -> list[dict[str, object]]:
    """Turn a pacing-guide spreadsheet into lesson dicts ready to insert."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    columns = _map_headers(list(reader.fieldnames) if reader.fieldnames else None)

    lessons: list[dict[str, object]] = []
    data_index = 0
    for raw_row_number, row in enumerate(reader, start=2):
        if _blank_row(row):
            continue
        data_index += 1
        title = _cell(row, columns["title"])
        if not title:
            raise CurriculumPlanImportError(f"row {raw_row_number}: Title is required")
        day_number = _optional_int(
            _cell(row, columns.get("day_number")), "Day", raw_row_number
        )
        week_number = _optional_int(
            _cell(row, columns.get("week_number")), "Week", raw_row_number
        )
        unit_title = _cell(row, columns.get("unit_title")) or None
        description = _cell(row, columns.get("description")) or None
        pages = _cell(row, columns.get("pages")) or None
        title_text, title_slot = split_title_time_slot(title)
        time_slot = (
            _cell(row, columns.get("time_slot"))
            or title_slot
            or extract_time_slot(description)
            or None
        )
        category = normalize_lesson_category(
            title_text,
            _cell(row, columns.get("category")) or None,
        )
        lessons.append(
            {
                "unit_title": unit_title,
                "week_number": week_number,
                "day_number": day_number if day_number is not None else data_index,
                "title": title_text[:255],
                "description": description,
                "pages": (pages[:64] if pages else None),
                "time_slot": (time_slot[:64] if time_slot else None),
                "category": category,
            }
        )

    if not lessons:
        raise CurriculumPlanImportError("the CSV has no lesson rows")
    return lessons


def plan_dimensions_from_rows(rows: list[dict[str, object]]) -> tuple[int, int]:
    """Infer ``frequency_days`` and ``total_weeks`` from imported lesson slots."""
    weeks = [
        int(row["week_number"])
        for row in rows
        if row.get("week_number") is not None
    ]
    days = [int(row["day_number"]) for row in rows if row.get("day_number") is not None]
    frequency_days = max(days) if days else 5
    total_weeks = max(weeks) if weeks else 1
    return max(1, min(7, frequency_days)), max(1, min(52, total_weeks))


def import_pacing_csv(db: Session, text: str, filename: str | None) -> CurriculumPlan:
    """Parse the CSV, then write one plan and its lessons in a single commit."""
    rows = parse_pacing_csv(text)
    frequency_days, total_weeks = plan_dimensions_from_rows(rows)
    plan = CurriculumPlan(
        title=plan_title_from_filename(filename)[:255],
        frequency_days=frequency_days,
        total_weeks=total_weeks,
    )
    db.add(plan)
    db.flush()
    db.add_all(
        [
            CurriculumLesson(
                plan_id=plan.id,
                unit_title=row["unit_title"],
                week_number=row["week_number"],
                day_number=row["day_number"],
                title=row["title"],
                description=row["description"],
                pages=row["pages"],
                time_slot=row["time_slot"],
                category=row["category"],
            )
            for row in rows
        ]
    )
    db.commit()
    db.refresh(plan)
    return plan
