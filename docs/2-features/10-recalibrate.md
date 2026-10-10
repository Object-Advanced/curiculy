# Recalibrate ("Life happens")

When a family falls behind, move the unfinished lessons forward without dragging each one by hand. Finished lessons never move.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | **Recalibrate Schedule** on the Calendar and on a child's Kids page |
| **Health** | **Solid** |

## Scope

### What it does
- **Shows what's overdue** for one child: the lessons before today that aren't done.
- **Offers two ways to catch up:**
  - **Extend the year:** keep the usual weekdays and shift the leftover work forward from today, so the year ends later.
  - **Add weekends:** temporarily add Saturday (or Sunday, if Saturday is already a school day) until the backlog is absorbed, then go back to the usual weekdays so the rest of the year stays put.
- Both skip days off.
- **Never moves completed lessons.**

### Out of scope today
- Recalibrating several children at once.
- Previewing the changes on the calendar before applying them.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/recalibrate/{student_id}/options` | parent | Overdue count and both options |
| POST | `/api/recalibrate/{student_id}/execute` | parent | Apply the chosen option |

### Rules
"Overdue" means before the household's **today**, in the family's own time zone. Before Phase 1 this used the server's UTC date, which flipped to tomorrow every US evening.

### Code
- `app/routers/recalibration.py`, `app/services/recalibration.py`
- Uses the pacing engine (`app/services/pacing.py`) for date placement.

## Review (October 2026)

### Working well
- **A clear, parent-friendly choice** between two strategies, built on the same tested date engine as Auto-schedule.

### Problems and risks
- **It's found only from the Calendar and Kids page.** Home doesn't say anything is overdue, so a parent may not know to recalibrate.
- **No preview** of which lessons move where.

### Tests
- `test_recalibration.py` (7 tests)
- `test_household_clock.py` covers the overdue cutoff in the evening.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | An **overdue banner** on Home and Today ("Sam has 1 lesson from Tuesday") that leads to Recalibrate | Phase 6 |
| Medium | Preview the moved lessons before applying | Phase 6 |
| Low | Recalibrate several children together | Later |
