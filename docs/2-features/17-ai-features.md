# AI features (all in one place)

Where Curiculy uses AI, what it sends, and the safety rules. Today all AI runs on the family server's own **Ollama** (a local model on the home-lab GPU). Nothing goes to a cloud AI service.

| | |
|---|---|
| **Health** | **Works for the beta. Must change before the public launch** (hosted AI, safety evaluations, limits) |

## Every AI use

| Feature | What the AI does | Model | Who sees it | Without the AI |
|---|---|---|---|---|
| ["Stuck?" nudges](07-stuck-nudges.md) | Writes **one** short nudge back to the child's own materials. Never answers or teaches. | Text model (`llama3.1`, falling back to `mistral`) | The child, and the parent (quoted in the notification) | A built-in nudge |
| ["Ask Sam"](05-kids-page.md) | A kind question for the parent to ask about today's lessons | Text model | The parent | A simple question built in the browser |
| [PDF lesson plans](09-pacing-and-lesson-plans.md) | Turns extracted PDF text into Week/Day lessons | Text model | The parent (the new plan) | The plan is marked "failed"; use CSV or the builder |
| [Paper lesson plans](09-pacing-and-lesson-plans.md) | Reads handwriting in each cell of a photographed week sheet | Vision model (`llama3.2-vision`) | The parent | The plan is marked "failed" |

**Not AI:** Auto-schedule (pacing) is plain arithmetic, the daily "Just for fun" puzzle is made in the browser, and ISBN lookup uses book databases.

## Rules
- **Guide, don't teach.** No AI output ever gives a child an answer or a lesson.
- **Send as little as possible.** The nudge sees only the first name, lesson title, book and parent's note.
- **The parent sees everything said to a child.**
- **Every AI feature has a fallback,** so the app works with the AI off.
- **Shared connection point:** `app/services/ollama_chat.py` (`chat_with_model_fallback`, which tries the primary model, then `mistral`).

## Review (October 2026)

### Problems and risks
- **Not ready for a public service as-is:**
  - It depends on one home GPU.
  - It has no limits or cost tracking per household.
  - It has no child-safety evaluation set.
- **Children's privacy (COPPA):** before launch, AI use with children's data needs consent when a child account is created, limits on how long logs are kept, and legal review.
- **Background AI jobs** (PDF and paper) run inside the web process. See [Pacing](09-pacing-and-lesson-plans.md).

### Tests
- `test_homework_help.py` (11 tests), `test_spark.py` (3), `test_ollama_chat.py` (6)
- `test_curriculum_pdf_import.py` (33), `test_paper_vision_worker.py` (5)

All of them mock the AI.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Decision record on the AI provider: hosted, data terms, cost, child safety | By end of Jan (M2) |
| High | A child-safety evaluation suite run in CI against the chosen provider | Phase 8 |
| High | Limits and cost tracking per household; feature switches | Phase 8 |
| Medium | Durable job queue for PDF and paper reading | Phase 8 |
