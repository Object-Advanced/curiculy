# Household setup and Settings

First-run setup, then the place a parent manages the family: kids, PINs, the family code, the time zone, the look, and admin tools.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | The first-run wizard; **Settings**, opened from the account menu (bottom left) |
| **Health** | **Works, needs reorganizing.** Everything is there, but it's spread across too many places. |

## Scope

### What it does
- **First-run wizard** (4 steps): welcome → household name → school year (dates and class weekdays) → first child.
- **Household:**
  - rename the family
  - the household **time zone**, which is set automatically from the parent's browser the first time and is what "today" means everywhere
- **Appearance:** light or dark mode. The choice is remembered on that device.
- **Students:**
  - add, rename, recolor or remove a child
  - set or clear their sign-in **PIN**
  - see and rotate the **family code**
  - make or revoke the **Chrome extension capture token** (see [Evidence](13-evidence-and-capture.md))
- **Calendar exceptions** (days off) and **school years**: see [School year and days off](11-school-year-and-days-off.md).
- **Enrollments:** which books or programs each child is using this year.
- **Admin** (only for the owner's account): make invite keys.

### Out of scope today
- Several parents in one household.
- Billing and plans (Phase 8).
- Deleting the household or exporting its data (Phase 8).

### Screens
- `#/settings` and `#/settings/<panel>`. The panels are `students`, `exceptions`, `school-years`, `enrollments` and `admin`.
- The account menu lists Settings, Manage Students, Calendar Exceptions, School Years, Enrollments, Admin, Switch user and Log out.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET / PATCH | `/api/household` | parent | Read; rename; set the time zone |
| GET / POST / PUT / DELETE | `/api/students[/{id}]` | parent | The kids |
| POST / DELETE | `/api/students/{id}/pin` | parent | Set or clear a PIN |
| GET / POST | `/api/enrollments[/{id}]` | parent | Enrollments |
| GET / PUT | `/api/settings/school-year`, `/api/settings/exception-colors` | parent | Class weekdays; colors for days off |

### Data
- The household database holds `households`, `students`, `household_settings` and `enrollments`.
- `admin.db` holds child sign-ins (`users`) and `family_codes`.

### Code
- `app/routers/household.py`, `students.py`, `settings.py`, `enrollments.py`
- `app/services/households.py`, `enrollments.py`, `clock.py`
- `static/js/app.js`: `renderSettings` and `renderStudentSettings`; the wizard steps are in `index.html`

## Review (October 2026)

### Working well
- The wizard gets a new family to a usable calendar quickly.
- The time zone fix (Phase 1) means "today" follows the family's clock, not the server's.
- Kid PINs, the family code and the extension token sit together under Students, which makes sense.

### Problems and risks
- **Settings is hard to find and scattered.**
  - Core settings hide in an 8-item account menu.
  - The school year can be edited in three places: the wizard, a dialog, and the School Years panel.
  - The Settings page shows three cards above its own tab bar.
- **Names drift:** "Kids", "My day" and "Someone's day" all mean the same page; "Calendar Exceptions" is "Days off" to a parent.
- **"Enrollments" is a technical idea** that parents rarely need to touch. Pacing and plan-apply now create enrollments automatically.

### Tests
- `test_household_api.py` (12 tests), `test_household_clock.py` (13), `test_students_api.py` (12), `test_enrollments.py` (16)
- The wizard is covered by every e2e run (`completeWizard` in `e2e/tests/support.ts`).

### Recommendations
| Priority | What | When |
|---|---|---|
| High | One Settings area with sections: Household · Students & sign-in · School year & days off · Courses · Devices & capture · Admin. Merge the three school-year editors into one. | Phase 4 |
| Medium | Rename to plain words: "Days off", "Courses" | Phase 4 (see the [glossary](../1-overview/glossary.md)) |
| Medium | Hide Enrollments behind "Courses", since it's mostly automatic now | Phase 4 |
| Low | Several parents per household; household deletion and export | Phase 8 |
