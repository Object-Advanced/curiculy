# School year and days off

When school happens: the school year's dates, which weekdays are school days, and the days off (holidays, vacations, sick days, appointments).

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | The wizard (step 3); the School year dialog; Settings → School Years; Settings → Calendar Exceptions; Home's "This month" calendar |
| **Health** | **Works; three overlapping editors need merging** |

## Scope

### What it does
- **School years:**
  - Each has a name, start date and end date.
  - The "operational" year is the latest by start date.
  - New families get sensible default dates.
  - **Terms:** four even quarters by default, which follow the year when its dates change. In Settings → School Years, **Change terms** sets the family's own (semesters, a co-op's terms): named, in order, inside the year, not overlapping, up to 12. They're kept until **Back to even quarters**, or until the year's dates move so a term no longer fits. Progress and work samples will be counted per term.
- **Class weekdays** for the household, such as Monday to Friday, or Monday to Thursday.
- **Days off** ("calendar exceptions"):
  - a kind: vacation, appointment, sick, holiday or other
  - a title
  - a date range
  - optional notes
  - optionally **for just one child** (a sick day)
- **Colors per kind**, used on the calendar and on Home.
- **Quick toggle** of a single day as a day off.
- **Import public holidays** by country and year (for example US 2026), using the `holidays` library and skipping dates that are already blocked.
- **Everything that schedules respects these:** Auto-schedule, plan Apply and Recalibrate all skip non-school days and days off.

### Out of scope today
- Several overlapping school years per child.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET / POST | `/api/school-years` | parent | List or add |
| GET / PATCH | `/api/school-years/{id}` | parent | Read or edit (each year includes its `terms` and `terms_by_parent`) |
| PUT | `/api/school-years/{id}/terms` | parent | The family's own terms |
| POST | `/api/school-years/{id}/terms/reset` | parent | Back to even quarters |
| GET / PUT | `/api/settings/school-year` | parent | Class weekdays (and current year) |
| GET / PUT | `/api/settings/exception-colors` | parent | Colors per kind |
| GET / POST | `/api/exceptions` | parent | Days off |
| GET | `/api/exceptions/dates` | parent | Every blocked date, expanded |
| POST | `/api/exceptions/toggle` | parent | Toggle one day |
| POST | `/api/exceptions/import-holidays` | parent | Public holidays |

### Data
The family's own rows (walled off by row-level security) are in:
- `school_years`, and `school_year_terms` (name, start, end, in order)
- `household_settings`: weekdays and colors
- `calendar_exceptions`: household-wide, or for one child when `student_id` is set

### Code
- `app/routers/school_years.py`, `settings.py`, `exceptions.py`
- `app/services/school_year.py`, `app/services/terms.py`
- `static/js/app.js`: the school-year dialog, `renderSettings` panels, `renderDashboardCalendar`

## Review (October 2026)

### Working well
- **Every scheduler shares one source of truth** for school days.
- **Holiday import** saves setup time.
- **Colors per kind** make the month readable.

### Problems and risks
- **Three ways to edit the school year:** the wizard, a dialog, and the Settings panel. A fourth form also sits on the Catalog page.
- **"Calendar Exceptions" is a technical name.** Parents say "Days off".
- **The full days-off list is fetched again** each time you move the calendar forward or back; there's no date window.
- **Most screens can't show one child's sick day** clearly.

### Tests
- `test_school_years.py` (14 tests), `test_school_year_settings.py` (21)
- Exceptions are covered within `test_assignments_api.py` and `test_pacing.py`.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | One **"School year & days off"** settings section that replaces the dialog, the panel and the Catalog form | Phase 4 |
| Medium | Rename to "Days off" everywhere | Phase 4 |
| Medium | Fetch days off only for the dates being shown | Phase 5 |
