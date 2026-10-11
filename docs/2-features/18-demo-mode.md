# Demo mode

"Try Demo" on the sign-in page: a throwaway household anyone can explore without an invite.

| | |
|---|---|
| **Who uses it** | Visitors; it's also used by the automated tests |
| **Where** | **Try Demo** on the sign-in page; a "DEMO" badge shows under the logo |
| **Health** | **Solid** |

## Scope

### What it does
- **Creates a temporary household** with its own throwaway database file, then runs the normal first-run wizard (the tests name it "The Rivera family", with Sam and Maya).
- **The demo session lasts 2 hours.** Demo households are cleaned up automatically; at most 64 are kept at once, and the oldest are dropped first.
- **Limited to 10 starts per 10 minutes** per address.
- **Some actions are off or simplified** in demo (for example the admin panel).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/demo` | anyone | Start a demo household |

### Code
- `app/routers/auth.py` (`demo_access_token`)
- `app/db.py` (demo databases, `purge_stale_demo_households`)

## Review (October 2026)

### Working well
- **Stable since Phase 0.** Several requests at once used to break the demo; it now uses temporary files with tidy cleanup, and a test guards against the bug returning.

### Problems and risks
- **Every demo starts empty** apart from the wizard. A pre-filled week of lessons would show off the app better.

### Tests
- Demo households are used by most e2e tests (`startDemo`).
- A regression test covers several requests arriving at once.

### Recommendations
| Priority | What | When |
|---|---|---|
| Medium | A pre-filled demo week (Sam and Maya, a few books, some work samples) for the public site | Phase 8 (marketing) |
