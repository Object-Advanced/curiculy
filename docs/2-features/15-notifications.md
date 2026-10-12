# Notifications

In-app messages for parents: a child needs them, a child got a nudge, a lesson plan finished processing.

| | |
|---|---|
| **Who uses it** | Parents |
| **Where** | The bell in the page header (with an unread count); the panel that opens from it |
| **Health** | **Works; it's simple** |

## Scope

### What it does
- **Messages:**
  - **"Ada asked for a nudge"**, quoting the nudge exactly
  - **"Ada needs you"** when a child asks for a grown-up
  - **"Curriculum plan is ready"** or **"Curriculum plan processing failed"** after a PDF or photo import
- An **unread count** on the bell (hidden when there's nothing unread, as of Phase 2), and **mark one or all as read**.
- **The app checks every 30 seconds** while a parent is signed in.

### Out of scope today
- Email or phone push notifications.
- Settings for which notifications to receive.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/notifications` | parent | List plus unread count |
| POST | `/api/notifications/{id}/read` | parent | Mark one read |
| POST | `/api/notifications/read-all` | parent | Mark all read |

Kids can't read notifications.

### Data
The family's own rows (walled off by row-level security) are in `parent_notifications`: type, child, lesson, title, body and the time it was read.

### Code
- `app/routers/notifications.py`, `app/services/notifications.py`
- `static/js/app.js`: `loadNotifications`, `paintNotifications`

## Review (October 2026)

### Working well
- **Clear, useful messages.** "Ada needs you" is the most important one, and it works end to end.

### Problems and risks
- **Polls every 30 seconds even when the tab is hidden.** That's wasted requests.
- **"Ada needs you" only reaches a parent with Curiculy open.** A parent in another room won't see it.

### Tests
- `test_homework_help.py` covers creating, listing and marking read.
- e2e: `kid.spec.ts` checks "Ada needs you" arrives.

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Phone push (the web app installed on the home screen) for "needs you" | Phase 6–8 |
| Medium | Pause checking while the tab is hidden; later, use server-sent updates | Phase 6 |
| Low | Notification preferences | Phase 8 |
