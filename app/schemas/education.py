"""Assignment models for the calendar, the detail view, and the writes behind them.

The calendar needs one row per assignment with enough denormalized text to draw a
tile without a second request, so ``AssignmentRead`` carries the subject, resource
and unit titles alongside their ids. The detail view adds the evidence list and
the full subject path.

The write models are deliberately narrower than the read ones: a caller may only
set the fields a parent edits by hand, so the denormalized display text and the
evidence list have no counterpart here.
"""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.enums import (
    AssignmentStatus,
    AttendanceStatus,
    CalendarPeriod,
    PortfolioReportType,
    ScoreType,
)
from app.schemas.core import ORMModel, SchoolYearRead, StudentRead


class AssignmentGradeRead(ORMModel):
    id: int
    score_type: ScoreType
    score_value: str
    graded_on: date | None
    notes: str | None


class AssignmentEvidenceRead(ORMModel):
    id: int
    file_path: str | None
    url: str | None
    captured_at: datetime | None
    notes: str | None


class EvidenceStagingRead(ORMModel):
    id: int
    tenant_id: str
    file_path: str
    captured_at: datetime
    source: str


class EvidenceLinkRequest(BaseModel):
    """Move a staged capture onto an assignment's evidence list."""

    evidence_id: int
    assignment_id: int


class SubjectTaxonomyRead(ORMModel):
    id: int
    parent_id: int | None
    code: str | None
    name: str
    full_name: str
    depth: int


class AssignmentRead(ORMModel):
    """One calendar tile."""

    id: int
    student_id: int
    title: str
    scheduled_date: date
    completion_date: date | None
    status: AssignmentStatus
    notes: str | None
    curriculum_resource_id: int | None
    curriculum_unit_id: int | None
    subject_taxonomy_id: int | None
    subject_name: str | None
    resource_title: str | None
    unit_title: str | None
    curriculum_id: int | None
    shared_group_uuid: str | None = None
    color_hex: str | None = None
    grade: AssignmentGradeRead | None
    evidence_count: int


class AssignmentDetailRead(AssignmentRead):
    subject_taxonomy: SubjectTaxonomyRead | None
    evidence: list[AssignmentEvidenceRead] = Field(default_factory=list)


class AssignmentCreate(BaseModel):
    """A new assignment. Everything but the student, title, and date is optional."""

    student_id: int
    title: str = Field(min_length=1, max_length=255)
    scheduled_date: date
    completion_date: date | None = None
    status: AssignmentStatus = AssignmentStatus.ASSIGNED
    notes: str | None = None
    curriculum_resource_id: int | None = None
    curriculum_unit_id: int | None = None
    subject_taxonomy_id: int | None = None


class AssignmentStatusUpdate(BaseModel):
    """A status-only write, used by the student dashboard checklist."""

    status: AssignmentStatus


class AssignmentUpdate(BaseModel):
    """A partial update of the three fields the calendar edits.

    Only the fields actually present in the request body are applied, which is
    what lets ``{"completion_date": null}`` clear a date while omitting the key
    leaves the stored one alone. ``scheduled_date`` and ``status`` back
    non-nullable columns, so an explicit null for either is rejected rather than
    silently ignored.
    """

    scheduled_date: date | None = None
    completion_date: date | None = None
    status: AssignmentStatus | None = None

    @field_validator("scheduled_date", "status")
    @classmethod
    def _reject_explicit_null(cls, value: date | AssignmentStatus) -> date | AssignmentStatus:
        # Only runs for keys the caller sent, so a plain omission still defaults.
        if value is None:
            raise ValueError("cannot be null")
        return value


class AssignmentGradeUpsert(BaseModel):
    """The recorded result for an assignment, replacing any earlier one in full.

    Omitted optional fields are stored as null rather than left untouched: an
    assignment has at most one grade, and a partial merge would make it
    impossible to clear a note or a date once written.
    """

    score_type: ScoreType = ScoreType.PERCENTAGE
    score_value: str = Field(min_length=1, max_length=64)
    graded_on: date | None = None
    notes: str | None = None


class AssignmentCalendarRead(BaseModel):
    """The assignments in a window, plus the bounds that window resolved to.

    The resolved bounds are echoed because a caller passing ``period=week`` does
    not otherwise know which Monday it got back, and the calendar has to label
    the range it is drawing.
    """

    student_id: int | None = None
    period: CalendarPeriod | None
    start_date: date | None
    end_date: date | None
    count: int
    assignments: list[AssignmentRead]


class AttendanceRead(ORMModel):
    id: int
    student_id: int
    date: date
    status: AttendanceStatus


class AttendanceUpsert(BaseModel):
    """Insert or replace the attendance row for one student on one date."""

    student_id: int
    date: date
    status: AttendanceStatus


class StudentCourseRead(ORMModel):
    """One active course on a student dashboard, with lesson completion counts."""

    curriculum_id: int
    title: str
    total_assignments: int
    completed_assignments: int


class StudentTodayProgress(ORMModel):
    """One student's assignments scheduled today, and how many are complete."""

    student_id: int
    name: str
    color_hex: str
    total: int
    completed: int


class StudentWeeklyTrend(ORMModel):
    """Completed assignments for one student, aligned with ``trend_dates``."""

    student_id: int
    name: str
    color_hex: str
    completed: list[int]


class DashboardStatsRead(BaseModel):
    """Family dashboard KPIs: today's progress and a seven-day completion trend."""

    today: date
    today_progress: list[StudentTodayProgress]
    trend_dates: list[date]
    weekly_trend: list[StudentWeeklyTrend]


class StudentSparkRead(BaseModel):
    """A question about today's lessons, when the local model is available."""

    student_id: int
    source: str
    question: str | None = None
    about: str | None = None


class AttendanceDayRead(ORMModel):
    date: date
    status: AttendanceStatus


class AttendanceSummaryRead(BaseModel):
    present: int = 0
    absent: int = 0
    sick: int = 0
    vacation: int = 0
    log: list[AttendanceDayRead] = Field(default_factory=list)

    @property
    def exceptions(self) -> int:
        return self.sick + self.vacation


class PortfolioBookRead(BaseModel):
    curriculum_id: int
    title: str
    publisher_name: str | None = None
    subject: str | None = None
    total_assignments: int = 0
    completed_assignments: int = 0
    progress: str


class PortfolioStudentSectionRead(BaseModel):
    """One student's slice of a custom (or preset) portfolio."""

    student: StudentRead
    attendance: AttendanceSummaryRead | None = None
    lessons: list[AssignmentDetailRead] = Field(default_factory=list)
    assignments: list[AssignmentDetailRead] = Field(default_factory=list)
    books: list[PortfolioBookRead] = Field(default_factory=list)
    attachments: list[AssignmentDetailRead] = Field(default_factory=list)
    notes: list[AssignmentDetailRead] = Field(default_factory=list)


class PortfolioGenerateRequest(BaseModel):
    """Filters for a portfolio preview, PDF, or evaluator email."""

    report_type: PortfolioReportType = PortfolioReportType.CUSTOM
    student_id: int | None = None
    student_ids: list[int] = Field(default_factory=list)
    school_year_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    include_attendance: bool = False
    include_lessons: bool = False
    include_assignments: bool = False
    include_books_completed: bool = False
    include_books_in_progress: bool = False
    include_books_incomplete: bool = False
    include_attachments: bool = False
    include_notes: bool = False

    @model_validator(mode="after")
    def _normalize_students_and_window(self) -> "PortfolioGenerateRequest":
        ids = list(self.student_ids)
        if self.student_id is not None and self.student_id not in ids:
            ids.insert(0, self.student_id)
        if not ids:
            raise ValueError("At least one student is required")
        self.student_ids = ids
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be on or before end_date")
        if self.report_type is PortfolioReportType.CUSTOM:
            if self.school_year_id is None and (
                self.start_date is None or self.end_date is None
            ):
                raise ValueError(
                    "start_date and end_date are required for custom reports"
                )
        elif self.school_year_id is None:
            raise ValueError("school_year_id is required for preset reports")
        return self

    @property
    def include_books(self) -> bool:
        return (
            self.include_books_completed
            or self.include_books_in_progress
            or self.include_books_incomplete
        )


class PortfolioReportRead(BaseModel):
    """A printable portfolio: one student for presets, one or more for custom."""

    report_type: PortfolioReportType
    student: StudentRead
    school_year: SchoolYearRead | None = None
    start_date: date | None = None
    end_date: date | None = None
    period_label: str = ""
    count: int
    assignments: list[AssignmentDetailRead] = Field(default_factory=list)
    students: list[PortfolioStudentSectionRead] = Field(default_factory=list)
    include_attendance: bool = False
    include_lessons: bool = False
    include_assignments: bool = False
    include_books_completed: bool = False
    include_books_in_progress: bool = False
    include_books_incomplete: bool = False
    include_attachments: bool = False
    include_notes: bool = False


class PortfolioPreviewRead(BaseModel):
    html: str


class PortfolioEmailRequest(PortfolioGenerateRequest):
    """Send a generated portfolio PDF to an evaluator."""

    evaluator_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=10000)


class PortfolioEmailRead(BaseModel):
    status: str = "success"
