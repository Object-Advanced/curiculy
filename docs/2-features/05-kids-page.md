# Kids page (a parent's view of one child's day)

A parent opens one child to see their day, check lessons off, and get a conversation starter.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `#/students` ("Kids"); the page title reads "Sam's day" |
| **Health** | **Solid since Phase 2b.** It will become a profile page in React. |

## Scope

### What it does
- **Tabs, one per child.** Each tab shows the child's color.
- **Today** card:
  - "1 of 2 complete", with today's lessons and check boxes (a small celebration plays on check-off)
  - **Recalibrate schedule** and **Print weekly checklist** in the card's heading
- **"Ask Sam":** a question for the parent to ask about today's book. A simple question appears at once; when the local AI is available, a better one about today's lessons replaces it.
- **Books in motion:** progress bars per book (lessons done out of the total).

### Out of scope today (by design)
Since Phase 2b, the kid-voice header ("Hey Sam — let's have a good day") and the daily puzzle are gone from this parent page. The puzzle now lives on the child's own [My work](06-kid-my-work.md) page as "Just for fun".

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/students/{id}/assignments?start_date=today` | parent | Today's lessons |
| GET | `/api/students/{id}/courses` | parent | Progress per book |
| GET | `/api/students/{id}/spark` | parent | A question about today's lessons from the AI (optional) |
| PATCH | `/api/assignments/{id}/status` | parent | Check off |

### Code
- `static/js/app.js`: `renderStudents`, `loadStudentDashboard`, `renderTodayChecklist`, `renderTalkCard`, `renderActiveCourses`
- `app/services/spark.py`

## Review (October 2026)

### Working well
- **Calm and parent-voiced.** The actions a parent needs sit right next to today's list.
- **Never waits on the AI.** The local question shows first, and the AI's question replaces it only if it arrives.

### Problems and risks
- **Three names for one page:** the menu says "Kids", the title says "Sam's day", and the code says `students` and "My day".
- **The tabs use `role="tab"`** but have no matching tab panel or arrow-key movement.
- **"Books in motion"** shows only books scheduled with Auto-schedule. Older lesson plans don't link to a book.

### Tests
- e2e: `smoke.spec.ts` checks the calm layout (a "Today" heading, "Ask …", and no puzzle) and checking a lesson off; `visual.spec.ts` snapshots this page; the a11y scan reports 0 serious issues.

### Recommendations
| Priority | What | When |
|---|---|---|
| Medium | Make this a **profile page** per child: an avatar header, then tabs for Today · Work (photo grid) · Courses · Records | Phase 4–6 |
| Medium | One name: "Kids" in the menu, the child's name as the title | Phase 4 |
| Low | Proper tabs: tab panels and arrow keys | Phase 4 |
