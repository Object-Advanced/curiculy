from datetime import date, datetime
from re import fullmatch

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import CurriculumSource, ExceptionKind, ScheduleGrain, UnitKind, WorkStatus

_HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
    dev_mode: bool = False


class HouseholdRead(ORMModel):
    id: int
    name: str
    jurisdiction_id: int | None


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    grade: str | None = None
    notes: str | None = None
    color_hex: str | None = Field(default=None, min_length=7, max_length=7)

    @field_validator("color_hex", mode="before")
    @classmethod
    def _normalize_color_hex(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned.startswith("#"):
                cleaned = f"#{cleaned}"
            if fullmatch(_HEX_COLOR, cleaned):
                return cleaned.lower()
            raise ValueError("color_hex must be a 6-digit hex color like #356b46")
        return value


class StudentRead(ORMModel):
    id: int
    household_id: int
    name: str
    grade: str | None
    notes: str | None
    color_hex: str
    has_login: bool = False


class CurriculumCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    subject: str | None = None
    description: str | None = None
    source_type: CurriculumSource = CurriculumSource.MANUAL
    sku: str | None = Field(
        default=None,
        max_length=64,
        description="ISBN or proprietary barcode so a later scan finds this book locally.",
    )

    @field_validator("title", "sku", mode="before")
    @classmethod
    def _blank_optional(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @model_validator(mode="after")
    def _title_required_without_sku(self) -> "CurriculumCreate":
        if self.sku is None and not self.title:
            raise ValueError("title is required")
        return self


class CurriculumRead(ORMModel):
    id: int
    title: str
    publisher_id: int | None
    publisher_name: str | None
    subject: str | None
    description: str | None
    source_type: CurriculumSource
    is_scheduled: bool = False


class SchoolYearCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    start_date: date
    end_date: date


class SchoolYearRead(ORMModel):
    id: int
    household_id: int
    name: str
    start_date: date
    end_date: date


def _normalize_class_weekdays(value: list[int]) -> list[int]:
    if not value:
        raise ValueError("at least one class day is required")
    for weekday in value:
        if not 0 <= weekday <= 6:
            raise ValueError("weekdays must be 0 (Monday) through 6 (Sunday)")
    return sorted(set(value))


class SchoolYearSettingsRead(BaseModel):
    start_date: date
    end_date: date
    weekdays: list[int]
    school_year_id: int | None = None


class SchoolYearSettingsUpdate(BaseModel):
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int]) -> list[int]:
        return _normalize_class_weekdays(value)

    @model_validator(mode="after")
    def _check_bounds(self) -> "SchoolYearSettingsUpdate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class CalendarExceptionDatesRead(BaseModel):
    dates: list[date]


class CalendarExceptionToggleRequest(BaseModel):
    date: date


class CalendarExceptionToggleRead(BaseModel):
    date: date
    excepted: bool
    dates: list[date]


class ImportHolidaysRequest(BaseModel):
    country: str = Field(min_length=2, max_length=8)
    subdiv: str | None = None
    year: int = Field(ge=1900, le=2100)

    @field_validator("country")
    @classmethod
    def _country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("subdiv")
    @classmethod
    def _subdiv(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip().upper()
            return cleaned or None
        return None


class ImportHolidaysRead(BaseModel):
    imported: int
    skipped: int
    dates: list[date]


DEFAULT_EXCEPTION_COLOR_VALUES = {
    "holiday": "#c2410c",
    "vacation": "#2563eb",
    "sick": "#7c3aed",
    "appointment": "#0f766e",
    "other": "#dc2626",
}


def _normalize_hex_color(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("color must be a 6-digit hex value like #dc2626")
    cleaned = value.strip()
    if not cleaned.startswith("#"):
        cleaned = f"#{cleaned}"
    if not fullmatch(_HEX_COLOR, cleaned):
        raise ValueError("color must be a 6-digit hex value like #dc2626")
    return cleaned.lower()


class ExceptionColorsRead(BaseModel):
    holiday: str
    vacation: str
    sick: str
    appointment: str
    other: str


class ExceptionColorsUpdate(BaseModel):
    holiday: str | None = None
    vacation: str | None = None
    sick: str | None = None
    appointment: str | None = None
    other: str | None = None

    @field_validator("holiday", "vacation", "sick", "appointment", "other")
    @classmethod
    def _hex(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_hex_color(value)


class EnrollmentCreate(BaseModel):
    student_id: int
    curriculum_id: int
    school_year_id: int
    start_date: date | None = None
    end_date: date | None = None


class EnrollmentRead(ORMModel):
    id: int
    student_id: int
    curriculum_id: int
    school_year_id: int
    start_date: date | None
    end_date: date | None


class CalendarExceptionCreate(BaseModel):
    student_id: int | None = None
    kind: ExceptionKind
    title: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    notes: str | None = None


class CalendarExceptionRead(ORMModel):
    id: int
    household_id: int
    student_id: int | None
    kind: ExceptionKind
    title: str
    start_date: date
    end_date: date
    notes: str | None


class CurriculumUnitRead(ORMModel):
    id: int
    curriculum_edition_id: int
    parent_id: int | None
    kind: UnitKind
    label: str | None
    title: str
    sort_order: int
    depth: int
    estimated_minutes: int | None
    estimated_sessions: int | None


class ScheduledWorkRead(ORMModel):
    id: int
    enrollment_id: int
    student_id: int
    unit_id: int | None
    grain: ScheduleGrain
    due_date: date
    title: str
    status: WorkStatus
    created_at: datetime
