"""Paper-sheet vision worker: sequential Ollama calls and a private tenant session."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.enums import CurriculumPlanStatus
from app.models import CurriculumLesson, CurriculumPlan
from app.services.paper_parser import MISSING_CORNERS
from app.services.paper_vision_worker import (
    OLLAMA_VISION_MODEL,
    extract_handwriting_from_slices,
)

DUMMY_SLICES = {
    "curriculum_id": 42,
    "week_number_image": "week-b64",
    "rows": [
        {
            "time_image": "time-b64",
            "days": ["mon-b64", "tue-b64", "wed-b64", "thu-b64", "fri-b64"],
        }
    ],
}

_OLLAMA_MATH = {
    "message": {"content": '{"text": "Math"}'},
}


def _tracked_opener(engine: Engine, expected_tenant: str, expected_jti: str | None):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    opened: list[Session] = []
    close_calls: list[int] = []

    def opener(tenant_uuid: str, demo_key: str | None = None) -> Session:
        assert tenant_uuid == expected_tenant
        assert demo_key == expected_jti
        session = factory()
        index = len(close_calls)
        close_calls.append(0)
        inner_close = session.close

        def close() -> None:
            close_calls[index] += 1
            inner_close()

        session.close = close  # type: ignore[method-assign]
        opened.append(session)
        return session

    return opener, opened, close_calls, factory


def _ollama_response(payload: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload or _OLLAMA_MATH,
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )


def _seed_processing_plan(db: Session) -> int:
    plan = CurriculumPlan(
        title="Paper Import",
        status=CurriculumPlanStatus.PROCESSING,
    )
    db.add(plan)
    db.commit()
    plan_id = plan.id
    db.close()
    return plan_id


class TestExtractHandwritingFromSlices:
    def test_inserts_lessons_and_marks_ready(
        self, engine: Engine, db: Session
    ) -> None:
        plan_id = _seed_processing_plan(db)
        opener, opened, close_calls, factory = _tracked_opener(
            engine, "household-a", "jti-a"
        )
        mock_post = MagicMock(return_value=_ollama_response())

        with (
            patch(
                "app.services.paper_vision_worker.open_tenant_session",
                side_effect=opener,
            ),
            patch("app.services.paper_vision_worker.httpx.post", mock_post),
        ):
            extract_handwriting_from_slices(
                DUMMY_SLICES, plan_id, "household-a", "jti-a"
            )

        assert opened
        assert close_calls == [1]
        assert mock_post.call_count == 7
        first_payload = mock_post.call_args_list[0].kwargs["json"]
        assert first_payload["model"] == OLLAMA_VISION_MODEL
        assert first_payload["stream"] is False
        assert first_payload["format"] == "json"
        assert first_payload["messages"][0]["images"] == ["week-b64"]
        for call in mock_post.call_args_list[1:]:
            assert call.args[0] == mock_post.call_args_list[0].args[0]

        verify = factory()
        try:
            saved = verify.get(CurriculumPlan, plan_id)
            assert saved is not None
            assert saved.status == CurriculumPlanStatus.READY
            lessons = (
                verify.query(CurriculumLesson)
                .filter_by(plan_id=plan_id)
                .order_by(CurriculumLesson.day_number.asc())
                .all()
            )
            assert [lesson.title for lesson in lessons] == ["Math"] * 5
            assert [lesson.day_number for lesson in lessons] == [1, 2, 3, 4, 5]
            assert all(lesson.week_number == 1 for lesson in lessons)
            assert all(lesson.time_slot == "Math" for lesson in lessons)
        finally:
            verify.close()

    def test_failure_marks_failed_on_a_fresh_session(
        self, engine: Engine, db: Session
    ) -> None:
        plan_id = _seed_processing_plan(db)
        opener, opened, close_calls, factory = _tracked_opener(
            engine, "household-a", None
        )

        with (
            patch(
                "app.services.paper_vision_worker.open_tenant_session",
                side_effect=opener,
            ),
            patch(
                "app.services.paper_vision_worker.httpx.post",
                side_effect=httpx.ConnectError("ollama down"),
            ),
        ):
            extract_handwriting_from_slices(DUMMY_SLICES, plan_id, "household-a")

        assert len(opened) == 2
        assert close_calls == [1, 1]

        verify = factory()
        try:
            saved = verify.get(CurriculumPlan, plan_id)
            assert saved is not None
            assert saved.status == CurriculumPlanStatus.FAILED
            assert (
                verify.query(CurriculumLesson).filter_by(plan_id=plan_id).count()
                == 0
            )
        finally:
            verify.close()


class TestImportPaperApi:
    def test_missing_corners_are_a_400(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(_raw: bytes) -> dict:
            raise ValueError(MISSING_CORNERS)

        monkeypatch.setattr("app.routers.curriculum_plans.parse_paper_upload", boom)
        response = client.post(
            "/api/curriculum/import-paper",
            files={"file": ("sheet.png", b"not-a-page", "image/png")},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == MISSING_CORNERS

    def test_queues_vision_after_slicing(
        self,
        client: TestClient,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "app.routers.curriculum_plans.parse_paper_upload",
            lambda _raw: DUMMY_SLICES,
        )
        captured: dict[str, object] = {}

        def fake_worker(
            slices: dict,
            plan_id: int,
            tenant_uuid: str,
            jti: str | None = None,
        ) -> None:
            captured["slices"] = slices
            captured["plan_id"] = plan_id
            captured["tenant_uuid"] = tenant_uuid
            captured["jti"] = jti

        monkeypatch.setattr(
            "app.routers.curriculum_plans.extract_handwriting_from_slices",
            fake_worker,
        )

        response = client.post(
            "/api/curriculum/import-paper",
            files={"file": ("sheet.png", b"png-bytes", "image/png")},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "processing"
        assert captured["plan_id"] == body["id"]
        assert captured["slices"] == DUMMY_SLICES
        assert captured["tenant_uuid"] == "test"
        assert captured["jti"] == "test"
        plan = db.get(CurriculumPlan, body["id"])
        assert plan is not None
        assert plan.title == "Paper Import"
        assert plan.status == CurriculumPlanStatus.PROCESSING

    def test_empty_upload_is_a_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/curriculum/import-paper",
            files={"file": ("sheet.png", b"", "image/png")},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "the image payload is empty"
