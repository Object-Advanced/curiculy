# Data model

Curiculy keeps its data in **one Postgres database** (`curiculy`, Postgres 18), stored on the server's NVMe drive (`./data/postgres`). The database itself walls every family off from every other with **row-level security**. Until October 2026 each family had its own SQLite file; see the [decision record](../6-planning/decision-records/data-tier.md) for why that changed.

## How families are kept apart
- **Every family table has `tenant_id`**: the family's id, the same as `users.tenant_uuid`. A demo visitor's family is `demo-…`.
- **Each family table has a policy:** a connection sees and writes only rows whose `tenant_id` equals `curiculy_current_tenant()`. That function reads the `app.tenant_id` setting of the current transaction, and returns NULL when none is set.
- **Row-level security is forced** on every family table, so even the tables' owner is held to it, unless it's a role allowed to bypass it (below).
- **A request's session (`TenantSession` in `app/db.py`) sets `app.tenant_id` at the start of every transaction,** with `set_config(..., true)`. That's the same as `SET LOCAL`: it ends with the transaction, so it can never carry over to the next request on a pooled connection.
- **A session that never sets it** (the sign-in and book-cache sessions) sees no family rows at all, and can't insert any. `tenant_id` defaults to `curiculy_current_tenant()` and is `NOT NULL`.
- **References between family tables also match on `tenant_id`.** Each foreign key has a twin on `(tenant_id, column)` → `(tenant_id, id)`, so a row can't point at another family's row.

### Two roles
| Role | Used by | Can |
|---|---|---|
| `curiculy_app` | the API (`DATABASE_URL`) | read and write rows only. **Owns nothing, can't bypass row-level security**, isn't a superuser. |
| `curiculy_owner` | migrations, startup upkeep, backups (`DATABASE_OWNER_URL`) | owns the tables; bypasses row-level security (backups must see every family). Never used to answer a request. |

Both are created on the database container's first start by `docker/postgres/10-curiculy-roles.sh`.

### The safety check
**`app/db_safety.py` refuses to start the app** (and fails the tests) unless:
1. the app's role isn't a superuser, can't bypass row-level security, and owns no tables
2. every table is either a family table (has `tenant_id`, row-level security on **and forced**, a policy), or on the short list of shared tables
3. every reference between family tables also matches on `tenant_id`
4. there are no views and no `SECURITY DEFINER` functions (both could skip the policies)

`tests/test_database.py` proves each rule against the live database. `tests/test_cross_family_probe.py` calls every API route as one family, using another family's ids.

## Shared tables (no `tenant_id`, no policy)
### Sign-ins (`AdminBase`)
| Table | Holds |
|---|---|
| `users` | Parents (email, password hash, admin flag) and **kid sign-ins** (role `child`, `student_id`, PIN lockout counters). Each row names its family by `tenant_uuid`. |
| `invite_keys` | Single-use registration keys |
| `family_codes` | One code per family, for kid sign-in |
| `capture_tokens` | Chrome extension credentials (revocable) |
| `idempotency_records` | Recent write keys, so retries apply once (kept 2 days) |

### Book cache and community catalog (`CatalogBase`, shared by all families)
| Table | Holds |
|---|---|
| `book_editions`, `works`, `authors`, `work_authors`, `publishers` | Book details looked up by ISBN (Open Library or Google Books) |
| `catalog_entries` | The **community catalog**: published books, textbooks, workbooks and online sites, with how many families entered or added each, and an approved cover (`community-covers/` on the evidence volume). `status` is `published` or `retired`. |
| `catalog_entry_versions` | Every version of an entry's details, chapters and lesson list (JSON), who approved it, and from which contribution. A rollback adds a version. |
| `catalog_contributions` | What families entered, waiting for review (`pending`, `asked`) or reviewed (`approved`, `merged`, `rejected`, `withdrawn`). `contributor` is the family's id, **for review only**: it's deliberately not called `tenant_id`, because this is shared data, and the API shows admins a label ("Family 3f9a2c"), never the id. One open contribution per family item or curriculum. |
| `catalog_flags` | The automatic checks' flags on a contribution: group, level (`review` or `note`), where, and the reason in words |
| `community_curricula`, `community_curriculum_items` | Curricula families built (a textbook plus its workbooks, sites and books, in roles), each combination once, with how many families used it |
| `subject_taxonomies`, `reporting_categories` | Subject lists (defined but **nothing writes to them yet**) |

**Family tables may point at the catalog** (`library_items.catalog_entry_id`, `planned_curricula.community_curriculum_id`; `ON DELETE SET NULL`). The safety check only requires family-to-family references to match on `tenant_id`; a shared row holds nothing private. Catalog entries are retired, never deleted.

## Family tables (`TenantBase`: `tenant_id`, row-level security)
```mermaid
erDiagram
  households ||--o{ students : has
  households ||--o{ school_years : has
  households ||--|| household_settings : has
  households ||--o{ calendar_exceptions : "days off"
  students ||--o{ assignments : "lessons"
  students ||--o{ enrollments : "older courses"
  library_items ||--o{ library_chapters : ""
  library_items ||--o{ library_lessons : "textbooks"
  planned_curricula ||--o{ planned_curriculum_items : "roles"
  library_items ||--o{ planned_curriculum_items : ""
  planned_curricula ||--o{ courses : "scheduled"
  students ||--o{ courses : ""
  courses ||--o{ assignments : "lessons"
  school_years ||--o{ school_year_terms : "quarters"
  students ||--o{ reading_list_entries : "reading list"
  library_items ||--o{ reading_list_entries : ""
  activities ||--o{ activity_students : "who"
  students ||--o{ activity_students : ""
  activities ||--o{ activity_evidence : "photos"
  students ||--o{ attendance : "daily"
  curricula ||--o{ curriculum_editions : ""
  curriculum_editions ||--o{ curriculum_units : ""
  curriculum_units ||--o{ curriculum_resources : ""
  curricula ||--o{ enrollments : ""
  curriculum_plans ||--o{ curriculum_lessons : ""
  assignments ||--o| assignment_grades : grade
  assignments ||--o{ assignment_evidence : "work samples"
  assignments ||--o{ homework_help_sessions : "Stuck?"
  homework_help_sessions ||--o{ homework_help_messages : ""
```

| Table | Holds |
|---|---|
| `households` | The family: name, **time zone**, whether the year is counted in days or hours (`count_by`), and the most lessons a child should have in a day (`daily_lesson_limit`). **Exactly one per family** (unique `tenant_id`). |
| `household_states` | The state the family homeschools in, from a date (`starts_on`); a move adds a row |
| `students` | Each child: name, **grade** (a code from the fixed list: `PreK`, `K`, `1`–`12`), `grade_confirmed_on` (re-asked after each July 1), `has_iep` (a yes/no only), color |
| `student_subjects` | A child's subjects for a school year: `required` (from the state's rules for the grade), `common` or `own`; what it counts toward; on or off this year; one objective |
| `library_items` | The Library: a book, textbook, workbook or online site (`kind`), with its details, cover, website link, `for_parent` (a teacher's edition), and the catalog entry and version it matches |
| `library_chapters` | Chapters with start pages (books, workbooks) |
| `library_lessons` | A textbook's full lesson list: number, name, type, unit, minutes, first and last page |
| `planned_curricula`, `planned_curriculum_items` | The Curriculum planner: a subject's curriculum (name, subject, grade, days a week, the community curriculum it started from) and its library items, each in a role (`textbook`, `workbook`, `online`, `reading`, `teacher`). `solo` marks the one-item curricula the Library's "Schedule it" makes, kept out of the planner's list |
| `courses` | A curriculum scheduled for one child: school year, start and end dates, weekdays, `default_minutes` (the "about how many minutes a lesson?" answer) |
| `reading_list_entries` | A child's reading list: a book, its school year, `status` (`up_next`, `reading`, `finished`), started and finished dates, `counts_toward` (a subject code), and `source` (`tracked` or `scheduled`). One per child, book and year. A scheduled book's progress is read from its lessons, not stored. |
| `activities`, `activity_students`, `activity_evidence` | Activities for subjects without a curriculum: title, date, minutes, notes, a link and subject codes; the children who took part; photos and PDFs (work samples) |
| `school_years` | Name, start and end dates (the latest is "operational"), and `terms_by_parent` |
| `school_year_terms` | A year's terms, in order: four even quarters by default, or the parent's own |
| `household_settings` | School weekdays; colors for days off |
| `calendar_exceptions` | Days off (kind, title, dates, optional single child) |
| `assignments` | **Lessons** (the code keeps the old name until the legacy screens go): child, title, `scheduled_date`, `completion_date`, `status`, `minutes`, `notes`, `shared_group_uuid`; the older book, unit and resource links; and, for planner lessons, `course_id`, `library_item_id` and `library_lesson_id` |
| `assignment_grades`, `assignment_evidence` | A grade; work-sample file paths |
| `evidence_staging` | The unsorted inbox (captures not yet filed) |
| `attendance` | One row per child per day: status (Present, Field trip, Sick, Absent, Vacation), `source` (`parent`, or `suggestion` when the parent confirmed what the day's work suggested), and `minutes` when the parent set the day's school time |
| `curricula`, `curriculum_editions`, `curriculum_units`, `curriculum_resources`, `curriculum_page_mappings` | The older "Curriculum catalog": books and programs and their structure (replaced by the Library and the Curriculum planner as the new screens arrive) |
| `curriculum_plans`, `curriculum_lessons` | Lesson plans (Week/Day guides) and their lessons |
| `enrollments` | The older child + book + school year link (replaced by `courses`) |
| `homework_help_sessions`, `homework_help_messages` | Stuck? nudges |
| `parent_notifications` | The bell's messages |
| `curriculum_classifications` | Links books to subjects (rarely used) |

**Reference lists live in code,** not tables: states, grades, subjects, and each reviewed state's required subjects (`app/reference/`). They change only with a release.

The placeholder tables `jurisdictions` and `compliance_packets` were removed in the move to Postgres; state requirements get a real design in the [Product spine](../6-planning/product-spine.md).

## Planned redesign (core loop, 2026-10-11)
There are no real users yet, so the tables for curricula, lesson plans, enrollments, work samples and subjects are being **redesigned cleanly**, not patched. Built so far: subjects, the Library (books, textbooks with their lesson lists, workbooks, online sites), the Curriculum planner and courses, the community catalog, reading lists, activities, lesson minutes, school-year terms and attendance suggestions. Still to come: requirement packs and Tasks. See [Product spine: data model changes](../6-planning/product-spine.md#data-model-changes).

## How the schema changes
- **Alembic migrations** in `migrations/versions/`, run as the owner role at startup (`python -m app.db_startup`, called by `entrypoint.sh`). Each migration runs in one transaction: it applies fully or not at all.
- **A new family table also needs, in its migration,** `tenancy.protect_family_table("<table>")` and `tenancy.add_family_reference(...)` for each reference to another family table (`migrations/tenancy.py`). The safety check refuses to start if either is missing.
- **To write one:** change the models, run `alembic revision --autogenerate -m "…"`, read what it wrote, then add the tenancy steps. `tests/test_database.py` fails if the migrations and models disagree.
- The baseline is `0001` (October 2026), the first Postgres schema. `0005` added textbooks, the Curriculum planner and the community catalog (and dropped the short-lived `library_materials` and `library_lesson_pages`). `0006` added `planned_curricula.solo`. `0007` dropped `homework_help_sessions.push_count` (no AI for children: nothing to count). `0008` added reading lists, activities, school-year terms (with quarters for existing years), lesson and course minutes, and `households.count_by`. `0009` added `attendance.source` and `attendance.minutes`. `0010` added `households.daily_lesson_limit` (the move engine).

## Known data gaps
- **Lessons aren't tied to a school year,** so reports use date ranges.
- **The subject comes from a taxonomy nothing fills in,** which is why lessons say "Subject: Unfiled". The spine gives subjects a real home.
- **Some lesson-to-book links are plain numbers without a foreign key** (`assignments.curriculum_id`, `curriculum_resource_id`, `curriculum_unit_id`, `enrollments.curriculum_id`), left over from when books might live in another file. Row-level security still hides other families' rows; the spine's redesign adds real references.
