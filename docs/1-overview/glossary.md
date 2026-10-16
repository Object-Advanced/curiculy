# Glossary

The words parents see, the words the code uses, and the words we're moving to. Where the "Use" column differs from what parents see today, it's planned for the React rebuild. The words agreed on 2026-10-11 are explained in [Product spine](../6-planning/product-spine.md#words).

| Use (plain word) | Shown in the app today | In the code | Meaning |
|---|---|---|---|
| **Household / family** | Household, "The Rivera family" | `Household`, "tenant" (`tenant_id`) | One family; its rows carry its `tenant_id`, and the database shows each family only its own |
| **Family code** | Family code | `family_codes` | 8 characters (`ABCD-2345`) a kid's device uses to find the family at sign-in |
| **PIN** | PIN | a child row in `users` (role `child`) | A kid's 4–8 digit sign-in number |
| **Lesson** | Lesson | `Assignment` (`/api/assignments`) | One dated piece of work for one child, with how many minutes it took. Every screen says "lesson"; the code and API keep `Assignment` until the legacy screens are retired |
| **Shared lesson** | (none) | `shared_group_uuid` | One lesson done by several kids; checking it off as a parent checks every copy |
| **Book**, **Textbook**, **Workbook** or **Online site** | Book, Textbook, Workbook, Online site | `LibraryItem` (`kind`: `reading_book`, `textbook`, `workbook`, `online_program`; `/api/library`) | The four kinds of library item, each with its own required fields. The older catalog page (`#/curricula`, out of the nav) still uses `Curriculum` (`/api/curricula`) |
| **Lesson list** | Lesson plan, pacing guide, curriculum plan | `LibraryLesson` on a textbook; older: `CurriculumPlan` (`/api/curriculum/plans`) | A textbook's lessons, each with its pages, from CSV, PDF, a paper photo, or typed in. Shared through the community catalog |
| **Curriculum** | (none yet) | `PlannedCurriculum` (`/api/planner`) | A subject's plan, built in the Curriculum planner: one textbook plus the workbooks, online sites, books and teacher's edition that go with it |
| **Schedule** | "Auto-schedule" (books), "Apply" (plans) | pacing commit; plan apply | Put a book or plan onto a child's calendar as dated lessons |
| **Course** | Enrollment | `Course`; older: `Enrollment` | One child + one curriculum + one school year, with a start date and weekdays; made when a curriculum is scheduled |
| **Community catalog** | (none yet) | `CatalogEntry`, `CatalogContribution`, `CommunityCurriculum` (`/api/community`, `/api/admin/community`) | Every book, textbook, workbook, online site and curriculum families have entered (structure only), reviewed by an admin before other families see it |
| **School days** | Class days, weekdays | `HouseholdSettings.weekdays` | Which weekdays are school days |
| **Days off** | Calendar exceptions | `CalendarException` | Holidays, vacations, sick days and appointments; for the household or one child |
| **School year** | School year | `SchoolYear` (the "operational" year is the latest) | Start and end dates |
| **Term** | Terms, Quarter 1 | `SchoolYearTerm` | A part of the school year: four even quarters by default, or the family's own (semesters, a co-op's terms) |
| **Attendance** | School today?, Attendance | `Attendance` (`/api/attendance`) | One mark per child per school day: Present, Field trip (counts as present), Sick or Absent. Suggested from the day's work; recorded only when the parent confirms |
| **Days or hours** | Count the school year in | `Household.count_by` | Whether the year is counted in school days (attendance) or hours (lesson and activity minutes) |
| **Reading list** | Reading lists | `ReadingListEntry` (`/api/reading-list`) | One child's books for the year: up next, reading now, finished, with dates and the subject each counts toward |
| **Activity** | Activities, Log an activity | `Activity` (`/api/activities`) | Something logged for a subject without a curriculum (a race for PE, a recital for music): children, subjects, minutes, notes, photos, a link |
| **Catch up** | Catch up, Move to…, Recalibrate | `moves` (`/api/moves`); older: `recalibration` | Move lessons after falling behind, a sick day or a day off: each course keeps its order, every move is previewed first, and finished lessons never move |
| **Work sample** | Evidence | `AssignmentEvidence` | A photo or PDF of a child's work on a lesson |
| **Unsorted** | Unsorted Evidence | `EvidenceStaging` | Captures waiting to be filed onto a lesson |
| **Capture token** | Capture token | `CaptureToken` | Lets the Chrome extension upload screenshots and nothing else |
| **Records** | Portfolios | `portfolio` | Printable reports for evaluators |
| **Weekly checklist** | Print Weekly Checklist | `weekly_manifest` | A one-child Monday–Friday PDF with check boxes |
| **Stuck? nudge** | Stuck?, "Here's a nudge" | `homework_help` | One nudge back to the child's materials, then a grown-up |
| **Just for fun** | Just for fun | `buildDailySpark` ("spark") | An optional daily puzzle on the kid's page; never a lesson |
| **Ask Sam** | Ask Sam | talk card, `localTalkPrompt` in `static/js/app.js` | A question for the parent to ask their child, from a fixed set (no AI) |
| **My work** | My work | `#/my-work` | The kid's own page |
| **My trail / Sticker journal** | My trail, Sticker journal | `/next/trail`, `/next/journal` (`frontend/`) | The kid's map of today's lessons, and their sticker book (React, October 2026) |
| **Kid look / parent look** | (none) | `data-persona="kid"` / `"parent"` | Which visual style is active |
| **Season** | (none) | `data-season` | Small decorative accents that change with the season |
| **Library** | Library | `/next/library` (`frontend/`) | One bookshelf of everything the family teaches or reads from, with filters: All · Books · Textbooks · Workbooks · Online sites |
| **Curriculum planner** | Curriculum planner | `/next/planner` (`frontend/`) | Where a curriculum is built around a textbook and put on the calendar |
| **Catalog review** | Catalog review (admins) | `/next/admin/catalog` | The community catalog's review queue |

## Planned words (product spine, October 2026)
Not in the app yet. See [Product spine](../6-planning/product-spine.md).

| Word | Meaning |
|---|---|
| **Catch-up sheet** | The choices offered when work is missed: push back, use a day off, double up, stretch, skip |
| **Subject** | What a child studies: required by the state for their grade, a common preset, or the family's own. Shown as slots on the dashboard. |
| **Objective** | One line per subject, per child, per year; together they make the state's "objectives by subject" outline |
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
- "Curriculum" for a single novel or for a child's whole year: it means a subject's plan, built around a textbook.
- "Curriculum catalog": it's the **Library**. "Material" and "guide": each book is its own library item, and a textbook has a **lesson list**.
- "Lesson plan", "Auto-schedule a book" and "Apply": it's the textbook's **lesson list**, and the verb is **Schedule**.
- "Assignment": it's a **lesson**.
