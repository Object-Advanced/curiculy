# Curriculum planner

One subject's plan, built around **one textbook**, then put on the calendar for one or more children. It has its own page, separate from the Library.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `/next/planner` (React), from **Curriculum planner** in the nav, or **Plan a curriculum with it** on any textbook |
| **Health** | **Works** (new in October 2026) |

## Scope

### What it does
- **The list:** every curriculum with:
  - its textbook's cover, subject and grade
  - what's in it ("1 textbook · 1 workbook · 4 books to read")
  - **Ready to schedule** or what's left
  - whose calendar it's on, and the dates
- **"How curricula work":** three steps in plain words (pick the textbook; add what goes with it; put it on the calendar).
  - It's shown before the first curriculum, and can be hidden or brought back with **How this works**.
- **Starting one** (`/next/planner/new?textbook=<id>`):
  1. **Which textbook is it built around?** The family's textbooks, or a link to add one.
  2. **Other families built a similar curriculum:** each combination families used, with how many families and which books are already theirs. There are three ways in:
     - **Start from this one** takes the whole combination.
     - **Choose pieces** keeps the textbook and lets the family untick what they'll swap, such as different novels.
     - **Build it** (or "Or build your own") starts with just the textbook.
- **A curriculum** (`/next/planner/<id>`), in four numbered steps:
  1. **The basics:** name, subject, grade, days a week (from the textbook).
  2. **What goes with it:** the textbook, workbooks, online sites, books to read and the teacher's edition, each in its role with what the role means.
     - **Add from your library**, with the role guessed from the kind.
     - **Other families used these with [textbook]**: one tap adds a catalog book to the library and the curriculum.
  3. **Ready to schedule?** Anything not ready is named, with what it's missing and a link to finish it in the Library.
  4. **Put it on the calendar:**
     - which children (one is picked automatically), a start date (next Monday by default), and which days (after the first preview)
     - **Preview the dates** shows each book's count and dates, the finish date, and a warning if it ends after the school year
     - **Put it on the calendar** saves it, then **Go to the calendar**
- **On the calendar:** each child's course and dates, with **Take off the calendar**. Finished lessons stay.
- **The calendar hand-off:**
  - the legacy calendar opens on the week the lessons start (`#/assignments?from=planner&date=…`)
  - it shows a three-step card: each day's lessons; moving one; sick days, days off and Recalibrate
  - **Got it** dismisses the card, and a reload doesn't bring it back

### Rules (pacing)
See `app/services/planner.py` and [Product spine: Curriculum planner](../6-planning/product-spine.md#curriculum-planner-a-textbook-and-what-goes-with-it):
- **The textbook sets the pace:** one lesson each course day.
- **Workbook pages** are spread over the same days, a chapter at a time, never the answer key.
- **Online sites** run on their own days a week.
- **Books to read** are read one after another.
- **Teacher's editions** are never scheduled.
- **Days off are skipped:** the household's, and each child's own.
- **A 4-day program on a 5-day week** leaves the last day free.

### API
`/api/planner/…`. See the [API reference](../5-engineering/api-reference.md#curriculum-planner).

### Code
- `frontend/src/routes/PlannerPage.tsx`, `NewCurriculumPage.tsx`, `CurriculumPage.tsx`
- `frontend/src/components/planner/`: `PlannerIntro`, `Suggestions`, `ScheduleStep`
- Server: `app/routers/planner.py`, `app/services/planner.py`
- The calendar hand-off: `takePlannerHandoff` and `showPlannerTour` in `static/js/app.js`

## Review (October 2026)
**Works well:** nothing is saved without a preview; suggestions make a second family's setup fast; each step explains itself.

**Gaps:**
- curricula without a textbook (a workbook-only subject) aren't supported yet
- the moves and catch-up formulas of the spine's calendar come later
- the calendar tour is a simple card in the legacy calendar until the React calendar exists

**Tests:**
- `frontend/src/routes/PlannerPage.test.tsx`, `tests/test_planner.py`
- e2e smoke test: textbook → plan → preview → calendar → tour
- the axe scan (`planner`, `curriculum`) and screenshots
