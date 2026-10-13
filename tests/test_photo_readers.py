"""Reading photos: a book's barcode (its ISBN), and a printed contents page or lesson list."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.services.barcodes import isbn_from_barcode
from app.services.page_reader import clean_line

# EAN-13, the barcode on the back of every book: each digit's bar pattern.
_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_R = ["".join("1" if bit == "0" else "0" for bit in code) for code in _L]
_G = [code[::-1] for code in _R]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def barcode_photo(digits: str, module: int = 10, turned: bool = False) -> bytes:
    """A phone-sized photo of an EAN-13 barcode on a grey page."""
    bits = "101"
    for digit, parity in zip(digits[1:7], _PARITY[int(digits[0])]):
        bits += (_L if parity == "L" else _G)[int(digit)]
    bits += "01010" + "".join(_R[int(digit)] for digit in digits[7:]) + "101"
    label = Image.new("L", (len(bits) * module + 24 * module, 60 * module), 255)
    draw = ImageDraw.Draw(label)
    for index, bit in enumerate(bits):
        if bit == "1":
            left = 12 * module + index * module
            draw.rectangle([left, 4 * module, left + module - 1, 56 * module], fill=0)
    photo = Image.new("L", (label.width + 1400, label.height + 1800), 228)
    photo.paste(label, (700, 900))
    if turned:
        photo = photo.rotate(90, expand=True)
    buffer = BytesIO()
    photo.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def contents_photo(lines: list[str]) -> bytes:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 34)
    page = Image.new("L", (1200, 80 + 60 * len(lines)), 255)
    draw = ImageDraw.Draw(page)
    for index, line in enumerate(lines):
        draw.text((60, 40 + 60 * index), line, font=font, fill=0)
    buffer = BytesIO()
    page.rotate(1.5, expand=True, fillcolor=255).save(buffer, format="PNG")
    return buffer.getvalue()


class TestBarcodes:
    def test_only_book_numbers_are_isbns(self) -> None:
        assert isbn_from_barcode("9780064400558") == "9780064400558"
        assert isbn_from_barcode("0-06-440055-7") == "9780064400558"
        assert isbn_from_barcode("4006381333931") is None  # a pencil, not a book
        assert isbn_from_barcode("9780064400559") is None  # a misread check digit

    @pytest.mark.parametrize("turned", [False, True])
    def test_a_photo_of_the_back_cover(self, client: TestClient, turned: bool) -> None:
        photo = barcode_photo("9780064400558", turned=turned)
        body = client.post("/api/library/read-barcode", files={"file": ("back.jpg", photo, "image/jpeg")}).json()
        assert body == {"isbn": "9780064400558", "message": "Found ISBN 9780064400558."}

    def test_another_kind_of_barcode(self, client: TestClient) -> None:
        body = client.post(
            "/api/library/read-barcode", files={"file": ("x.jpg", barcode_photo("4006381333931"), "image/jpeg")}
        ).json()
        assert body["isbn"] is None and "starts with 978 or 979" in body["message"]

    def test_no_barcode_and_not_a_photo(self, client: TestClient) -> None:
        blank = BytesIO()
        Image.new("L", (800, 600), 230).save(blank, format="PNG")
        body = client.post("/api/library/read-barcode", files={"file": ("x.png", blank.getvalue(), "image/png")}).json()
        assert body["isbn"] is None and "No barcode found" in body["message"]
        assert client.post("/api/library/read-barcode", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 415


class TestContentsPages:
    @pytest.mark.parametrize(
        ("line", "cleaned"),
        [
            ("1 Addition .............6 5", "1 Addition 5"),
            ("1 Addition ..........00.5", "1 Addition 5"),
            ("2 Subtraction ............+++ 31", "2 Subtraction 31"),
            ("Answer Key ....--ecceee L45", "Answer Key 145"),
            ("12 The Lost Dog 45-49", "12 The Lost Dog 45-49"),
            ("Test 2, 54 – 55", "Test 2, 54-55"),
            ("Contents", None),
            ("4 Time and Money .........---", None),
            ("", None),
        ],
    )
    def test_lines_are_tidied_for_the_paste_rules(self, line: str, cleaned: str | None) -> None:
        assert clean_line(line) == cleaned

    def test_a_photo_of_a_contents_page(self, client: TestClient) -> None:
        photo = contents_photo([
            "Contents", "",
            "1  Addition .................. 5",
            "2  Subtraction ............... 31",
            "3  Fractions ................. 62",
            "4  Time and Money ............ 101",
        ])
        body = client.post("/api/library/read-page", files={"file": ("toc.png", photo, "image/png")}).json()
        assert body["text"].splitlines() == [
            "1 Addition 5", "2 Subtraction 31", "3 Fractions 62", "4 Time and Money 101",
        ]
        assert body["lines"] == 4 and body["left_out"] == 1  # "Contents" has no page number
        assert "Check them against the page" in body["message"]

    def test_a_photo_of_a_lesson_list_keeps_page_ranges(self, client: TestClient) -> None:
        photo = contents_photo(["Lesson Plan", "1  Adding  1-4", "2  Subtracting  5-8", "Test 1  9-10"])
        body = client.post("/api/library/read-page", files={"file": ("plan.png", photo, "image/png")}).json()
        assert body["text"].splitlines() == ["1 Adding 1-4", "2 Subtracting 5-8", "Test 1 9-10"]

    def test_not_a_photo(self, client: TestClient) -> None:
        response = client.post("/api/library/read-page", files={"file": ("x.txt", b"hello", "text/plain")})
        assert response.status_code == 415
