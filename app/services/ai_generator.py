"""Draft a syllabus from a book's page range.

Real generation will call a local LLM with the book's table of contents. Until
that exists the split is arithmetic: the page range is divided into as many
near-equal chunks as there are lessons.

The mock is deterministic on purpose. It lets the preview endpoint be tested
without a model in the loop, and it pins down the contract the model will have to
satisfy afterwards — lessons numbered from one, in page order, covering the
requested range exactly once with no gap and no overlap. A model that returns
something else is wrong, not creative.
"""

from app.schemas.pacing import SyllabusLesson

# Both Assignment.title and CurriculumUnit.title are String(255), and a generated
# title flows into each of them.
MAX_TITLE_LENGTH = 255


class SyllabusGenerationError(ValueError):
    """No syllabus could be drafted for the requested range."""


class SyllabusGenerator:
    """Splits a page range into lessons.

    Stateless, and swappable for an LLM-backed implementation with the same
    ``generate_syllabus`` signature.
    """

    def generate_syllabus(
        self,
        book_title: str,
        start_page: int,
        end_page: int,
        target_lessons: int,
        pages_per_day: int | None = None,
    ) -> list[SyllabusLesson]:
        """``target_lessons`` consecutive slices of pages ``start_page``-``end_page``.

        Without ``pages_per_day``, every slice is within one page of every other,
        so a remainder is absorbed across the range instead of landing on one
        lesson several times the length of its neighbours. With ``pages_per_day``,
        each lesson takes that many pages and the last lesson takes the leftover.
        """
        total_pages = self._validate(book_title, start_page, end_page, target_lessons)
        if pages_per_day is not None:
            return self._chunk_by_pace(book_title, start_page, end_page, pages_per_day)

        lessons: list[SyllabusLesson] = []
        for index in range(target_lessons):
            first = start_page + index * total_pages // target_lessons
            last = start_page + (index + 1) * total_pages // target_lessons - 1
            sequence = index + 1
            lessons.append(
                SyllabusLesson(
                    sequence=sequence,
                    title=_lesson_title(book_title, sequence, first, last),
                    start_page=first,
                    end_page=last,
                )
            )
        return lessons

    def _chunk_by_pace(
        self,
        book_title: str,
        start_page: int,
        end_page: int,
        pages_per_day: int,
    ) -> list[SyllabusLesson]:
        if pages_per_day < 1:
            raise SyllabusGenerationError(
                f"pages_per_day must be 1 or greater, got {pages_per_day}"
            )

        lessons: list[SyllabusLesson] = []
        cursor = start_page
        sequence = 1
        while cursor <= end_page:
            last = min(cursor + pages_per_day - 1, end_page)
            lessons.append(
                SyllabusLesson(
                    sequence=sequence,
                    title=_lesson_title(book_title, sequence, cursor, last),
                    start_page=cursor,
                    end_page=last,
                )
            )
            cursor = last + 1
            sequence += 1
        return lessons

    @staticmethod
    def _validate(book_title: str, start_page: int, end_page: int, target_lessons: int) -> int:
        if not book_title.strip():
            raise SyllabusGenerationError("a book title is required to draft a syllabus")
        if start_page < 1:
            raise SyllabusGenerationError(f"start_page must be 1 or greater, got {start_page}")
        if end_page < start_page:
            raise SyllabusGenerationError(
                f"end_page {end_page} precedes start_page {start_page}"
            )
        if target_lessons < 1:
            raise SyllabusGenerationError(
                f"target_lessons must be 1 or greater, got {target_lessons}"
            )

        total_pages = end_page - start_page + 1
        if target_lessons > total_pages:
            raise SyllabusGenerationError(
                f"pages {start_page} to {end_page} cannot be split into {target_lessons} "
                f"lessons; there are only {total_pages} pages to go around"
            )
        return total_pages


def _lesson_title(book_title: str, sequence: int, start_page: int, end_page: int) -> str:
    """A title a calendar tile can be read from on its own."""
    pages = f"p. {start_page}" if start_page == end_page else f"pp. {start_page}-{end_page}"
    prefix = f"Lesson {sequence}: "
    suffix = f" ({pages})"

    title = book_title.strip()
    room = MAX_TITLE_LENGTH - len(prefix) - len(suffix)
    if len(title) > room:
        title = title[: max(room - 3, 0)].rstrip() + "..."
    return f"{prefix}{title}{suffix}"
