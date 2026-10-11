# "Stuck?" nudges (formerly homework help)

When a child is stuck on a lesson, they get **one small nudge back toward their own materials**. If they're still stuck, they **go get a grown-up**, and the parent is told.

| | |
|---|---|
| **Who uses it** | Kids (ask); parents (are told, can allow another nudge) |
| **Where** | The "Stuck?" card on a lesson in My work; the "Stuck? nudges" section in a parent's lesson details |
| **Health** | **Solid** (redesigned 2026-10-10) |

## Scope

### The flow
1. **Stuck?** The child can say what's tricky (optional, up to 500 characters) and taps **Give me a nudge**. They can also skip straight to **Get a grown-up**.
2. **Here's a nudge.** One or two sentences, such as "Read the directions one more time, out loud. Then look for an example in your book or on the page before."
3. **That helped!** or **Still stuck? Get a grown-up.** The second shows "Time to find a grown-up… Bring your book!" and notifies the parent: "*Ada needs you*".

### Rules
- **One nudge per lesson.** Coming back shows the same nudge. A parent can choose **Allow another nudge** in the lesson details.
- **The nudge never answers, solves, writes, explains, or gives a worked example.** The AI is told: "You are not their teacher."
- If the child asks for the answer ("just tell me the answer"), they get a **fixed reply** and the AI is not called.
- If the AI is unavailable, a **built-in nudge** is used, so the feature always works.
- Long AI replies are cut down to a nudge (at most 280 characters).
- **Privacy:** the AI sees only the child's **first name**, the lesson title, which book it's from, and the parent's note.
- **The parent sees exactly what was said.** The notification "Ada asked for a nudge" quotes it. The lesson details show the child's words, the nudge, and the outcome.
- Help activity is no longer written into the parent's own lesson notes.
- Nudge requests are never queued offline; they need a live answer.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/homework-help/sessions` | the child | Open (or reopen) the nudge for a lesson |
| POST | `/api/homework-help/sessions/{id}/messages` | the child | What's tricky → the one nudge |
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
- `app/services/homework_help.py`: the prompt, the fixed and built-in nudges, and trimming
- `static/js/app.js`: `renderStuckCard`, `askForNudge`, `recordStuckOutcome`, `renderHomeworkHelpHistory`

## Review (October 2026)

### Working well
- **Matches the product principle exactly:** guide, don't teach.
- **Safe by default:** no answers, works without the AI, sends the AI as little as possible, and the parent sees everything.
- **Covered end to end by tests:** the backend rules plus a browser walk through all three steps.

### Problems and risks
- **The AI is the family's local Ollama model.** For the public launch it needs a hosted provider with child-safety checks, an evaluation set and per-household limits (Phase 8).
- **There's no parent setting to turn nudges off** for a household or a child.
- Older parent notes may still contain old `[Homework help]` log lines. Kids don't see them; parents still do.

### Tests
- `test_homework_help.py` (11 tests):
  - one nudge only
  - the fixed reply when asked for the answer
  - helped, grown-up, and the parent's reset
  - permissions
  - AI-down fallback
  - what the prompt contains
  - trimming
- e2e: `kid.spec.ts` walks Stuck? → nudge → grown-up and checks the parent's notification.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Child-safety evaluation set (prompts that try to extract answers, unsafe topics) run against whatever AI provider is used | Phase 8 |
| Medium | A Settings switch to turn nudges off per household or per child | Phase 4 |
| Low | A one-time cleanup of old `[Homework help]` lines in notes | Phase 5 |
