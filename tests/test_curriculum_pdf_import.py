"""PDF pacing-guide import: extraction, background worker, and AI schemas."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.enums import CurriculumPlanStatus
from app.models import CurriculumLesson, CurriculumPlan
from app.schemas.curriculum_plans import AIParsedCurriculum, AIParsedLesson
from app.services.ai_curriculum_worker import (
    parse_text_with_ollama,
    process_pdf_curriculum_background,
)
from app.services.pdf_parser import extract_text_from_pdf, is_sparse_curriculum_text


def _see_worker_commit(db: Session) -> None:
    """The worker commits on its own Session; drop this identity map."""
    db.expire_all()


def _tracked_opener(engine: Engine, expected_tenant: str, expected_demo_key: str | None):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    opened: list[Session] = []
    close_calls: list[int] = []

    def opener(tenant_uuid: str, demo_key: str | None = None) -> Session:
        assert tenant_uuid == expected_tenant
        assert demo_key == expected_demo_key
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


def _pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


class TestAIParsedSchemas:
    def test_lesson_fields_are_strict(self) -> None:
        lesson = AIParsedLesson(day_number=1, title="Lesson 1")
        assert lesson.unit_title is None
        assert lesson.week_number is None
        assert lesson.time_slot is None
        assert lesson.subject is None
        assert lesson.category == "Daily Work"
        with pytest.raises(ValidationError):
            AIParsedLesson(day_number=1, title="Lesson 1", extra="nope")

    def test_curriculum_wraps_lessons(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    unit_title="Multiplication",
                    week_number=1,
                    day_number=1,
                    title="Lesson 1",
                    description="Skip counting",
                    pages="7-10",
                )
            ]
        )
        assert len(parsed.lessons) == 1
        assert parsed.lessons[0].title == "Lesson 1"

    def test_lunch_is_routine_break_and_time_is_split_from_title(self) -> None:
        lesson = AIParsedLesson(
            day_number=1,
            title="12:00-12:30 Lunch",
            category="Daily Work",
        )
        assert lesson.title == "Lunch"
        assert lesson.time_slot == "12:00-12:30"
        assert lesson.category == "Routine/Break"

    def test_subject_fills_blank_title_and_unit(self) -> None:
        lesson = AIParsedLesson(day_number=1, title="", subject="Phonics")
        assert lesson.title == "Phonics"
        assert lesson.subject == "Phonics"
        assert lesson.unit_title == "Phonics"
        assert lesson.category == "Daily Work"

    def test_daily_routine_dumped_on_day_one_is_replicated(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    day_number=1, title="Bible", time_slot="8:30-9:00"
                ),
                AIParsedLesson(
                    day_number=1, title="Phonics", time_slot="9:00-9:45"
                ),
                AIParsedLesson(
                    day_number=1, title="Lunch", time_slot="12:00-12:30"
                ),
            ]
        )
        slots = {(lesson.week_number, lesson.day_number) for lesson in parsed.lessons}
        assert slots == {(1, 1), (1, 2), (1, 3), (1, 4), (1, 5)}
        assert len(parsed.lessons) == 15
        assert [lesson.title for lesson in parsed.lessons[:3]] == [
            "Bible",
            "Phonics",
            "Lunch",
        ]
        lunch = [lesson for lesson in parsed.lessons if lesson.title == "Lunch"]
        assert len(lunch) == 5
        assert all(item.category == "Routine/Break" for item in lunch)
        assert all(item.time_slot == "8:30-9:00" for item in parsed.lessons if item.title == "Bible")

    def test_duplicate_blocks_on_the_same_slot_are_dropped(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    day_number=1, title="Bible", time_slot="8:30-9:00"
                ),
                AIParsedLesson(
                    day_number=1, title="Bible", time_slot="8:30-9:00"
                ),
                AIParsedLesson(
                    day_number=1, title="Phonics", time_slot="9:00-9:45"
                ),
            ]
        )
        assert len(parsed.lessons) == 10
        week1_day1 = [
            lesson.title
            for lesson in parsed.lessons
            if lesson.day_number == 1
        ]
        assert week1_day1 == ["Bible", "Phonics"]

    def test_multi_week_pacing_guide_is_not_replicated(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    unit_title="Early America",
                    week_number=1,
                    day_number=1,
                    title="Read Chapter 1",
                    pages="4-10",
                ),
                AIParsedLesson(
                    unit_title="Early America",
                    week_number=1,
                    day_number=2,
                    title="Complete Worksheet A",
                ),
            ]
        )
        assert [(lesson.week_number, lesson.day_number, lesson.title) for lesson in parsed.lessons] == [
            (1, 1, "Read Chapter 1"),
            (1, 2, "Complete Worksheet A"),
        ]

    def test_stacked_pacing_lessons_on_one_day_are_not_treated_as_a_routine(
        self,
    ) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    week_number=1,
                    day_number=1,
                    title="Lesson 1",
                    pages="7-10",
                ),
                AIParsedLesson(
                    week_number=1,
                    day_number=1,
                    title="Lesson 2",
                    pages="11-14",
                ),
            ]
        )
        assert len(parsed.lessons) == 2
        assert {lesson.day_number for lesson in parsed.lessons} == {1}

    def test_subject_stack_without_clock_times_is_still_replicated(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(day_number=1, title="Bible"),
                AIParsedLesson(day_number=1, title="Phonics"),
                AIParsedLesson(day_number=1, title="Reading"),
                AIParsedLesson(day_number=1, title="Math"),
            ]
        )
        assert len(parsed.lessons) == 20
        assert {lesson.day_number for lesson in parsed.lessons} == {1, 2, 3, 4, 5}

    def test_json_payload_from_the_model_is_expanded(self) -> None:
        payload = {
            "lessons": [
                {
                    "day_number": 1,
                    "title": "Bible",
                    "time_slot": "8:30-9:00",
                },
                {
                    "day_number": 1,
                    "title": "Phonics",
                    "time_slot": "9:00-9:45",
                },
            ]
        }
        parsed = AIParsedCurriculum.model_validate_json(json.dumps(payload))
        assert len(parsed.lessons) == 10
        assert parsed.lessons[0].category == "Daily Work"

    def test_placeholder_week_labels_are_dropped(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(week_number=week, day_number=1, title=f"Week {week}")
                for week in range(1, 37)
            ]
        )
        assert parsed.lessons == []

    def test_real_pacing_lessons_are_not_treated_as_placeholders(self) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    week_number=1,
                    day_number=1,
                    title="Lesson 1",
                    pages="7-10",
                )
            ]
        )
        assert len(parsed.lessons) == 1
        assert parsed.lessons[0].title == "Lesson 1"


class TestExtractTextFromPdf:
    def test_concatenates_page_text(self) -> None:
        payload = _pdf_bytes("Week 1 Day 1 Lesson 1")
        assert "Week 1 Day 1 Lesson 1" in extract_text_from_pdf(payload)

    def test_keeps_time_and_subject_on_the_same_line(self) -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 100), "8:30-9:00")
        page.insert_text((200, 100), "Bible")
        page.insert_text((72, 128), "9:00-9:45")
        page.insert_text((200, 128), "Phonics")
        payload = document.tobytes()
        document.close()
        text = extract_text_from_pdf(payload)
        assert "8:30-9:00 Bible" in text
        assert "9:00-9:45 Phonics" in text

    def test_cover_page_week_count_is_sparse(self) -> None:
        payload = _pdf_bytes("Abeka Kindergarten\n36-Week Program\nTeacher Edition")
        text = extract_text_from_pdf(payload)
        assert is_sparse_curriculum_text(text)
        assert not is_sparse_curriculum_text(
            "8:30-9:00 Bible\n9:00-9:45 Phonics\n12:00 Lunch"
        )

    def test_rejects_non_pdf_bytes(self) -> None:
        with pytest.raises(Exception):
            extract_text_from_pdf(b"not a pdf")


class TestImportCurriculumPdf:
    def test_empty_file_is_rejected(self, client: TestClient, db: Session) -> None:
        response = client.post(
            "/api/curriculum/import-pdf",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400
        assert db.query(CurriculumPlan).count() == 0

    def test_accepts_pdf_and_creates_a_processing_plan(
        self, client: TestClient, db: Session
    ) -> None:
        with patch(
            "app.routers.curriculum_plans.process_pdf_curriculum_background",
            new=AsyncMock(),
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": (
                        "Saxon Math 5-4.pdf",
                        _pdf_bytes("Lesson 1"),
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 202
        body = response.json()
        assert body["message"] == "PDF accepted for background AI processing."
        plan = db.get(CurriculumPlan, body["plan_id"])
        assert plan is not None
        assert plan.title == "Saxon Math 5-4"
        assert plan.status == "processing"
        assert db.query(CurriculumLesson).filter_by(plan_id=plan.id).count() == 0

        listed = client.get("/api/curriculum/plans")
        assert listed.status_code == 200
        assert listed.json()[0]["status"] == "processing"
        assert listed.json()[0]["lesson_count"] == 0

    def test_background_worker_bulk_inserts_parsed_lessons(
        self, client: TestClient, db: Session
    ) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    unit_title="Multiplication",
                    week_number=1,
                    day_number=1,
                    title="Lesson 1",
                    description="Skip counting",
                    pages="7-10",
                    time_slot="9:00-9:45",
                    category="Daily Work",
                ),
                AIParsedLesson(
                    unit_title="Multiplication",
                    week_number=1,
                    day_number=2,
                    title="Lesson 2",
                    pages="11-14",
                ),
            ]
        )
        with patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(return_value=parsed),
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": ("guide.pdf", _pdf_bytes("pacing"), "application/pdf")
                },
            )

        assert response.status_code == 202
        plan_id = response.json()["plan_id"]
        _see_worker_commit(db)
        plan = db.get(CurriculumPlan, plan_id)
        assert plan is not None
        assert plan.status == "ready"
        lessons = (
            db.query(CurriculumLesson)
            .filter_by(plan_id=plan_id)
            .order_by(CurriculumLesson.day_number)
            .all()
        )
        assert [lesson.title for lesson in lessons] == ["Lesson 1", "Lesson 2"]
        assert lessons[0].unit_title == "Multiplication"
        assert lessons[0].pages == "7-10"
        assert lessons[0].time_slot == "9:00-9:45"
        assert lessons[0].category == "Daily Work"

    def test_background_worker_saves_a_replicated_daily_routine(
        self, client: TestClient, db: Session
    ) -> None:
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    day_number=1, title="Bible", time_slot="8:30-9:00"
                ),
                AIParsedLesson(
                    day_number=1, title="Phonics", time_slot="9:00-9:45"
                ),
            ]
        )
        with patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(return_value=parsed),
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": ("abeka.pdf", _pdf_bytes("daily schedule"), "application/pdf")
                },
            )

        assert response.status_code == 202
        plan_id = response.json()["plan_id"]
        _see_worker_commit(db)
        plan = db.get(CurriculumPlan, plan_id)
        assert plan is not None
        assert plan.status == "ready"
        assert plan.frequency_days == 5
        assert plan.total_weeks == 1
        lessons = (
            db.query(CurriculumLesson)
            .filter_by(plan_id=plan_id)
            .order_by(CurriculumLesson.day_number, CurriculumLesson.id)
            .all()
        )
        assert len(lessons) == 10
        assert {lesson.day_number for lesson in lessons} == {1, 2, 3, 4, 5}
        assert [lesson.title for lesson in lessons[:2]] == ["Bible", "Phonics"]
        assert lessons[0].time_slot == "8:30-9:00"

    def test_empty_parse_marks_the_plan_failed(
        self, client: TestClient, db: Session
    ) -> None:
        with patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(return_value=AIParsedCurriculum(lessons=[])),
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": ("empty-guide.pdf", _pdf_bytes("nothing"), "application/pdf")
                },
            )
        _see_worker_commit(db)
        plan = db.get(CurriculumPlan, response.json()["plan_id"])
        assert plan is not None
        assert plan.status == "failed"
        assert plan.total_weeks == 1

    def test_ollama_error_marks_the_plan_failed(
        self, client: TestClient, db: Session
    ) -> None:
        with patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(side_effect=ValueError("invalid JSON")),
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": ("bad-ai.pdf", _pdf_bytes("Lesson 1"), "application/pdf")
                },
            )
        assert response.status_code == 202
        _see_worker_commit(db)
        plan = db.get(CurriculumPlan, response.json()["plan_id"])
        assert plan is not None
        assert plan.status == "failed"

    def test_corrupt_pdf_does_not_fail_the_request(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.post(
            "/api/curriculum/import-pdf",
            files={"file": ("bad.pdf", b"not-a-pdf", "application/pdf")},
        )
        assert response.status_code == 202
        plan_id = response.json()["plan_id"]
        _see_worker_commit(db)
        plan = db.get(CurriculumPlan, plan_id)
        assert plan is not None
        assert plan.status == "failed"
        assert db.query(CurriculumLesson).filter_by(plan_id=plan_id).count() == 0

    def test_queues_the_worker_with_tenant_identity_not_the_request_session(
        self, client: TestClient
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_worker(
            plan_id: int,
            file_bytes: bytes,
            tenant_uuid: str,
            demo_key: str | None = None,
        ) -> None:
            captured["plan_id"] = plan_id
            captured["tenant_uuid"] = tenant_uuid
            captured["demo_key"] = demo_key
            captured["bytes_len"] = len(file_bytes)

        with patch(
            "app.routers.curriculum_plans.process_pdf_curriculum_background",
            new=fake_worker,
        ):
            response = client.post(
                "/api/curriculum/import-pdf",
                files={
                    "file": ("guide.pdf", _pdf_bytes("Lesson 1"), "application/pdf")
                },
            )

        assert response.status_code == 202
        assert captured["plan_id"] == response.json()["plan_id"]
        assert captured["tenant_uuid"] == "test"
        assert captured["demo_key"] == "test"
        assert captured["bytes_len"] > 0
        assert "db" not in captured


class TestPdfWorkerOwnsItsSession:
    async def test_success_does_not_use_the_closed_request_session(
        self, engine: Engine, db: Session
    ) -> None:
        plan = CurriculumPlan(
            title="Guide",
            status=CurriculumPlanStatus.PROCESSING,
        )
        db.add(plan)
        db.commit()
        plan_id = plan.id
        request_session = db
        db.close()

        opener, opened, close_calls, factory = _tracked_opener(
            engine, "household-a", "jti-a"
        )
        parsed = AIParsedCurriculum(
            lessons=[
                AIParsedLesson(
                    week_number=1,
                    day_number=1,
                    title="Lesson 1",
                    pages="7-10",
                )
            ]
        )
        with patch(
            "app.services.ai_curriculum_worker.open_tenant_session",
            side_effect=opener,
        ), patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(return_value=parsed),
        ):
            await process_pdf_curriculum_background(
                plan_id,
                _pdf_bytes("Lesson 1"),
                "household-a",
                "jti-a",
            )

        assert opened
        assert request_session not in opened
        assert close_calls == [1]

        verify = factory()
        try:
            saved = verify.get(CurriculumPlan, plan_id)
            assert saved is not None
            assert saved.status == CurriculumPlanStatus.READY
            lessons = (
                verify.query(CurriculumLesson).filter_by(plan_id=plan_id).all()
            )
            assert [lesson.title for lesson in lessons] == ["Lesson 1"]
        finally:
            verify.close()

    async def test_failure_marks_failed_on_a_fresh_session(
        self, engine: Engine, db: Session
    ) -> None:
        plan = CurriculumPlan(
            title="Guide",
            status=CurriculumPlanStatus.PROCESSING,
        )
        db.add(plan)
        db.commit()
        plan_id = plan.id
        request_session = db
        db.close()

        opener, opened, close_calls, factory = _tracked_opener(
            engine, "household-a", "jti-a"
        )
        with patch(
            "app.services.ai_curriculum_worker.open_tenant_session",
            side_effect=opener,
        ), patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(side_effect=ValueError("invalid JSON")),
        ):
            await process_pdf_curriculum_background(
                plan_id,
                _pdf_bytes("Lesson 1"),
                "household-a",
                "jti-a",
            )

        assert len(opened) == 2
        assert request_session not in opened
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

    async def test_empty_parse_marks_failed_without_the_request_session(
        self, engine: Engine, db: Session
    ) -> None:
        plan = CurriculumPlan(
            title="Guide",
            status=CurriculumPlanStatus.PROCESSING,
        )
        db.add(plan)
        db.commit()
        plan_id = plan.id
        db.close()

        opener, opened, close_calls, factory = _tracked_opener(
            engine, "household-a", None
        )
        with patch(
            "app.services.ai_curriculum_worker.open_tenant_session",
            side_effect=opener,
        ), patch(
            "app.services.ai_curriculum_worker.parse_text_with_ollama",
            new=AsyncMock(return_value=AIParsedCurriculum(lessons=[])),
        ):
            await process_pdf_curriculum_background(
                plan_id,
                _pdf_bytes("nothing"),
                "household-a",
                None,
            )

        assert len(opened) == 1
        assert close_calls == [1]

        verify = factory()
        try:
            saved = verify.get(CurriculumPlan, plan_id)
            assert saved is not None
            assert saved.status == CurriculumPlanStatus.FAILED
            assert saved.total_weeks == 1
            assert (
                verify.query(CurriculumLesson).filter_by(plan_id=plan_id).count()
                == 0
            )
        finally:
            verify.close()


class TestParseTextWithOllama:
    async def test_sends_system_prompt_and_json_schema(self) -> None:
        payload = {
            "lessons": [
                {
                    "unit_title": "Early America",
                    "week_number": 1,
                    "day_number": 1,
                    "title": "Read Chapter 1",
                    "description": None,
                    "pages": "4-10",
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value={"message": {"content": json.dumps(payload)}}
        )
        with patch(
            "app.services.ai_curriculum_worker.ollama.AsyncClient",
            return_value=mock_client,
        ):
            result = await parse_text_with_ollama(
                "Week 1 - Early America\nDay 1: Read Chapter 1 (Pages 4-10)"
            )

        mock_client.chat.assert_awaited_once()
        kwargs = mock_client.chat.await_args.kwargs
        assert kwargs["model"] == "llama3.1"
        assert kwargs["format"] == AIParsedCurriculum.model_json_schema()
        assert kwargs["options"] == {"temperature": 0.0}
        assert kwargs["messages"][0]["role"] == "system"
        assert "STRICTLY as JSON" in kwargs["messages"][0]["content"]
        assert "Type A (Multi-Week Pacing Guide)" in kwargs["messages"][0]["content"]
        assert "Type B (Daily Routine / Block Schedule)" in kwargs["messages"][0]["content"]
        assert "Routine/Break" in kwargs["messages"][0]["content"]
        assert kwargs["messages"][1]["role"] == "user"
        assert "Early America" in kwargs["messages"][1]["content"]
        assert result.lessons[0].title == "Read Chapter 1"
        assert result.lessons[0].pages == "4-10"

    async def test_falls_back_to_mistral_when_llama_is_missing(self) -> None:
        payload = {"lessons": [{"day_number": 1, "title": "Lesson 1"}]}
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            side_effect=[
                Exception("model 'llama3.1' not found"),
                {"message": {"content": json.dumps(payload)}},
            ]
        )
        with patch(
            "app.services.ai_curriculum_worker.ollama.AsyncClient",
            return_value=mock_client,
        ):
            result = await parse_text_with_ollama("Day 1: Lesson 1")

        assert mock_client.chat.await_count == 2
        assert mock_client.chat.await_args_list[0].kwargs["model"] == "llama3.1"
        assert mock_client.chat.await_args_list[1].kwargs["model"] == "mistral"
        assert result.lessons[0].title == "Lesson 1"

    async def test_empty_text_skips_the_model(self) -> None:
        with patch(
            "app.services.ai_curriculum_worker.ollama.AsyncClient"
        ) as factory:
            result = await parse_text_with_ollama("   ")
        factory.assert_not_called()
        assert result.lessons == []

    async def test_cover_page_week_count_skips_the_model(self) -> None:
        with patch(
            "app.services.ai_curriculum_worker.ollama.AsyncClient"
        ) as factory:
            result = await parse_text_with_ollama(
                "Abeka K4\n36 weeks\nTeacher Edition"
            )
        factory.assert_not_called()
        assert result.lessons == []

