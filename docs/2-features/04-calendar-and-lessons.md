# Calendar and lessons

The family's school calendar. Every lesson (an "assignment" in the code) lives here, and the lesson details open from here.

| | |
|---|---|
| **Who uses it** | Parents (the full calendar); kids see their own lessons on [My work](06-kid-my-work.md) |
| **Where** | `#/assignments` ("Calendar") and the lesson details dialog |
| **Health** | **Works, needs a redesign for phones and for "All Students"** |

> **Planned (core loop, 2026-10-11):** move one lesson or a whole day with a preview, checks against the family's and the state's guidelines, and an agenda list on phones. See [Calendar: move things, stay within the guidelines](../6-planning/product-spine.md#calendar-move-things-stay-within-the-guidelines).

## Scope

### What it does
- **Views:** Day, Week and Month for one child, or **All Students**. Previous, Today and Next move through time.
- **Add a lesson** by hand (title, date, notes, optional book).
- Toolbar shortcuts:
  - **Recalibrate Schedule** (see [Recalibrate](10-recalibrate.md))
  - **Print Weekly Checklist** (a PDF; see [Portfolios and reports](14-portfolios-and-reports.md))
  - **Auto-schedule a book** (see [Pacing](09-pacing-and-lesson-plans.md))
- **Lesson status:** assigned, in progress, completed, skipped or excused. A parent can change any lesson. A child can change only their own.
- **Completion date:** checking a lesson off records the household's today as its `completion_date` (a lesson already dated keeps its date); unchecking it, or any other status, clears it. A lesson done ahead of schedule keeps the day it was really done, and the lesson editor can still save it as long as neither date is moved.
- **Shared lessons:** one lesson done by several kids (a "shared group"). When a parent checks it off, every child's copy is checked and dated; a child who finished their copy earlier keeps their own date.
- **Lesson details dialog:**
  - edit the lesson
  - grade it
  - attach work samples (photos or PDFs)
  - see the "Stuck?" nudge history
  - delete it
- **Attendance:** Yes/No radios in each day cell, per child (see [Attendance](12-attendance.md)).
- **Unsorted Evidence:** a side panel of Chrome-extension captures waiting to be filed onto a lesson (see [Evidence](13-evidence-and-capture.md)).

### Out of scope today
- **"All Students" shows only *shared* lessons**, not every child's lessons. You decided to change this to all lessons with filters.
- Drag to reschedule, an agenda list on phones, and moving through the grid with the keyboard.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/students/{id}/assignments` | parent; the child for themselves | One child's lessons in a date window (`start_date`, `end_date` or `period`) |
| GET | `/api/calendar` | parent | All Students: shared lessons only |
| GET | `/api/students/{id}/courses` | parent | Progress per book for one child |
| GET / PUT / DELETE | `/api/assignments/{id}` | parent (GET also the child) | Details, edit, delete |
| POST | `/api/assignments` | parent | New lesson |
| PATCH | `/api/assignments/{id}/status` | parent; the child for their own | Check off or change status; sets or clears `completion_date` |
| PUT | `/api/assignments/{id}/grade` | parent | Grade |
| POST | `/api/assignments/{id}/evidence` | parent | Attach a photo or PDF (20 MB cap; images shrunk to 1600 px) |

### Data
The household database holds:
- `assignments`: student, title, `scheduled_date`, `completion_date`, `status`, `notes`, links to the book, unit and resource, and an optional `shared_group_uuid`
- `assignment_grades`
- `assignment_evidence`

### Code
- `app/routers/assignments.py`, `app/routers/calendar.py`
- `app/services/assignments.py` (`AssignmentQuery`, `resolve_window`)
- `static/js/app.js`: `renderAssignments`, `loadAssignmentsPage`, `renderDetail`, `openAssignment`

## Review (October 2026)

### Working well
- **Fast, careful reads.** `AssignmentQuery` loads everything a lesson needs up front, so the calendar doesn't make one query per lesson.
- **Safe access.** A child can never read or change a sibling's lesson.
- **Calm status colors since Phase 2:** amber for scheduled, green for done, red for overdue. All meet contrast rules in light and dark.

### Problems and risks
- **Phones:**
  - Below 900 px the month view becomes a single column about 5,000 px tall, with no weekday names.
  - The toolbar has up to 8 controls.
  - The dialogs aren't bottom sheets.
- **All Students looks broken.** Private lessons don't show, so a parent's view of the week looks empty.
- **Attendance radios in every cell** crowd the grid.
- **Lessons checked off before October 2026 have no `completion_date`.** Check-off records it now, but older lessons were never dated. Home and Portfolios count by status, so only the planned Sticker Journal notices.
- **Every assignment shows "Subject: Unfiled."** The subject should come from the book.
- **Leftover code:** the `apply_to_group` parameter on evidence upload is ignored but still accepted.

### Tests
- `test_assignments_api.py` (99 tests), `test_child_assignment_status.py` (8), `test_education.py` (20)
- e2e: `smoke.spec.ts` covers day, week and month and adding plus checking off a lesson; `visual.spec.ts` snapshots week and month; the a11y scan reports 0 serious issues.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | All Students shows every lesson, with a filter chip per child; a shared lesson appears once with each child's avatar | Phase 5 (API) + Phase 6 (screen) |
| High | Phone layout: an agenda list, a compact toolbar plus an overflow menu, and bottom sheets | Phase 6 |
| Medium | Attendance as one popover per day instead of radios in every cell | Phase 6 |
| High | Real subjects, from the curriculum; remove "Subject: Unfiled" | Core loop |
| High | Move a lesson or a day with a preview and guideline checks (drag on computers, Move to… on phones) | Core loop |
