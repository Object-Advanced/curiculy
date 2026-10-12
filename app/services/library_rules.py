"""What each kind of library item needs before it can be scheduled, and why.

``readiness(item)`` returns the missing required fields, each with the reason
in plain words, and the structure problems that would break scheduling
(chapters out of order, pages past the end, a title that's keyboard mashing).
An item can always be saved unfinished; it can be scheduled only when
nothing is missing and there are no "fix" problems.

The required fields are the product decision recorded in
docs/6-planning/product-spine.md ("What each type asks for").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import LibraryItem
from app.services.text_checks import keyboard_mash_reason

READING_BOOK, TEXTBOOK, WORKBOOK, ONLINE_PROGRAM = "reading_book", "textbook", "workbook", "online_program"
KINDS = {
    READING_BOOK: "Book",
    TEXTBOOK: "Textbook",
    WORKBOOK: "Workbook",
    ONLINE_PROGRAM: "Online site",
}
# One line under each choice in "What is this?"
KIND_HINTS = {
    READING_BOOK: "A book to read: a novel, biography, poetry or a read-aloud.",
    TEXTBOOK: "The main book you teach a subject from, with numbered lessons (Saxon Math 5/4, BJU Reading 4).",
    WORKBOOK: "A book your child writes in, page by page, often split into chapters (Spectrum Math, Explode the Code).",
    ONLINE_PROGRAM: "Lessons done on a website or app (IXL, Khan Academy, Teaching Textbooks).",
}
READING_KINDS = ("novel", "biography", "poetry", "picture_book", "read_aloud", "other")
LESSON_TYPES = ("lesson", "test", "quiz", "review", "project")
MEASURES = ("lessons", "minutes")

WHY = {
    "title": "Every book needs a name to show on the shelf, the calendar and the reading log.",
    "author": "The reading list and state logs name each book's author.",
    "total_pages": "Curiculy divides the pages into daily reading, and re-plans them when a day is missed.",
    "subject_code": "Subjects connect this to the child's subject slots and your state's requirements.",
    "grade": "The grade helps match it to the right child and the right catalog edition.",
    "chapters": (
        "Curiculy uses each chapter's start page to keep assignments inside a chapter, "
        "and to re-plan cleanly when you miss a day."
    ),
    "publisher": "The publisher and edition make sure the lesson list matches the books you own.",
    "edition": "The publisher and edition make sure the lesson list matches the books you own.",
    "days_per_week": "The calendar paces lessons to the days a week the program is designed for.",
    "lessons": (
        "The calendar places each lesson in order, keeps tests on their own day, and can only "
        "catch up properly after a missed day when every lesson is listed."
    ),
    "teacher_lessons": "A teacher's edition is for you, so it doesn't need lessons of its own.",
    "lesson_names": "Lesson names tell your child what to do each day.",
    "lesson_pages": "Each lesson's pages (including quizzes and tests) are what your child opens to each day.",
    "website_url": "The link opens the program from the calendar and your child's trail.",
    "measure": "Online work is scheduled by lessons or by minutes.",
    "lesson_count": "Curiculy needs the number of lessons to spread them across the year.",
    "minutes_per_session": "Curiculy needs the session length to schedule time each day.",
}


@dataclass(frozen=True)
class Missing:
    field: str
    label: str
    reason: str


@dataclass(frozen=True)
class Problem:
    level: str  # "fix" (blocks scheduling) or "check" (worth a look)
    where: str
    message: str


@dataclass
class Readiness:
    missing: list[Missing] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    lessons_total: int = 0
    lessons_with_pages: int = 0
    lessons_with_names: int = 0

    @property
    def ready(self) -> bool:
        return not self.missing and not any(problem.level == "fix" for problem in self.problems)


def _need(readiness: Readiness, field_name: str, label: str, present: bool, why: str | None = None) -> None:
    if not present:
        readiness.missing.append(Missing(field_name, label, why or WHY[field_name]))


def _text_problems(readiness: Readiness, where: str, text: str | None) -> None:
    reason = keyboard_mash_reason(text)
    if reason:
        readiness.problems.append(
            Problem("fix", where, f"That doesn't look like real words ({reason}). Fix it?")
        )


def _chapter_problems(item: LibraryItem, readiness: Readiness) -> None:
    previous = 0
    for chapter in item.chapters:
        where = f'Chapter "{chapter.name}"'
        _text_problems(readiness, where, chapter.name)
        if chapter.start_page < 1:
            readiness.problems.append(Problem("fix", where, "Start pages begin at 1."))
        if chapter.start_page <= previous:
            readiness.problems.append(
                Problem("fix", where, f"Starts on p. {chapter.start_page}, not after the chapter before it (p. {previous}).")
            )
        if item.total_pages and chapter.start_page > item.total_pages:
            readiness.problems.append(
                Problem("fix", where, f"Starts on p. {chapter.start_page}, past the book's {item.total_pages} pages.")
            )
        if item.answer_key_start_page and chapter.start_page >= item.answer_key_start_page:
            readiness.problems.append(
                Problem("check", where, f"Starts inside the answer key (p. {item.answer_key_start_page} on).")
            )
        previous = max(previous, chapter.start_page)


def _lesson_problems(item: LibraryItem, readiness: Readiness) -> None:
    seen: set[int] = set()
    last_start = 0
    for lesson in item.lessons:
        label = f"Lesson {lesson.number}" if lesson.number is not None else "A lesson"
        if lesson.number is None:
            readiness.problems.append(Problem("fix", label, "Every lesson needs a number."))
        elif lesson.number in seen:
            readiness.problems.append(Problem("fix", label, f"Lesson {lesson.number} is listed twice."))
        else:
            seen.add(lesson.number)
        _text_problems(readiness, label, lesson.name)
        start, end = lesson.start_page, lesson.end_page
        if start is None and end is None:
            continue
        if start is None or end is None:
            readiness.problems.append(Problem("fix", label, "Give both the first and the last page."))
            continue
        if start < 1 or end < start:
            readiness.problems.append(Problem("fix", label, f"Pages {start}–{end} run backwards."))
        if item.total_pages and end > item.total_pages:
            readiness.problems.append(
                Problem("fix", label, f"Ends on p. {end}, past the book's {item.total_pages} pages.")
            )
        if start < last_start:
            readiness.problems.append(
                Problem("check", label, f"Goes back to p. {start}, before the lesson before it.")
            )
        last_start = max(last_start, start)
    if seen:
        gaps = sorted(set(range(1, max(seen) + 1)) - seen)
        if gaps:
            shown = ", ".join(str(number) for number in gaps[:5]) + ("…" if len(gaps) > 5 else "")
            readiness.problems.append(Problem("check", "Lesson list", f"No lesson numbered {shown}."))


def _range_problems(item: LibraryItem, readiness: Readiness) -> None:
    checks = (
        ("days_per_week", item.days_per_week, 1, 7, "Days a week run from 1 to 7."),
        ("minutes_per_session", item.minutes_per_session, 1, 300, "A session runs from 1 to 300 minutes."),
        ("lesson_count", item.lesson_count, 1, 1000, "Lesson counts run from 1 to 1000."),
        ("total_pages", item.total_pages, 1, 5000, "Page counts run from 1 to 5000."),
    )
    for name, value, low, high, message in checks:
        if value is not None and not low <= value <= high:
            readiness.problems.append(Problem("fix", name, message))
    if item.answer_key_start_page and item.total_pages and item.answer_key_start_page > item.total_pages:
        readiness.problems.append(Problem("fix", "answer_key_start_page", "The answer key starts past the last page."))


def readiness(item: LibraryItem) -> Readiness:
    result = Readiness()
    _need(result, "title", "Title", bool(item.title))
    _text_problems(result, "Title", item.title)
    _text_problems(result, "Author", item.author)
    _range_problems(item, result)

    if item.kind == READING_BOOK:
        _need(result, "author", "Author", bool(item.author))
        _need(result, "total_pages", "Total pages", bool(item.total_pages))
        _chapter_problems(item, result)
    elif item.kind == WORKBOOK:
        _need(result, "subject_code", "Subject", bool(item.subject_code))
        _need(result, "grade", "Grade", bool(item.grade))
        _need(result, "total_pages", "Total pages", bool(item.total_pages))
        _need(result, "chapters", "Chapters and their start pages", bool(item.chapters))
        _chapter_problems(item, result)
    elif item.kind == TEXTBOOK:
        for name, label in (("publisher", "Publisher"), ("edition", "Edition or year"),
                            ("subject_code", "Subject"), ("grade", "Grade"), ("total_pages", "Total pages")):
            _need(result, name, label, bool(getattr(item, name)),
                  WHY.get(name) if name != "total_pages" else "Curiculy checks every lesson's pages fit inside the book.")
        result.lessons_total = len(item.lessons)
        result.lessons_with_names = sum(1 for lesson in item.lessons if lesson.name)
        result.lessons_with_pages = sum(
            1 for lesson in item.lessons if lesson.start_page is not None and lesson.end_page is not None
        )
        if not item.for_parent:
            _need(result, "lessons", "The lesson list", bool(item.lessons))
            if item.lessons:
                unnamed = result.lessons_total - result.lessons_with_names
                if unnamed:
                    result.missing.append(Missing(
                        "lesson_names", f"{unnamed} of {result.lessons_total} lessons need a name", WHY["lesson_names"]))
                no_pages = result.lessons_total - result.lessons_with_pages
                if no_pages:
                    result.missing.append(Missing(
                        "lesson_pages", f"{no_pages} of {result.lessons_total} lessons need pages", WHY["lesson_pages"]))
        _lesson_problems(item, result)
    elif item.kind == ONLINE_PROGRAM:
        _need(result, "website_url", "Website link", bool(item.website_url))
        _need(result, "subject_code", "Subject", bool(item.subject_code))
        _need(result, "grade", "Grade", bool(item.grade))
        _need(result, "measure", "Lessons or minutes", item.measure in MEASURES)
        if item.measure == "lessons":
            _need(result, "lesson_count", "Number of lessons", bool(item.lesson_count))
        if item.measure == "minutes":
            _need(result, "minutes_per_session", "Minutes a session", bool(item.minutes_per_session))
        _need(result, "days_per_week", "Days a week", bool(item.days_per_week),
              "The calendar schedules online work on this many days a week.")
        if item.website_url and not item.website_url.startswith("https://"):
            result.problems.append(Problem("check", "Website link", "Links should start with https://"))
    return result
