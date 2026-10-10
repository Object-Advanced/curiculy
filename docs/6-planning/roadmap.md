# Roadmap

**Goal:** stay an invite-only beta through the 2026–27 school year, and have a **public, self-serve service ready for parents to set up in summer 2027**. That's about 8 months from October 2026, roughly one developer working with AI help.

## Phases and status
| Phase | Theme | Target | Status (2026-10-10) |
|---|---|---|---|
| **0** | Baseline and safety net: Playwright suite, visual snapshots, accessibility ratchet, lint in CI | Oct 2026 | **Done** |
| **1** | Beta hardening: household time zone, family-code kid sign-in, rate limits, upload limits, security headers, SQLite settings, offline-queue fixes, nightly backups, password-reset script, recovering plans after a restart | Oct–Nov 2026 | **Done and deployed** (2026-10-09) |
| **2** | Design language and tokens: style tiles, `tokens.css`, self-hosted fonts, AA contrast, the kid look, calmer parent Kids page, "Stuck?" nudges | Nov–Dec 2026 | **Done and deployed** (2026-10-10), ahead of schedule |
| **3** | React foundation: Vite + TypeScript + React 19, Tailwind on the tokens, a typed API client, TanStack Query, PWA, cookie sessions, Storybook. **Pilot route: the kid's My trail and Sticker journal.** | Dec 2026–Jan 2027 | Next |
| **4** | App shell and navigation: a bottom tab bar on phones (Today · Calendar · ＋ · Kids · More), a sidebar on desktop, one Settings area, plain names | Jan–Feb 2027 | Planned |
| **5** | API v2 and backend cleanup: one error format, `/api/workspace`, an all-lessons calendar, renames, versioned migrations, removing dead code | Jan–Mar 2027 | Planned (some cleanup already done: the Alembic chain and placeholder modules were removed, and check-off records `completion_date`) |
| **6** | Screen-by-screen migration and polish, then cutover: Today feed, Calendar, Kids profiles, Library, lesson details, Records, Settings | Feb–Apr 2027 | Planned |
| **7** | Platform, delivery and docs: non-root image, locked dependencies, no source mounts in production, type checks, vulnerability scans, docs | Ongoing; done by Apr 2027 | Started: this handbook |
| **8** | Public-launch track: durable jobs, storage interface, hosted AI with safety evaluations, self-serve accounts, COPPA and legal, billing, monitoring, edge rate limits | Jan–May 2027 | Planned |

## Milestones
| Milestone | Date | What's true |
|---|---|---|
| **M1** | mid-Nov 2026 | Beta hardening live. **Met early (2026-10-09).** |
| **M2** | end of Jan 2027 | Decision records made (data tier, hosting, AI provider, sessions, billing). The React shell with My trail available as an opt-in beta. |
| **M3** | early Apr 2027 | Every screen on React; beta families default to it; the old frontend deleted |
| **M4** | mid-May 2027 | Launch ready: feature freeze, penetration test, load test, disaster-recovery drill, COPPA and legal sign-off, Chrome Web Store approval, live billing |
| **M5** | June 2027 | Public sign-up opens; beta families migrated |

## Next up (in order)
1. **Small fix:** turn off public `/docs`.
2. **Off-site backup** (owner task). See [Backups](../4-operations/backups-and-restore.md).
3. **Decision records** (by end of January): data tier, hosting, AI provider and child safety, COPPA and legal, billing.
4. **Phase 3:** scaffold `frontend/`, then build **My trail** and the **Sticker journal** as the first React screens.

See [Open issues](open-issues.md) for every known problem, by priority.
