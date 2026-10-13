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
  1. **Find it.** One search box for an ISBN, title, author or series, or **Scan the barcode** on the back cover. Results come in groups:
     - **In the Curiculy catalog: ready to use**, with "170 lessons, 300 pages, entered by 3 families". **Add to my library** copies the details, chapters and lesson list in one step.
     - **Already in your library.**
     - **Book matches** from the book lookup, to start from.
     - **Can't find it? Add it yourself.**
  2. **The basics:** title, author, publisher, ISBN (pre-filled from a match).
  3. **What is this?** Four cards, each with one line saying what it means. A match pre-selects a guess ("Our guess").
  4. **The details for that kind.** Each field says why it's asked. Fields marked * are needed before it can be scheduled; it can still be saved without them.
  5. **Chapters** (books, optional; workbooks, required) or **the lesson list** (textbooks). Rows can be:
     - typed
     - pasted from a contents page ("Fractions, 62"; "12 The Lost Dog 45-49")
     - **read from a photo of the page**
     - made with "Make numbered lessons"

     Or **Skip for now**.
  6. **Done:** what's still missing and why, the item's place in the community catalog, and, for a textbook, **Plan a curriculum with it**.
- **Scanning a barcode:**
  - **Live**, where the browser can read barcodes (Chrome, Android): point the camera at the back cover.
  - **From a photo** everywhere else (iPhones): Curiculy reads the photo with OpenCV's barcode reader, at several sizes and turned, for sideways photos.
  - Only book barcodes count (ISBNs, starting 978 or 979); any other barcode is explained.
- **Reading a photo of the page:**
  - Tesseract reads the printed text, after the dotted leaders between names and page numbers are erased (they confuse it).
  - Each line is tidied for the paste rules: leftover leaders are cut, and look-alike letters in page numbers are fixed ("L45" is 145). Lines without a page number, like "Contents", are left out.
  - The text lands in the paste box for the parent to check before **Add these**.
  - The photo is read in memory and never stored. No AI is involved.
- **Opening an item** (`?item=<id>`) shows:
  - its **Ready to schedule?** checklist
  - tabs for **Details**, **Chapters** or **Lesson list**, **Cover** (upload a real cover image, not a photo of the book, or remove the upload), and **Schedule**
  - the curricula it's part of
  - **Delete**
  - **Plan a curriculum with it**, for a textbook
- **Schedule it: one book on its own,** without building a curriculum:
  - The parent picks who, from when, and how fast: pages a day, chapters a day (when the chapters are entered), a finish date, or the rest of the school year.
  - A preview shows every date before anything is saved.
  - The item shows where it's **on the calendar**, with **Take off the calendar**.
  - Under the hood it's a one-item curriculum, marked `solo`. It isn't in the planner's list and is never shared with the catalog.
  - Deleting the book takes its schedule with it; finished lessons stay.

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
- `frontend/src/components/library/`: `AddWalkthrough`, `ItemPanel`, `KindFields`, `StructureEditors`, `BookCover`, `BarcodeScanner`
- `frontend/src/lib/structure.ts`: reading pasted chapters and lessons; `lib/isbn.ts`: book barcodes
- `frontend/src/api/parent.ts`
- Server: `app/routers/library.py`, `app/services/library.py`, `app/services/library_rules.py`, `app/services/barcodes.py`, `app/services/page_reader.py`

## Review (October 2026)
**Works well:** search-first adding means a catalog hit takes seconds; every required field explains itself; nothing blocks saving.

**Gaps:**
- scheduling a book by **minutes** a day ("read 20 minutes") isn't offered yet
- reading photos of handwriting (as opposed to print) needs the vision model, which isn't installed (see open issue 3a)

**Tests:**
- `frontend/src/routes/LibraryPage.test.tsx` (including scanning from a photo, reading a page photo, and scheduling one book)
- `tests/test_library.py`
- `tests/test_photo_readers.py`: real barcodes (drawn, then turned) and real contents pages, read by the real Tesseract
- the e2e smoke tests: adding a textbook by hand; the shelf's filters; scheduling one book
- the axe scan (`library`, `library-add`) and screenshots
