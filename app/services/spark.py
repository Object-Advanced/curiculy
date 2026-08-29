"""A short, age-kind question about what a child is studying today.

The family dashboard never waits on this. The kid view paints a local puzzle
first, then swaps in a model question when Ollama answers quickly enough.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = """You write one short question for a homeschooled child about today's lesson.
Be warm and curious. One or two sentences. No spoilers, no answer, no markdown, no quotes around the whole thing.
Use the child's first name once if it fits naturally."""


def lesson_question(
    name: str,
    grade: str | None,
    lessons: list[str],
) -> tuple[str, str] | None:
    """Return ``(question, lesson_title)`` or ``None`` if the local model is quiet."""
    titles = [title.strip() for title in lessons if title and title.strip()]
    if not titles:
        return None
    about = titles[0]
    first = (name or "there").strip().split()[0] or "there"
    grade_line = f"Grade {grade}" if grade else "elementary age"
    catalog = "\n".join(f"- {title}" for title in titles[:8])
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Child's first name: {first}\n"
                    f"Age band: {grade_line}\n"
                    f"Today's lessons:\n{catalog}\n\n"
                    "Write one kind question about the reading or lesson."
                ),
            },
        ],
        "options": {"temperature": 0.7, "num_predict": 90},
    }
    url = f"{settings.ollama_host.rstrip('/')}/api/chat"
    try:
        with httpx.Client(timeout=httpx.Timeout(2.5, connect=0.4)) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            text = ((response.json().get("message") or {}).get("content") or "").strip()
    except Exception as error:
        logger.info("Spark question skipped: %s", error)
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) < 12:
        return None
    return cleaned[:400], about
