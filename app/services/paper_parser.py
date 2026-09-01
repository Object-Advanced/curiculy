"""Flatten a photographed week sheet and slice the handwriting cells.

Geometry only: ArUco homography, QR identity, and fixed crops from the
shared paper_template layout. Handwriting OCR is a later pass.
"""

from __future__ import annotations

import base64
import json

import cv2
import numpy as np

from app.services.paper_template import (
    ARUCO_IDS,
    FORM_ID,
    PAGE_HEIGHT_PX,
    PAGE_WIDTH_PX,
    CropBox,
    flattened_crop_boxes,
    marker_destination_px,
    qr_box_px,
)

MISSING_CORNERS = (
    "Could not detect all 4 page corners. "
    "Please ensure the whole page is visible and well-lit."
)
INVALID_QR = "Invalid or missing Curiculy QR code."

_REQUIRED_MARKER_IDS = frozenset(ARUCO_IDS.values())


def parse_paper_upload(image_bytes: bytes) -> dict:
    gray = _decode_grayscale(image_bytes)
    centers = _detect_marker_centers(gray)
    flat = _flatten_page(gray, centers)
    payload = _read_qr_payload(flat)
    crops = flattened_crop_boxes()
    rows = [
        {
            "time_image": _png_b64(_crop(flat, row["time"])),
            "days": [_png_b64(_crop(flat, box)) for box in row["days"]],
        }
        for row in crops["rows"]
    ]
    return {
        "curriculum_id": _curriculum_id(payload),
        "week_number_image": _png_b64(_crop(flat, crops["week"])),
        "rows": rows,
    }


def _decode_grayscale(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(MISSING_CORNERS)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _detect_marker_centers(gray: np.ndarray) -> dict[int, tuple[float, float]]:
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters(),
    )
    corners, ids, _rejected = detector.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        raise ValueError(MISSING_CORNERS)
    centers: dict[int, tuple[float, float]] = {}
    for marker_corners, marker_id in zip(corners, ids.flatten().tolist(), strict=True):
        points = marker_corners.reshape(-1, 2)
        cx, cy = points.mean(axis=0)
        centers[int(marker_id)] = (float(cx), float(cy))
    if not _REQUIRED_MARKER_IDS <= centers.keys():
        raise ValueError(MISSING_CORNERS)
    return centers


def _flatten_page(
    gray: np.ndarray, centers: dict[int, tuple[float, float]]
) -> np.ndarray:
    destinations = marker_destination_px()
    order = (ARUCO_IDS["tl"], ARUCO_IDS["tr"], ARUCO_IDS["bl"], ARUCO_IDS["br"])
    source = np.array([centers[marker_id] for marker_id in order], dtype=np.float32)
    target = np.array([destinations[marker_id] for marker_id in order], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(source, target)
    return cv2.warpPerspective(gray, transform, (PAGE_WIDTH_PX, PAGE_HEIGHT_PX))


def _read_qr_payload(flat: np.ndarray) -> dict:
    detector = cv2.QRCodeDetector()
    for candidate in _qr_search_images(flat):
        data, _points, _straight = detector.detectAndDecode(candidate)
        if not data:
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(INVALID_QR) from exc
        if not isinstance(payload, dict) or payload.get("form") != FORM_ID:
            raise ValueError(INVALID_QR)
        return payload
    raise ValueError(INVALID_QR)


def _qr_search_images(flat: np.ndarray) -> tuple[np.ndarray, ...]:
    y1, y2, x1, x2 = qr_box_px()
    pad = 24
    header = flat[: max(1, flat.shape[0] // 4)]
    qr_region = flat[
        max(0, y1 - pad) : min(flat.shape[0], y2 + pad),
        max(0, x1 - pad) : min(flat.shape[1], x2 + pad),
    ]
    return (flat, header, qr_region)


def _curriculum_id(payload: dict) -> int | None:
    raw = payload.get("curriculum_id")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(INVALID_QR) from exc


def _crop(image: np.ndarray, box: CropBox) -> np.ndarray:
    y1, y2, x1, x2 = box
    tile = image[y1:y2, x1:x2]
    if tile.size == 0:
        raise ValueError(MISSING_CORNERS)
    return tile


def _png_b64(image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("failed to encode cell crop")
    return base64.b64encode(encoded.tobytes()).decode("ascii")
