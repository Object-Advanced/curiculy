# Curiculy Handbook

Everything about Curiculy for people to read: what it is, how each part works, how healthy it is, how to run it, and what's next. **This folder is the single home for Curiculy's documentation.** Last full review: **October 2026**.

## Start here
| If you want to… | Read |
|---|---|
| Understand what Curiculy is and its principles | [What Curiculy is](1-overview/what-curiculy-is.md) |
| See how the pieces fit together | [How it works](1-overview/how-it-works.md) |
| Look up a word | [Glossary](1-overview/glossary.md) |
| Review every feature (scope + health) | [Features](2-features/README.md) |
| Know what's broken or missing, by priority | [Open issues](6-planning/open-issues.md) |
| Deploy, roll back, back up, or check on the site | [Operations](#4-operations) |
| Work on the code | [Engineering](#5-engineering) |
| See the plan and past decisions | [Roadmap](6-planning/roadmap.md) · [Decisions](6-planning/decisions.md) |

## What's in this folder

### 1. Overview
- [What Curiculy is](1-overview/what-curiculy-is.md): who it's for, the principles ("guides, doesn't teach"), and where it stands
- [How it works](1-overview/how-it-works.md): a plain-language architecture diagram, where data lives, and where the folders are
- [Glossary](1-overview/glossary.md): app words, code words, and the names we're moving to

### 2. Features: scope and review for every major function
| | | |
|---|---|---|
| [01 Accounts and sign-in](2-features/01-accounts-and-sign-in.md) | [07 Stuck? nudges](2-features/07-stuck-nudges.md) | [13 Evidence and capture](2-features/13-evidence-and-capture.md) |
| [02 Household setup and Settings](2-features/02-household-setup-and-settings.md) | [08 Library and books](2-features/08-library-and-books.md) | [14 Portfolios and reports](2-features/14-portfolios-and-reports.md) |
| [03 Home](2-features/03-home.md) | [09 Pacing and lesson plans](2-features/09-pacing-and-lesson-plans.md) | [15 Notifications](2-features/15-notifications.md) |
| [04 Calendar and lessons](2-features/04-calendar-and-lessons.md) | [10 Recalibrate](2-features/10-recalibrate.md) | [16 Offline and sync](2-features/16-offline-and-sync.md) |
| [05 Kids page](2-features/05-kids-page.md) | [11 School year and days off](2-features/11-school-year-and-days-off.md) | [17 AI features](2-features/17-ai-features.md) |
| [06 Kid's My work](2-features/06-kid-my-work.md) | [12 Attendance](2-features/12-attendance.md) | [18 Demo mode](2-features/18-demo-mode.md) |

### 3. Design
- [Design system](3-design/design-system.md): tokens, the parent and kid looks, type, fonts, voice
- [Style tiles and the kid pages](3-design/style-tiles-and-kid-pages.md): the design canvas, My trail, and the Sticker journal

### 4. Operations
- [Production and deploys](4-operations/production.md): how the live site runs, the deploy steps, rollback
- [Backups and restore](4-operations/backups-and-restore.md)
- [Monitoring](4-operations/monitoring.md): health, logs, the log check
- [Operator scripts](4-operations/operator-scripts.md): invites, password reset, cleanups
- [Security and privacy](4-operations/security-and-privacy.md): what's protected and what's open

### 5. Engineering
- [Codebase map](5-engineering/codebase-map.md)
- [Data model](5-engineering/data-model.md)
- [API reference](5-engineering/api-reference.md): all 103 endpoints, by feature
- [Testing and CI](5-engineering/testing-and-ci.md)
- [Development setup](5-engineering/development-setup.md)

### 6. Planning
- [Roadmap](6-planning/roadmap.md): phases, milestones, status
- [Decisions](6-planning/decisions.md): the decision log
- [Open issues](6-planning/open-issues.md): every problem the reviews found, prioritized

## At a glance (October 2026)
- **Status:**
  - an invite-only beta at **curiculy.com**
  - Phases 0–2 done and deployed
  - React rebuild next (Phase 3), starting with the kid's **My trail**
- **Health:** 7 features rated Solid, 11 rated Works, none rated Needs work.
  - Every screen passes the accessibility scan (0 serious issues).
  - About 1,000 backend tests and 36 browser tests pass in CI.
- **Do first:**
  1. an off-site backup copy
  2. an uptime monitor
  3. turn off the public `/docs`

  See [Open issues](6-planning/open-issues.md).

## Outside this folder
| What | Where |
|---|---|
| The live site | https://curiculy.com |
| Code and pull requests | GitHub **Object-Advanced/curiculy** |
| Design boards | [Curiculy Style Tiles canvas](https://claude.ai/artifact/3VsX9TqdT7HK7nLyL1MdD2) (private; share from its menu) |
| Production folder (don't edit) | `/home/objadv/curiculy` |
| Development copy | `/home/objadv/curiculy-dev` |
| Log check and reports | `/home/objadv/curiculy-ops` |
| Backups and work samples | `/datalake/projects/curiculy/` |

## Keeping this handbook current
- **When a feature changes,** update its page in `2-features/`, the [API reference](5-engineering/api-reference.md) if routes changed, and [Open issues](6-planning/open-issues.md).
- **When a decision is made,** add a row to [Decisions](6-planning/decisions.md).
- **Earlier documents** (`ARCHITECTURE.md`, `ROADMAP.md`, `TECHNICAL_DEBT.md` and others, plus `CompleteExplanation.txt`) were written before October 2026 and are replaced by this handbook. They're kept in git history; see commit `51cce3b`.
