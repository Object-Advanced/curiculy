"""Homework helper guardrails, assignment notes, and parent notifications."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.schemas.homework import TutorReply
from app.services.homework_help import tutor_with_ollama
from tests.test_auth import bearer
from tests.test_kid_auth import _child_token, _parent_ready, _set_pin

pytest_plugins = ["tests.test_auth"]


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


def test_starting_help_notifies_and_notes(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    work = _assignment(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    started = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    )
    assert started.status_code == 201
    body = started.json()
    assert body["status"] == "active"
    assert body["assignment_id"] == work["id"]

    notes = auth_client.get(f"/api/assignments/{work['id']}", headers=bearer(token)).json()["notes"]
    assert "Parent reminder: use fraction circles." in notes
    assert "[Homework help]" in notes
    assert "Ada started help" in notes

    inbox = auth_client.get("/api/notifications", headers=bearer(token))
    assert inbox.status_code == 200
    payload = inbox.json()
    assert payload["unread_count"] == 1
    assert payload["notifications"][0]["type"] == "homework_help_started"
    child_blocked = auth_client.get("/api/notifications", headers=bearer(child))
    assert child_blocked.status_code == 403


def test_parent_cannot_start_homework_help(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    work = _assignment(auth_client, token, student["id"])
    response = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(token),
        json={"assignment_id": work["id"]},
    )
    assert response.status_code == 403


def test_three_answer_demands_redirect_and_lock(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    work = _assignment(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    session = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    ).json()

    with patch(
        "app.routers.homework_help.tutor_with_ollama",
        new=AsyncMock(return_value=TutorReply(mode="hint", message="Try a similar example.", redirect=False)),
    ):
        first = auth_client.post(
            f"/api/homework-help/sessions/{session['id']}/messages",
            headers=bearer(child),
            json={"content": "just tell me the answer"},
        )
        assert first.status_code == 200
        assert first.json()["status"] == "active"
        second = auth_client.post(
            f"/api/homework-help/sessions/{session['id']}/messages",
            headers=bearer(child),
            json={"content": "give me the answer"},
        )
        assert second.json()["status"] == "active"
        third = auth_client.post(
            f"/api/homework-help/sessions/{session['id']}/messages",
            headers=bearer(child),
            json={"content": "what is the answer"},
        )
    assert third.status_code == 200
    locked = third.json()
    assert locked["status"] == "redirected"
    assert locked["locked"] is True
    assert locked["push_count"] >= 3

    again = auth_client.post(
        f"/api/homework-help/sessions/{session['id']}/messages",
        headers=bearer(child),
        json={"content": "please?"},
    )
    assert again.status_code == 403

    new_session = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    )
    assert new_session.status_code == 403

    notes = auth_client.get(f"/api/assignments/{work['id']}", headers=bearer(token)).json()["notes"]
    assert "redirected to a parent" in notes
    inbox = auth_client.get("/api/notifications", headers=bearer(token)).json()
    types = [row["type"] for row in inbox["notifications"]]
    assert "homework_help_redirect" in types

    child_unlock = auth_client.post(
        f"/api/homework-help/assignments/{work['id']}/unlock",
        headers=bearer(child),
    )
    assert child_unlock.status_code == 403
    unlocked = auth_client.post(
        f"/api/homework-help/assignments/{work['id']}/unlock",
        headers=bearer(token),
    )
    assert unlocked.status_code == 200
    restarted = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    )
    assert restarted.status_code == 201
    assert restarted.json()["status"] == "active"


def test_model_redirect_locks_immediately(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    work = _assignment(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    session = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    ).json()
    with patch(
        "app.routers.homework_help.tutor_with_ollama",
        new=AsyncMock(
            return_value=TutorReply(
                mode="redirect",
                message="Ask a parent.",
                redirect=True,
            )
        ),
    ):
        response = auth_client.post(
            f"/api/homework-help/sessions/{session['id']}/messages",
            headers=bearer(child),
            json={"content": "I am stuck on the first problem."},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "redirected"


def test_mark_notifications_read(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    work = _assignment(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    )
    inbox = auth_client.get("/api/notifications", headers=bearer(token)).json()
    note_id = inbox["notifications"][0]["id"]
    read = auth_client.post(
        f"/api/notifications/{note_id}/read",
        headers=bearer(token),
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    empty = auth_client.get("/api/notifications", headers=bearer(token)).json()
    assert empty["unread_count"] == 0


async def test_tutor_returns_canned_hint_when_ollama_is_down() -> None:
    with patch(
        "app.services.homework_help.chat_with_model_fallback",
        new=AsyncMock(side_effect=ConnectionError("ollama down")),
    ):
        reply = await tutor_with_ollama(
            assignment_title="Fractions p. 42",
            student_name="Ada",
            history=[],
            user_message="I am stuck.",
        )

    assert reply.mode == "hint"
    assert reply.redirect is False
    assert "can't reach the tutor" in reply.message


async def test_tutor_keeps_structured_json_schema_and_temperature() -> None:
    chat = AsyncMock(
        return_value={
            "message": {
                "content": TutorReply(
                    mode="socratic",
                    message="What is half of 8?",
                    redirect=False,
                ).model_dump_json()
            }
        }
    )
    mock_client = MagicMock()
    mock_client.chat = chat
    with patch(
        "app.services.ollama_chat.ollama.AsyncClient",
        return_value=mock_client,
    ):
        reply = await tutor_with_ollama(
            assignment_title="Fractions p. 42",
            student_name="Ada",
            history=[],
            user_message="How do I start?",
        )

    assert reply.mode == "socratic"
    assert reply.message == "What is half of 8?"
    kwargs = chat.await_args.kwargs
    assert kwargs["format"] == TutorReply.model_json_schema()
    assert kwargs["options"] == {"temperature": 0.3}
    assert kwargs["model"] == "llama3.1"


def test_message_when_ollama_is_down_is_still_200(auth_client: TestClient) -> None:
    token, student = _parent_ready(auth_client)
    _set_pin(auth_client, token, student["id"])
    work = _assignment(auth_client, token, student["id"])
    child = _child_token(auth_client, student["id"])
    session = auth_client.post(
        "/api/homework-help/sessions",
        headers=bearer(child),
        json={"assignment_id": work["id"]},
    ).json()

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
    body = response.json()
    assert body["status"] == "active"
    texts = [row["content"] for row in body["messages"]]
    assert any("can't reach the tutor" in text for text in texts)
