# Roadmap

**Goal:** a **public, self-serve service ready for parents to set up in summer 2027**. Curiculy is **pre-beta**: no families use it yet, and invites go out once the core loop works end to end. That's about 8 months from October 2026, roughly one developer working with AI help.

**Re-ordered on 2026-10-11:** the core loop comes first. It covers Library, Courses, Calendar, Attendance, Work samples, Requirements, Records and Tasks (see [Product spine](product-spine.md)). The React rebuild continues, but the loop's screens are built directly in React rather than ported one by one, and new kid extras wait until after launch.

## Core loop: order of work
| When | Work |
|---|---|
| **Oct–Dec 2026** | **Move to Postgres first** ([decided](decision-records/data-tier.md)). Then the backend spine, one piece at a time: ~~state and grades~~ → ~~subjects and objectives~~ → ~~the Library's four kinds (book, textbook, workbook, online site; chapters, lesson lists, required-field rules, covers)~~ → ~~the Curriculum planner and Course~~ → ~~the community catalog: automatic contributions, checks, the admin review queue's API, curriculum suggestions~~ (moved up, 2026-10-12) → reading lists → the Lesson rename, minutes and school-year terms → activities → attendance suggestions → move engine with previews, the catch-up formulas and the plan checker → requirement packs and Tasks → **Pennsylvania pack** (its [worksheet](state-requirements/pennsylvania.md) is reviewed; Q12–Q14 still open) → Records API, progress by course, subject and term, and the portfolio builder → inbox suggestions → transcript and credits → photo orientation fix and PDF metadata scrub |
| **Jan–Mar 2027** | The loop's screens in React: the **year-setup interview**; **Today** ("School today?", Tasks, overdue banner, "sample wanted"), **Calendar** (drag and Move to…, previews, warnings, Schedule from library), the **catch-up sheet**, the **Library bookshelf** (a step-by-step adding walkthrough, search first; books, textbooks, workbooks and online sites; covers), the **Curriculum planner** and its calendar walkthrough, the **admin review queue**, the lesson sheet with **Add work**, **Log an activity**, **Records** (Checklist · Portfolio · Your state), progress rings and course bars, the kid's **My books**. Fillable state forms, filled in the browser. The community catalog, seeded with the most-used programs and their covers. Public state pages. Parent phone capture. |
| **Mar–May 2027** | Second wave of states: New York on its own, then a base pack for states with similar light laws; the lifetime archive download; extension docs; launch work (Phase 8 below). **Feature freeze mid-May.** |
| **Jun 2027** | Public sign-up opens, with an honest "N states supported" claim and a seeded guide catalog |

**Parked until after launch:** cheers from home and more kid extras, kids capturing their own work, the kid score-snap extension idea, a generic custom-report designer, an upload email address, Share to Curiculy.

## Phases and status
The phases from October 2026 still describe the engineering work; the core loop above sets the order.

| Phase | Theme | Status (2026-10-11) |
|---|---|---|
| **0** | Baseline and safety net: Playwright suite, visual snapshots, accessibility ratchet, lint in CI | **Done** |
| **1** | Hardening: household time zone, family-code kid sign-in, rate limits, upload limits, security headers, SQLite settings, offline-queue fixes, nightly backups, password-reset script, recovering plans after a restart | **Done and deployed** (2026-10-09) |
| **2** | Design language and tokens: style tiles, `tokens.css`, self-hosted fonts, AA contrast, the kid look, calmer parent Kids page, "Stuck?" nudges | **Done and deployed** (2026-10-10) |
| **3** | React foundation: Vite + TypeScript + React 19, Tailwind on the tokens, a typed API client, TanStack Query, PWA, cookie sessions, Storybook | **Foundation built** (`frontend/`, at `/next`) with **My trail** and the **Sticker journal**. Still to do: cookie sessions, PWA, Storybook. Cheers from home is **parked**. |
| **4** | App shell and navigation: a bottom tab bar on phones, a sidebar on desktop, one Settings area, plain names | Planned. The tabs follow the spine's words: Today · Calendar · ＋ · Records · More (Library, Kids, Settings). |
| **5** | API v2 and backend cleanup: one error format, `/api/workspace`, renames, versioned migrations, removing dead code | **Absorbs the backend spine.** No user data to migrate, so tables are redesigned rather than patched. The `jurisdictions` and `compliance_packets` placeholders are replaced by requirement packs, not just dropped. |
| **6** | Screens and cutover | **The loop's screens are built new in React**, then the legacy app is retired |
| **7** | Platform, delivery and docs: non-root image, locked dependencies, no source mounts in production, type checks, vulnerability scans, docs | Ongoing; done by April 2027 |
| **8** | Public-launch track: durable jobs, storage interface, hosted AI with safety evaluations, self-serve accounts, COPPA and legal (including a read on sharing guides), billing, monitoring, edge rate limits | Jan–May 2027 |

## Milestones
| Milestone | Date | What's true |
|---|---|---|
| **M1** | mid-Nov 2026 | Hardening live. **Met early (2026-10-09).** |
| **M2** | end of Dec 2026 | Data tier decided; the backend spine works end to end for one Pennsylvania family, on paper and in tests. |
| **M3** | end of Mar 2027 | The loop's screens on React; invites go out; the old frontend retired |
| **M4** | mid-May 2027 | Launch ready: feature freeze, penetration test, load test, disaster-recovery drill, COPPA and legal sign-off, Chrome Web Store approval, live billing |
| **M5** | June 2027 | Public sign-up opens |

## Next up (in order)
1. **Confirm the last Pennsylvania wordings** against the statute (see the [worksheet](state-requirements/pennsylvania.md)); Q1–Q14 are decided.
2. **Done and deployed 2026-10-12:** the move to Postgres ([decision](decision-records/data-tier.md)) and backend spine part 1: state and grades, subjects and objectives (Pennsylvania's required subjects), and the Library's four kinds of book with readiness rules, search-first adding and covers (APIs; the screens come next).
3. **Next:** the screens for those pieces (the year-setup interview, the Library bookshelf), and the next backend pieces: Course, the Lesson rename, minutes and terms, then the catch-up formulas.
4. **Backups:** layer 1 (continuous archive) and the encrypted off-site copy (needs a cloud storage account).
5. Ops tasks that still stand: an uptime monitor, turning off the public `/docs`.

See [Open issues](open-issues.md) for every known problem, by priority.
