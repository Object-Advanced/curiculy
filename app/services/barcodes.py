"""The ISBN from a photo of a book's barcode.

For phones whose browser can't scan live (iPhones): the parent takes a photo,
and OpenCV's EAN-13 reader finds the barcode. It reads best when the bars are
a few pixels wide, so the photo is tried at several sizes, and turned a
quarter in case it was taken sideways. The photo is read in memory and never
stored.
"""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.utils.isbn import is_valid_isbn10, is_valid_isbn13, to_isbn13

MAX_BYTES = 15 * 1024 * 1024
WIDTHS = (800, 1000, 600, 1200, 1600, 400)


class NotAnImage(ValueError):
    """The upload wasn't a photo."""


def isbn_from_barcode(text: str | None) -> str | None:
    """An ISBN-13 from what a barcode says, or None if it isn't a book's ISBN.
    Book barcodes are EAN-13 numbers starting 978 or 979."""
    digits = "".join(char for char in (text or "") if char.isdigit() or char in "Xx")
    if len(digits) == 13 and digits[:3] in {"978", "979"} and is_valid_isbn13(digits):
        return digits
    if len(digits) == 10 and is_valid_isbn10(digits):
        return to_isbn13(digits)
    return None


def _open(data: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(data)) as image:
            gray = ImageOps.exif_transpose(image).convert("L")
            return np.array(gray)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise NotAnImage("That isn't a photo.") from error


def read_barcode(data: bytes) -> tuple[str | None, bool]:
    """(the ISBN, whether some other barcode was found instead)."""
    image = _open(data)
    detector = cv2.barcode.BarcodeDetector()
    found_other = False
    for turned in (image, np.rot90(image)):
        height, width = turned.shape[:2]
        for target in WIDTHS:
            scaled = cv2.resize(turned, (target, max(1, round(height * target / width))), interpolation=cv2.INTER_AREA)
            text = detector.detectAndDecode(scaled)[0]
            if not text:
                continue
            isbn = isbn_from_barcode(text)
            if isbn:
                return isbn, False
            found_other = True
    return None, found_other
