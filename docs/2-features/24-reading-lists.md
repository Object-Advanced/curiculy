# Reading lists

Each child's books for the school year: what they're **reading now**, what's **up next**, and what they've **finished**, with the days they started and finished. Books whose reading is on the calendar join the list by themselves and move along as the reading is checked off.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `/next/reading` (React), from **Reading** in the nav; `?child=<id>` picks the child. A book's **Reading list** tab in the [Library](21-library.md) |
| **Health** | **Works** (new in October 2026) |

## Scope

### What it does
- **One list per child per school year,** in three parts: **Reading now**, **Up next**, **Finished** (most recent first). Each book shows its cover, author, what it **counts toward**, its dates, and for a scheduled book, "On the calendar: 3 of 10 readings done".
- **One tap moves a book along:** **Started it**, then **Finished it** (dated today, on the family's clock).
- **Change** sets the dates by hand ("read last summer"), what it counts toward, or takes it off the list (its reading stays on the calendar).
- **Add a book** picks from the family's Library books. To give it daily reading instead, **Schedule it** in the Library: it joins the list by itself.
- **From the Library:** a book's **Reading list** tab shows each child, with **Add to Ada's list** or **Open Ada's list**. A family read-aloud goes on each child's list.

### Rules
- **Only books to read** go on a reading list (not textbooks, workbooks or sites). A book is on a child's list once per school year.
- **Counts toward** the parent's choice, else the book's own subject, else English and language arts (reading). A book inside a curriculum counts toward that curriculum's subject (a novel in a history curriculum counts toward history).
- **Scheduled books move by themselves** (`app/services/reading.py`):
  - started when its first reading is checked off (or under way), dated that day
  - finished when every reading is done, skipped or excused, dated the last one
  - lessons only move a book forward: a parent who marks it finished early keeps that
- **Unscheduling** takes a never-started book off the list. A started one stays, as a tracked book, with how far it got and its dates.
- **Dates:** a book being read has a start date (today, if none is given); a finished one has both. The finish can't be before the start.
- **Deleting the book** from the Library, or the child, removes their entries.

### API
`GET /api/reading-list` (by `student_id`, `library_item_id`, `school_year_id`), `POST /api/reading-list`, `PATCH` and `DELETE /api/reading-list/{reading_id}`. Parents only. See the [API reference](../5-engineering/api-reference.md#reading-lists-and-activities).

### Data
`reading_list_entries`: child, library item, school year, status (`up_next`, `reading`, `finished`), started and finished dates, counts toward, and source (`tracked` or `scheduled`). A scheduled book's progress isn't stored: it's read from its lessons.

### Code
- `frontend/src/routes/ReadingPage.tsx`, `frontend/src/components/reading/ReadingForms.tsx`; the Library tab in `components/library/ItemPanel.tsx`
- Server: `app/routers/reading.py`, `app/services/reading.py` (and its hooks in `app/services/planner.py`), `app/models/reading.py`

## Review (October 2026)
**Works well:** scheduling and tracking end up on the same list; nothing has to be marked twice.

**Gaps:**
- the kid's **My books** shelf isn't built
- the portfolio's reading log still comes from the older catalog; the Records work will use this list
- the list shows the current school year's entries and older ones together; a year filter comes with Records

**Tests:**
- `tests/test_reading_lists.py`; the cross-family probe
- `frontend/src/routes/ReadingPage.test.tsx`, and the Library test for the Reading list tab
- the e2e smoke tests (tracking a book; a scheduled book on the list), the axe scan (`reading`) and a screenshot
