# Demo mode

"Try Demo" on the sign-in page: a throwaway household anyone can explore without an invite.

| | |
|---|---|
| **Who uses it** | Visitors; it's also used by the automated tests |
| **Where** | **Try Demo** on the sign-in page; a "DEMO" badge shows under the logo |
| **Health** | **Solid** |

## Scope

### What it does
- **Creates a temporary household:** each demo token gets its own throwaway family (`demo-…`), walled off from real families and other visitors like any family. Then it runs the normal first-run wizard (the tests name it "The Rivera family", with Sam and Maya).
- **The demo session lasts 2 hours.** A demo family with no activity for that long is deleted: at startup, and every 10 minutes or so while new demos start. Backups skip demo families.
- **Limited to 10 starts per 10 minutes** per address.
- **Some actions are off or simplified** in demo (for example the admin panel).

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/demo` | anyone | Start a demo household |

### Code
- `app/routers/auth.py` (`demo_access_token`)
- `app/db.py` (`tenant_id_for`: one `demo-…` family per demo token), `app/services/demo_households.py` (clearing expired demos)

## Review (October 2026)

### Working well
- **Stable since Phase 0.** Several requests at once used to break the demo; each demo is its own family in Postgres, cleared when it expires, and a test guards against the bug returning.

### Problems and risks
- **Every demo starts empty** apart from the wizard. A pre-filled week of lessons would show off the app better.

### Tests
- Demo households are used by most e2e tests (`startDemo`).
- A regression test covers several requests arriving at once.

### Recommendations
| Priority | What | When |
|---|---|---|
| Medium | A pre-filled demo week (Sam and Maya, a few books, some work samples) for the public site | Phase 8 (marketing) |
