# What Curiculy is

**Curiculy is a homeschool planner for families.** Parents plan lessons from whatever curriculum they use, see each child's day at a glance, keep work samples, and print records for evaluators. Kids sign in on their own tablet to see their lessons, check them off, and get a nudge when they're stuck.

## Why it exists: four pillars
1. **A cheaper hub for families who mix programs** instead of using one all-in-one curriculum.
2. **A community catalog:** one family enters a book or program (its structure, never anything about the family, goes to the catalog after review), and every family after them plans a year in minutes.
3. **State requirements, met and not just explained:** each state's law becomes a checklist Curiculy fills from the family's records.
4. **Records that build themselves:** work is attached to lessons as it happens, and reports show what's missing and print as PDFs.

**The two selling points:** scheduling several curricula is easy, and families follow their state's rules and end the year with the right portfolio. Think tax software: plain questions, rules explained where they matter, a "what's left" checklist, and a finished packet at the end. How the pieces fit is on [Product spine](../6-planning/product-spine.md) (agreed October 2026; mostly not built yet).

## Who it's for
- **Parents** who homeschool one or more children and want the plan, the daily list, and the records in one calm place.
- **Kids**, usually on a shared family tablet or computer, who want to know "what do I do today?" and enjoy finishing it.
- **Evaluators**, indirectly: they receive portfolio PDFs and never sign in.

## What it does, in one line each
| Area | In plain words |
|---|---|
| [Home](../2-features/03-home.md) | "Good afternoon, Schroeder Family": today at a glance and the next break |
| [Calendar](../2-features/04-calendar-and-lessons.md) | Every lesson for every child, by day, week or month |
| [Kids page](../2-features/05-kids-page.md) | One child's day for the parent, plus a question to ask them |
| [My work](../2-features/06-kid-my-work.md) | The child's own playful list, pointing to their books |
| ["Stuck?"](../2-features/07-stuck-nudges.md) | One nudge back to their own materials, then "get a grown-up" |
| [Library](../2-features/08-library-and-books.md) | The family's books and programs, found by ISBN |
| [Pacing and lesson plans](../2-features/09-pacing-and-lesson-plans.md) | Turn a book or a guide into dated lessons |
| [Recalibrate](../2-features/10-recalibrate.md) | Fell behind? Shift the leftover work forward |
| [School year and days off](../2-features/11-school-year-and-days-off.md) | Which days are school days |
| [Attendance](../2-features/12-attendance.md) | Who did school each day |
| [Evidence](../2-features/13-evidence-and-capture.md) | Photos and screenshots of work, attached to lessons |
| [Portfolios](../2-features/14-portfolios-and-reports.md) | Printable records and the weekly checklist |

## Principles
1. **Curiculy guides; it doesn't teach.** The parent owns the curriculum and the teaching. The app is the plan, the nudge and the record. Kid screens point to the real materials ("From Saxon Math 5/4", "Pages 14–15 in the blue workbook"). Puzzles and stickers are optional play, never lessons. When a child is stuck, they get one nudge, then a grown-up.
2. **Calm for parents, playful for kids.** Parents get "Morning Light": airy, natural, social-app modern, with light whimsy. Kids get "Sticker Book": chunky, bright, collectible. One design system serves both (see [Design system](../3-design/design-system.md)).
3. **The family's day comes first.** "Today" follows the family's own clock and time zone, and every scheduler respects school days and days off.
4. **Parents see everything said to a child.** Nudges and AI questions are visible to the parent.
5. **The family's records are safe.** Each family's rows are walled off by the database itself (row-level security, checked on every start and by tests), with nightly backups that are restored to prove they work.
6. **Honest records, no square pegs.** When a state asks for something Curiculy can't check, it says so ("parent confirms") instead of forcing a fit. See [State requirements](../6-planning/state-requirements/README.md).
7. **Keep the minimum.** No sensitive records (health, birth dates, addresses); state forms leave private details blank for the parent. See [Privacy](../6-planning/product-spine.md#privacy-keep-the-minimum).

## Where it is today (October 2026)
- **Pre-beta: still being built.** No families use it yet; invites go out once the core loop works. It runs on a home server at **curiculy.com** behind a Cloudflare tunnel.
- **A public, self-serve launch is planned for summer 2027**, so parents can set up for the 2027–28 year (see [Roadmap](../6-planning/roadmap.md)).
- **The current app is plain JavaScript.** A rebuild in **React + TypeScript** has started at `/next` (the kid's **My trail** and **Sticker journal**). From here, the core loop's screens are built directly in React (see [Roadmap](../6-planning/roadmap.md)).
