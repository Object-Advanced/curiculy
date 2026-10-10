from enum import StrEnum


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Persist the lowercase member values rather than the member names."""
    return [member.value for member in enum_cls]


class CurriculumSource(StrEnum):
    MANUAL = "manual"
    BARCODE = "barcode"
    PARSED_TEXTBOOK = "parsed_textbook"


class ContributorRole(StrEnum):
    AUTHOR = "author"
    CO_AUTHOR = "co_author"
    EDITOR = "editor"
    ILLUSTRATOR = "illustrator"
    TRANSLATOR = "translator"
    CONTRIBUTOR = "contributor"


class BookFormat(StrEnum):
    HARDCOVER = "hardcover"
    SOFTCOVER = "softcover"
    SPIRAL = "spiral"
    LOOSE_LEAF = "loose_leaf"
    PDF = "pdf"
    EBOOK = "ebook"
    ONLINE = "online"
    OTHER = "other"


class ResourceKind(StrEnum):
    STUDENT_TEXT = "student_text"
    STUDENT_WORKBOOK = "student_workbook"
    TEACHER_GUIDE = "teacher_guide"
    ANSWER_KEY = "answer_key"
    SOLUTIONS_MANUAL = "solutions_manual"
    TEST_BOOK = "test_book"
    READER = "reader"
    MANIPULATIVE = "manipulative"
    VIDEO = "video"
    AUDIO = "audio"
    SOFTWARE = "software"
    OTHER = "other"


class UnitKind(StrEnum):
    COURSE = "course"
    SEMESTER = "semester"
    QUARTER = "quarter"
    MODULE = "module"
    UNIT = "unit"
    CHAPTER = "chapter"
    SECTION = "section"
    LESSON = "lesson"
    ACTIVITY = "activity"
    ASSESSMENT = "assessment"
    REVIEW = "review"


class MappingSource(StrEnum):
    MANUAL = "manual"
    IMPORTED = "imported"
    AI_PARSED = "ai_parsed"


class CurriculumPlanStatus(StrEnum):
    """Lifecycle of a pacing guide while AI (or a parent) fills in lessons."""

    READY = "ready"
    PROCESSING = "processing"
    FAILED = "failed"


class MetadataSource(StrEnum):
    MANUAL = "manual"
    OPEN_LIBRARY = "open_library"
    GOOGLE_BOOKS = "google_books"


class ExceptionKind(StrEnum):
    VACATION = "vacation"
    APPOINTMENT = "appointment"
    SICK = "sick"
    HOLIDAY = "holiday"
    OTHER = "other"


class CalendarPeriod(StrEnum):
    """A named window the calendar can ask for, resolved against an anchor date.

    This says which slice of the calendar to render (today, this week, this month).
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    EXCUSED = "excused"


class AttendanceStatus(StrEnum):
    """Daily attendance for a student. Stored with these exact capitalizations."""

    PRESENT = "Present"
    ABSENT = "Absent"
    SICK = "Sick"
    VACATION = "Vacation"


class ScoreType(StrEnum):
    """How to read ``AssignmentGrade.score_value``, which is always a string."""

    PERCENTAGE = "percentage"
    LETTER = "letter"
    POINTS = "points"
    PASS_FAIL = "pass_fail"
    COMPLETE_INCOMPLETE = "complete_incomplete"
    CUSTOM = "custom"


class PortfolioReportType(StrEnum):
    """Printable portfolio presets, plus a fully configured custom report."""

    STATE_EVALUATION_LOG = "state_evaluation_log"
    READING_LIST = "reading_list"
    WORK_SAMPLES = "work_samples"
    CUSTOM = "custom"


class UserRole(StrEnum):
    PARENT = "parent"
    CHILD = "child"
    # JWT-only. Never stored on ``users.role``. Chrome capture credentials.
    EVIDENCE = "evidence"


class HomeworkHelpStatus(StrEnum):
    ACTIVE = "active"  # started; the one nudge may or may not have been given yet
    HELPED = "helped"  # the child said the nudge helped
    REDIRECTED = "redirected"  # the child went to get a grown-up
    CLOSED = "closed"  # a parent turned nudges back on for the lesson


class HomeworkHelpMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ParentNotificationType(StrEnum):
    HOMEWORK_HELP_STARTED = "homework_help_started"
    HOMEWORK_HELP_REDIRECT = "homework_help_redirect"
    CURRICULUM_PLAN_READY = "curriculum_plan_ready"
    CURRICULUM_PLAN_FAILED = "curriculum_plan_failed"
