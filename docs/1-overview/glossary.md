# Glossary

The words parents see, the words the code uses, and the words we're moving to. Where the "Use" column differs from what parents see today, it's planned for the React rebuild. The words agreed on 2026-10-11 are explained in [Product spine](../6-planning/product-spine.md#words).

| Use (plain word) | Shown in the app today | In the code | Meaning |
|---|---|---|---|
| **Household / family** | Household, "The Rivera family" | `Household`, "tenant" (`tenant_id`) | One family; its rows carry its `tenant_id`, and the database shows each family only its own |
| **Family code** | Family code | `family_codes` | 8 characters (`ABCD-2345`) a kid's device uses to find the family at sign-in |
| **PIN** | PIN | a child row in `users` (role `child`) | A kid's 4–8 digit sign-in number |
| **Lesson** | Assignment, lesson | `Assignment` | One dated piece of work for one child. Planned: renamed `Lesson` in the code and API too |
| **Shared lesson** | (none) | `shared_group_uuid` | One lesson done by several kids; checking it off as a parent checks every copy |
| **Curriculum** or **Reading book** | Curriculum | `Curriculum` (`/api/curricula`) | Today one table holds both. Planned: a **curriculum** is a program you teach from (its materials plus a guide); a **reading book** is a book to read, with its own lighter setup |
| **Guide** | Lesson plan, pacing guide, curriculum plan | `CurriculumPlan` (`/api/curriculum/plans`) | A curriculum's lesson list, from CSV, PDF, a paper photo, or typed in. Planned: one guide model (replacing plans and units) that families can share |
| **Schedule** | "Auto-schedule" (books), "Apply" (plans) | pacing commit; plan apply | Put a book or plan onto a child's calendar as dated lessons |
| **Course** | Enrollment | `Enrollment` | One child + one curriculum + one school year (mostly automatic now). Planned: weekdays, a start date and the subject |
| **School days** | Class days, weekdays | `HouseholdSettings.weekdays` | Which weekdays are school days |
| **Days off** | Calendar exceptions | `CalendarException` | Holidays, vacations, sick days and appointments; for the household or one child |
| **School year** | School year | `SchoolYear` (the "operational" year is the latest) | Start and end dates |
| **Catch up** | Recalibrate | `recalibration` | Shift unfinished lessons forward after falling behind |
| **Work sample** | Evidence | `AssignmentEvidence` | A photo or PDF of a child's work on a lesson |
| **Unsorted** | Unsorted Evidence | `EvidenceStaging` | Captures waiting to be filed onto a lesson |
| **Capture token** | Capture token | `CaptureToken` | Lets the Chrome extension upload screenshots and nothing else |
| **Records** | Portfolios | `portfolio` | Printable reports for evaluators |
| **Weekly checklist** | Print Weekly Checklist | `weekly_manifest` | A one-child Monday–Friday PDF with check boxes |
| **Stuck? nudge** | Stuck?, "Here's a nudge" | `homework_help` | One nudge back to the child's materials, then a grown-up |
| **Just for fun** | Just for fun | `buildDailySpark` ("spark") | An optional daily puzzle on the kid's page; never a lesson |
| **Ask Sam** | Ask Sam | talk card, `/students/{id}/spark` | A question for the parent to ask their child |
| **My work** | My work | `#/my-work` | The kid's own page |
| **My trail / Sticker journal** | My trail, Sticker journal | `/next/trail`, `/next/journal` (`frontend/`) | The kid's map of today's lessons, and their sticker book (React, October 2026) |
| **Kid look / parent look** | (none) | `data-persona="kid"` / `"parent"` | Which visual style is active |
| **Season** | (none) | `data-season` | Small decorative accents that change with the season |

## Planned words (product spine, October 2026)
Not in the app yet. See [Product spine](../6-planning/product-spine.md).

| Word | Meaning |
|---|---|
| **Library** | The family's shelf, in two sections: **Curricula** and **Reading books**, each with its own Add flow |
| **Material** | One item in a curriculum: student text, workbook, teacher's edition, answer key, tests |
| **Reading list** | One child's reading books, with started and finished dates and the subject each counts toward |
| **Subject** | What a child studies: required by the state for their grade, a common preset, or the family's own. Shown as slots on the dashboard. |
| **Objective** | One line per subject, per child, per year; together they make the state's "objectives by subject" outline |
| **Activity** | Something logged for a subject without a curriculum (a race for PE, a recital for music): note, minutes, photos, video or link |
| **Year setup** | The guided interview at sign-up and every July 1: state, grades, subjects, objectives, curricula, schedule |
| **Requirement** / **state pack** | One rule from a state's homeschool law, adjusted for the family's evaluator; a state pack is the set |
| **Records** | The dashboard that checks the requirements (✓ · parent confirms · missing), and the reports it prints |
| **Parent confirms** | A requirement Curiculy can't check from its data: a checklist item with an optional upload |
| **Task** | A **parent** to-do with a due date, mostly made by the state pack ("Affidavit due Aug 1") |
| **Sample wanted** | A lesson the requirements say needs a work sample |
| **Inbox** | Work samples waiting to be filed (today: "Unsorted"), each with a suggested lesson |

## Words to avoid in parent and kid screens
- "Tenant", "enrollment", "exception", "staging", "manifest", "spark": these are internal names.
- "Homework help": it's **Stuck?** now. Curiculy doesn't teach.
- "Adventures" on parent pages: kid-voice words belong on the kid's own screens.
- "Curriculum" for a single novel or for a child's whole year: it means a program you teach from.
- "Lesson plan", "Auto-schedule" and "Apply": it's a **guide**, and the verb is **Schedule**.
- "Assignment": it's a **lesson**.
