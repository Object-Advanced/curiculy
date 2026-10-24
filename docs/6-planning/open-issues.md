# Open issues (from the October 2026 reviews)

Every problem the feature reviews found, in one prioritized list. Each links to the page with the details. The 2026-10-23 code review is sequenced as pull requests in [Technical debt](technical-debt.md). This list stays the inventory. That page is the order to land the debt.
- **Now:** worth doing before the next feature work.
- **Launch:** required before the public launch (June 2027).
- **Later:** improvements.

## Core loop (the product spine)
The gaps between the app and its purpose, found on 2026-10-11. Each is planned in [Product spine](product-spine.md).

| # | Issue | Fix |
|---|---|---|
| C1 | **No requirement layer.** Reports print whatever exists; nothing knows what *should* exist or what's missing. | Requirement packs, Records, Tasks; Pennsylvania first |
| C2 | **Subject isn't real** ("Subject: Unfiled"). ~~No lesson minutes; no terms on the school year~~ **minutes and terms built 2026-10-15** | Subjects on lessons |
| C3 | **Two unconnected curriculum structures** (library units and lesson plans); the same book can exist twice | One Curriculum + Materials + Guide model |
| C4 | **Books and programs share one setup** (one form, no type, no author, no structure) | One Library, search-first adding, four kinds with their own required fields |
| C5 | **Work samples are slow to add, and captures don't know who or what** | Add work on the lesson, ask at check-off, snap the stack, inbox suggestions |
| C6 | ~~**Attendance isn't suggested,** and there's no "everyone present"~~ **Built 2026-10-16:** the "School today?" card (Home and Attendance), the two-week sweep and the year's counts. Still open: one dot per child on the calendar instead of radios; "Move Ada's lessons?" after a sick day (with the move engine) | [Attendance](../2-features/12-attendance.md) |
| C7 | **The calendar can't move one lesson, preview a change, or check it against any rules** | Move engine with previews and the plan checker |
| C8 | **No state or structured grade** on the household and children | State at sign-up; grades from a fixed list, re-confirmed each July 1 (no birth date, on purpose) |
| C10 | ~~**No way to record subjects that have no curriculum** (PE, music, art, safety)~~ **Fixed 2026-10-15** | [Activities](../2-features/25-activities.md); repeating activities still to come |
| C11 | **No transcript or credits for grades 9–12** | Courses carry credits; a running transcript |
| C12 | **No guided setup:** a new family has to find Library, Settings and Calendar on their own | The year-setup interview |
| C13 | **Phone photos can be stored sideways:** uploads drop the EXIF rotate tag without applying it (found while confirming GPS is stripped) | `ImageOps.exif_transpose` before re-saving, plus tests |
| C14 | **PDF work samples keep their metadata** | Scrub with PyMuPDF on upload |
| C9 | **No shared catalog between families** | The community catalog: automatic contribution of structure, checks, admin review |

## Now
| # | Issue | Where | Fix |
|---|---|---|---|
| 1 | **No off-site backup.** A fire or theft loses the server and its backups together. | [Backups](../4-operations/backups-and-restore.md) | Copy `/datalake/projects/curiculy/backups` off-site (restic, rclone or a drive). Owner task. |
| 2 | **No outside uptime monitor or alerts** | [Monitoring](../4-operations/monitoring.md) | A free uptime check on `/api/health` |
| 3 | ~~**Public `/docs` and `/openapi.json`** on curiculy.com~~ **Fixed 2026-10-15** | [Security](../4-operations/security-and-privacy.md) | Off unless `API_DOCS=true` |
| 3a | **Paper lesson-plan import can't run in production** (found 2026-10-13): the server's Ollama has only `llama3.1`, not the vision model it needs (`llama3.2-vision`). **2026-10-23:** the catalog no longer offers the sheet or the photo import, and a blank read is marked failed. The routes stay until nothing calls them. | [AI features](../2-features/17-ai-features.md) | **Decided 2026-10-13: don't install the vision model.** Retire the routes once they are unused. The Library's "Read a photo of the page" (Tesseract, no AI) covers printed pages. |

## Launch
| # | Issue | Where | Fix (phase) |
|---|---|---|---|
| 4 | The sign-in token is kept in browser storage | [Accounts](../2-features/01-accounts-and-sign-in.md) | Cookie sessions plus CSRF (3) |
| 5 | No self-serve password reset, email verification, sign out everywhere, account deletion or export | [Accounts](../2-features/01-accounts-and-sign-in.md) | (8) |
| 6 | COPPA: consent, how long data is kept, parent access and deletion, legal documents | [Security](../4-operations/security-and-privacy.md) | (8), legal sign-off by April |
| 7 | Parent-side AI (reading PDF and handwritten lesson plans) depends on one home GPU, with no per-household limits. No AI talks to children since 2026-10-13, so no child-safety evaluations are needed. | [AI features](../2-features/17-ai-features.md) | Hosted provider when the PDF import is rebuilt in the Library (8) |
| 8 | Background jobs (PDF and paper reading, portfolio email) run inside the web process, with no retries. **2026-10-23:** PDF text extraction runs on a worker thread, and that chat gives up after a bounded wait. A jobs table is still the launch fix. | [Pacing](../2-features/09-pacing-and-lesson-plans.md), [Portfolios](../2-features/14-portfolios-and-reports.md) | A jobs table plus a worker (8) |
| 9a | **Backups: no continuous archive yet** (a restore reaches last night, not any minute) | [Backups](../4-operations/backups-and-restore.md) | WAL archiving with pgBackRest or WAL-G (layer 1) |
| 9 | Work samples on one disk, with no per-household limit | [Evidence](../2-features/13-evidence-and-capture.md) | Storage interface plus S3 and limits (8) |
| 10 | The Chrome extension asks for every website and isn't published | [Evidence](../2-features/13-evidence-and-capture.md) | Narrow the permissions; Web Store by April (7–8) |
| 11 | Rate limits live in memory | [Accounts](../2-features/01-accounts-and-sign-in.md) | Edge limits (8) |
| 12 | Unmaintained `passlib`; the image runs as root; production mounts source code | [Security](../4-operations/security-and-privacy.md) | (7) |
| 13 | No load test, disaster-recovery drill or penetration test | [Testing](../5-engineering/testing-and-ci.md) | Before M4 |

## Later (screens and cleanup)
| # | Issue | Where | Fix (phase) |
|---|---|---|---|
| 14 | Home shows counts, not each child's lessons; no overdue banner | [Home](../2-features/03-home.md) | Content-first Today (6) |
| 15 | Calendar on phones: a 5,000 px month column and a crowded toolbar | [Calendar](../2-features/04-calendar-and-lessons.md) | Agenda list, bottom sheets (6) |
| 16 | "All Students" shows only shared lessons | [Calendar](../2-features/04-calendar-and-lessons.md) | All lessons plus filters (5–6) |
| 17 | Attendance radios in every cell | [Attendance](../2-features/12-attendance.md) | One popover per day (6) |
| 18 | Settings scattered; three school-year editors | [Settings](../2-features/02-household-setup-and-settings.md), [School year](../2-features/11-school-year-and-days-off.md) | One Settings area (4) |
| 19 | Names drift (Kids / My day / Someone's day; Exceptions vs Days off; Auto-schedule vs Apply) | [Glossary](../1-overview/glossary.md) | Words decided 2026-10-11; applied as screens are rebuilt |
| 20 | "Subject: Unfiled" everywhere | [Calendar](../2-features/04-calendar-and-lessons.md) | Subject from the book (5) |
| 21 | About 9 requests to open Home; days off re-fetched on every calendar move | [Home](../2-features/03-home.md) | `/api/workspace`, a date-windowed days-off list (5) |
| 22 | Notifications poll every 30 s even in hidden tabs; no phone push | [Notifications](../2-features/15-notifications.md) | (6–8) |
| 23 | Offline cold start shows an empty app | [Offline](../2-features/16-offline-and-sync.md) | Workbox data caching (3) |
| 24 | Four ISBN entry points; `/curricula` vs `/curriculum` | [Library](../2-features/08-library-and-books.md) | Consolidate and rename (5) |
| 25 | `ai_generator.py` is plain arithmetic (the placeholder models were removed in the move to Postgres) | [Pacing](../2-features/09-pacing-and-lesson-plans.md) | Rename it `pacing_math.py` |
| 26 | The legacy `app.js` has no unit tests or type checks (the React app has both) | [Testing](../5-engineering/testing-and-ci.md) | Retire `app.js` screen by screen; pyright for Python (6, 7) |
| 27 | No switch to turn nudges off per family or per child | [Stuck?](../2-features/07-stuck-nudges.md) | (4) |
| 28 | HEIC photos from iPhones are refused | [Evidence](../2-features/13-evidence-and-capture.md) | Convert HEIC on upload (part of C5) |
| 29 | The React app (`/next`) has no offline support and shares the legacy sign-in token | [My trail](../2-features/19-my-trail.md) | vite-plugin-pwa; cookie sessions (3) |
