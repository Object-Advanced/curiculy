"""Kid dashboard spark: a question about today's lessons when the model is up."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Household, Student


def _add_student(db: Session, name: str = "Ada") -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name, grade="4")
    db.add(student)
    db.commit()
    return student


class TestStudentSpark:
    def test_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.get("/api/students/4242/spark")

        assert response.status_code == 404

    def test_quiet_model_returns_source_none(
        self, client: TestClient, db: Session, monkeypatch
    ) -> None:
        student = _add_student(db, "Nikolai")
        monkeypatch.setattr("app.routers.students.lesson_question", lambda *_args, **_kwargs: None)

        response = client.get(f"/api/students/{student.id}/spark")

        assert response.status_code == 200
        assert response.json() == {
            "student_id": student.id,
            "source": "none",
            "question": None,
            "about": None,
        }

    def test_model_question_is_passed_through(
        self, client: TestClient, db: Session, monkeypatch
    ) -> None:
        student = _add_student(db, "Harold")
        monkeypatch.setattr(
            "app.routers.students.lesson_question",
            lambda *_args, **_kwargs: ("What do you think happens next in the barn?", "Little House"),
        )

        response = client.get(f"/api/students/{student.id}/spark")

        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "ai"
        assert body["about"] == "Little House"
        assert "barn" in body["question"]
