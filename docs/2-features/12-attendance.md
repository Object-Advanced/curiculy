# Attendance

A daily record of whether each child did school. Many states require this.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | Yes/No radios in each day cell of the Calendar; included in portfolio reports |
| **Health** | **Works; the screen design is cramped** |

## Scope

### What it does
- **One record per child per day:** Present, Absent, Sick or Vacation. Saving the same day again updates it, never duplicates it.
- **Marked from the Calendar** (Yes/No per child in each day cell). Days off show as blocked.
- **Feeds the state evaluation log** portfolio preset (see [Portfolios](14-portfolios-and-reports.md)).

### Out of scope today
- Automatic attendance ("present when any lesson is done").
- Hour logs, which some states require.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/attendance` | parent | Attendance for a date range |
| POST | `/api/attendance` | parent | Save one child's day (add or update) |

### Data
The household's own file holds `attendance` (student, date, status), one row per student per date.

### Code
- `app/routers/attendance.py`
- `static/js/app.js`: `attendance-header` in the calendar day cells

## Review (October 2026)

### Working well
- **Simple and reliable:** adding or updating on the student-and-date pair means no duplicates.

### Problems and risks
- **Radios in every cell, for every child,** crowd the calendar, especially on phones.
- **No quick "mark everyone present today."**
- **Nothing suggests attendance** from completed lessons.

### Tests
- `test_attendance_api.py` (9 tests)

### Recommendations
| Priority | What | When |
|---|---|---|
| High | One **attendance popover per day** ("Everyone present" plus per-child changes) instead of radios in every cell | Phase 6 |
| Medium | Suggest "present" when a child finishes any lesson that day (the parent confirms) | Phase 6 |
| Low | Hour logs for states that require them | Later |
