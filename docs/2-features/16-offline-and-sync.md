# Offline use and sync

What happens when the internet drops: the app still opens, and changes made offline are saved later.

| | |
|---|---|
| **Who uses it** | Everyone, without noticing; it matters most on a kid's tablet with patchy Wi-Fi |
| **Where** | Built into the app. A "N changes couldn't be saved" pill appears if something fails. |
| **Health** | **Solid for short drops.** A cold start while offline shows an empty app. |

## Scope

### What it does
- **The app's files are saved on the device.** A small service worker (`sw.js`) keeps the app's code, styles, fonts and images, so the app still opens without a connection. Each release changes the version token (for example `20261010-greeting`), so devices pick up new code automatically.
- **Changes made offline are queued.** Checking off a lesson or saving a change while offline is stored on the device and **replayed when the connection returns**:
  - **No sign-in token is ever stored in the queue.** The current one is attached when the change is replayed.
  - **The queue belongs to the person who made it.** Signing out empties it.
  - **Every change carries an "idempotency key"**, so a replay is never applied twice, even if the first try actually reached the server.
  - **A change the server refuses** (for example a deleted lesson) moves to a "couldn't be saved" list that's visible to the user, instead of retrying forever.
- **Some requests never queue,** because they need a live answer: imports, "Stuck?" nudges, sign-in.

### Out of scope today
- Offline reading of data. The `/api` data itself isn't cached, so an offline cold start shows an empty app.

### Code
- `sw.js`: shell cache only
- `static/js/app.js`: `api()`, `shouldQueueRequest`, `enqueueOutboxRequest`, the outbox replay, `#sync-pill`
- `app/core/idempotency.py`: records live two days in `admin.db`

## Review (October 2026)

### Working well
- **Phase 1 fixed the dangerous parts:** stored tokens, endless retries, double-applied writes, and queues leaking between users on a shared device.
- **Covered by browser tests:** go offline, queue, sign out and empty, reconnect and apply once.

### Problems and risks
- **No cached data,** so offline is only useful during short drops.
- **A hand-written service worker and queue.** They'll be replaced in React by standard tools (Workbox and TanStack Query) with background sync.

### Tests
- `test_idempotency.py` (9 tests)
- e2e: `offline.spec.ts` (3)

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Replace with vite-plugin-pwa (Workbox): keep this week's data available offline, plus background sync for queued changes | Phase 3 |
| Medium | An installable app (manifest, icons) | Phase 6 |
