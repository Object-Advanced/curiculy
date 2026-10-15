# "Stuck?" nudges (formerly homework help)

When a child is stuck on a lesson, they get **one small nudge back toward their own materials**. If they're still stuck, they **go get a grown-up**, and the parent is told.

| | |
|---|---|
| **Who uses it** | Kids (ask); parents (are told, can allow another nudge) |
| **Where** | The "Stuck?" card on a lesson in My work; the "Stuck? nudges" section in a parent's lesson details |
| **Health** | **Solid** (redesigned 2026-10-10; no AI since 2026-10-13) |

## Scope

**No AI talks to children** (decided 2026-10-13). The nudge is built from the lesson itself, and the child types nothing.

### The flow
1. **Stuck?** The child taps **Give me a nudge**, or skips straight to **Get a grown-up**. There's nothing to type.
2. **Here's a nudge.** One or two sentences pointing back to their own materials. The most specific one the lesson allows:
   - **a textbook lesson from the Curriculum planner:** "Open Saxon Math 5/4 to pages 45–49 and read the directions again, out loud. Look for an example on the page or the page before."
   - **a workbook or reading lesson:** the same, with the pages from the lesson ("Open Spectrum Math 4 to pages 18–20…")
   - **an online site:** "Go back to IXL Math and look at its example or hint, then try the first one again."
   - **an older lesson with a book:** "Look in Saxon Math 5/4 and read the directions again…"
   - **otherwise:** "Read the directions one more time, out loud. Then look for an example in your book or on the page before."

   The parent's note on the lesson is added when there is one: "Your grown-up left a note: “Use the blue workbook.”"
3. **That helped!** or **Still stuck? Get a grown-up.** The second shows "Time to find a grown-up… Bring your book!" and notifies the parent: "*Ada needs you*".

### Rules
- **One nudge per lesson.** Coming back shows the same nudge. A parent can choose **Allow another nudge** in the lesson details.
- **The nudge never answers, solves, explains, or gives a worked example.** It only says where to look.
- **Nothing typed, nothing sent anywhere.** The child's tap is recorded as "I'm stuck."; no AI is called (a test trips if anything in the flow reaches a model).
- At most 280 characters; a long parent note is shortened to fit.
- **The parent sees exactly what was said.** The notification "Ada asked for a nudge" quotes it. The lesson details show the tap, the nudge, and the outcome.
- Help activity is no longer written into the parent's own lesson notes.
- Nudge requests are never queued offline; they need a live answer.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/homework-help/sessions` | the child | Open (or reopen) the nudge for a lesson |
| POST | `/api/homework-help/sessions/{id}/nudge` | the child | The one nudge, built from the lesson |
| POST | `/api/homework-help/sessions/{id}/outcome` | the child | `helped` or `ask_grown_up` |
| GET | `/api/homework-help/sessions?assignment_id=` | the parent, or the child for their own | History |
| POST | `/api/homework-help/assignments/{id}/unlock` | parent | Allow another nudge |

The session status is one of:
- `active`: opened, nudged or not
- `helped`: the child said it helped
- `redirected`: went to a grown-up
- `closed`: a parent allowed another nudge

### Data
The household database holds `homework_help_sessions`, `homework_help_messages` and `parent_notifications`.

### Code
- `app/routers/homework_help.py`
- `app/services/homework_help.py`: `nudge_for` (where to look, from the lesson's book and pages) and the parent's note
- `static/js/app.js`: `renderStuckCard`, `askForNudge`, `recordStuckOutcome`, `renderHomeworkHelpHistory`

## Review (October 2026)

### Working well
- **Matches the product principle exactly:** guide, don't teach. It can only point at the family's own book and pages.
- **Safe by construction:** no AI, nothing typed by the child, and the parent sees everything.
- **Better with the Curriculum planner:** planner lessons know their book and pages, so the nudge names them.
- **Covered end to end by tests:** the backend rules plus a browser walk through all three steps.

### Problems and risks
- **There's no parent setting to turn nudges off** for a household or a child.
- Older parent notes may still contain old `[Homework help]` log lines. Kids don't see them; parents still do.
- Until 2026-10-13 the nudge was written by the family server's AI model, and children could type what was tricky. Both are gone.

### Tests
- `test_homework_help.py`:
  - one nudge only
  - helped, grown-up, and the parent's reset
  - permissions
  - where the nudge points: textbook pages, workbook and reading pages, an online site, an older lesson's book, the parent's note, trimming
  - a tripwire: nothing in the flow reaches an AI model
- e2e: `kid.spec.ts` walks Stuck? → nudge → grown-up (with nothing to type) and checks the parent's notification.

### Recommendations
| Priority | What | When |
|---|---|---|
| Medium | A Settings switch to turn nudges off per household or per child | Phase 4 |
| Low | A one-time cleanup of old `[Homework help]` lines in notes | Phase 5 |
