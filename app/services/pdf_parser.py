"""Extract plain text from an uploaded pacing-guide PDF.

Curriculum PDFs often hide the real schedule in a table or a scanned image.
A header like "36 weeks" is selectable text; the daily blocks are not. This
module reconstructs reading-order lines, pulls table cells, and OCRs sparse
pages so Ollama sees the timetable instead of an empty year.
"""

from __future__ import annotations

import logging
import re

import pymupdf as fitz

logger = logging.getLogger(__name__)

MAX_OCR_PAGES = 20
_LINE_Y_TOLERANCE = 4
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_SUBJECT_RE = re.compile(
    r"\b(bible|phonics|reading|math|arithmetic|writing|penmanship|seatwork|"
    r"science|history|spelling|handwriting|grammar|language|art|music|poetry|"
    r"social studies|health|geography|numbers|letters)\b",
    re.IGNORECASE,
)
_LESSON_RE = re.compile(
    r"\b(lesson\s+\d+|chapter\s+\d+|day\s+\d+|unit\s+\d+)\b",
    re.IGNORECASE,
)
_METADATA_WORD_RE = re.compile(
    r"^(week|weeks|grade|kindergarten|curriculum|teacher|edition|copyright|"
    r"page|pages|abeka|saxon|homeschool|program|schedule|daily|year)$",
    re.IGNORECASE,
)


def is_sparse_curriculum_text(text: str) -> bool:
    """True when the extract is a cover blurb, not a usable schedule."""
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if not compact:
        return True
    if _TIME_RE.search(compact) or _SUBJECT_RE.search(compact) or _LESSON_RE.search(compact):
        return False
    if re.search(r"\b(p\.|pp\.|pages?)\s*\d+\s*[-–]\s*\d+", compact, re.IGNORECASE):
        return False
    if re.search(r"\b(p\.|pp\.)\s*\d+", compact, re.IGNORECASE):
        return False
    words = [
        word
        for word in re.findall(r"[A-Za-z]{3,}", compact)
        if not _METADATA_WORD_RE.fullmatch(word)
    ]
    if len(compact) < 40:
        return True
    return len(words) < 8


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Return reading-order text, tables, and OCR for sparse/image pages."""
    document = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        chunks: list[str] = []
        ocr_pages = 0
        for page in document:
            page_text = _extract_page_text(page)
            if is_sparse_curriculum_text(page_text) and ocr_pages < MAX_OCR_PAGES:
                ocr_text = _ocr_page(page)
                ocr_pages += 1
                if ocr_text.strip() and ocr_text.strip() not in page_text:
                    page_text = "\n\n".join(
                        part for part in (page_text, ocr_text) if part.strip()
                    )
            if page_text.strip():
                chunks.append(page_text.strip())
        return "\n\n".join(chunks)
    finally:
        document.close()


def _extract_page_text(page: fitz.Page) -> str:
    parts = [_reading_order_text(page), _table_text(page)]
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = re.sub(r"\s+", " ", part).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(part.strip())
    return "\n\n".join(unique)


def _reading_order_text(page: fitz.Page) -> str:
    words = page.get_text("words") or []
    if words:
        lines = _lines_from_words(words)
        if lines.strip():
            return lines
    try:
        return (page.get_text("text", sort=True) or "").strip()
    except TypeError:
        return (page.get_text("text") or "").strip()


def _lines_from_words(words: list[tuple]) -> str:
    ordered = sorted(words, key=lambda word: (round(float(word[1])), float(word[0])))
    lines: list[str] = []
    current: list[str] = []
    current_y: float | None = None
    for word in ordered:
        token = str(word[4]).strip()
        if not token:
            continue
        y = float(word[1])
        if current_y is None or abs(y - current_y) <= _LINE_Y_TOLERANCE:
            current.append(token)
            if current_y is None:
                current_y = y
        else:
            lines.append(" ".join(current))
            current = [token]
            current_y = y
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _table_text(page: fitz.Page) -> str:
    try:
        finder = page.find_tables()
    except Exception:
        return ""
    tables = getattr(finder, "tables", None) or []
    rendered: list[str] = []
    for table in tables:
        markdown = ""
        try:
            markdown = (table.to_markdown() or "").strip()
        except Exception:
            markdown = ""
        if not markdown:
            try:
                rows = table.extract() or []
            except Exception:
                continue
            markdown = "\n".join(
                "\t".join((cell or "").strip() for cell in row) for row in rows
            ).strip()
        if markdown:
            rendered.append(markdown)
    return "\n\n".join(rendered)


def _ocr_page(page: fitz.Page) -> str:
    try:
        textpage = page.get_textpage_ocr(dpi=200, full=True, language="eng")
        return (page.get_text("text", textpage=textpage, sort=True) or "").strip()
    except Exception:
        logger.info("OCR skipped for a PDF page; Tesseract may be unavailable")
        return ""
