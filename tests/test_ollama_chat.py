"""Shared ollama.AsyncClient primary → mistral fallback."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ollama_chat import (
    OLLAMA_FALLBACK_MODEL,
    chat_with_model_fallback,
    message_content,
)


def _client(chat: AsyncMock) -> MagicMock:
    mock = MagicMock()
    mock.chat = chat
    return mock


class TestMessageContent:
    def test_reads_a_dict_response(self) -> None:
        assert message_content({"message": {"content": "hello"}}) == "hello"

    def test_reads_an_sdk_chat_response(self) -> None:
        response = SimpleNamespace(message=SimpleNamespace(content="from-sdk"))
        assert message_content(response) == "from-sdk"


class TestChatWithModelFallback:
    async def test_primary_success_does_not_call_mistral(self) -> None:
        chat = AsyncMock(return_value={"message": {"content": "ok"}})
        with patch(
            "app.services.ollama_chat.ollama.AsyncClient",
            return_value=_client(chat),
        ):
            result = await chat_with_model_fallback(
                messages=[{"role": "user", "content": "hi"}],
                format={"type": "object"},
                options={"temperature": 0.0},
            )

        assert result == "ok"
        chat.assert_awaited_once()
        kwargs = chat.await_args.kwargs
        assert kwargs["model"] == "llama3.1"
        assert kwargs["format"] == {"type": "object"}
        assert kwargs["options"] == {"temperature": 0.0}
        assert kwargs["messages"] == [{"role": "user", "content": "hi"}]

    async def test_missing_primary_retries_mistral(self) -> None:
        chat = AsyncMock(
            side_effect=[
                Exception("model 'llama3.1' not found"),
                {"message": {"content": "from-mistral"}},
            ]
        )
        with patch(
            "app.services.ollama_chat.ollama.AsyncClient",
            return_value=_client(chat),
        ):
            result = await chat_with_model_fallback(
                messages=[{"role": "user", "content": "hi"}],
            )

        assert result == "from-mistral"
        assert chat.await_count == 2
        assert chat.await_args_list[0].kwargs["model"] == "llama3.1"
        assert chat.await_args_list[1].kwargs["model"] == OLLAMA_FALLBACK_MODEL

    async def test_non_missing_model_error_does_not_fallback(self) -> None:
        chat = AsyncMock(side_effect=ConnectionError("connection refused"))
        with patch(
            "app.services.ollama_chat.ollama.AsyncClient",
            return_value=_client(chat),
        ):
            with pytest.raises(ConnectionError, match="connection refused"):
                await chat_with_model_fallback(
                    messages=[{"role": "user", "content": "hi"}],
                )

        chat.assert_awaited_once()
        assert chat.await_args.kwargs["model"] == "llama3.1"

    async def test_does_not_retry_when_primary_is_already_mistral(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.ollama_chat.settings.ollama_model",
            OLLAMA_FALLBACK_MODEL,
        )
        chat = AsyncMock(side_effect=Exception("model 'mistral' not found"))
        with patch(
            "app.services.ollama_chat.ollama.AsyncClient",
            return_value=_client(chat),
        ):
            with pytest.raises(Exception, match="mistral"):
                await chat_with_model_fallback(
                    messages=[{"role": "user", "content": "hi"}],
                )

        chat.assert_awaited_once()
        assert chat.await_args.kwargs["model"] == OLLAMA_FALLBACK_MODEL
