"""Shared ``ollama.AsyncClient`` chat with primary → mistral fallback.

PDF pacing-guide parse and homework tutoring use this. Spark and paper vision
keep raw ``httpx``. Missing-model errors retry with mistral. Other errors
propagate so each caller can keep its own failure behavior.
"""

from __future__ import annotations

import logging
from typing import Any

import ollama

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_FALLBACK_MODEL = "mistral"


def message_content(response: object) -> str:
    """Read chat content from a dict response or an ollama ChatResponse."""
    try:
        return response["message"]["content"]
    except (TypeError, KeyError, AttributeError):
        return response.message.content


def is_missing_model(error: BaseException) -> bool:
    text = str(error).lower()
    return "not found" in text or "does not exist" in text or "404" in text


def _models_to_try() -> list[str]:
    models = [settings.ollama_model]
    if settings.ollama_model != OLLAMA_FALLBACK_MODEL:
        models.append(OLLAMA_FALLBACK_MODEL)
    return models


async def chat_with_model_fallback(
    *,
    messages: list[dict[str, Any]],
    format: object | None = None,
    options: dict[str, Any] | None = None,
) -> str:
    """Return ``message.content``. Raises immediately on non-missing-model errors.

    If every candidate is missing, raises the last missing-model error.
    """
    client = ollama.AsyncClient(host=settings.ollama_host)
    last_error: BaseException | None = None
    for model in _models_to_try():
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if format is not None:
                kwargs["format"] = format
            if options is not None:
                kwargs["options"] = options
            response = await client.chat(**kwargs)
            return message_content(response)
        except Exception as error:
            last_error = error
            if not is_missing_model(error):
                raise
            logger.warning("Ollama model %s is unavailable; trying fallback", model)

    assert last_error is not None
    raise last_error
