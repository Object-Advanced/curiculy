"""Subjects: the state's required ones by grade, common and own subjects, objectives."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import SchoolYear, StudentSubject
from app.services.households import get_default_household


def _pa_student(client: TestClient, grade: str = "3") -> int:
    client.post("/api/household/state", json={"state_code": "PA", "starts_on": "2020-01-01"})
    return client.post("/api/students", json={"name": "Ada", "grade": grade}).json()["id"]


def _subjects(client: TestClient, student_id: int, **params) -> dict:
    response = client.get(f"/api/students/{student_id}/subjects", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_code(view: dict) -> dict[str, dict]:
    return {row["subject_code"]: row for row in view["subjects"] if row["subject_code"]}


class TestReference:
    def test_the_fixed_lists_are_public(self, committed_db: None) -> None:
        body = TestClient(create_app()).get("/api/reference").json()
        assert len(body["states"]) == 51
        assert [grade["code"] for grade in body["grades"]][:3] == ["PreK", "K", "1"]
        assert {"english", "math", "safety", "bible"} <= {subject["code"] for subject in body["subjects"]}
        assert [kind["label"] for kind in body["library_kinds"]] == ["Book", "Textbook", "Workbook", "Online site"]
        assert all(kind["hint"] for kind in body["library_kinds"])
        assert [role["code"] for role in body["curriculum_roles"]] == ["textbook", "workbook", "online", "reading", "teacher"]
        assert "never anything about your family" in body["community_notice"]

    def test_pennsylvania_elementary(self, client: TestClient) -> None:
        body = client.get("/api/state-requirements/pa/subjects", params={"grade": "3rd"}).json()
        assert (body["supported"], body["band"], body["grade"]) == (True, "elementary", "3")
        codes = [subject["code"] for subject in body["subjects"]]
        assert codes[:2] == ["english", "math"] and "world_history" not in codes
        safety = next(subject for subject in body["subjects"] if subject["code"] == "safety")
        assert safety["every_year"] is True and "fire" in safety["state_label"]

    def test_pennsylvania_secondary_adds_world_history(self, client: TestClient) -> None:
        body = client.get("/api/state-requirements/PA/subjects", params={"grade": "9"}).json()
        assert body["band"] == "secondary"
        assert "world_history" in [subject["code"] for subject in body["subjects"]]

    def test_before_kindergarten_nothing_is_required(self, client: TestClient) -> None:
        body = client.get("/api/state-requirements/PA/subjects", params={"grade": "PreK"}).json()
        assert (body["supported"], body["subjects"]) == (True, [])

    def test_a_state_not_reviewed_yet_says_so(self, client: TestClient) -> None:
        body = client.get("/api/state-requirements/OH/subjects", params={"grade": "3"}).json()
        assert (body["supported"], body["subjects"], body["state_name"]) == (False, [], "Ohio")


class TestStudentSubjects:
    def test_required_subjects_appear_on_their_own(self, client: TestClient) -> None:
        view = _subjects(client, _pa_student(client))
        assert (view["state_code"], view["supported"], view["band"]) == ("PA", True, "elementary")
        rows = view["subjects"]
        assert len(rows) == 11 and all(row["kind"] == "required" and row["active"] for row in rows)
        assert rows[0]["subject_code"] == "english" and rows[0]["state_label"].startswith("English")

    def test_adding_common_and_own_subjects(self, client: TestClient) -> None:
        student_id = _pa_student(client)
        client.post(f"/api/students/{student_id}/subjects", json={"subject_code": "bible"})
        view = client.post(
            f"/api/students/{student_id}/subjects",
            json={"name": "  Latin   roots ", "counts_toward": "english"},
        ).json()
        kinds = [(row["name"], row["kind"]) for row in view["subjects"][-2:]]
        assert kinds == [("Bible and religion", "common"), ("Latin roots", "own")]
        assert view["subjects"][-1]["counts_toward_name"] == "English and language arts"

    def test_a_subject_needs_a_list_choice_or_a_name(self, client: TestClient) -> None:
        student_id = _pa_student(client)
        assert client.post(f"/api/students/{student_id}/subjects", json={}).status_code == 422
        assert client.post(f"/api/students/{student_id}/subjects", json={"subject_code": "astrology"}).status_code == 422

    def test_objectives_and_turning_subjects_off(self, client: TestClient) -> None:
        student_id = _pa_student(client)
        rows = _by_code(_subjects(client, student_id))
        math = client.patch(
            f"/api/student-subjects/{rows['math']['id']}", json={"objective": "Finish Saxon 5/4"}
        ).json()
        assert math["objective"] == "Finish Saxon 5/4"
        art = client.patch(f"/api/student-subjects/{rows['art']['id']}", json={"active": False}).json()
        assert (art["active"], art["warning"]) == (False, None)
        safety = client.patch(f"/api/student-subjects/{rows['safety']['id']}", json={"active": False}).json()
        assert safety["warning"] == "Pennsylvania expects this every year."

    def test_required_subjects_cant_be_deleted_or_renamed(self, client: TestClient) -> None:
        student_id = _pa_student(client)
        math_id = _by_code(_subjects(client, student_id))["math"]["id"]
        assert client.delete(f"/api/student-subjects/{math_id}").status_code == 409
        assert client.patch(f"/api/student-subjects/{math_id}", json={"name": "Sums"}).status_code == 409
        own = client.post(f"/api/students/{student_id}/subjects", json={"name": "Chess"}).json()["subjects"][-1]
        assert client.delete(f"/api/student-subjects/{own['id']}").status_code == 204

    def test_moving_states_keeps_subjects_and_objectives(self, client: TestClient) -> None:
        student_id = _pa_student(client)
        math_id = _by_code(_subjects(client, student_id))["math"]["id"]
        client.patch(f"/api/student-subjects/{math_id}", json={"objective": "Fractions"})
        client.post("/api/household/state", json={"state_code": "OH", "starts_on": "2020-06-01"})
        view = _subjects(client, student_id)
        assert view["supported"] is False
        math = _by_code(view)["math"]
        assert (math["kind"], math["objective"]) == ("common", "Fractions")

    def test_a_new_grade_band_brings_its_subjects(self, client: TestClient) -> None:
        student_id = _pa_student(client, grade="6")
        assert "world_history" not in _by_code(_subjects(client, student_id))
        client.put(f"/api/students/{student_id}", json={"name": "Ada", "grade": "7"})
        assert _by_code(_subjects(client, student_id))["world_history"]["kind"] == "required"

    def test_earlier_years_show_as_covered(self, client: TestClient, db: Session) -> None:
        student_id = _pa_student(client)
        _subjects(client, student_id)  # this school year exists first
        household = get_default_household(db)
        last_year = SchoolYear(household_id=household.id, name="2019–20", start_date=date(2019, 8, 1), end_date=date(2020, 6, 1))
        db.add(last_year)
        db.flush()
        db.add(StudentSubject(student_id=student_id, school_year_id=last_year.id, subject_code="music",
                              name="Music", kind="required", counts_toward="music", active=True))
        db.commit()
        rows = _by_code(_subjects(client, student_id))
        assert rows["music"]["covered_before"] is True
        assert rows["art"]["covered_before"] is False

    def test_without_a_state_families_pick_freely(self, client: TestClient) -> None:
        student_id = client.post("/api/students", json={"name": "Ada", "grade": "3"}).json()["id"]
        view = _subjects(client, student_id)
        assert (view["state_code"], view["supported"], view["subjects"]) == (None, False, [])
