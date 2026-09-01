"""Printable week sheet: ArUco corners, plan QR, Time + Monday–Friday grid.

WeasyPrint is patched so CI never talks to Cairo; HTML, ArUco, and QR are real.
"""

from __future__ import annotations

import base64
import json
import re

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.paper_template import (
    ARUCO_DICTIONARY,
    ARUCO_IDS,
    FORM_ID,
    FORM_VERSION,
    LESSON_ROWS,
    WEEKDAYS,
    aruco_data_uris,
    generate_paper_template_pdf,
    qr_data_uri,
    qr_payload,
    render_paper_template_html,
)

_DATA_URI_RE = re.compile(r'src="(data:image/png;base64,[^"]+)"')
_FAKE_PDF = b"%PDF-1.4 fake"


def _png_from_bytes(png_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(png_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_GRAYSCALE)
    assert image is not None
    return image


def _png_from_data_uri(uri: str) -> bytes:
    return base64.b64decode(uri.split(",", 1)[1])


def _decode_aruco_id(png_bytes: bytes) -> int:
    image = _png_from_bytes(png_bytes)
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    _corners, ids, _rejected = detector.detectMarkers(image)
    assert ids is not None and len(ids) == 1
    return int(ids.flatten()[0])


def _decode_qr(png_bytes: bytes) -> dict:
    data, _points, _straight = cv2.QRCodeDetector().detectAndDecode(
        _png_from_bytes(png_bytes)
    )
    assert data, "QRCodeDetector returned no payload"
    return json.loads(data)


@pytest.fixture
def fake_weasyprint(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    class FakeHTML:
        def __init__(self, string: str, **_kwargs: object) -> None:
            captured["html"] = string

        def write_pdf(self) -> bytes:
            return _FAKE_PDF

    monkeypatch.setattr("weasyprint.HTML", FakeHTML)
    return captured


class TestPaperTemplateHtml:
    def test_letter_page_markers_week_grid_and_plan_caption(self) -> None:
        html = render_paper_template_html(42)

        assert "@page { size: letter; margin: 0; }" in html
        assert "width: 8.5in" in html
        assert "height: 11in" in html
        assert html.count('class="marker') == 4
        assert 'class="week-box"' in html
        assert "Curiculy week sheet" in html
        assert ">Time<" in html
        for day in WEEKDAYS:
            assert day in html
        assert html.count('class="cell head"') == 6
        assert html.count("<col ") == 6
        assert "table-layout: fixed" in html
        assert 'class="time-col"' in html
        assert ">Thursday</th>" in html
        assert ">Friday</th>" in html
        assert "Jesson" not in html
        assert html.count('class="cell time-box"') == LESSON_ROWS
        assert html.count('class="cell lesson-box"') == LESSON_ROWS * len(WEEKDAYS)
        assert html.count('class="hint">time<') == LESSON_ROWS
        assert html.count('class="hint">lesson<') == LESSON_ROWS * len(WEEKDAYS)
        assert "Plan 42" in html
        uris = _DATA_URI_RE.findall(html)
        assert len(uris) == 5
        assert all(uri.startswith("data:image/png;base64,") for uri in uris)

    def test_omitted_curriculum_id_has_no_plan_caption(self) -> None:
        html = render_paper_template_html()
        assert "<p>Plan " not in html


class TestPaperTemplateMarkers:
    def test_aruco_ids_decode(self) -> None:
        uris = aruco_data_uris()
        decoded = {
            corner: _decode_aruco_id(_png_from_data_uri(uri))
            for corner, uri in uris.items()
        }
        assert decoded == ARUCO_IDS

    def test_html_embeds_four_distinct_markers(self) -> None:
        html = render_paper_template_html()
        uris = _DATA_URI_RE.findall(html)
        marker_uris = uris[:4]
        assert len(set(marker_uris)) == 4
        decoded = [_decode_aruco_id(_png_from_data_uri(uri)) for uri in marker_uris]
        assert decoded == [ARUCO_IDS["tl"], ARUCO_IDS["tr"], ARUCO_IDS["bl"], ARUCO_IDS["br"]]


class TestPaperTemplateQr:
    def test_payload_includes_form_type_and_id(self) -> None:
        payload = json.loads(qr_payload(42))
        assert payload == {
            "form": FORM_ID,
            "version": FORM_VERSION,
            "curriculum_id": 42,
        }
        assert json.loads(qr_payload(None))["curriculum_id"] is None

    def test_png_decodes_to_payload(self) -> None:
        assert _decode_qr(_png_from_data_uri(qr_data_uri(7))) == {
            "form": "week_grid",
            "version": 1,
            "curriculum_id": 7,
        }
        assert _decode_qr(_png_from_data_uri(qr_data_uri(None)))["curriculum_id"] is None

    def test_html_qr_matches_payload(self) -> None:
        html = render_paper_template_html(7)
        qr_uri = _DATA_URI_RE.findall(html)[-1]
        decoded = _decode_qr(_png_from_data_uri(qr_uri))
        assert decoded == {
            "form": "week_grid",
            "version": 1,
            "curriculum_id": 7,
        }


class TestPaperTemplateApi:
    def test_returns_pdf_without_curriculum_id(
        self, client: TestClient, fake_weasyprint: dict[str, object]
    ) -> None:
        response = client.get("/api/curriculum/paper-template")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert 'filename="paper_template.pdf"' in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"
        assert response.content == _FAKE_PDF
        html = str(fake_weasyprint["html"])
        assert "Monday" in html
        assert 'class="week-box"' in html

    def test_passes_curriculum_id(
        self, client: TestClient, fake_weasyprint: dict[str, object]
    ) -> None:
        response = client.get("/api/curriculum/paper-template?curriculum_id=7")

        assert response.status_code == 200
        assert response.content == _FAKE_PDF
        html = str(fake_weasyprint["html"])
        assert "Plan 7" in html
        qr_uri = _DATA_URI_RE.findall(html)[-1]
        assert _decode_qr(_png_from_data_uri(qr_uri))["curriculum_id"] == 7

    def test_generate_pdf_uses_patched_weasyprint(
        self, fake_weasyprint: dict[str, object]
    ) -> None:
        assert generate_paper_template_pdf(None) == _FAKE_PDF
        assert "Curiculy week sheet" in str(fake_weasyprint["html"])
