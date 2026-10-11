# Kid's "My work"

The child's own screen after signing in with their PIN. It's playful, made for a tablet, and it points to the family's own books and plans.

| | |
|---|---|
| **Who uses it** | Kids |
| **Where** | `#/my-work`, and `#/my-work/<lesson id>` for one lesson. A signed-in child can't open any other page. |
| **Health** | **Works, with one known bug** (below). Much improved in Phase 2b; it gets the full "Sticker Book" and "My trail" treatment in React. |

## Scope

### What it does
- **"Hi Ada!"** with today's progress as stars (one per lesson, filled when done) and "All done for today. Nice work!" at the end.
- **Today**, **Coming up** (the next 60 days) and **Earlier** (the last 14 days) lists.
  - Each lesson says where it comes from ("From Saxon Math 5/4") and shows the parent's note ("Note: Pages 14–15 in the blue workbook").
  - Checking a lesson off plays a small celebration.
- **Just for fun:** an optional daily puzzle (unscramble a word from today's reading, a quick count, or simple math), seeded so it stays the same all day. It's never a lesson.
- **One lesson's page:** its date and source, the "Note from home", a "Done" check box, and the **[Stuck?](07-stuck-nudges.md)** card.
- **Kid look ("Sticker Book"):**
  - colors: cream background, grape accent, thick ink outlines, raised buttons
  - type: Fredoka headings and Nunito text
  - big check boxes
  - it's switched on by `data-persona="kid"` from the very first frame after sign-in

### Out of scope today (designed, not built)
- **My trail:** today's lessons as stops on a trail, a bonus chest (the puzzle), and camp when everything is done.
- **Sticker journal:** stickers by day, the month's seasonal collection, and cheers from home.

Both are designed on the [style tiles canvas](../3-design/style-tiles-and-kid-pages.md) and will be built as the first React page (Phase 3).

### Principle
**Curiculy guides; it doesn't teach.** Kid screens point to the real materials and track progress. Fun extras are optional play or rewards. See [What Curiculy is](../1-overview/what-curiculy-is.md).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/auth/me` | the child | Name and student id |
| GET | `/api/students/{own id}/assignments?start_date=…&end_date=…` | the child | Their lessons |
| PATCH | `/api/assignments/{id}/status` | the child, own lessons only | Check off |
| GET | `/api/assignments/{id}` | the child, own lessons only | One lesson |

### Code
- `static/js/app.js`: `loadKidWorkspace`, `renderMyWork`, `renderKidHello`, `kidWorkRow`, `parentNoteText`, `renderKidAssignment`, `buildDailySpark`, `renderSparkCard`
- `static/css/app.css`: the "child's own screens" section
- `static/css/tokens.css`: `[data-persona="kid"]`
- `static/js/theme-boot.js`: sets the kid look before the first paint

## Review (October 2026)

### Working well
- **Clear and encouraging.** The child sees today, what's next, and a friendly finish line.
- **Follows the "guide, don't teach" principle:** the materials and the parent's note come first, and the puzzle is clearly an extra.
- **Accessible:** the a11y scan includes this screen, with 0 serious issues.

### Problems and risks
- **Bug (introduced in Phase 2b): the page asks for the child's own student record (`GET /api/students/{id}`), and the server refuses**, because that route is for parents only. The page quietly falls back to the sign-in name, so it still says "Hi Ada!". But the puzzle never learns the child's grade and always uses the middle difficulty, and every visit logs one refused request. **Fix:** add the child's grade to `GET /api/auth/me` and stop the extra call.
- **Lists can get long.** "Coming up" shows 60 days. A trail or "this week" view will feel calmer.
- **The puzzle's "solved" state is stored per browser tab**, so a child who changes devices starts over. That's fine for play.

### Tests
- e2e `kid.spec.ts` (6 tests):
  - sign-in and the kid look
  - greeting and stars, the parent's note and "Just for fun"
  - the whole Stuck? flow
- `visual.spec.ts` snapshots My work in light and dark, at phone, tablet and desktop widths.
- The a11y ratchet covers `my-work`.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Fix the refused student-record call: return `grade` from `/api/auth/me` | Next small PR |
| High | Build **My trail** and the **Sticker journal** as the React pilot route. Stickers come from completed lessons, which needs `completion_date` recorded on check-off. | Phase 3 |
| Medium | Show a "this week" view by default, with the full lists one tap away | Phase 6 |
| Low | Remember the solved puzzle on the server, so it survives changing devices | Phase 6 |
