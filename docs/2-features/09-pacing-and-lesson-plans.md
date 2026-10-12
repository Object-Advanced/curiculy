# Pacing and lesson plans

Turning a book or a pacing guide into dated lessons on a child's calendar. There are two ways.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | "Auto-schedule a book" (Catalog and Calendar); the **Lesson plans** list in the Catalog (import, builder, Apply) |
| **Health** | **Works and well tested.** The PDF and photo imports depend on the local AI and are the least predictable part. |

> **Planned (core loop, 2026-10-12):** scheduling follows each kind of book's structure: a curriculum's full lesson list, a workbook's chapters and total pages, a reading book's pages, minutes or chapters. "Auto-schedule" and "Apply" become one verb, **Schedule**. See [Library](../6-planning/product-spine.md#library-one-shelf-four-kinds-of-book).

## Scope

### 1. Auto-schedule a book (pacing)
- The parent picks a book, a child, a page range, and either a **finish-by date** or **pages per day**.
- **Preview:** the page range is split into near-equal lessons over the child's school days. Weekends, unticked weekdays and days off are skipped.
- If the schedule needs more than one lesson a day, it's **flagged as "rigorous" rather than refused**.
- **Commit:** writes the lessons and the book structure, and **enrolls the child**, all in one save.
- Simple arithmetic only; **no AI.** It always gives the same result for the same inputs.

### 2. Lesson plans (structured pacing guides)
A "plan" is a Week/Day guide made of lessons, with optional time slots. It can come from:
- **CSV** with columns Unit, Week, Day and Title. One bad row rejects the whole file, so you never get half a guide.
- **PDF:** the text is extracted (tables, reading order, and OCR for scanned pages), then the **local AI** turns it into lessons in the background. The plan shows "processing", then "ready" or "failed", and the parent is notified.
- **Paper:** print a week sheet with corner markers and a QR code, fill it in by hand, then photograph it. The photo is straightened and cut into cells, and the **local vision AI** reads each cell's handwriting in the background.
- **Builder:** type lessons in by hand.

**Apply** a plan to a child from a start date. Each Week/Day slot takes the next school day, skipping weekends, unticked weekdays and days off. Applying also **enrolls the child**.

### Out of scope today
- Editing the AI's PDF output side by side with the original.
- A shared library of lesson lists between families (planned: the community catalog).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/pacing/generate-preview` | parent | Preview lessons for a page range |
| POST | `/api/pacing/commit` | parent | Save them to the calendar |
| GET / POST | `/api/curriculum/plans` | parent | List; create (builder) |
| GET / PUT / DELETE | `/api/curriculum/plans/{id}` | parent | Read, edit, delete |
| POST | `/api/curriculum/plans/{id}/archive` | parent | Archive |
| POST | `/api/curriculum/plans/{id}/apply` | parent | Put the plan on a child's calendar |
| POST | `/api/curriculum/import-csv` | parent | CSV → plan |
| POST | `/api/curriculum/import-pdf` | parent | PDF → plan (AI, runs in the background) |
| GET | `/api/curriculum/paper-template` | parent | Printable week sheet (PDF) |
| POST | `/api/curriculum/import-paper` | parent | Photo of the sheet → plan (vision AI, runs in the background) |

### Data
The family's own rows (walled off by row-level security) are in `curriculum_plans` (status: processing, ready or failed) and `curriculum_lessons`, plus the assignments and enrollments they create.

### Code
- `app/routers/pacing.py`, `app/routers/curriculum_plans.py`
- `app/services/pacing.py` (`PacingEngine`, `SyllabusCommitter`), `ai_generator.py` (despite the name, it's plain arithmetic)
- `curriculum_plan_import.py`, `curriculum_plan_apply.py`
- `pdf_parser.py`, `ai_curriculum_worker.py`
- `paper_template.py`, `paper_parser.py`, `paper_vision_worker.py`
- `plan_recovery.py`

## Review (October 2026)

### Working well
- **The pacing engine is pure date arithmetic**, with 75 tests. Being flagged "rigorous" instead of refused is a kind, useful rule.
- **Imports are all-or-nothing.**
- **A restart can't leave a plan stuck in "processing".** Since Phase 1, interrupted plans are marked failed when the app starts.

### Problems and risks
- **Background AI jobs run inside the web process** (FastAPI `BackgroundTasks`). A restart loses the job; it's marked failed, but not retried. There's no queue, retry, or second worker.
- **The PDF and handwriting results depend on the local Ollama model and the GPU.** Quality varies, and there's no side-by-side check.
- **The file name `ai_generator.py` is misleading.** It does arithmetic; rename it `pacing_math.py`.
- **"Auto-schedule" (books) and "Apply" (plans)** are different verbs for the same result.

### Tests
- `test_pacing.py` (75 tests), `test_curriculum_plans.py` (25), `test_curriculum_pdf_import.py` (33)
- `test_paper_template.py` (10), `test_paper_parser.py` (6), `test_paper_vision_worker.py` (5)
- `test_plan_recovery.py` (2)
- e2e: "a CSV pacing guide imports and applies to the calendar"

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Durable jobs: a jobs table, a separate worker process, retries, and a cleanup for stalled jobs | Phase 8 |
| High | Hosted AI for PDF and photo reading behind the existing `ollama_chat` connection point, with limits per household | Phase 8 |
| High | One **Guide** model and one verb, **Schedule**; a review step for AI-read plans | Core loop |
| Low | Rename `ai_generator.py` → `pacing_math.py` | Phase 5 |
