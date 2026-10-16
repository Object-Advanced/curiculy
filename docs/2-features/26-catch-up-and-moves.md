# Catch up and moving lessons

When life happens, lessons move: one lesson to another day, a sick day's lessons, a course's days of the week, or a course that's fallen behind. Every move shows what it does first, keeps each course's lessons in order, and never moves a finished lesson.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | **Catch up** (`/next/catch-up`, React), reached from the Calendar's **Catch up** button, a lesson's **Move to…**, Home's "behind" line, and Attendance's "Move Ada's lessons from Thursday"; **Change days or pause** on a curriculum's courses in the planner |
| **Health** | **Works** (new in October 2026) |

## Scope

### What it does
- **Behind:** every course with lessons left on days that have passed ("Ada: 3 lessons behind, since Mon, Oct 12"), each with **Catch up**.
- **The catch-up sheet** ("How should Saxon 5/4 catch up?"), one card per option, each with its result in plain words ("Finishes Thu, Dec 17, on time"). Options that don't fit say why. One is **Recommended**: it finishes on time, with the smallest change to any single day, then the fewest moves.
  - **Use a day off:** the missed work goes on days the course doesn't meet (a 4-day course's Friday first, then weekends if **Allow weekends** is on), before the next test. Lessons shift only up to the last free day used; nothing after it moves.
  - **Double up:** missed course days share the coming days, two to a day, until caught up. Never on a test day, and never over the family's daily lesson limit. A course with fewer lessons left than it's behind simply finishes sooner.
  - **Push everything back:** every lesson from the first missed one slides forward onto the course's days, in order.
  - **Push back a whole week:** the same, starting next Monday.
  - **Skip it:** marks the missed lessons skipped, when they're all review lessons.
- **Move one lesson** ("Move to…"): pick the day, then
  - **Push the rest back:** everything after it in the course moves along too, or
  - **Just this one:** only the same book's lessons between the two days slide by one so their order holds; nothing after moves.
- **A day off or a sick day:** for one child or everyone, that day's lessons move forward: each course by one of its days, in order; lessons added by hand to the next school day. A day ahead can go on the calendar too, as a sick day or a day off.
- **Change a course's days or pause it** (from the planner): its lessons from today move onto the new days, or around the pause.
- **What changes** before anything moves: how many lessons move, each course's finish date before and after, the lessons themselves, and the plan checker's warnings.

### The plan checker (warnings, never blocks)
- "Saxon 5/4 now finishes Mon, Jun 7, after your school year ends Fri, Jun 4."
- "Thu, Oct 15 becomes 6 lessons for Ada (your limit is 5)." The limit is **Most lessons in a day, per child** in Settings.
- "1 lesson lands on Sat, Jan 2, not a school day for Ada."
- "Test 4 moves from Fri, Oct 23 to Mon, Oct 26."

### Rules
- **Nothing changes until it's applied, and what's applied is what was shown:** the plan is worked out again and compared with the preview's fingerprint; if the calendar changed in between (a lesson checked off in another tab), nothing is saved and the parent looks again.
- **Finished lessons never move.** Skipped and excused lessons stay where they are too.
- **Order:** a course's lessons for one day (Saxon's lesson and its worktext pages) move together; lesson 43 never lands before 42. Pulling a lesson earlier past an earlier lesson of its course is refused with the reason.
- **Lessons move to today or later,** never into the past.
- Lessons added by hand (not from the Curriculum planner) aren't in **Behind**; **Recalibrate** on the Calendar still catches those up.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/moves/preview` | parent | What a move would change (`kind`: `lesson`, `day`, `catch_up`, `course`). Saves nothing |
| POST | `/api/moves/apply` | parent | Apply it, with the preview's `plan_hash` (409 if the calendar changed) |
| GET | `/api/moves/behind` | parent | Courses with lessons on days that have passed |
| GET | `/api/moves/catch-up/{course_id}` | parent | The catch-up sheet: every option, its result and preview (`allow_weekends`) |

### Data
No new tables: moves change `assignments.scheduled_date` (or `status` to skipped), `courses.weekdays` and `courses.end_date`, and can add `calendar_exceptions`. The family's limit is `households.daily_lesson_limit`.

### Code
- `app/services/moves.py`, `app/routers/moves.py`, `app/schemas/moves.py`
- `frontend/src/routes/CatchUpPage.tsx`, `frontend/src/components/moves/` (`CatchUpSheet`, `MoveSheets`, `PreviewList`)
- `static/js/app.js`: `loadBehind` (Home), "Move to…" in the lesson details, **Catch up** on the calendar toolbar, the lesson limit in Settings

## Review (October 2026)
**Works well:** every option shows its result before anything moves; the recommendation follows the family's own limit and tests.

**Not built yet:**
- dragging a lesson on the calendar (with the React Calendar)
- **Stretch the pages**, **keep test days where they are**, and **how far to look**
- catching up every child at once (a family snow day uses **A day off or sick day** for everyone, which pushes each course back)
- "Remember this for Saxon" and a family-wide default; "None of these fit?"
- the state's numbers in the warnings ("176 of 180 days planned"), with the requirement packs
- **Change days or pause** for a single book scheduled from the Library
- a finished lesson moving to the day it was done ("Done on Tuesday, or today?")

**Tests:**
- `tests/test_moves.py` (each move, the sheet and its recommendation, the plan checker, stale previews); the cross-family probe
- `frontend/src/routes/CatchUpPage.test.tsx`
- the e2e smoke tests (catching a course up; moving one lesson) and the axe scans (`catch-up`, `catch-up-sheet`). No screenshots: what the page shows follows the server's real date.
