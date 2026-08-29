"""Build a printable portfolio and email it to an evaluator.

The HTTP handler aggregates the report and queues SMTP on FastAPI's
``BackgroundTasks``. PDF rendering stays in this module so the route can return
before the handshake, and tests can swap ``render_portfolio_pdf`` without
importing WeasyPrint.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import SecretStr
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

from app.config import settings
from app.enums import AssignmentStatus, AttendanceStatus, PortfolioReportType
from app.evidence import evidence_root
from app.models import Attendance, Curriculum, Enrollment, SchoolYear, Student
from app.schemas import (
    AssignmentDetailRead,
    AttendanceDayRead,
    AttendanceSummaryRead,
    PortfolioBookRead,
    PortfolioGenerateRequest,
    PortfolioReportRead,
    PortfolioStudentSectionRead,
    SchoolYearRead,
    StudentRead,
)
from app.services.assignments import AssignmentQuery, DateRange

logger = logging.getLogger(__name__)

REPORT_TYPE_LABELS = {
    PortfolioReportType.STATE_EVALUATION_LOG: "State Evaluation Log",
    PortfolioReportType.READING_LIST: "Reading List",
    PortfolioReportType.WORK_SAMPLES: "Work Samples",
    PortfolioReportType.CUSTOM: "Custom Report",
}

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif"}
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class PortfolioLookupError(LookupError):
    """Student or school year is missing from this lockbox."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def mail_connection() -> ConnectionConfig:
    """Build fastapi-mail config from settings, with the same dummy fallbacks."""
    return ConnectionConfig(
        MAIL_USERNAME=settings.mail_username or "curiculy",
        MAIL_PASSWORD=SecretStr(settings.mail_password or "changeme"),
        MAIL_FROM=settings.mail_from or "noreply@example.com",
        MAIL_FROM_NAME=settings.mail_from_name or "Curiculy",
        MAIL_PORT=settings.mail_port or 587,
        MAIL_SERVER=settings.mail_server or "localhost",
        MAIL_STARTTLS=settings.mail_starttls,
        MAIL_SSL_TLS=settings.mail_ssl_tls,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["report_date"] = lambda value: value.strftime("%d %b %Y") if value else ""
    env.filters["humanize"] = _humanize
    return env


def _humanize(value: object) -> str:
    text = str(value or "").replace("_", " ")
    return text[:1].upper() + text[1:] if text else ""


def load_portfolio_report(
    tenant_db: Session,
    catalog_db: Session,
    student_id: int,
    school_year_id: int,
    report_type: PortfolioReportType,
) -> PortfolioReportRead:
    return build_portfolio_report(
        tenant_db,
        catalog_db,
        PortfolioGenerateRequest(
            report_type=report_type,
            student_id=student_id,
            school_year_id=school_year_id,
        ),
    )


def build_portfolio_report(
    tenant_db: Session,
    catalog_db: Session,
    filters: PortfolioGenerateRequest,
) -> PortfolioReportRead:
    students = _load_students(tenant_db, filters.student_ids)
    school_year, start_date, end_date = _resolve_window(tenant_db, filters)
    window = DateRange(start_date, end_date)
    flags = _section_flags(filters)
    query = AssignmentQuery(tenant_db, catalog_db)
    all_assignments = query.for_students([student.id for student in students], window)
    by_student: dict[int, list] = {student.id: [] for student in students}
    for item in all_assignments:
        by_student.setdefault(item.student_id, []).append(item)

    attendance_by_student: dict[int, list[Attendance]] = {student.id: [] for student in students}
    if flags["include_attendance"]:
        rows = (
            tenant_db.query(Attendance)
            .filter(
                Attendance.student_id.in_([student.id for student in students]),
                Attendance.date >= start_date,
                Attendance.date <= end_date,
            )
            .order_by(Attendance.date, Attendance.id)
            .all()
        )
        for row in rows:
            attendance_by_student.setdefault(row.student_id, []).append(row)

    sections: list[PortfolioStudentSectionRead] = []
    for student in students:
        work = by_student.get(student.id, [])
        lessons = [
            AssignmentDetailRead.model_validate(item)
            for item in work
            if item.status is AssignmentStatus.COMPLETED
        ]
        assignments = [AssignmentDetailRead.model_validate(item) for item in work]
        books = (
            _filter_books(
                _books_for_student(
                    tenant_db,
                    student.id,
                    work,
                    school_year_id=filters.school_year_id,
                ),
                flags,
            )
            if (
                flags["include_books_completed"]
                or flags["include_books_in_progress"]
                or flags["include_books_incomplete"]
            )
            else []
        )
        attachments = [
            AssignmentDetailRead.model_validate(item)
            for item in work
            if item.evidence
        ]
        notes = [
            AssignmentDetailRead.model_validate(item)
            for item in work
            if (item.notes or "").strip()
        ]
        attendance = (
            _attendance_summary(attendance_by_student.get(student.id, []))
            if flags["include_attendance"]
            else None
        )
        sections.append(
            PortfolioStudentSectionRead(
                student=StudentRead.model_validate(student),
                attendance=attendance,
                lessons=lessons if flags["include_lessons"] else [],
                assignments=assignments if flags["include_assignments"] else [],
                books=books,
                attachments=attachments if flags["include_attachments"] else [],
                notes=notes if flags["include_notes"] else [],
            )
        )

    primary = students[0]
    preset_assignments = [
        AssignmentDetailRead.model_validate(item)
        for item in by_student.get(primary.id, [])
        if item.status is AssignmentStatus.COMPLETED
    ]
    year_read = (
        SchoolYearRead.model_validate(school_year) if school_year is not None else None
    )
    return PortfolioReportRead(
        report_type=filters.report_type,
        student=StudentRead.model_validate(primary),
        school_year=year_read,
        start_date=start_date,
        end_date=end_date,
        period_label=_period_label(year_read, start_date, end_date),
        count=len(preset_assignments) if filters.report_type is not PortfolioReportType.CUSTOM
        else sum(_section_count(section, flags) for section in sections),
        assignments=preset_assignments,
        students=sections,
        **flags,
    )


def _load_students(tenant_db: Session, student_ids: list[int]) -> list[Student]:
    found = {
        student.id: student
        for student in tenant_db.query(Student).filter(Student.id.in_(student_ids)).all()
    }
    students = []
    for student_id in student_ids:
        student = found.get(student_id)
        if student is None:
            raise PortfolioLookupError("Student not found")
        students.append(student)
    return students


def _resolve_window(
    tenant_db: Session, filters: PortfolioGenerateRequest
) -> tuple[SchoolYear | None, date, date]:
    school_year = None
    if filters.school_year_id is not None:
        school_year = tenant_db.get(SchoolYear, filters.school_year_id)
        if school_year is None:
            raise PortfolioLookupError("School year not found")
    start_date = filters.start_date
    end_date = filters.end_date
    if school_year is not None:
        if start_date is None:
            start_date = school_year.start_date
        if end_date is None:
            end_date = school_year.end_date
    if start_date is None or end_date is None:
        raise PortfolioLookupError("A date range is required")
    return school_year, start_date, end_date


def _section_flags(filters: PortfolioGenerateRequest) -> dict[str, bool]:
    if filters.report_type is not PortfolioReportType.CUSTOM:
        return {
            "include_attendance": False,
            "include_lessons": True,
            "include_assignments": False,
            "include_books_completed": False,
            "include_books_in_progress": False,
            "include_books_incomplete": False,
            "include_attachments": True,
            "include_notes": False,
        }
    return {
        "include_attendance": filters.include_attendance,
        "include_lessons": filters.include_lessons,
        "include_assignments": filters.include_assignments,
        "include_books_completed": filters.include_books_completed,
        "include_books_in_progress": filters.include_books_in_progress,
        "include_books_incomplete": filters.include_books_incomplete,
        "include_attachments": filters.include_attachments,
        "include_notes": filters.include_notes,
    }


def _section_count(section: PortfolioStudentSectionRead, flags: dict[str, bool]) -> int:
    total = 0
    if flags["include_lessons"]:
        total += len(section.lessons)
    if flags["include_assignments"]:
        total += len(section.assignments)
    if flags["include_attachments"]:
        total += len(section.attachments)
    return total


def _period_label(
    school_year: SchoolYearRead | None, start_date: date, end_date: date
) -> str:
    if school_year is not None:
        return school_year.name
    return f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"


def _attendance_summary(rows: list[Attendance]) -> AttendanceSummaryRead:
    present = absent = sick = vacation = 0
    log: list[AttendanceDayRead] = []
    for row in rows:
        if row.status is AttendanceStatus.PRESENT:
            present += 1
        elif row.status is AttendanceStatus.ABSENT:
            absent += 1
        elif row.status is AttendanceStatus.SICK:
            sick += 1
        elif row.status is AttendanceStatus.VACATION:
            vacation += 1
        log.append(AttendanceDayRead(date=row.date, status=row.status))
    return AttendanceSummaryRead(
        present=present,
        absent=absent,
        sick=sick,
        vacation=vacation,
        log=log,
    )


def _books_for_student(
    tenant_db: Session,
    student_id: int,
    assignments: list,
    *,
    school_year_id: int | None,
) -> list[PortfolioBookRead]:
    counts: dict[int, tuple[int, int]] = {}
    for item in assignments:
        curriculum_id = item.curriculum_id
        if curriculum_id is None:
            continue
        total, completed = counts.get(curriculum_id, (0, 0))
        total += 1
        if item.status is AssignmentStatus.COMPLETED:
            completed += 1
        counts[curriculum_id] = (total, completed)

    enrolled = tenant_db.query(Enrollment.curriculum_id).filter(
        Enrollment.student_id == student_id
    )
    if school_year_id is not None:
        enrolled = enrolled.filter(Enrollment.school_year_id == school_year_id)
    for (curriculum_id,) in enrolled.all():
        counts.setdefault(curriculum_id, (0, 0))
    if not counts:
        return []

    curricula = {
        row.id: row
        for row in tenant_db.query(Curriculum).filter(Curriculum.id.in_(counts)).all()
    }
    books: list[PortfolioBookRead] = []
    for curriculum_id, (total, completed) in counts.items():
        curriculum = curricula.get(curriculum_id)
        if curriculum is None:
            continue
        if total > 0 and completed >= total:
            progress = "completed"
        elif completed > 0:
            progress = "in_progress"
        else:
            progress = "incomplete"
        books.append(
            PortfolioBookRead(
                curriculum_id=curriculum_id,
                title=curriculum.title,
                publisher_name=curriculum.publisher_name,
                subject=curriculum.subject,
                total_assignments=total,
                completed_assignments=completed,
                progress=progress,
            )
        )
    books.sort(key=lambda book: (book.title.lower(), book.curriculum_id))
    return books


def _filter_books(
    books: list[PortfolioBookRead], flags: dict[str, bool]
) -> list[PortfolioBookRead]:
    allowed = set()
    if flags["include_books_completed"]:
        allowed.add("completed")
    if flags["include_books_in_progress"]:
        allowed.add("in_progress")
    if flags["include_books_incomplete"]:
        allowed.add("incomplete")
    if not allowed:
        return []
    return [book for book in books if book.progress in allowed]


def pdf_filename(report: PortfolioReportRead) -> str:
    if len(report.students) > 1:
        student = "Family"
    else:
        student = _UNSAFE_FILENAME.sub("_", report.student.name).strip("._") or "student"
    year = _UNSAFE_FILENAME.sub("_", report.period_label).strip("._") or "year"
    return f"{student}_{year}_{report.report_type}.pdf"


def _evidence_file(file_path: str | None) -> Path | None:
    if not file_path:
        return None
    relative = Path(str(file_path).replace("\\", "/").lstrip("/"))
    parts = relative.parts
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "evidence":
        relative = Path(*parts[2:])
    if not relative.parts or ".." in relative.parts:
        return None
    root = evidence_root().resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_file() and candidate.suffix.lower() in _IMAGE_SUFFIXES:
        return candidate
    return None


def evidence_src(file_path: str | None, *, for_pdf: bool) -> str | None:
    path = _evidence_file(file_path)
    if path is None:
        return None
    if for_pdf:
        return path.as_uri()
    relative = path.relative_to(evidence_root().resolve())
    return "/evidence/" + "/".join(quote(part) for part in relative.parts)


def _template_context(report: PortfolioReportRead, *, for_pdf: bool) -> dict:
    return {
        "report": report,
        "label": REPORT_TYPE_LABELS.get(report.report_type, str(report.report_type)),
        "custom": report.report_type is PortfolioReportType.CUSTOM,
        "for_pdf": for_pdf,
        "evidence_src": lambda path: evidence_src(path, for_pdf=for_pdf),
        "include_books": (
            report.include_books_completed
            or report.include_books_in_progress
            or report.include_books_incomplete
        ),
    }


def render_portfolio_fragment(report: PortfolioReportRead, *, for_pdf: bool = False) -> str:
    template = _jinja_env().get_template("portfolio_body.html")
    body = template.render(**_template_context(report, for_pdf=for_pdf))
    if for_pdf:
        return body
    css = (_TEMPLATES_DIR / "portfolio.css").read_text(encoding="utf-8")
    css = "\n".join(
        line for line in css.splitlines() if not line.lstrip().startswith("@page")
    )
    return f"<style>{css}</style>\n{body}"


def render_portfolio_html(report: PortfolioReportRead, *, for_pdf: bool = True) -> str:
    template = _jinja_env().get_template("portfolio.html")
    return template.render(
        **_template_context(report, for_pdf=for_pdf),
        body=render_portfolio_fragment(report, for_pdf=for_pdf),
    )


def render_portfolio_pdf(report: PortfolioReportRead) -> bytes:
    """Turn the report HTML into PDF bytes. WeasyPrint is imported here so the
    rest of the app (and tests that mock this function) can load without Cairo.
    """
    from weasyprint import HTML

    html_document = render_portfolio_html(report, for_pdf=True)
    pdf = HTML(string=html_document, base_url=str(evidence_root())).write_pdf()
    if not pdf:
        raise RuntimeError("WeasyPrint returned an empty PDF")
    return pdf


def build_portfolio_message(
    *,
    evaluator_email: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    filename: str,
) -> MessageSchema:
    attachment = UploadFile(
        file=BytesIO(pdf_bytes),
        filename=filename,
        headers=Headers({"content-type": "application/pdf"}),
    )
    return MessageSchema(
        subject=subject,
        recipients=[evaluator_email],
        body=body or "Please find the attached homeschool portfolio.",
        subtype=MessageType.plain,
        attachments=[attachment],
    )


async def send_portfolio_email(message: MessageSchema) -> None:
    """SMTP handshake lives here so the HTTP route can return immediately."""
    try:
        await FastMail(mail_connection()).send_message(message)
    except Exception:
        logger.exception("Failed to send portfolio evaluator email")
