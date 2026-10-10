# Home

The parent's landing page: a greeting, today at a glance, the month's days off, and the next break.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `#/dashboard` ("Home" in the side menu) |
| **Health** | **Works, needs a content-first redesign** (planned for Phase 6) |

## Scope

### What it does
- **Greeting by family name:** "Good afternoon, Schroeder Family". A leading "The" is dropped and "Family" is always capitalized. Under it are a one-line seasonal mood (for example "Crunchy-leaf days"), its blurb, and a countdown hint to the next break.
- **Today at a glance:** today's lessons, lessons finished this week, and the number of kids.
- **Charts:** today's progress per child and a seven-day completion trend, drawn with Chart.js (bundled, not loaded from a CDN).
- **This month:** a small calendar that marks days off in their category colors, with tooltips.
- **Counting down:** the next holiday or break, with a themed card (Thanksgiving, Christmas and so on) and a "Coming up" list.

### Out of scope today
- Each child's actual list of today's lessons. Home shows only counts; the lessons are on the Kids page.
- Recent work and photos.
- Quick-add.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/dashboard/stats` | parent | Today's totals per child plus the seven-day trend |
| GET | `/api/exceptions`, `/api/school-years`, `/api/students`, `/api/enrollments` | parent | Loaded with the rest of the app |

### Rules
- "Today" is the household's own date, using its time zone (`household_today`).
- A lesson counts as done by its **status** ("completed"), not its completion date.

### Code
- `app/routers/dashboard.py`
- `static/js/app.js`: `renderDashboard`, `familyGreetingName`, `clockGreeting`, `MONTH_MOODS`, `HOLIDAY_THEMES`, `renderDashboardCalendar`, `paintDashboardCharts`

## Review (October 2026)

### Working well
- The serif greeting and calm palette match the chosen "Morning Light" direction.
- Seasonal moods and holiday cards give the parent side its light whimsy.
- The date logic is right since Phase 1; Home no longer flips to tomorrow in the evening.

### Problems and risks
- **Decoration comes before the work.** "What's due today for each child, and what's overdue" appears only as a number.
- **Too many requests.** Opening Home runs about 9 requests, and returning to Home re-runs them all.
- **The two canvas charts have no text alternative** for screen readers, and they redraw on every visit.
- The "Today's lessons" and "Finished this week" numbers are blanked out in visual tests, because they depend on live data.

### Tests
- `test_dashboard_api.py` (4 tests)
- e2e: `smoke.spec.ts` checks the greeting and that the charts draw; `visual.spec.ts` snapshots Home in light and dark, at phone, tablet and desktop widths; the a11y scan reports 0 serious issues on Home.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | A content-first Today, in this order: **stories row** of kids with progress rings, **today's lessons per child** with check-off, an **overdue banner** leading to Recalibrate, then a calm **feed** of finished work and photos. Keep the one-line seasonal greeting. | Phase 6 (React) |
| Medium | Replace the two charts with progress rings | Phase 6 |
| Medium | One `GET /api/workspace` request instead of about 9 | Phase 5 |
| Low | Parents "cheer" a child's finished work; the child sees it as a sticker | Phase 6 |
