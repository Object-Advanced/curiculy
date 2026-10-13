# Library and books (Curriculum catalog)

The family's shelf: the books and programs they use, found by ISBN or added by hand, and who is using what this year.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `#/curricula` ("Curriculum catalog") |
| **Health** | **Works, needs a simpler list-first layout** |

> **Replacing this page (core loop, 2026-10-12):** one **Library** that looks like a bookshelf, with filters (All · Books · Textbooks · Workbooks · Online sites); a step-by-step walkthrough for adding, search first (the community catalog, then ISBN lookups); four kinds of book, each with its own required fields; real cover images. Curricula move to their own page, the **Curriculum planner**: a textbook plus what goes with it, scheduled per child. The **community catalog** is built from every family's entries and reviewed by admins. **All three are built** (October 2026): see [Library](21-library.md), [Curriculum planner](22-curriculum-planner.md) and [Community catalog](23-community-catalog.md). This older page stays at `#/curricula` (no longer in the nav) until its tables are retired. See [Library](../6-planning/product-spine.md#library-one-shelf-four-kinds-of-book), [Curriculum planner](../6-planning/product-spine.md#curriculum-planner-a-textbook-and-what-goes-with-it) and [Community catalog](../6-planning/product-spine.md#community-catalog-built-by-every-family).

## Scope

### What it does
- **Catalog list** of books and programs, with filters (all / scheduled / …) and a switch between books and lesson plans.
- **Add curriculum** by **ISBN lookup** (barcode number) or by hand: title, subject, publisher, and page count (pacing uses it).
- ISBN lookup checks the shared book cache first, then **Open Library**, then **Google Books**.
- **Auto-schedule** a book onto a child's calendar (see [Pacing](09-pacing-and-lesson-plans.md)).
- **Remove a book's schedule** (deletes its lessons that aren't done yet) or **delete the book**.
- **Enrollments and years:** enroll a child in a book for a school year; add a school year. These forms also appear in Settings.

### Out of scope today
- Scanning a barcode with the phone camera (Phase 6, nice-to-have).
- Sharing book structures between families (planned: the community catalog).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET / POST | `/api/curricula` | parent | List or add |
| GET / DELETE | `/api/curricula/{id}` | parent | Read or delete |
| DELETE | `/api/curricula/{id}/schedule` | parent | Remove the book's unfinished lessons |
| GET | `/api/curricula/{id}/tree`, `/resources` | parent | The book's units and resources |
| POST | `/api/curricula/import` | parent | **API only**: import a program's structure from JSON or CSV |
| POST | `/api/catalog/lookup-isbn` | parent | ISBN → book details for the Add form (what the app uses) |
| POST | `/api/catalog/from-isbn` | parent | **API only**: ISBN → book added straight to the library |
| POST | `/api/books/resolve`, GET `/api/books/isbn/{isbn}`, GET `/api/books/{id}` | parent | **API only**: the scanner's entry point |

### Data
- **Shared** (the book cache tables): book editions, works, authors and publishers, which act as a cache of looked-up ISBNs.
- **The family's own rows:** `curricula`, `curriculum_editions`, `curriculum_units`, `curriculum_resources`, `enrollments`.

### Code
- `app/routers/curricula.py`, `catalog.py`, `books.py`, `enrollments.py`
- `app/services/catalog.py`, `resolver.py`, `providers/` (Open Library, Google Books), `curriculum_import.py`, `curriculum_structure.py`
- `static/js/app.js`: `renderCurricula`, `lookupIsbn`

## Review (October 2026)

### Working well
- **Careful ISBN lookup:**
  - It checks the cache first.
  - It tells "this book doesn't exist" apart from "the providers are down".
  - It handles ISBN-10 and ISBN-13.
- **Well tested:** 26 ISBN tests, 23 resolver tests, 31 provider tests.

### Problems and risks
- **Four ways in for ISBNs** (lookup-isbn, from-isbn, books/resolve, books/isbn). The app uses only one; the other three are API-only.
- **Crowded page.** The Add form permanently takes half the page; there are two ISBN fields; enroll and school-year forms repeat what's in Settings.
- **Different words for the same result.** Books say "Auto-schedule" and lesson plans say "Apply".
- **The "Source" column shows internal values** (`manual`, `barcode`).
- **Confusing names:** `/curricula` (library) and `/curriculum` (lesson plans) differ by one letter.
- The `curricula` router holds 17 queries and some business rules that belong in services.

### Tests
- `test_curricula_api.py` (10 tests), `test_curriculum_import.py` (42), `test_catalog_api.py` (14), `test_books_api.py` (15), `test_isbn.py` (26), `test_resolver.py` (23), `test_providers.py` (31), `test_metadata.py` (16)
- e2e: "a parent adds a book to the library by hand"

### Recommendations
| Priority | What | When |
|---|---|---|
| High | One Library bookshelf with filters; search-first adding; four kinds (reading book, workbook, curriculum, online program) with their own required fields; real cover images; the community catalog with admin review. One verb, **Schedule**. | Core loop |
| Medium | Rename `/curricula` → `/library` and `/curriculum` → `/guides`, keeping the old names for one release; put the ISBN entry points under `/catalog` | Phase 5 |
| Medium | Move the router's queries into services | Phase 5 |
| Low | Camera barcode scan | Phase 6, nice-to-have |
