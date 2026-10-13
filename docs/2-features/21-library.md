# Library

Everything the family teaches or reads from, on one bookshelf: **books, textbooks, workbooks and online sites**. It replaces the "Curriculum catalog" in the nav. Adding is a step-by-step pop-up walkthrough that searches the community catalog first.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `/next/library` (React), from **Library** in the nav; the setup wizard ends here (`?welcome=1`) |
| **Health** | **Works** (new in October 2026) |

## Scope

### What it does
- **The shelf:**
  - every item stands on a shelf with its cover: the book lookup's cover, an uploaded one, or a generated cover in the subject's color with the title
  - filter chips: **All · Books · Textbooks · Workbooks · Online sites**, with counts
  - each item says **Ready to schedule** or **"2 things to finish"**
- **Adding (the walkthrough), one step at a time:**
  1. **Find it.** One search box for an ISBN, title, author or series. Results come in groups:
     - **In the Curiculy catalog: ready to use**, with "170 lessons, 300 pages, entered by 3 families". **Add to my library** copies the details, chapters and lesson list in one step.
     - **Already in your library.**
     - **Book matches** from the book lookup, to start from.
     - **Can't find it? Add it yourself.**
  2. **The basics:** title, author, publisher, ISBN (pre-filled from a match).
  3. **What is this?** Four cards, each with one line saying what it means. A match pre-selects a guess ("Our guess").
  4. **The details for that kind.** Each field says why it's asked. Fields marked * are needed before it can be scheduled; it can still be saved without them.
  5. **Chapters** (books, optional; workbooks, required) or **the lesson list** (textbooks). Rows can be typed, pasted from a contents page ("Fractions, 62"; "12 The Lost Dog 45-49"), or made with "Make numbered lessons". Or **Skip for now**.
  6. **Done:** what's still missing and why, the item's place in the community catalog, and, for a textbook, **Plan a curriculum with it**.
- **Opening an item** (`?item=<id>`) shows:
  - its **Ready to schedule?** checklist
  - tabs for **Details**, **Chapters** or **Lesson list**, and **Cover**: upload a real cover image (not a photo of the book) or remove the upload
  - the curricula it's part of
  - **Delete**
  - **Plan a curriculum with it**, for a textbook

### Rules
- **Required fields per kind** (`app/services/library_rules.py`):
  - Book: author, total pages
  - Textbook: publisher, edition, subject, grade, total pages, and the full lesson list with names and pages
  - Workbook: subject, grade, total pages, chapters
  - Online site: website, subject, grade, lessons or minutes, days a week
- **A teacher's edition** is a textbook marked *for the parent*: no lesson list, never on a child's calendar.
- **Never a password** in the online-site note.
- **Contributed to the community catalog automatically,** once the item is ready to schedule (see [Community catalog](23-community-catalog.md)).
- **Covers:**
  - uploaded covers are shown from memory, because the API needs the sign-in token
  - lookup covers load from Open Library, archive.org or Google Books, which the Content-Security-Policy allows for images only

### API
`/api/library…` and `/api/reference` (the four kinds, with hints). See the [API reference](../5-engineering/api-reference.md#library-books-textbooks-workbooks-online-sites).

### Code
- `frontend/src/routes/LibraryPage.tsx`
- `frontend/src/components/library/`: `AddWalkthrough`, `ItemPanel`, `KindFields`, `StructureEditors`, `BookCover`
- `frontend/src/lib/structure.ts`: reading pasted chapters and lessons
- `frontend/src/api/parent.ts`
- Server: `app/routers/library.py`, `app/services/library.py`, `app/services/library_rules.py`

## Review (October 2026)
**Works well:** search-first adding means a catalog hit takes seconds; every required field explains itself; nothing blocks saving.

**Gaps:**
- reading a contents page from a photo (the vision import) isn't wired into the walkthrough yet
- **Schedule** for a single book, workbook or site (without a curriculum) is still to come
- barcode scanning isn't built yet

**Tests:** `frontend/src/routes/LibraryPage.test.tsx`; `tests/test_library.py`; the e2e smoke tests (adding a textbook by hand; the shelf's filters), the axe scan (`library`, `library-add`), and screenshots.
