# Curiculy Domain Model

Canonical language for the product. Use these names in code comments, UI copy, and future schema work.

The live calendar object is the **assignment**. Older **scheduled work** is not part of the target model.

---

## Bounded contexts

```text
Identity          admin.db     who may log in, which tenant file
Catalog           catalog.db   shared ISBN / book dictionary
Planner           tenant file  one family’s year, children, library, calendar
Evidence volume   disk         photos/PDFs; DB stores paths
```

Do not put planner rows in `catalog.db`. Do not put ISBN cache in the tenant file (barcode reuse across families is the point of a shared dictionary).

---

## Identity

| Term | Meaning |
|---|---|
| **Tenant** | One household’s lockbox. UUID in JWT. File `tenant_{uuid}.db`. |
| **Parent** | Email/password user. Full planner. |
| **Child user** | PIN user tied to one `student_id`. Sees My work only. |
| **Invite key** | One-time registration gate. |
| **Capture credential** | Long-lived JWT that may only `POST` evidence staging for one tenant. Revocable via `admin.db`. Not a parent session. |
| **Demo** | Ephemeral in-memory tenant. Not a real family. |

**Rule:** One tenant file = one family. Do not plan multi-household inside one file.

---

## Family

| Term | Table | Meaning |
|---|---|---|
| **Household** | `households` | The family. Display name in the chrome. |
| **Student** | `students` | A child being taught. Has a calendar color. |
| **School year** | `school_years` | Named academic period (e.g. 2026-2027) with start and end dates. |
| **Class days** | `household_settings.weekdays` | Which weekdays count as school (0=Mon). |
| **Exception** | `calendar_exceptions` | Days not to schedule: holiday, vacation, sick, appointment. Household-wide or one student. |

**Target rule:** Dates of the current year live on `SchoolYear`. Weekdays and exception colors live on `HouseholdSettings`. Settings still store start/end as a write-through mirror of the operational year so existing tenant files keep those columns; they are not a second source of truth.

**Attendance** (`attendance`) is a log for reports: Present / Absent / Sick / Vacation. It is not the same as an exception. Exceptions change **whether work is generated**. Attendance records **what happened**.

---

## Library vs guide (two curriculum objects)

Homeschoolers use both. They must not be merged.

### 1. Program (book-based)

| Term | Table | Meaning |
|---|---|---|
| **Curriculum** | `curricula` | A program in this house (“Saxon Math 3”). |
| **Curriculum edition** | `curriculum_editions` | A revision; pacing is edition-specific. |
| **Resource** | `curriculum_resources` | A physical/digital piece (student text, answer key). |
| **Unit** | `curriculum_units` | Tree produced by auto-schedule (lessons/chapters). |
| **Page mapping** | `curriculum_page_mappings` | Where a unit sits in a resource. |

Auto-schedule: parent picks a resource/book page range → preview lessons → commit → **assignments** (+ units).

### 2. Pacing guide (week/day)

| Term | Table | Meaning |
|---|---|---|
| **Curriculum plan** | `curriculum_plans` | A multi-week guide (Abeka-style grid or daily routine). |
| **Curriculum lesson** | `curriculum_lessons` | One cell: week, day, title, optional time slot. |

Apply plan: walk school days, skip exceptions, write **assignments**. Does not require a book page count.

### Shared bibliographic cache (not the household library)

| Term | Table | Database |
|---|---|---|
| **Work** | `works` | catalog |
| **Book edition** | `book_editions` | catalog (ISBN/barcode) |
| **Publisher / author** | `publishers`, `authors` | catalog |

A resource **may** point at a book edition by integer id. That is a cache link, not a SQL FK.

---

## Enrollment

| Term | Table | Meaning |
|---|---|---|
| **Enrollment** | `enrollments` | This student is using this curriculum in this school year. |

**Target:** Created automatically when a book is committed or a plan is applied to a student. Used by portfolio reading lists. Settings can still edit. Duplicate student + curriculum + year is reused, not inserted twice.

`curriculum_id` is an integer (no FK) because it was designed like catalog ids; it actually points at tenant `curricula`. Plan-apply matches or creates that library row from the plan title.

---

## Calendar event

| Term | Table | Meaning |
|---|---|---|
| **Assignment** | `assignments` | One dated piece of work for one student. |
| **Shared group** | `assignments.shared_group_uuid` | Same lesson cloned to siblings; completion/evidence can sync. |
| **Grade** | `assignment_grades` | One optional score, stored as a string plus type. |
| **Assignment evidence** | `assignment_evidence` | Filed work sample (path or URL). |

Statuses: assigned, in_progress, completed, skipped, excused.

**Not in the target model:** `scheduled_work`, `WorkStatus` on that table, `ScheduleGrain` as a pacing grain for generated work. Those models and enums are unmapped. Empty leftover tables may remain on older SQLite files until an operator COUNT=0 and DROP. Grain/period enums that remain are for **calendar windows** (day/week/month), not for a second work table.

---

## Evidence inbox

| Term | Table | Meaning |
|---|---|---|
| **Staging evidence** | `evidence_staging` | Capture not yet filed (Chrome extension). |
| **Filed evidence** | `assignment_evidence` | Attached to an assignment. |

Flow: screenshot → staging → parent links (or drag) onto a lesson. Direct upload on an assignment skips the inbox.

**Not in the target model:** `evidence_captures` (legacy, tied to scheduled_work). Model unmapped. Empty tables may remain; do not DROP from boot.

---

## Child learning extras

| Term | Table | Meaning |
|---|---|---|
| **Homework help session** | `homework_help_sessions` | Chat on one assignment. |
| **Help message** | `homework_help_messages` | User / assistant / system. |
| **Parent notification** | `parent_notifications` | Bell: help started or redirected. |

Spark is not a table: a read-only Ollama question about today’s titles.

---

## Portfolios and print

No extra “portfolio” table. A **report** is a query:

- student(s)
- date window (usually a school year)
- which sections (attendance, lessons, books, attachments, notes)

Output: HTML fragment, PDF, or email-with-PDF.

Weekly manifest is a separate print: Mon–Fri checklist for one student.

---

## Deferred (exist in schema, not in the product)

| Term | Tables | When to activate |
|---|---|---|
| **Jurisdiction** | `jurisdictions` | A named state with a required packet format |
| **Compliance packet** | `compliance_packets` | Generated from the same facts as portfolios |
| **Subject taxonomy** | `subject_taxonomies` | Hierarchical subjects for transcripts |
| **Reporting category** | `reporting_categories` | Flat state buckets |
| **Classification** | `curriculum_classifications` | Filing a resource under taxonomy |

Until then, free-text `subject` on curricula/plans is enough.

---

## Relationships (target)

```text
Tenant 1 — 1 Household
Household 1 — * Student
Household 1 — * SchoolYear (one current)
Household 1 — 1 HouseholdSettings (weekdays, colors)
Household 1 — * CalendarException
Student 1 — * Assignment
Student 1 — * Attendance
Student 1 — * Enrollment
Enrollment * — 1 SchoolYear
Enrollment * — 1 Curriculum
Curriculum 1 — * CurriculumEdition 1 — * Resource / Unit
CurriculumPlan 1 — * CurriculumLesson
Assignment 0..1 — Grade
Assignment 1 — * AssignmentEvidence
Assignment 0..* — HomeworkHelpSession
```

Catalog sits beside this: `BookEdition` ← optional `CurriculumResource.book_edition_id`.

---

## Invariants worth enforcing

1. A child JWT may only read assignments (and homework help) for `student_id` in the token, and may change **status** on those assignments only.
2. Pacing and plan-apply skip household exceptions and off weekdays; student-specific exceptions skip that child only.
3. Shared-group members keep the same lesson identity; private assignments never appear on `/calendar`.
4. Evidence files are tenant-prefixed; serving them requires the same tenant’s parent or child JWT. A child may only read files attached to their own assignments. A capture credential cannot read files.
5. Demo data never writes `tenant_*.db`.
6. Scheduling works if Ollama is down; PDF import and tutoring may fail closed.
7. A capture credential identifies a tenant and may only stage evidence for that tenant. It is rejected by parent authentication.

---

## Language to avoid

| Avoid | Use instead |
|---|---|
| “Course” as a table | Curriculum or enrollment |
| “Scheduled work” in new code | Assignment |
| “AI syllabus” for page math | Auto-schedule / pacing preview |
| “Device token” as parent password | Upload token / staging credential |
| “Catalog” for the household library | Library / curricula |
