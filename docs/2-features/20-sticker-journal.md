# Sticker journal (kid)

The child's sticker book: this week's stickers by day, a tent on each day they reached camp, and the month's seasonal collection. It's the second React screen, next to [My trail](19-my-trail.md).

| | |
|---|---|
| **Who uses it** | Kids (their own journal); parents can preview any child's |
| **Where** | `/next/journal`. Reach it from **Sticker journal** on the kid's My work page, or the **Sticker journal** tab on My trail. A parent keeps the chosen child (`?student=<id>`). |
| **Health** | **Works** (new in October 2026; part of Phase 3) |

## Scope

### What it does
- **This week (Monday to Friday):** Saturday and Sunday appear only when something happened.
  - **Stickers:** each finished lesson's **subject sticker**, on the day it was finished.
  - **Camp tent** on a day when every lesson scheduled that day is done. Today shows **"N stops to go"** linking to My trail.
  - **Other days:** "Rest day" for school days without lessons, "Coming up" for future days. A missed camp is just a dashed tent, never a red mark.
- **Tap a sticker** to see which lesson earned it: "Your Math sticker is from 'Saxon Math Lesson 41', finished on Tuesday."
- **Week before / Week after** pages back through earlier weeks. It can't go into the future.
- **Monthly collection** (for example "October collection"):
  - **8 seasonal stickers.** Each camp day wins that day's prize, the same one My trail shows ("You earned the Harvest moon sticker").
  - **Earned** stickers show in colour, **today's prize** is outlined, and the rest are **mysteries**. A count shows progress ("2 of 8").
- **Parent preview:** the same child chips as My trail. The header says how many stickers that week has.

### Rules
- **Sticker day = the lesson's `completion_date`.** Checking a lesson off has recorded it since October 2026. **Older finished lessons have no date, so they appear on the day they were scheduled.** That way the journal isn't empty for work done before then.
- **Camp is reached on a day when it had lessons and all of them are done.** That's the same rule as My trail, and it counts even if some were finished later.
- **A lesson scheduled one day and finished another** puts its sticker on the finish day and its camp on the scheduled day.
- **Read-only:** the journal never changes lessons.

### Out of scope (next)
- **Cheers from home:** parents react to finished work and the child sees a sticker. This needs an `assignment_reactions` table and a parent button.
- Keeping a permanent, server-side record of earned stickers. Today they're worked out from lessons, so unchecking a lesson removes its sticker.
- Printing the journal page.

### API (no new endpoints)
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/auth/me` | signed in | Role and the child's details |
| GET | `/api/students` | parent | Children to preview |
| GET | `/api/students/{id}/assignments?start_date=&end_date=` | parent; the child for themselves | Lessons from a month before the shown week to the end of its month (one request) |

### Code
- `frontend/src/routes/JournalPage.tsx`
- `frontend/src/lib/journal.ts` (sticker day, camp days, the week, the collection)
- `frontend/src/lib/dates.ts` (week and month arithmetic)
- Shared with My trail: `frontend/src/api/kid.ts` (which child) and `components/KidHeader.tsx` (the three tabs)
- Legacy entry point: `renderKidHello` in `static/js/app.js`

## Review (October 2026)

### Working well
- **Turns finished work into something to collect,** with an encouraging, no-shame week view.
- **All rules live in one pure, tested module.** The edge cases are covered: late finishes, undated older lessons, weekends, month boundaries, camp only up to today.
- **Accessible:**
  - stickers are real buttons with names ("Math sticker: Saxon Math Lesson 41")
  - the detail line is announced
  - the axe scan reports 0 serious issues

### Problems and risks
- **Stickers are worked out from lessons, not stored.** Moving or unchecking a lesson changes past pages. That's honest, but a child may notice a sticker disappear.
- **The prize is decided by the date,** so two camp days can win the same sticker. The collection counts each sticker once.
- **No cheers yet,** so the journal is all self-earned.

### Tests
- **Vitest:** `journal.test.ts` (10 rule tests) and `JournalPage.test.tsx` (5 page tests: the week, sticker details, the collection, paging, tabs).
- **Playwright:**
  - a kid goes from My work → Sticker journal, taps a sticker, sees the collection, then goes to My trail
  - a parent switches to the journal and keeps the chosen child
  - visual snapshots in 5 sizes and themes
  - axe (`sticker-journal`: 0)

### Recommendations
| Priority | What | When |
|---|---|---|
| High | **Cheers from home:** a parent button on finished work, a sticker in the journal, and waiting at camp on My trail | Phase 3–6 |
| Medium | Store earned collection stickers so they never disappear | Phase 5 |
| Low | A printable journal page for the fridge | Later |
