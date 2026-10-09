"""OpenCV week-sheet slicer: ArUco flatten, QR identity, fixed cell crops."""

from __future__ import annotations

import base64
import json

import cv2
import numpy as np
import pytest
import qrcode
from qrcode.image.pil import PilImage

from app.services.paper_parser import INVALID_QR, MISSING_CORNERS, parse_paper_upload
from app.services.paper_template import (
    ARUCO_IDS,
    FORM_ID,
    FORM_VERSION,
    LESSON_ROWS,
    MARKER_SIZE_IN,
    PAGE_HEIGHT_PX,
    PAGE_WIDTH_PX,
    WEEKDAYS,
    inches_to_px,
    marker_destination_px,
    qr_box_px,
)


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _decode_png_b64(payload: str) -> np.ndarray:
    raw = base64.b64decode(payload)
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert image is not None and image.size > 0
    return image


def _place_markers(canvas: np.ndarray) -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    size = inches_to_px(MARKER_SIZE_IN)
    for marker_id, (cx, cy) in marker_destination_px().items():
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size)
        x0 = int(round(cx - size / 2))
        y0 = int(round(cy - size / 2))
        canvas[y0 : y0 + size, x0 : x0 + size] = marker


def _place_qr(canvas: np.ndarray, curriculum_id: int | None) -> None:
    payload = json.dumps(
        {"form": FORM_ID, "version": FORM_VERSION, "curriculum_id": curriculum_id},
        separators=(",", ":"),
    )
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    pil = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    array = np.array(pil.convert("L"))
    y1, y2, x1, x2 = qr_box_px()
    canvas[y1:y2, x1:x2] = cv2.resize(
        array, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST
    )


def _synthetic_sheet(curriculum_id: int | None = 42, *, with_qr: bool = True) -> bytes:
    canvas = np.full((PAGE_HEIGHT_PX, PAGE_WIDTH_PX), 255, dtype=np.uint8)
    _place_markers(canvas)
    if with_qr:
        _place_qr(canvas, curriculum_id)
    return _encode_png(canvas)


class TestParsePaperUploadErrors:
    def test_blank_image_raises_missing_corners(self) -> None:
        blank = np.full((400, 400), 255, dtype=np.uint8)
        with pytest.raises(ValueError, match="Could not detect all 4 page corners"):
            parse_paper_upload(_encode_png(blank))

    def test_random_noise_raises_missing_corners(self) -> None:
        rng = np.random.default_rng(0)
        noise = rng.integers(0, 256, size=(480, 640), dtype=np.uint8)
        with pytest.raises(ValueError, match="Could not detect all 4 page corners") as caught:
            parse_paper_upload(_encode_png(noise))
        assert str(caught.value) == MISSING_CORNERS


class TestParsePaperUploadSynthetic:
    def test_returns_week_grid_crops(self) -> None:
        result = parse_paper_upload(_synthetic_sheet(42))

        assert result["curriculum_id"] == 42
        assert set(result) == {"curriculum_id", "week_number_image", "rows"}
        assert len(result["rows"]) == LESSON_ROWS
        _decode_png_b64(result["week_number_image"])
        for row in result["rows"]:
            assert set(row) == {"time_image", "days"}
            _decode_png_b64(row["time_image"])
            assert len(row["days"]) == len(WEEKDAYS)
            for day in row["days"]:
                _decode_png_b64(day)

    def test_null_curriculum_id_is_preserved(self) -> None:
        result = parse_paper_upload(_synthetic_sheet(None))
        assert result["curriculum_id"] is None
        assert len(result["rows"]) == 6
        assert all(len(row["days"]) == 5 for row in result["rows"])

    def test_markers_without_qr_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid or missing Curiculy QR code") as caught:
            parse_paper_upload(_synthetic_sheet(with_qr=False))
        assert str(caught.value) == INVALID_QR

    def test_four_marker_ids_are_the_page_corners(self) -> None:
        assert ARUCO_IDS == {"tl": 0, "tr": 1, "bl": 2, "br": 3}
        assert PAGE_WIDTH_PX == 2550
        assert PAGE_HEIGHT_PX == 3300
