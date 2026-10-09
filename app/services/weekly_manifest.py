"""Ink-saver weekly checklist: one student's Monday–Friday assignments as a PDF.

WeasyPrint is imported only when rendering bytes so the rest of the app (and
tests that mock this function) can load without Cairo.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.models import Assignment, Student
from app.services.assignments import AssignmentQuery, DateRange
from app.services.clock import household_today

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class WeeklyManifestLookupError(LookupError):
    """Student is missing from this lockbox."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class ManifestAssignment:
    title: str
    subject: str | None
    notes: str | None
    pages: str | None

    @property
    def detail(self) -> str:
        return " · ".join(
            part for part in (self.subject, self.pages, self.notes) if part
        )


@dataclass(frozen=True)
class ManifestDay:
    date: date
    heading: str
    assignments: list[ManifestAssignment]


@dataclass(frozen=True)
class WeeklyManifest:
    student: Student
    start_date: date
    end_date: date
    week_label: str
    days: list[ManifestDay]


def _today(tenant_db: Session) -> date:
    return household_today(tenant_db)


def week_monday(day: date) -> date:
    """Snap ``day`` back to that week's Monday."""
    return day - timedelta(days=day.weekday())


def _heading(day: date) -> str:
    return f"{day.strftime('%A, %b')} {day.day}"


def _pages_label(assignment: Assignment) -> str | None:
    unit = assignment.curriculum_unit
    if unit is None:
        return None
    mappings = list(unit.page_mappings or [])
    if not mappings:
        return None
    mapping = next((item for item in mappings if item.is_primary), mappings[0])
    start = mapping.printed_page_start or str(mapping.page_start)
    end = mapping.printed_page_end or str(mapping.page_end)
    if start == end:
        return f"p. {start}"
    return f"pp. {start}–{end}"


def _row(assignment: Assignment) -> ManifestAssignment:
    notes = (assignment.notes or "").strip() or None
    subject = assignment.subject_name or assignment.resource_title
    return ManifestAssignment(
        title=assignment.title,
        subject=subject,
        notes=notes,
        pages=_pages_label(assignment),
    )


def build_weekly_manifest(
    tenant_db: Session,
    catalog_db: Session,
    student_id: int,
    start_date: date | None = None,
) -> WeeklyManifest:
    student = tenant_db.get(Student, student_id)
    if student is None:
        raise WeeklyManifestLookupError("Student not found")

    monday = week_monday(start_date or _today(tenant_db))
    friday = monday + timedelta(days=4)
    assignments = AssignmentQuery(tenant_db, catalog_db).for_student(
        student_id, DateRange(monday, friday)
    )
    by_date: dict[date, list[ManifestAssignment]] = defaultdict(list)
    for item in assignments:
        by_date[item.scheduled_date].append(_row(item))

    days = [
        ManifestDay(
            date=monday + timedelta(days=offset),
            heading=_heading(monday + timedelta(days=offset)),
            assignments=by_date.get(monday + timedelta(days=offset), []),
        )
        for offset in range(5)
    ]
    return WeeklyManifest(
        student=student,
        start_date=monday,
        end_date=friday,
        week_label=f"Week of {_heading(monday)} – {_heading(friday)}",
        days=days,
    )


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_weekly_manifest_html(manifest: WeeklyManifest) -> str:
    template = _jinja_env().get_template("weekly_manifest.html")
    return template.render(
        student=manifest.student,
        week_label=manifest.week_label,
        days=manifest.days,
    )


def pdf_filename(manifest: WeeklyManifest) -> str:
    student = _UNSAFE_FILENAME.sub("_", manifest.student.name).strip("._") or "student"
    return f"{student}_weekly_checklist_{manifest.start_date.isoformat()}.pdf"


def render_weekly_manifest_pdf(manifest: WeeklyManifest) -> bytes:
    """Turn the checklist HTML into PDF bytes."""
    from weasyprint import HTML

    html_document = render_weekly_manifest_html(manifest)
    pdf = HTML(string=html_document, base_url=str(_TEMPLATES_DIR)).write_pdf()
    if not pdf:
        raise RuntimeError("WeasyPrint returned an empty PDF")
    return pdf
