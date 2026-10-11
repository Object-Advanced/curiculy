# My trail (kid map view)

Today's lessons as stops on a winding trail to camp. A kid checks off each stop, opens a bonus chest for the daily puzzle, and earns the day's seasonal sticker at camp. **It's the first screen of the new React app.**

| | |
|---|---|
| **Who uses it** | Kids (their own day); parents can preview any child's trail |
| **Where** | `/next/trail`, opened from **My trail** on the kid's My work page, or **See Sam's trail** on the parent's Kids page (`/next/trail?student=<id>`) |
| **Health** | **Works** (new in October 2026; part of Phase 3) |

## Scope

### What it does
- **The map:**
  - stops are **today's lessons in order**, spaced evenly whether there's one lesson or eight
  - each finished stop shows its **subject sticker** with a green check
  - the next stop pulses as **"You are here"**, with the child's initial beside it
  - the **traveled part of the road** is tinted
  - the **bonus chest** sits on a side path
  - **camp** is at the end
  - trees follow the **season** (orange and red in autumn)
- **Today's stops** list, next to the map:
  - each stop's title, **where it comes from** ("From The Hobbit"), and the **parent's note**
  - **I did it!** checks a stop off, and **Not done yet** undoes a mistaken tap
  - checking off updates instantly; if the save fails, it rolls back and says "That didn't save"
- **Today's stickers:**
  - one slot per stop: math is a star, reading a book, writing a pencil, science a leaf, and so on
  - a slot for the bonus
  - a slot for the **camp prize**, a seasonal sticker chosen by the date (October gives Acorn, Maple leaf, Apple, Owl…)
- **Reaching camp:** when every stop is done, a "You reached camp!" banner shows the prize sticker.
- **Bonus chest:**
  - the same daily "Just for fun" puzzle as My work, ported exactly, so both pages show the same puzzle
  - solving it lights up the chest and earns the bonus sticker
- **Rest day:** with no lessons today, it says "No stops today. It's a rest day at camp."
- **Parent preview:** a parent sees a bar ("Parent preview. Checking off here counts for Sam.") and chips to switch children. **Back to Kids** returns to the parent's page.
- **Looks:** the kid look in light and dark, with large touch targets. It's tablet-first, and on phones it stacks.

### Principle
**Guide, don't teach.** The stops are the parent's scheduled lessons. The page points to the family's own materials, and the puzzle and stickers are optional rewards.

### Out of scope (next)
- **The Sticker journal page** (stickers by day, the month's collection, cheers from home). Lessons checked off since October 2026 record `completion_date`, which it needs.
- **Parent "cheers"** waiting at camp. This needs an `assignment_reactions` table.
- **Offline support** for `/next`: the React app has no service worker yet (vite-plugin-pwa, Phase 3).
- **Tapping a stop on the map** to jump to its card.

### API (no new endpoints)
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/auth/me` | signed in | Role, the child's name, student id and grade |
| GET | `/api/students` | parent | Children to preview |
| GET | `/api/students/{id}/assignments?start_date=today&end_date=today` | parent; the child for themselves | Today's stops |
| PATCH | `/api/assignments/{id}/status` | parent; the child for their own | I did it! / Not done yet (with an idempotency key) |

The server serves the app itself at `GET /next` and `/next/{path}` (the page) and `/next/assets/*` (hashed files, cached for a year).

### Code
- `frontend/src/routes/TrailPage.tsx`
- `frontend/src/components/` (TrailMap, StopList, StickerPanel, BonusChest, KidHeader, CampBanner, StickerIcon)
- `frontend/src/lib/` (trailLayout, stickers, spark, dates)
- `frontend/src/api/`
- Server: `app/main.py` (the `/next` routes)
- Entry points in the legacy app: `renderKidHello` (My trail) and `renderStudents` (See …'s trail) in `static/js/app.js`

## Review (October 2026)

### Working well
- **Turns the day into a visible journey.** The kid sees how far they are and what's next, and the finish line is a reward.
- **Works for any number of lessons.** The layout math is pure and tested (stops stay apart, inside the map, and clear of the chest).
- **Same rules as the rest of the app:** the same sign-in, the same "today", the same puzzle, and the same tokens. A child can only change their own lessons.
- **Accessible:** the map is one labelled image ("Trail map: 1 of 2 stops done."), and all actions are real buttons in the list. The axe scan reports 0 serious issues.

### Problems and risks
- **Shares the legacy sign-in token** in `localStorage` until cookie sessions land (Phase 3).
- **No offline support yet.** An offline visit falls back to the legacy app's cached page.
- **The bundle is 387 KB (124 KB gzipped)** for one screen. That's fine for now; split routes as screens are added.
- **The camp prize changes daily but isn't saved.** The Sticker journal will keep the collection.
- **No parent setting** to turn the trail off or choose which stickers appear.

### Tests
- **Vitest** (28 tests): map layout, the puzzle (checked against the legacy generator's exact values), stickers, dates, idempotency keys, and the page against a mock API (stops, I did it! → camp, undo, rest day, parent preview).
- **Playwright:**
  - a kid goes from My work → My trail → camp → undo → back
  - a parent opens a child's trail from the Kids page
  - visual snapshots in 5 sizes and themes
  - an axe scan (`my-trail`: 0)
- **pytest:** `tests/test_next_app.py` (serving and caching; the API contract stays current).

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Build the **Sticker journal** as the next React screen, from `completion_date` | Phase 3 |
| High | Cookie sessions shared by both apps; then drop the token from `localStorage` | Phase 3 |
| Medium | Offline support for `/next` (vite-plugin-pwa) | Phase 3 |
| Medium | Parent cheers that appear at camp | Phase 3–6 |
| Low | Tap a map stop to scroll to its card; a celebration burst at camp (respecting reduced motion) | Phase 6 |
