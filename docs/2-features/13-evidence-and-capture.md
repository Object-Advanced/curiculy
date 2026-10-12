# Evidence and capture (work samples)

Photos, PDFs and screenshots of a child's work, attached to lessons so they appear in portfolios.

| | |
|---|---|
| **Who uses it** | Parents (attach, file); kids' computers (the Chrome extension sends screenshots) |
| **Where** | Lesson details → evidence; Calendar → **Unsorted Evidence** panel; Settings → Students → capture token; the **Curiculy Capture** Chrome extension |
| **Health** | **Solid** since Phase 1 hardening. The capture flow needs the phone camera and an extension store listing. |

> **Planned (core loop, 2026-10-11):** parent capture for launch: **Add work** on every lesson, an offer at check-off when a sample is wanted, "snap the stack", and inbox suggestions. The extension stays as an optional parent tool. See [Work samples](../6-planning/product-spine.md#work-samples-adding-them-should-take-seconds).

## Scope

### What it does
- **Attach a work sample** to a lesson: a photo (JPEG, PNG, WebP or GIF) or a PDF. iPhone HEIC photos aren't accepted yet.
  - **Up to 20 MB.**
  - The real file type is checked from its contents, not its name; anything else is refused.
  - Photos are shrunk to 1600 px and stored as WebP under random names.
- **Chrome extension, "Curiculy Capture":**
  - one click screenshots the current tab and sends it to the household's **unsorted inbox**
  - it's paired with a **capture token** a parent makes in Settings → Students (valid 365 days; can be revoked)
  - **the token can only upload**: it can't read anything
- **Unsorted inbox:** a parent files each capture onto a lesson.
- **Viewing files:** only the household that owns a file can open it.
  - A child can open only files on their own lessons.
  - Images display in the page; other files download.

### Out of scope today
- Capturing straight from a phone's camera (the "＋" quick-add is planned).
- A storage limit per household.
- Cloud storage (S3).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/assignments/{id}/evidence` | parent | Attach to a lesson |
| POST | `/api/evidence/staging` | parent or capture token | Send to the unsorted inbox |
| GET | `/api/evidence/staging` | parent | List the inbox |
| POST | `/api/evidence/link` | parent | File an inbox item onto a lesson |
| GET | `/api/evidence/files/{path}` | the owning household (a child only for their own lessons) | View or download |
| GET / POST / DELETE | `/api/auth/capture-token` | parent | Token status, make, revoke |

### Data
- **Files** live on the evidence volume: `/data/evidence/<household id>/…`, which is `/datalake/projects/curiculy/evidence` on the server.
- **Records:**
  - the family's own rows are in `assignment_evidence` and `evidence_staging`
  - the shared sign-in tables hold `capture_tokens`, so a stolen token can be revoked without changing the master secret

### Code
- `app/evidence/__init__.py`: type check, size cap, resizing, safe paths
- `app/routers/evidence.py`, `app/routers/assignments.py` (upload)
- `app/services/capture_tokens.py`
- `extension/`: Manifest V3, with `background.js`, `options.html` and `options.js`

## Review (October 2026)

### Working well
- **Strong safety checks:**
  - checks the real file type
  - size cap
  - blocks path tricks like `../`
  - refuses SVG
  - `nosniff` header
  - downloads for anything that isn't an image
  - every file belongs to one household
- **The capture token is narrowly limited** and can be revoked.

### Problems and risks
- **The extension asks for access to every website** (`http://*/*` and `https://*/*`). That's needed today to talk to any server address, but **Chrome Web Store review will push back.** It should ask only for the family's own server.
- **The extension isn't published.** Families have to load it by hand.
- **No storage limit per household,** and files sit on one disk. They are backed up nightly (see [Backups](../4-operations/backups-and-restore.md)).
- **The app loads images as blobs in the page,** which uses memory on large galleries.

### Tests
- `test_evidence_files_api.py` (10 tests), `test_evidence_staging_api.py` (8), `test_capture_token.py` (14)
- `test_http_hardening.py` (14) covers the size and type limits.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | **Parent capture:** Add work on the lesson, an offer at check-off, snap the stack, one photo for every sibling on a shared lesson, inbox suggestions | Core loop |
| High | Extension: ask only for the configured server (optional host permissions); publish it on the Chrome Web Store | Phase 7–8 (submit by April) |
| High | A storage interface: the local disk for self-hosting, S3-compatible storage with signed links for the public service; a limit per household | Phase 8 |
| Medium | Serve files by direct link, not loaded as blobs | Phase 6 |
