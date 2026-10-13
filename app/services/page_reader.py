"""Reading a printed page from a photo: a contents page or a publisher's lesson list.

Tesseract (already in the image, for scanned PDFs) reads the printed text.
The dotted leaders between a chapter's name and its page confuse it, so specks
much smaller than the letters are erased from the photo first. Each line is
then tidied for the same rules as pasting: any leaders left are cut, and
look-alike letters in the page number are fixed ("L45" is 145). Lines without a page number (headings
like "Contents") are left out. The parent checks the result before anything
is saved. The photo is read in memory and never stored.
"""

from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 15 * 1024 * 1024
# Phone photos are resized to this width: big enough for book print, small
# enough that Tesseract reads the dotted leaders as dots.
MAX_WIDTH = 1800
OCR_TIMEOUT_SECONDS = 45
# One CPU-heavy read at a time per pair of requests; others wait their turn.
_SLOTS = threading.BoundedSemaphore(2)

_LEADER = re.compile(r"(?:[.·•…_\-–—:;,~+=*]\s?){3,}")
_PAGE_TOKEN = re.compile(r"[0-9OoIlLSB|]{1,4}(?:\s*[-–]\s*[0-9OoIlLSB|]{1,4})?")
_LOOK_ALIKES = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "L": "1", "|": "1", "S": "5", "B": "8"})


class NotAnImage(ValueError):
    """The upload wasn't a photo."""


class ReaderBusy(RuntimeError):
    """Too many pages being read right now."""


@dataclass(frozen=True)
class PageReading:
    lines: list[str]
    left_out: int


def _page_number(token: str) -> str | None:
    fixed = token.translate(_LOOK_ALIKES)
    fixed = re.sub(r"\s*[-–]\s*", "-", fixed)
    return fixed if re.fullmatch(r"\d{1,4}(?:-\d{1,4})?", fixed) else None


def clean_line(line: str) -> str | None:
    """A line ready for the paste rules ("Addition 5", "12 The Lost Dog 45-49"),
    or None when it has no page number."""
    line = " ".join(line.split())
    if not line:
        return None
    leader = _LEADER.search(line)
    if leader:
        name = line[: leader.start()].strip(" .:-")
        tokens = _PAGE_TOKEN.findall(line[leader.start():])
        page = next((number for number in map(_page_number, reversed(tokens)) if number), None)
        return f"{name} {page}" if name and page else None
    spaced = re.fullmatch(r"(.*\S)\s+([0-9OoIlLSB|]{1,4}\s*[-–]\s*[0-9OoIlLSB|]{1,4})", line)
    if spaced and _page_number(spaced.group(2)):
        return f"{spaced.group(1)} {_page_number(spaced.group(2))}"
    head, _, last = line.rpartition(" ")
    page = _page_number(last) if head else None
    if page:
        return f"{head} {page}"
    return line if re.search(r"\d", line) and not re.fullmatch(r"[\d\s.,:-]+", line) else None


def erase_specks(gray: np.ndarray) -> np.ndarray:
    """Erase marks much smaller than the letters: dotted leaders, dust."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    heights = stats[1:, cv2.CC_STAT_HEIGHT]
    if count < 2:
        return gray
    # The letters' height. Dotted leaders can outnumber the letters, so not the
    # median mark: one near the top of the range.
    letters = float(np.percentile(heights, 90))
    small = (stats[:, cv2.CC_STAT_HEIGHT] < 0.3 * letters) & (stats[:, cv2.CC_STAT_WIDTH] < 0.3 * letters)
    small[0] = False  # the background
    cleaned = gray.copy()
    cleaned[np.isin(labels, np.nonzero(small)[0])] = 255
    return cleaned


def _prepare(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            page = ImageOps.exif_transpose(image).convert("L")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise NotAnImage("That isn't a photo.") from error
    if page.width > MAX_WIDTH:
        page = page.resize((MAX_WIDTH, round(page.height * MAX_WIDTH / page.width)))
    page = Image.fromarray(erase_specks(np.array(ImageOps.autocontrast(page))))
    buffer = BytesIO()
    page.save(buffer, format="PNG")
    return buffer.getvalue()


def _tesseract(png: bytes, psm: str) -> str:
    result = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", psm],
        input=png,
        capture_output=True,
        timeout=OCR_TIMEOUT_SECONDS,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _cleaned(text: str) -> tuple[list[str], int]:
    raw = [line for line in text.splitlines() if line.strip()]
    lines = [cleaned for cleaned in map(clean_line, raw) if cleaned]
    return lines, len(raw) - len(lines)


def read_page(data: bytes) -> PageReading:
    png = _prepare(data)
    if not _SLOTS.acquire(timeout=20):
        raise ReaderBusy("Curiculy is reading other pages right now. Try again in a minute.")
    try:
        # One block of text first; if few lines end in a page number, try
        # reading it as a column instead and keep whichever read better.
        lines, left_out = _cleaned(_tesseract(png, "6"))
        if len(lines) < max(2, (len(lines) + left_out) // 2):
            other, other_left_out = _cleaned(_tesseract(png, "4"))
            if len(other) > len(lines):
                lines, left_out = other, other_left_out
    finally:
        _SLOTS.release()
    return PageReading(lines=lines, left_out=left_out)
