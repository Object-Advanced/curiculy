# AI features (all in one place)

Where Curiculy uses AI, what it sends, and the safety rules. Today all AI runs on the family server's own **Ollama** (a local model on the home-lab GPU). Nothing goes to a cloud AI service.

**No AI talks to children** (decided 2026-10-13). AI is only used on the parent's side, to read documents the parent then checks. "Stuck?" nudges and "Ask Sam" were AI until then; both are now plain templates built from the lesson.

| | |
|---|---|
| **Health** | **Works for the beta. Must change before the public launch** (hosted AI, safety evaluations, limits) |

## Every AI use

| Feature | What the AI does | Model | Who sees it | Without the AI |
|---|---|---|---|---|
| [PDF lesson plans](09-pacing-and-lesson-plans.md) | Turns extracted PDF text into Week/Day lessons | Text model | The parent (the new plan) | The plan is marked "failed"; use CSV or the builder |
| [Paper lesson plans](09-pacing-and-lesson-plans.md) | Reads handwriting in each cell of a photographed week sheet | Vision model (`llama3.2-vision`): **not installed on the production server as of 2026-10-13**, so this fails there ([open issue 3a](../6-planning/open-issues.md)) | The parent | The plan is marked "failed" |

**Not AI:**
- **"Stuck?" nudges:** built from the lesson's book, pages and the parent's note. A test trips if the flow reaches a model.
- **"Ask Sam":** questions picked from a fixed set, in the browser.
- Auto-schedule (pacing) is plain arithmetic.
- The daily "Just for fun" puzzle is made in the browser.
- ISBN lookup uses book databases.

## Rules
- **No AI talks to children.** Nothing a child does reaches a model.
- **Guide, don't teach.** No AI output is ever shown to a child.
- **The parent checks AI output** (an imported plan) before it's used.
- **Every AI feature has a fallback,** so the app works with the AI off.
- **Shared connection point:** `app/services/ollama_chat.py` (`chat_with_model_fallback`, which tries the primary model, then `mistral`).

## Review (October 2026)

### Problems and risks
- **Not ready for a public service as-is:**
  - It depends on one home GPU.
  - It has no limits or cost tracking per household.
- **The remaining uses are parent-side importers** on the older catalog page, which the Library replaces. Reading a publisher's PDF lesson plan into a textbook's lesson list is worth rebuilding in the Library later, with a hosted provider chosen then.
- **Background AI jobs** (PDF and paper) run inside the web process. See [Pacing](09-pacing-and-lesson-plans.md).

### Tests
- `test_homework_help.py` (no AI: includes a tripwire that fails if the flow reaches a model), `test_ollama_chat.py` (6)
- `test_curriculum_pdf_import.py` (33), `test_paper_vision_worker.py` (5)

All of them mock the AI.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Decision record on the AI provider: hosted, data terms, cost, child safety | By end of Jan (M2) |
| High | Limits and cost tracking per household; feature switches | Phase 8 |
| Medium | Durable job queue for PDF and paper reading | Phase 8 |

**Not AI:** the Library's barcode reading (OpenCV) and "Read a photo of the page" (Tesseract) are ordinary image processing on the server's CPU, with the parent checking every result. See [Library](21-library.md).
