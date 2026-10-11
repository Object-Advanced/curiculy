# Accounts and sign-in

How parents and kids get into Curiculy, and how the app knows who they are.

| | |
|---|---|
| **Who uses it** | Parents (email and password), kids (family code, name, PIN), the site owner (invite keys) |
| **Where** | The sign-in page; the account menu ("Switch user", "Sign out") |
| **Health** | **Solid** for the beta. Missing self-serve basics needed before public launch. |

## Scope

### What it does
- **Invite-only registration.** A new parent needs an invite key. The owner makes keys from the command line (`scripts/create_invite.py`) or the admin panel in Settings. Registering creates the household and its own database file.
- **Parent sign-in** with email and password. The session lasts 24 hours.
- **Kid sign-in on a shared device:**
  1. The child types the **family code** (8 characters shown as `ABCD-2345`, with look-alike letters left out). A parent finds it in Settings → Students and can rotate it.
  2. The child taps their first name. The device remembers the code, so next time they skip straight to the names.
  3. The child enters their 4–8 digit **PIN**. After 5 wrong tries the PIN locks for 15 minutes.
- **Switch user** between a parent and the kids on one device. A child switching to a parent needs the parent's password.
- **Demo mode:** see [Demo mode](18-demo-mode.md).

### Out of scope today
- Self-serve password reset. Today the owner runs `scripts/reset_password.py`; email reset comes in Phase 8.
- Email verification, two-factor sign-in, signing out other devices, and deleting an account. All are planned for the public launch.

### Rules
| Endpoint | Rate limit |
|---|---|
| Register | 5 tries per 10 minutes per address |
| Parent sign-in | 10 per minute per address, and 20 per 15 minutes per email |
| Family-code lookup | 20 per minute |
| Kid PIN sign-in | 20 per minute |
| Switch user | 10 per minute |

The family-code lookup returns **first names only**. It used to reveal children's full names to anyone who typed a parent's email; Phase 1 replaced that with the family code.

### API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | anyone with an invite key | Create a parent account and household |
| POST | `/api/auth/token` | anyone | Parent sign-in |
| GET | `/api/auth/me` | signed in | Who am I (role, household, child's student id) |
| POST | `/api/auth/student-household` | anyone | Family code → first names for the sign-in screen |
| POST | `/api/auth/student-token` | anyone | Kid PIN sign-in |
| GET / POST | `/api/auth/family-code`, `/rotate` | parent | Show or replace the family code |
| GET | `/api/auth/switchable-users` | signed in | People this device can switch to |
| POST | `/api/auth/switch` | signed in | Switch user |
| POST / GET | `/api/admin/invite`, `/api/admin/invites` | admin parent | Make and list invite keys |

### Data
`admin.db` holds:
- `users`: parents, plus one row per child who has a PIN
- `invite_keys`
- `family_codes`

### Code
- `app/routers/auth.py`
- `app/services/child_accounts.py`, `app/services/family_codes.py`
- `app/core/security.py`, `app/core/rate_limit.py`
- `app/routers/admin.py`
- The sign-in page lives in `index.html`; its logic is in `static/js/app.js` (`openLoginModal`, the kid sign-in steps).

## Review (October 2026)

### Working well
- The family code plus PIN flow is simple for kids, and it no longer leaks names.
- Rate limits and PIN lockout are in place, and they use the visitor's real address behind the Cloudflare tunnel.
- Child accounts can only read their own lessons (`_require_student_access`).

### Problems and risks
- **The sign-in token is kept in browser storage** (`localStorage`). A cross-site scripting bug could steal it. The planned fix is cookie sessions in Phase 3.
- **No self-serve password reset.** A parent who forgets must ask the owner.
- **Rate limits live in memory.** They reset whenever the app restarts, and they won't work if the app ever runs as more than one process. Phase 8 moves limits to the edge.
- `passlib` (password hashing) is unmaintained and needs a pinned `bcrypt==4.0.1`. Replace it in Phase 7.

### Tests
- `test_auth.py` (26 tests)
- `test_kid_auth.py` (12), `test_family_codes.py` (14)
- `test_rate_limit.py` (7), `test_create_invite.py` (7), `test_reset_password.py` (5)
- `e2e/tests/kid.spec.ts`: family code → name → PIN, a wrong PIN, and a remembered device

### Recommendations
| Priority | What | When |
|---|---|---|
| High | Cookie sessions with CSRF protection; stop storing the token in the browser | Phase 3 |
| High | Email verification, password reset by email, sign out everywhere, account deletion and data export | Phase 8 |
| Medium | Replace `passlib` with `bcrypt` or `pwdlib` | Phase 7 |
| Medium | Shared or edge rate limits | Phase 8 |
| Low | Optional parent two-factor sign-in | Phase 8 |
