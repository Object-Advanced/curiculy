"""Stuck? nudges: one nudge per lesson back to the family's materials, then a grown-up."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.schemas.homework import NudgeReply
from app.services.homework_help import (
    ANSWER_SEEKING_NUDGE,
    FALLBACK_NUDGE,
    NUDGE_MAX_CHARS,
    nudge_with_ollama,
)
from tests.test_auth import bearer
from tests.test_kid_auth import _child_token, _parent_ready, _set_pin

pytest_plugins = ["tests.test_auth"]

NUDGE = "Look at the fraction circles example on the page before, then try the first one."


def _assignment(client: TestClient, token: str, student_id: int, title: str = "Fractions p. 42") -> dict:
    return client.post(
        "/api/assignments",
        headers=bearer(token),
        json={
            "student_id": student_id,
            "title": title,
            "scheduled_date": date.today().isoformat(),
            "notes": "Parent reminder: use fraction circles.",
        },
    ).json()


def _ready(client: TestClient) -> tuple[str, dict, dict, str]:
    token, student = _parent_ready(client)
    _set_pin(client, token, student["id"])
    work = _assignment(client, token, student["id"])
    return token, student, work, _child_token(client, student["id"])


def _start(client: TestClient, child: str, assignment_id: int):
    return client.post("/api/homework-help/sessions", headers=bearer(child), json={"assignment_id": assignment_id})


def _ask(client: TestClient, child: str, session_id: int, content: str = "I don't get the second one."):
    with patch("app.routers.homework_help.nudge_with_ollama", new=AsyncMock(return_value=NUDGE)) as model:
        response = client.post(
            f"/api/homework-help/sessions/{session_id}/messages",
            headers=bearer(child),
            json={"content": content},
        )
    return response, model


def _outcome(client: TestClient, token: str, session_id: int, outcome: str):
    return client.post(
        f"/api/homework-help/sessions/{session_id}/outcome",
        headers=bearer(token),
        json={"outcome": outcome},
    )


def _inbox(client: TestClient, token: str) -> list[dict]:
    return client.get("/api/notifications", headers=bearer(token)).json()["notifications"]


def test_one_nudge_then_the_parent_sees_exactly_what_was_said(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    started = _start(auth_client, child, work["id"])
    assert started.status_code == 201
    assert started.json()["status"] == "active"
    assert started.json()["nudged"] is False
    assert _inbox(auth_client, token) == []

    response, model = _ask(auth_client, child, started.json()["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["nudged"] is True
    assert [row["role"] for row in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["content"] == NUDGE
    kwargs = model.await_args.kwargs
    assert kwargs["child_name"] == "Ada"
    assert kwargs["note"] == "Parent reminder: use fraction circles."

    [note] = _inbox(auth_client, token)
    assert note["type"] == "homework_help_started"
    assert note["title"] == "Ada asked for a nudge"
    assert NUDGE in note["body"]
    # The parent's own notes are left alone.
    saved = auth_client.get(f"/api/assignments/{work['id']}", headers=bearer(token)).json()
    assert saved["notes"] == "Parent reminder: use fraction circles."

    second, model = _ask(auth_client, child, body["id"], "another hint please")
    assert second.status_code == 403
    assert "ask a grown-up" in second.json()["detail"]
    model.assert_not_awaited()


def test_parent_cannot_ask_for_a_nudge(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    work = _assignment(auth_client, token, student["id"])
    assert _start(auth_client, token, work["id"]).status_code == 403


def test_asking_for_the_answer_gets_a_fixed_nudge_without_the_model(auth_client: TestClient) -> None:
    _token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    response, model = _ask(auth_client, child, session["id"], "just tell me the answer")
    assert response.status_code == 200
    assert response.json()["messages"][-1]["content"] == ANSWER_SEEKING_NUDGE
    assert response.json()["push_count"] == 1
    model.assert_not_awaited()


def test_helped_uses_up_the_nudge_until_a_parent_allows_another(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    assert _outcome(auth_client, child, session["id"], "helped").status_code == 409  # no nudge yet
    _ask(auth_client, child, session["id"])

    helped = _outcome(auth_client, child, session["id"], "helped")
    assert helped.status_code == 200
    assert helped.json()["status"] == "helped"
    # Coming back to the lesson shows the same, used nudge; no second one.
    again = _start(auth_client, child, work["id"])
    assert again.json()["id"] == session["id"]
    assert _ask(auth_client, child, session["id"])[0].status_code == 403

    assert auth_client.post(
        f"/api/homework-help/assignments/{work['id']}/unlock", headers=bearer(child)
    ).status_code == 403
    allowed = auth_client.post(f"/api/homework-help/assignments/{work['id']}/unlock", headers=bearer(token))
    assert allowed.status_code == 200
    assert allowed.json()[0]["status"] == "closed"
    fresh = _start(auth_client, child, work["id"])
    assert fresh.status_code == 201
    assert fresh.json()["id"] != session["id"]
    assert fresh.json()["nudged"] is False


def test_still_stuck_sends_them_to_a_grown_up_and_tells_the_parent(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    _ask(auth_client, child, session["id"])

    stuck = _outcome(auth_client, child, session["id"], "ask_grown_up")
    assert stuck.status_code == 200
    body = stuck.json()
    assert body["status"] == "redirected"
    assert body["locked"] is True
    assert body["messages"][-1]["role"] == "system"
    assert "find a grown-up" in body["messages"][-1]["content"]
    titles = [row["title"] for row in _inbox(auth_client, token)]
    assert "Ada needs you" in titles

    assert _start(auth_client, child, work["id"]).status_code == 403
    assert _outcome(auth_client, child, session["id"], "ask_grown_up").status_code == 409


def test_a_child_can_go_straight_to_a_grown_up(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    stuck = _outcome(auth_client, child, session["id"], "ask_grown_up")
    assert stuck.status_code == 200
    assert stuck.json()["nudged"] is False
    assert [row["type"] for row in _inbox(auth_client, token)] == ["homework_help_redirect"]


def test_only_the_child_acts_on_their_own_nudge(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    assert _outcome(auth_client, token, session["id"], "ask_grown_up").status_code == 403
    assert _outcome(auth_client, child, session["id"] + 99, "helped").status_code == 404
    assert _outcome(auth_client, child, session["id"], "solve_it").status_code == 422


def test_mark_notifications_read(auth_client: TestClient) -> None:
    token, _student, work, child = _ready(auth_client)
    _ask(auth_client, child, _start(auth_client, child, work["id"]).json()["id"])
    note_id = _inbox(auth_client, token)[0]["id"]
    read = auth_client.post(f"/api/notifications/{note_id}/read", headers=bearer(token))
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    assert auth_client.get("/api/notifications", headers=bearer(token)).json()["unread_count"] == 0
    assert auth_client.get("/api/notifications", headers=bearer(child)).status_code == 403


def test_a_nudge_still_arrives_when_the_model_is_down(auth_client: TestClient) -> None:
    _token, _student, work, child = _ready(auth_client)
    session = _start(auth_client, child, work["id"]).json()
    with patch(
        "app.services.homework_help.chat_with_model_fallback",
        new=AsyncMock(side_effect=ConnectionError("ollama down")),
    ):
        response = auth_client.post(
            f"/api/homework-help/sessions/{session['id']}/messages",
            headers=bearer(child),
            json={"content": "I am stuck on the first problem."},
        )
    assert response.status_code == 200
    assert response.json()["messages"][-1]["content"] == FALLBACK_NUDGE


async def test_nudge_prompt_points_back_to_the_family_materials() -> None:
    chat = AsyncMock(return_value={"message": {"content": NudgeReply(message=NUDGE).model_dump_json()}})
    client = MagicMock()
    client.chat = chat
    with patch("app.services.ollama_chat.ollama.AsyncClient", return_value=client):
        nudge = await nudge_with_ollama(
            assignment_title="Fractions p. 42",
            resource_title="Saxon Math 5/4",
            note="Use fraction circles.",
            child_name="Ada",
            user_message="How do I start?",
        )
    assert nudge == NUDGE
    kwargs = chat.await_args.kwargs
    assert kwargs["format"] == NudgeReply.model_json_schema()
    assert kwargs["options"] == {"temperature": 0.3}
    system = kwargs["messages"][0]["content"]
    assert "You are not their teacher" in system
    assert "Never give an answer" in system
    assert "From their book or plan: Saxon Math 5/4" in system
    assert "Note from their grown-up: Use fraction circles." in system


async def test_a_long_reply_is_trimmed_to_a_nudge() -> None:
    rambling = "Try the first step. " + "Then keep going with more and more detail. " * 20
    with patch(
        "app.services.homework_help.chat_with_model_fallback",
        new=AsyncMock(return_value=NudgeReply(message=rambling).model_dump_json()),
    ):
        nudge = await nudge_with_ollama(
            assignment_title="Fractions p. 42",
            resource_title=None,
            note=None,
            child_name="Ada",
            user_message="help",
        )
    assert len(nudge) <= NUDGE_MAX_CHARS
    assert nudge.startswith("Try the first step.")
    assert nudge.endswith(".")
