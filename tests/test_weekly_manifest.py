"""Ink-saver weekly checklist: Monday–Friday assignments as a WeasyPrint PDF.

The date fixtures sit on Wednesday 2026-09-16 so the printed window is
2026-09-14 (Monday) through 2026-09-18 (Friday). Neighbours one day outside
that window — the previous Friday and the following Saturday — must not appear.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import MappingSource, ResourceKind, UnitKind
from app.models import (
    Assignment,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Household,
    Student,
    SubjectTaxonomy,
)
from app.services.weekly_manifest import (
    build_weekly_manifest,
    render_weekly_manifest_html,
    week_monday,
)

ANCHOR = date(2026, 9, 16)
MONDAY = date(2026, 9, 14)
FRIDAY = date(2026, 9, 18)
PREVIOUS_FRIDAY = date(2026, 9, 11)
SATURDAY = date(2026, 9, 19)


@pytest.fixture
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.weekly_manifest._today", lambda *_: ANCHOR)


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    row = Student(household=household, name="Ada", grade="4")
    db.add(row)
    db.commit()
    return row


def add_assignment(
    db: Session,
    student: Student,
    scheduled_date: date,
    *,
    title: str | None = None,
    notes: str | None = None,
    subject_taxonomy_id: int | None = None,
    curriculum_unit_id: int | None = None,
    curriculum_resource_id: int | None = None,
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        title=title or f"Work for {scheduled_date.isoformat()}",
        scheduled_date=scheduled_date,
        notes=notes,
        subject_taxonomy_id=subject_taxonomy_id,
        curriculum_unit_id=curriculum_unit_id,
        curriculum_resource_id=curriculum_resource_id,
    )
    db.add(assignment)
    db.commit()
    return assignment


def test_week_monday_snaps_wednesday_back() -> None:
    assert week_monday(ANCHOR) == MONDAY
    assert week_monday(MONDAY) == MONDAY
    assert week_monday(FRIDAY) == MONDAY


class TestWeeklyManifestHtml:
    def test_groups_weekday_assignments_and_omits_neighbours(
        self, db: Session, student: Student
    ) -> None:
        add_assignment(db, student, PREVIOUS_FRIDAY, title="Last week's leftover")
        add_assignment(
            db,
            student,
            MONDAY,
            title="Lesson 12 problem set",
            notes="odd problems only",
        )
        add_assignment(db, student, date(2026, 9, 15), title="Read chapter 4")
        add_assignment(db, student, FRIDAY, title="Spelling quiz")
        add_assignment(db, student, SATURDAY, title="Weekend catch-up")

        html = render_weekly_manifest_html(
            build_weekly_manifest(db, db, student.id, ANCHOR)
        )

        assert "Weekly Checklist" in html
        assert "Ada" in html
        assert "Grade 4" in html
        assert "Monday, Sep 14" in html
        assert "Friday, Sep 18" in html
        assert "Lesson 12 problem set" in html
        assert "odd problems only" in html
        assert "Read chapter 4" in html
        assert "Spelling quiz" in html
        assert "Last week's leftover" not in html
        assert "Weekend catch-up" not in html
        assert html.count('class="checkbox"') == 3
        assert html.count('class="day-header"') == 5
        assert "No assignments" in html
        assert "@page { size: letter; margin: 0.5in; }" in html
        assert "font-family: 'Times New Roman', serif" in html
        assert "background: #fff" in html
        assert "background-color" not in html
        assert "background: #" not in html.replace("background: #fff", "")

    def test_includes_subject_and_page_range(
        self, db: Session, student: Student
    ) -> None:
        subject = SubjectTaxonomy(name="Mathematics", depth=0, sort_order=0)
        db.add(subject)
        db.flush()
        curriculum = Curriculum(title="Saxon Math 3")
        edition = CurriculumEdition(
            curriculum=curriculum, edition_label="1st edition", is_current=True
        )
        resource = CurriculumResource(
            curriculum_edition=edition,
            kind=ResourceKind.STUDENT_TEXT,
            title="Saxon Math 3",
        )
        db.add_all([curriculum, edition, resource])
        db.flush()
        lesson = CurriculumUnit(
            curriculum_edition=edition,
            kind=UnitKind.LESSON,
            title="Lesson 12",
            sort_order=0,
            depth=0,
        )
        db.add(lesson)
        db.flush()
        db.add(
            CurriculumPageMapping(
                curriculum_unit_id=lesson.id,
                curriculum_resource_id=resource.id,
                page_start=42,
                page_end=45,
                source=MappingSource.MANUAL,
            )
        )
        db.commit()
        add_assignment(
            db,
            student,
            MONDAY,
            title="Lesson 12 problem set",
            subject_taxonomy_id=subject.id,
            curriculum_unit_id=lesson.id,
            curriculum_resource_id=resource.id,
        )

        html = render_weekly_manifest_html(
            build_weekly_manifest(db, db, student.id, MONDAY)
        )

        assert "Lesson 12 problem set" in html
        assert "Mathematics" in html
        assert "pp. 42–45" in html

    def test_omitted_start_date_uses_this_weeks_monday(
        self, db: Session, student: Student, freeze_today: None
    ) -> None:
        add_assignment(db, student, MONDAY, title="This weeks opener")
        manifest = build_weekly_manifest(db, db, student.id)
        assert manifest.start_date == MONDAY
        assert manifest.end_date == FRIDAY
        assert "This weeks opener" in render_weekly_manifest_html(manifest)


class TestWeeklyManifestApi:
    def test_returns_pdf_for_the_snapped_weekday_window(
        self,
        client: TestClient,
        student: Student,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        add_assignment(db, student, MONDAY, title="Lesson 12 problem set")
        captured: dict[str, object] = {}

        def fake_pdf(manifest: object) -> bytes:
            captured["student"] = getattr(manifest, "student").name
            captured["start"] = getattr(manifest, "start_date")
            captured["end"] = getattr(manifest, "end_date")
            captured["html"] = render_weekly_manifest_html(manifest)  # type: ignore[arg-type]
            return b"%PDF-1.4 fake"

        monkeypatch.setattr("app.routers.reports.render_weekly_manifest_pdf", fake_pdf)

        response = client.get(
            f"/api/reports/weekly-manifest?student_id={student.id}"
            f"&start_date={ANCHOR.isoformat()}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert "Ada_weekly_checklist_2026-09-14.pdf" in response.headers[
            "content-disposition"
        ]
        assert response.content == b"%PDF-1.4 fake"
        assert captured["student"] == "Ada"
        assert captured["start"] == MONDAY
        assert captured["end"] == FRIDAY
        assert "Lesson 12 problem set" in str(captured["html"])

    def test_default_start_date_is_this_weeks_monday(
        self,
        client: TestClient,
        student: Student,
        freeze_today: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_pdf(manifest: object) -> bytes:
            captured["start"] = getattr(manifest, "start_date")
            captured["end"] = getattr(manifest, "end_date")
            return b"%PDF-1.4 fake"

        monkeypatch.setattr("app.routers.reports.render_weekly_manifest_pdf", fake_pdf)

        response = client.get(f"/api/reports/weekly-manifest?student_id={student.id}")

        assert response.status_code == 200
        assert captured["start"] == MONDAY
        assert captured["end"] == FRIDAY

    def test_unknown_student_is_a_404(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.routers.reports.render_weekly_manifest_pdf",
            lambda manifest: b"%PDF-fake",
        )
        response = client.get("/api/reports/weekly-manifest?student_id=999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_student_id_is_required(self, client: TestClient) -> None:
        response = client.get("/api/reports/weekly-manifest")
        assert response.status_code == 422
