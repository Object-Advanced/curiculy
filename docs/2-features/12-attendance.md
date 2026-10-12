# Attendance

A daily record of whether each child did school. Many states require this.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | Yes/No radios in each day cell of the Calendar; included in portfolio reports |
| **Health** | **Works; the screen design is cramped** |

> **Planned (core loop, 2026-10-11):** a one-tap "School today?" card per child, pre-filled from finished lessons, a weekly sweep, and minutes for states that count hours. See [Attendance: per child, one tap](../6-planning/product-spine.md#attendance-per-child-one-tap).

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
The family's own rows (walled off by row-level security) are in `attendance` (student, date, status), one row per student per date.

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
| High | A **"School today?" card** ("Looks right" for everyone, plus per-child changes) and one dot per child on the calendar instead of radios | Core loop |
| High | Suggest "present" when a child starts or finishes any lesson that day (the parent confirms); a weekly sweep for unmarked days | Core loop |
| High | Lesson minutes for states that count hours | Core loop |
