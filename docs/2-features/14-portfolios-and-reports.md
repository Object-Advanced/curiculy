# Portfolios and reports

Printable records of the school year: portfolios for an evaluator or state review, and a weekly checklist to print for the fridge.

| | |
|---|---|
| **Who uses it** | Parents (and the evaluators they send portfolios to) |
| **Where** | `#/portfolios`; **Print Weekly Checklist** on the Calendar and Kids page |
| **Health** | **Works; email delivery isn't reliable yet** |

> **Planned (core loop, 2026-10-11):** state requirement packs (Pennsylvania first) and a **Records** dashboard showing ✓, "parent confirms" or missing, with a report template per state. See [Requirements, Records and Tasks](../6-planning/product-spine.md#requirements-records-and-tasks) and [State requirements](../6-planning/state-requirements/README.md).

## Scope

### What it does
- **A portfolio for one child and one school year**, using one of these presets:
  - **State evaluation log:** completed lessons and attendance
  - **Reading list:** the books completed
  - **Work samples:** a gallery of attached evidence
  - **Custom:** choose the children, the date range, and which sections to include: attendance, lessons, assignments, and books completed, in progress or not finished
- **On-screen preview** on an A4 page, then a **PDF** made with WeasyPrint.
- **Email the PDF to an evaluator** through the family's mail settings (`MAIL_*` in `.env`).
- **Weekly checklist:** one child's Monday-to-Friday lessons as a black-and-white PDF with check boxes.

### Rules
- **A lesson counts as done by its status.** The year range is the school year's start and end dates.
- **Report paper is never themed.** It always prints black on white, whatever the screen theme.

### Out of scope today
- Ready-made templates for each US state.
- E-signature or evaluator accounts.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/portfolios/report` | parent | Report data for one child and year |
| POST | `/api/portfolios/preview` | parent | HTML preview |
| POST | `/api/portfolios/generate` | parent | PDF |
| POST | `/api/portfolios/email` | parent | Email the PDF (sent in the background) |
| GET | `/api/reports/weekly-manifest?student_id=&start_date=` | parent | Weekly checklist PDF |

### Code
- `app/routers/portfolios.py`, `app/routers/reports.py`
- `app/services/portfolio.py`, `app/services/weekly_manifest.py`
- `static/js/app.js`: `renderPortfolios`, `loadPortfolioReport`

## Review (October 2026)

### Working well
- **Useful presets that match what evaluators ask for.**
- **The PDF and HTML come from one template.** WeasyPrint is loaded only when a PDF is actually made.

### Problems and risks
- **Email is sent inside the web process after the reply.** A restart or mail-server error silently loses it, and the parent isn't told.
- **"Subject: Unfiled"** shows on every lesson in reports (see [Calendar](04-calendar-and-lessons.md)).
- **Lessons aren't tied to a school year,** so the year is worked out from dates. A lesson moved outside the year drops out of that year's report.
- **The reading list misses older lesson-plan books,** which have no book link. The page says so and points to an operator fix.

### Tests
- `test_portfolios_api.py` (14 tests), `test_weekly_manifest.py` (8)
- e2e: "the portfolio preview renders a report for the school year"; the a11y scan reports 0 serious issues on Portfolios.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Durable email jobs with retries, and a "sent / failed" status the parent can see | Phase 8 |
| Medium | Subject from the book, so reports group by subject | Phase 5 |
| High | Move Portfolios and attendance into one **Records** area, with the requirements dashboard | Core loop |
| High | State requirement packs and report templates, Pennsylvania first | Core loop |
