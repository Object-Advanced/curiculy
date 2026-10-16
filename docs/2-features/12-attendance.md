# Attendance

A daily record of whether each child did school. Many states count it: days present, or hours.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | **School today?** on Home; the **Attendance** page (`/next/attendance`, React); Yes/No radios in each day cell of the Calendar; portfolio reports |
| **Health** | **Works** (suggestions new in October 2026); the calendar's radios are still cramped |

## Scope

### What it does
- **One record per child per day:** Present, **Field trip** (counts as present), Sick, Absent, or Vacation (older rows). Saving the same day again updates it, never duplicates it.
- **Suggested from the day's work, recorded only with the parent's tap** (`app/services/attendance.py`):
  - **Present (suggested)** when the child finished or started a lesson, or took part in an activity, that day
  - **Sick (suggested)** when the calendar has a sick day for that child
  - nothing on a school day with no work: the row says "2 lessons planned, none checked off yet" and waits for the parent
  - **days off fill themselves in:** a weekend, a family day off or a child's own day off isn't a school day, so nothing is asked. Work done on one anyway is suggested ("Count Saturday as one?").
- **School today? on Home:** one line per child ("Present (suggested): Finished 2 lessons"), **Looks right** to confirm every suggestion, and a link to mark the rest.
- **The Attendance page:**
  - **School today?**, pre-filled; each child has Present · Field trip · Sick · Absent. **Looks right** saves; a child left unpicked stays unmarked ("Ben isn't marked: pick one, or leave it for later").
  - **Not marked yet:** the days of the last two weeks with a child unmarked, each pre-filled from that day's work.
  - **The year so far,** per child: days present (field trips included), sick and absent, school days not marked, and "On track for 181 days by June 4, with 88 school days left on your calendar". The state's own number comes with its requirement pack.
- **Marked sick or absent with lessons still on the day:** "Move Ada's lessons from Thursday" opens that day's move ([Catch up and moving lessons](26-catch-up-and-moves.md)).
- **Hours mode** (Settings → Count the school year in: Hours): a present child's **minutes of school** are added up from their finished lessons and activities, shown and editable on the card. A number the parent types is kept on the day; otherwise the work is added up. The year so far shows hours, and how many finished lessons have no minutes yet.
- **How it was set:** each row says whether the parent confirmed a suggestion (`source: suggestion`) or chose it (`parent`), for the evaluator's log.
- **Marked from the Calendar** too (Yes/No per child in each day cell; a field trip shows as Yes).
- **Feeds the state evaluation log** portfolio preset (see [Portfolios](14-portfolios-and-reports.md)).

### Rules
- **Nothing is recorded without a tap.** Whether a day with finished work may count by itself is an [open question](../6-planning/product-spine.md#open-questions).
- **Only days that have happened** can be marked from the card (days off ahead go on the calendar). The calendar's radios still allow any day.
- A school day is a school weekday inside a school year that isn't a family day off. A child's sick day is still a school day (they're marked Sick); their other days off aren't.

### Out of scope today
- One small dot per child on the calendar, instead of radios (with the Calendar rebuild).
- Counting attendance against the state's requirement (with the requirement packs).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/attendance` | parent | Attendance for a date range |
| POST | `/api/attendance` | parent | Save one child's day (the calendar's radios) |
| GET | `/api/attendance/days` | parent | Each day and child, marked or suggested (today when no dates; up to 62 days) |
| POST | `/api/attendance/confirm` | parent | Save the parent's marks ("Looks right"), with optional minutes |
| GET | `/api/attendance/summary` | parent | Each child's school year so far |

### Data
`attendance` (student, date, status, `source`, `minutes`), one row per student per date, in the family's own rows (walled off by row-level security).

### Code
- `app/routers/attendance.py`, `app/services/attendance.py`, `app/schemas/attendance.py`
- `frontend/src/routes/AttendancePage.tsx`, `frontend/src/components/attendance/DayCard.tsx`
- `static/js/app.js`: `loadSchoolToday` and `renderSchoolToday` (Home), `attendance-header` in the calendar day cells

## Review (October 2026)

### Working well
- **Simple and reliable:** adding or updating on the student-and-date pair means no duplicates.
- **One tap a day** when the lessons are checked off in Curiculy; siblings can differ.

### Problems and risks
- **Radios in every calendar cell, for every child,** still crowd the calendar, especially on phones.
- **Families who don't check lessons off in Curiculy** get no suggestion and tap each child. An "Everyone present" shortcut could help if that turns out common.

### Tests
- `tests/test_attendance_api.py`, `tests/test_attendance_suggestions.py`; the cross-family probe
- `frontend/src/routes/AttendancePage.test.tsx`
- the e2e smoke test (confirming from Home, changing it on the Attendance page) and the axe scan (`attendance`). The page has no screenshot: what it shows follows the server's real date.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | One dot per child on the calendar instead of radios; a day's card opens from it | Calendar rebuild |
| High | Count against the state's requirement on Records | Requirement packs |
