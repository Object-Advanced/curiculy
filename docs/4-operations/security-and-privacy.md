# Security and privacy

What protects families today, and what's still open. Children's data lives here, so this matters more than usual.

## In place (as of October 2026)
| Area | Protection |
|---|---|
| **Families kept apart** | Every family table is walled off by Postgres row-level security; the app's database role can't switch it off; the app refuses to start unless every family table is protected; references between family tables must match the family; a test calls every API route as one family with another's ids. Every request is tied to its family, and work-sample paths are checked so one family can't reach another's files. See [Data model](../5-engineering/data-model.md). |
| **Kids' access** | A child can read and change only their own lessons and files; they can't open notifications, Settings or other pages |
| **Kid sign-in** | Family code (about 40 bits, look-alike characters left out) plus a PIN; first names only on the sign-in screen; PIN locks for 15 minutes after 5 wrong tries |
| **Rate limits** | Register, parent sign-in (per address and per email), demo, family-code lookup, kid PIN and switch user |
| **Uploads** | 20 MB cap; the real file type is checked from its contents (JPEG, PNG, WebP, GIF, PDF only); SVG refused; random file names; images re-encoded; non-images download instead of opening |
| **Security headers** | Content-Security-Policy (`script-src 'self'`, `font-src 'self'`), `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`; they survive Cloudflare |
| **Request size** | 50 MB cap on any request |
| **Secrets** | The app refuses to start with a missing, weak or placeholder `JWT_SECRET`; `.env` is never committed |
| **Chrome extension token** | Can only upload to the unsorted inbox; can be revoked without changing the master secret |
| **AI and children** | **No AI talks to children** (since 2026-10-13). "Stuck?" nudges are built from the lesson's own book and pages; children type nothing; parents see every nudge |
| **Offline queue** | No sign-in tokens stored; emptied on sign-out; idempotency keys stop double writes |
| **Backups** | Nightly, checked, kept 14 days, on a separate disk |

## Open items (by priority)
1. **High:** the sign-in token is kept in browser storage (`localStorage`). Move to secure cookies with CSRF protection (Phase 3).
2. **High:** **children's privacy law (COPPA):** verifiable parental consent when a child account is created; limits on how long nudge histories are kept; parents can see and delete data; a privacy policy, terms and data-processing agreements; legal sign-off by April 2027 (Phase 8).
3. **High:** **no off-site backup** (see [Backups](backups-and-restore.md)).
4. **Medium:** the **Chrome extension asks for access to every website.** Narrow it to the family's server before the Web Store submission.
5. **Medium:** **self-serve password reset, email verification, sign out everywhere, and optional two-factor sign-in for parents** (Phase 8).
6. **Medium:** rate limits live in memory; move them to the edge (Cloudflare) for the public launch.
7. **Medium:** replace the unmaintained `passlib` (Phase 7). The image also runs as root; make it non-root (Phase 7).
8. **Low:** `/api/health` still reports `dev_mode` publicly; remove it.
9. ~~**Low:** the interactive API docs (`/docs`, `/openapi.json`) are public on curiculy.com.~~ **Fixed 2026-10-15:** they're off unless `API_DOCS=true` (or `DEV_MODE`), so the live site returns 404 for `/docs`, `/redoc` and `/openapi.json`.
10. **Before launch:** an external penetration test and a dependency vulnerability scan in CI.
