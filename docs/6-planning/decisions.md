# Decision log

Product and technical decisions, newest first. Each says what was decided, why, and what it affects. Revisit a decision only on purpose.

| Date | Decision | Why | Affects |
|---|---|---|---|
| 2026-10-11 | **Sticker journal rules:** a sticker lands on the lesson's finish date, or its scheduled date for older lessons with no finish date. Camp means every lesson scheduled that day is done. Each camp day wins that date's seasonal prize. Stickers are worked out from lessons, not stored. | Show a full journal from day one; keep one source of truth | [Sticker journal](../2-features/20-sticker-journal.md) |
| 2026-10-11 | **The React app lives at `/next`, built into the Docker image,** with exact package versions released at least two weeks earlier (React 19.3, TypeScript 5.9, Vite 7.3, Tailwind 4.3, React Router 7.18, TanStack Query 5, Vitest 3). Until cookie sessions land, it shares the legacy sign-in token and `theme-boot.js`. | Ship screens one at a time beside the legacy app; established major versions over brand-new ones | [My trail](../2-features/19-my-trail.md), `frontend/README.md` |
| 2026-10-11 | **The first React screen is the kid's My trail**, with a parent preview | The user asked for the map view; the screen is self-contained | [My trail](../2-features/19-my-trail.md) |
| 2026-10-10 | **Remove the archived Alembic migrations, two placeholder modules, duplicate images and superseded docs.** Organize all documentation in `docs/`. | They were never run or used, and they confused readers. Git history keeps them. | Repo layout; [this handbook](../README.md) |
| 2026-10-10 | **Greet families by family name** ("Good afternoon, Schroeder Family"): drop a leading "The", capitalize "Family", no period | Reads naturally | [Home](../2-features/03-home.md) |
| 2026-10-10 | **Homework help becomes "Stuck?":** one nudge back to the child's own materials, then "get a grown-up" (which notifies the parent) | Curiculy guides; it doesn't teach | [Stuck? nudges](../2-features/07-stuck-nudges.md) |
| 2026-10-10 | **Product principle: Curiculy guides the child through the parent's curriculum and never teaches.** Kid screens point to real materials; fun extras are optional play. | The parent owns the curriculum and the teaching | Every kid screen; AI features |
| 2026-10-10 | **Build the kid's My trail and Sticker journal in React** as the Phase 3 pilot route, not in the current app | A self-contained first screen for the new foundation; nothing built twice | [Roadmap](roadmap.md), [Style tiles](../3-design/style-tiles-and-kid-pages.md) |
| 2026-10-10 | **Visual direction:** parents get "Morning Light" with Newsreader headlines; kids get "Sticker Book", plus an Explorer-style trail page | Calm, natural and social-modern for parents; fully playful for kids | [Design system](../3-design/design-system.md) |
| 2026-10-09 | **Kid sign-in by family code** instead of the parent's email | The old way revealed children's names to anyone | [Accounts](../2-features/01-accounts-and-sign-in.md) |
| 2026-10-09 | **The production folder runs a local `production` branch**; all work happens in a separate worktree | Editing the live folder once broke kid sign-in | [Production](../4-operations/production.md) |
| 2026-10-09 | **Horizon:** invite-only beta through 2026–27; public service ready for summer-2027 setup | Families set up over the summer | [Roadmap](roadmap.md) |
| 2026-10-09 | **"All Students" calendar shows every lesson,** with per-child filters (not just shared lessons) | The current view looks broken | [Calendar](../2-features/04-calendar-and-lessons.md), Phase 5–6 |
| 2026-10-09 | **Frontend rebuild in Vite + TypeScript + React,** screen by screen behind `/next` | The 9,500-line single file can't scale; overrides the earlier "no framework" rule | Phases 3–6 |
| 2026-10-09 | **Keep FastAPI and one SQLite file per family** for the beta; decide the public-launch data tier by end of January | The backend is in good shape; per-family files isolate and back up cleanly | Phase 8 decision record |

## Defaults for Phase 3 (unless changed)
Tailwind v4 with Radix-based local components, React Router, TanStack Query, Storybook, and cookie sessions for the web app.

## Still to decide (by end of January 2027)
- **Data tier:** SQLite per family plus replication, or Postgres.
- **Hosting:** home lab or cloud; TLS, CDN.
- **AI provider:** hosted model, data terms, cost, child safety.
- **Billing and plans:** trial, prices, grandfathering beta families.
- **Session details:** cookies, CSRF, revocation.
