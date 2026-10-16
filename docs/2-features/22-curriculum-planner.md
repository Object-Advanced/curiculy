# Curriculum planner

One subject's plan, usually built around **one textbook**, then put on the calendar for one or more children. A subject without a textbook can be built around a workbook, an online site or a book instead, and the parent picks the pace. It has its own page, separate from the Library. (One book on its own is scheduled from the [Library](21-library.md) instead: **Schedule it**.)

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
  1. **Which textbook is it built around?** The family's textbooks, or a link to add one. Below that, **No textbook for this subject?** lists the family's workbooks, sites and books, and **Build it around…** starts there instead.
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
    - **without a textbook, how fast:** pages a day, a chapter or more a day (books and workbooks with chapters), finish by a date, or the rest of the school year (an online site measured in lessons: one lesson a session until it's done)
     - **about how many minutes a lesson** (optional): kept as the course's default, and given to each lesson that has no length of its own (a textbook lesson's minutes, or an online site's session length, come first)
     - **Preview the dates** shows each book's count and dates, the finish date, and a warning if it ends after the school year
     - **Put it on the calendar** saves it, then **Go to the calendar**
- **On the calendar:** each child's course and dates, with **Change days or pause** (its lessons from today move onto the new days, or around the pause, after a preview; see [Catch up and moving lessons](26-catch-up-and-moves.md)) and **Take off the calendar**. Finished lessons stay.
- **Books to read** in a scheduled curriculum go on each child's [reading list](24-reading-lists.md), counting toward the curriculum's subject. Taking the course off the calendar takes a never-started book off the list.
- **The calendar hand-off:**
  - the legacy calendar opens on the week the lessons start (`#/assignments?from=planner&date=…`)
  - it shows a three-step card: each day's lessons; moving one; sick days, days off and Recalibrate
  - **Got it** dismisses the card, and a reload doesn't bring it back

### Rules (pacing)
See `app/services/planner.py` and [Product spine: Curriculum planner](../6-planning/product-spine.md#curriculum-planner-a-textbook-and-what-goes-with-it):
- **The textbook sets the pace:** one lesson each course day.
- **Without a textbook,** the first workbook (else book, else online site) sets the pace, at the parent's choice:
  - **pages a day:** the course runs as many days as its pages need (the answer key and front matter left out)
  - **chapters a day:** whole chapters each day, "ch. 3–4"
  - **finish by:** every school day up to that date
  - **an online site measured in lessons:** as many weeks as its lessons need, on its days a week
  - **otherwise:** the rest of the school year (36 weeks when there's no year to go by)
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
- curricula without a textbook aren't shared with the catalog (suggestions are found through a textbook)
- the moves and catch-up formulas of the spine's calendar come later
- the calendar tour is a simple card in the legacy calendar until the React calendar exists

**Tests:**
- `frontend/src/routes/PlannerPage.test.tsx`, `tests/test_planner.py`
- e2e smoke test: textbook → plan → preview → calendar → tour
- the axe scan (`planner`, `curriculum`) and screenshots
