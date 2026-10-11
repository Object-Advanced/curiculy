# Glossary

The words parents see, the words the code uses, and the words we're moving to. Where the "Use" column differs from what parents see today, it's planned for the React rebuild (Phase 4).

| Use (plain word) | Shown in the app today | In the code | Meaning |
|---|---|---|---|
| **Household / family** | Household, "The Rivera family" | `Household`, "tenant" | One family; it has its own database file |
| **Family code** | Family code | `family_codes` | 8 characters (`ABCD-2345`) a kid's device uses to find the family at sign-in |
| **PIN** | PIN | a child row in `users` (role `child`) | A kid's 4–8 digit sign-in number |
| **Lesson** | Assignment, lesson | `Assignment` | One dated piece of work for one child |
| **Shared lesson** | (none) | `shared_group_uuid` | One lesson done by several kids; checking it off as a parent checks every copy |
| **Book / program** | Curriculum | `Curriculum` (`/api/curricula`) | Something the family teaches from: a textbook, a novel, a program |
| **Lesson plan** | Lesson plan, pacing guide, curriculum plan | `CurriculumPlan` (`/api/curriculum/plans`) | A Week/Day guide of lessons, from CSV, PDF, a paper photo, or typed in |
| **Schedule** | "Auto-schedule" (books), "Apply" (plans) | pacing commit; plan apply | Put a book or plan onto a child's calendar as dated lessons |
| **Course** | Enrollment | `Enrollment` | "This child is using this book this year" (mostly automatic now) |
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

## Words to avoid in parent and kid screens
- "Tenant", "enrollment", "exception", "staging", "manifest", "spark": these are internal names.
- "Homework help": it's **Stuck?** now. Curiculy doesn't teach.
- "Adventures" on parent pages: kid-voice words belong on the kid's own screens.
