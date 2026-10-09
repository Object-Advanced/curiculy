"""Printable week sheet for paper-to-digital pacing-guide intake.

ArUco corners and a QR payload are the schema a later photo step will crop.
WeasyPrint is imported only when rendering bytes so tests can mock HTML
without Cairo.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import cv2
import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape
from qrcode.image.pil import PilImage

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Layout constants reused by the scan/crop step. Inch values must match
# paper_template.html; pixel values are that geometry at SCAN_DPI.
FORM_ID = "week_grid"
FORM_VERSION = 1
PAGE_WIDTH_IN = 8.5
PAGE_HEIGHT_IN = 11.0
MARKER_SIZE_IN = 0.65
MARKER_INSET_IN = 0.12
QR_SIZE_IN = 0.85
LESSON_ROWS = 6
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
ARUCO_IDS = {"tl": 0, "tr": 1, "bl": 2, "br": 3}
_ARUCO_PIXELS = 240

SCAN_DPI = 300
PAGE_WIDTH_PX = 2550
PAGE_HEIGHT_PX = 3300
SHEET_MARGIN_X_IN = 0.55
SHEET_MARGIN_Y_IN = 0.9
HEADER_GAP_IN = 0.12
BRAND_WIDTH_IN = 2.4
WEEK_FIELD_WIDTH_IN = 1.35
WEEK_BOX_WIDTH_IN = 1.1
WEEK_BOX_HEIGHT_IN = 0.7
WEEK_LABEL_PT = 9
WEEK_LABEL_MARGIN_CSS_PX = 4
TIME_COLUMN_IN = 0.85
GRID_HEADER_ROW_IN = 0.32
CROP_INSET_PX = 8

# (y1, y2, x1, x2) on the flattened 2550x3300 page.
CropBox = tuple[int, int, int, int]


def inches_to_px(inches: float) -> int:
    return int(round(inches * SCAN_DPI))


def marker_destination_px() -> dict[int, tuple[float, float]]:
    """Homography destinations: ArUco *centers* on the 300 DPI letter page.

    ``MARKER_INSET_IN`` is the gap from the page edge to the marker tile, so
    the center is inset plus half the tile.
    """
    half = MARKER_SIZE_IN / 2
    inset = MARKER_INSET_IN + half
    return {
        ARUCO_IDS["tl"]: (inset * SCAN_DPI, inset * SCAN_DPI),
        ARUCO_IDS["tr"]: ((PAGE_WIDTH_IN - inset) * SCAN_DPI, inset * SCAN_DPI),
        ARUCO_IDS["bl"]: (inset * SCAN_DPI, (PAGE_HEIGHT_IN - inset) * SCAN_DPI),
        ARUCO_IDS["br"]: (
            (PAGE_WIDTH_IN - inset) * SCAN_DPI,
            (PAGE_HEIGHT_IN - inset) * SCAN_DPI,
        ),
    }


def _pt_to_px(points: float) -> int:
    return int(round(points * SCAN_DPI / 72))


def _css_px_to_px(css_px: float) -> int:
    return int(round(css_px * SCAN_DPI / 96))


def _clamp_box(y1: int, y2: int, x1: int, x2: int) -> CropBox:
    y1 = max(0, min(PAGE_HEIGHT_PX - 1, y1))
    x1 = max(0, min(PAGE_WIDTH_PX - 1, x1))
    y2 = max(y1 + 1, min(PAGE_HEIGHT_PX, y2))
    x2 = max(x1 + 1, min(PAGE_WIDTH_PX, x2))
    return y1, y2, x1, x2


def _inset_box(y1: int, y2: int, x1: int, x2: int, inset: int = CROP_INSET_PX) -> CropBox:
    return _clamp_box(y1 + inset, y2 - inset, x1 + inset, x2 - inset)


def _split_span(start: int, end: int, count: int) -> list[tuple[int, int]]:
    length = end - start
    base, remainder = divmod(length, count)
    spans: list[tuple[int, int]] = []
    cursor = start
    for index in range(count):
        size = base + (1 if index < remainder else 0)
        spans.append((cursor, cursor + size))
        cursor += size
    return spans


def qr_box_px() -> CropBox:
    """QR tile on the flattened page (matches the header flex layout)."""
    sheet_left = inches_to_px(SHEET_MARGIN_X_IN)
    sheet_right = inches_to_px(PAGE_WIDTH_IN - SHEET_MARGIN_X_IN)
    brand_w = inches_to_px(BRAND_WIDTH_IN)
    qr_s = inches_to_px(QR_SIZE_IN)
    week_field_w = inches_to_px(WEEK_FIELD_WIDTH_IN)
    free = (sheet_right - sheet_left) - brand_w - qr_s - week_field_w
    gap = free // 2
    x1 = sheet_left + brand_w + gap
    y1 = inches_to_px(SHEET_MARGIN_Y_IN)
    return y1, y1 + qr_s, x1, x1 + qr_s


def flattened_crop_boxes() -> dict[str, object]:
    """Week, time, and lesson cell boxes on the flattened 2550x3300 page."""
    sheet_left = inches_to_px(SHEET_MARGIN_X_IN)
    sheet_right = inches_to_px(PAGE_WIDTH_IN - SHEET_MARGIN_X_IN)
    sheet_top = inches_to_px(SHEET_MARGIN_Y_IN)
    sheet_bottom = inches_to_px(PAGE_HEIGHT_IN - SHEET_MARGIN_Y_IN)

    label_h = _pt_to_px(WEEK_LABEL_PT) + _css_px_to_px(WEEK_LABEL_MARGIN_CSS_PX)
    week_box_h = inches_to_px(WEEK_BOX_HEIGHT_IN)
    week_box_w = inches_to_px(WEEK_BOX_WIDTH_IN)
    week_field_w = inches_to_px(WEEK_FIELD_WIDTH_IN)
    header_h = max(inches_to_px(QR_SIZE_IN), label_h + week_box_h)

    week_pad = (week_field_w - week_box_w) // 2
    week_x1 = sheet_right - week_field_w + week_pad
    week_y1 = sheet_top + label_h
    week = _inset_box(week_y1, week_y1 + week_box_h, week_x1, week_x1 + week_box_w)

    grid_top = sheet_top + header_h + inches_to_px(HEADER_GAP_IN)
    head_h = inches_to_px(GRID_HEADER_ROW_IN)
    data_top = grid_top + head_h
    time_w = inches_to_px(TIME_COLUMN_IN)
    time_right = sheet_left + time_w

    row_spans = _split_span(data_top, sheet_bottom, LESSON_ROWS)
    day_spans = _split_span(time_right, sheet_right, len(WEEKDAYS))

    rows = []
    for y1, y2 in row_spans:
        rows.append(
            {
                "time": _inset_box(y1, y2, sheet_left, time_right),
                "days": [_inset_box(y1, y2, x1, x2) for x1, x2 in day_spans],
            }
        )
    return {"week": week, "rows": rows}


def qr_payload(curriculum_id: int | None) -> str:
    return json.dumps(
        {
            "form": FORM_ID,
            "version": FORM_VERSION,
            "curriculum_id": curriculum_id,
        },
        separators=(",", ":"),
    )


def _png_data_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def qr_png_bytes(curriculum_id: int | None) -> bytes:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_payload(curriculum_id))
    qr.make(fit=True)
    image = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(curriculum_id: int | None) -> str:
    return _png_data_uri(qr_png_bytes(curriculum_id))


def aruco_png_bytes(marker_id: int) -> bytes:
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    image = cv2.aruco.generateImageMarker(dictionary, marker_id, _ARUCO_PIXELS)
    border = max(24, _ARUCO_PIXELS // 8)
    image = cv2.copyMakeBorder(
        image, border, border, border, border, cv2.BORDER_CONSTANT, value=255
    )
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode ArUco marker {marker_id}")
    return encoded.tobytes()


@lru_cache(maxsize=1)
def aruco_data_uris() -> dict[str, str]:
    return {
        corner: _png_data_uri(aruco_png_bytes(marker_id))
        for corner, marker_id in ARUCO_IDS.items()
    }


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_paper_template_html(curriculum_id: int | None = None) -> str:
    template = _jinja_env().get_template("paper_template.html")
    return template.render(
        markers=aruco_data_uris(),
        qr_data_uri=qr_data_uri(curriculum_id),
        curriculum_id=curriculum_id,
        weekdays=WEEKDAYS,
        lesson_rows=range(LESSON_ROWS),
    )


def generate_paper_template_pdf(curriculum_id: int | None) -> bytes:
    """Turn the week-sheet HTML into PDF bytes."""
    from weasyprint import HTML

    html_document = render_paper_template_html(curriculum_id)
    pdf = HTML(string=html_document, base_url=str(_TEMPLATES_DIR)).write_pdf()
    if not pdf:
        raise RuntimeError("WeasyPrint returned an empty PDF")
    return pdf
