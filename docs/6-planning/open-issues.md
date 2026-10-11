# Open issues (from the October 2026 reviews)

Every problem the feature reviews found, in one prioritized list. Each links to the page with the details.
- **Now:** worth doing before the next feature work.
- **Launch:** required before the public launch (June 2027).
- **Later:** improvements.

## Core loop (the product spine)
The gaps between the app and its purpose, found on 2026-10-11. Each is planned in [Product spine](product-spine.md).

| # | Issue | Fix |
|---|---|---|
| C1 | **No requirement layer.** Reports print whatever exists; nothing knows what *should* exist or what's missing. | Requirement packs, Records, Tasks; Pennsylvania first |
| C2 | **Subject isn't real** ("Subject: Unfiled"); no lesson minutes; no terms on the school year | Subjects, minutes, terms |
| C3 | **Two unconnected curriculum structures** (library units and lesson plans); the same book can exist twice | One Curriculum + Materials + Guide model |
| C4 | **Books and programs share one setup** | Two shelves: Add curriculum · Add reading book |
| C5 | **Work samples are slow to add, and captures don't know who or what** | Add work on the lesson, ask at check-off, snap the stack, inbox suggestions |
| C6 | **Attendance isn't suggested,** and there's no "everyone present" | "School today?" card and weekly sweep |
| C7 | **The calendar can't move one lesson, preview a change, or check it against any rules** | Move engine with previews and the plan checker |
| C8 | **No state or structured grade** on the household and children | State at sign-up; grades from a fixed list, re-confirmed each July 1 (no birth date, on purpose) |
| C10 | **No way to record subjects that have no curriculum** (PE, music, art, safety) | Activities |
| C11 | **No transcript or credits for grades 9–12** | Courses carry credits; a running transcript |
| C12 | **No guided setup:** a new family has to find Library, Settings and Calendar on their own | The year-setup interview |
| C13 | **Phone photos can be stored sideways:** uploads drop the EXIF rotate tag without applying it (found while confirming GPS is stripped) | `ImageOps.exif_transpose` before re-saving, plus tests |
| C14 | **PDF work samples keep their metadata** | Scrub with PyMuPDF on upload |
| C9 | **No shared guides between families** | Community guides v1 |

## Now
| # | Issue | Where | Fix |
|---|---|---|---|
| 1 | **No off-site backup.** A fire or theft loses the server and its backups together. | [Backups](../4-operations/backups-and-restore.md) | Copy `/datalake/projects/curiculy/backups` off-site (restic, rclone or a drive). Owner task. |
| 2 | **No outside uptime monitor or alerts** | [Monitoring](../4-operations/monitoring.md) | A free uptime check on `/api/health` |
| 3 | **Public `/docs` and `/openapi.json`** on curiculy.com | [Security](../4-operations/security-and-privacy.md) | Turn them off in production |

## Launch
| # | Issue | Where | Fix (phase) |
|---|---|---|---|
| 4 | The sign-in token is kept in browser storage | [Accounts](../2-features/01-accounts-and-sign-in.md) | Cookie sessions plus CSRF (3) |
| 5 | No self-serve password reset, email verification, sign out everywhere, account deletion or export | [Accounts](../2-features/01-accounts-and-sign-in.md) | (8) |
| 6 | COPPA: consent, how long data is kept, parent access and deletion, legal documents | [Security](../4-operations/security-and-privacy.md) | (8), legal sign-off by April |
| 7 | AI depends on one home GPU, with no per-household limits and no safety evaluations | [AI features](../2-features/17-ai-features.md) | Hosted provider plus an evaluation suite (8) |
| 8 | Background jobs (PDF and paper reading, portfolio email) run inside the web process, with no retries | [Pacing](../2-features/09-pacing-and-lesson-plans.md), [Portfolios](../2-features/14-portfolios-and-reports.md) | A jobs table plus a worker (8) |
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
| 25 | `ai_generator.py` is plain arithmetic; placeholder models `Jurisdiction` and `CompliancePacket` | [Pacing](../2-features/09-pacing-and-lesson-plans.md), [Data model](../5-engineering/data-model.md) | Rename; replace the placeholders with requirement packs (C1) |
| 26 | The legacy `app.js` has no unit tests or type checks (the React app has both) | [Testing](../5-engineering/testing-and-ci.md) | Retire `app.js` screen by screen; pyright for Python (6, 7) |
| 27 | No switch to turn nudges off per family or per child | [Stuck?](../2-features/07-stuck-nudges.md) | (4) |
| 28 | HEIC photos from iPhones are refused | [Evidence](../2-features/13-evidence-and-capture.md) | Convert HEIC on upload (part of C5) |
| 29 | The React app (`/next`) has no offline support and shares the legacy sign-in token | [My trail](../2-features/19-my-trail.md) | vite-plugin-pwa; cookie sessions (3) |
