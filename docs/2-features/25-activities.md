# Activities

What a subject without a curriculum looks like on the record: **"5K race, PE, 40 minutes"** with a photo at the finish line, a piano recital, a visit to the fire station. For one child or several, counting toward one or more subjects.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | `/next/activities` (React), from **Activities** in the nav |
| **Health** | **Works** (new in October 2026) |

## Scope

### What it does
- **The list,** newest first, by month. Each activity shows its date, the children, the minutes, its subjects, notes, photos, and its link. With more than one child, chips show **Everyone** or one child.
- **Log an activity:** what you did, the date (today by default), who took part, which subjects it **counts toward** (any number: a nature walk can be Science and PE), minutes (optional; families who count hours add them up), photos or PDFs, a link (an unlisted YouTube video, a shared Drive file), and notes.
- **Change** edits any of it, adds or removes photos, or deletes the activity.
- An activity with no subject says so: "add one so it counts on the records".

### Rules
- **Parents only.** Photos and PDFs are stored like lesson work samples (checked, resized, kept under the family's folder) and shown with the family's sign-in.
- **Links start with https:// or http://.** Subjects come from the fixed subject list.
- **Removing a child** removes the activities that were only theirs; a shared one stays for the siblings.
- **Saving is safe to retry:** if a photo fails after the activity is saved, trying again doesn't log it twice.

### API
`GET /api/activities` (`student_id`, `from`, `to`), `POST /api/activities`, `GET`, `PATCH` and `DELETE /api/activities/{activity_id}`, `POST /api/activities/{activity_id}/evidence` (a photo or PDF), `DELETE /api/activities/{activity_id}/evidence/{activity_evidence_id}`. Files are served by `GET /api/evidence/files/{path}`. See the [API reference](../5-engineering/api-reference.md#reading-lists-and-activities).

### Data
`activities` (title, date, minutes, notes, link, subject codes), `activity_students` (who took part), `activity_evidence` (photos and PDFs).

### Code
- `frontend/src/routes/ActivitiesPage.tsx`, `frontend/src/components/activities/` (`ActivityForm`, `ActivityPhoto`)
- Server: `app/routers/activities.py`, `app/services/activities.py`, `app/models/activities.py`

## Review (October 2026)
**Works well:** one form covers every subject without a curriculum, for siblings together.

**Gaps:**
- **repeating activities** ("Piano Mon/Wed/Fri, 20 min") on the calendar aren't built
- activities don't count on Records, attendance or hours yet (the Records work)
- logging from ＋ or a subject's slot comes with those screens

**Tests:**
- `tests/test_activities.py`; the cross-family probe
- `frontend/src/routes/ActivitiesPage.test.tsx`
- the e2e smoke test (logging one with a photo), the axe scans (`activities`, `activity-log`) and a screenshot
