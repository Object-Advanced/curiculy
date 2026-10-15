# API reference

Every endpoint the server answers, generated from the running app's route table (October 2026). All paths are under `https://curiculy.com`. **Who** is the minimum role: *parent* routes refuse kids; *signed in* routes accept a parent or a child (a child only for their own data); *public* routes need no sign-in (sign-in, registration, demo, health). The app also serves an interactive version at `/docs` (FastAPI's default). It's currently public on the live site; see [Security](../4-operations/security-and-privacy.md).

## Accounts and sign-in
Feature page: [Accounts and sign-in](../2-features/01-accounts-and-sign-in.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/admin/invite` | admin parent | Create invite key |
| GET | `/api/admin/invites` | admin parent | List unused invite keys |
| DELETE | `/api/auth/capture-token` | parent | Revoke capture token |
| GET | `/api/auth/capture-token` | parent | Read capture token status |
| POST | `/api/auth/capture-token` | parent | Create capture token |
| POST | `/api/auth/demo` | public | Demo access token |
| GET | `/api/auth/family-code` | parent | Read family code |
| POST | `/api/auth/family-code/rotate` | parent | Rotate household family code |
| GET | `/api/auth/me` | signed in | Read current user |
| POST | `/api/auth/register` | public | Register user |
| POST | `/api/auth/student-household` | public | List student household |
| POST | `/api/auth/student-token` | public | Student login |
| POST | `/api/auth/switch` | signed in | Switch user |
| GET | `/api/auth/switchable-users` | signed in | List switchable users |
| POST | `/api/auth/token` | public | Login for access token |

## Household, students and settings
Feature page: [Household, students and settings](../2-features/02-household-setup-and-settings.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/enrollments` | parent | List enrollments |
| POST | `/api/enrollments` | parent | Create enrollment |
| GET | `/api/enrollments/{enrollment_id}` | parent | Get enrollment |
| GET | `/api/household` | parent | Read household |
| PATCH | `/api/household` | parent | Rename, time zone, icon, or `count_by` (`days` or `hours`) |
| POST | `/api/household/state` | parent | Set the family's state from a date (a move adds a period) |
| PUT | `/api/household/states` | parent | Replace the state history |
| GET | `/api/settings/exception-colors` | parent | Get exception colors |
| PUT | `/api/settings/exception-colors` | parent | Put exception colors |
| GET | `/api/settings/school-year` | parent | Get school year |
| PUT | `/api/settings/school-year` | parent | Put school year |
| GET | `/api/students` | parent | List students |
| POST | `/api/students` | parent | Create student |
| DELETE | `/api/students/{student_id}` | parent | Delete student |
| GET | `/api/students/{student_id}` | parent | Get student |
| PUT | `/api/students/{student_id}` | parent | Update student |
| DELETE | `/api/students/{student_id}/pin` | parent | Clear student pin |
| POST | `/api/students/{student_id}/pin` | parent | Set student pin |
| POST | `/api/students/{student_id}/confirm-grade` | parent | Confirm the grade for the new school year |

## Reference lists and subjects
See [Product spine: Subjects](../6-planning/product-spine.md#subjects-what-everything-hangs-on)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/reference` | public | States, grades, subjects, the Library's four kinds and the curriculum roles (each with a one-line hint), and the community catalog notice |
| GET | `/api/state-requirements/{state_code}/subjects` | public | A state's required subjects for a grade |
| GET | `/api/students/{student_id}/subjects` | parent | A child's subjects for a school year (required ones added automatically) |
| POST | `/api/students/{student_id}/subjects` | parent | Add a listed subject or the family's own |
| PATCH | `/api/student-subjects/{subject_id}` | parent | On or off this year, objective, rename (own) |
| DELETE | `/api/student-subjects/{subject_id}` | parent | Remove a common or own subject |

## Library (books, textbooks, workbooks, online sites)
See the Library section of the [Product spine](../6-planning/product-spine.md#library-one-shelf-four-kinds-of-book). Built alongside the older `/api/curricula` routes, which stay until the new screens replace them. **Every change also updates the item's community catalog contribution** (automatic, once it's ready to schedule).

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/library` | parent | List, with readiness (`?kind=` filter: `reading_book`, `textbook`, `workbook`, `online_program`) |
| POST | `/api/library` | parent | Add (kind first) |
| POST | `/api/library/from-community` | parent | Add a community catalog entry (details, chapters, lesson list copied in); returns your copy if you already have it |
| GET | `/api/library/search` | parent | Search your library, the community catalog, the book cache, Open Library and Google Books; each result's kind (or guessed kind) |
| GET / PATCH / DELETE | `/api/library/{item_id}` | parent | Read (with readiness: what's missing and why; its curricula; its place in the community catalog), edit, delete |
| POST | `/api/library/read-barcode` | parent | The ISBN from a photo of a book's barcode |
| POST | `/api/library/read-page` | parent | Chapters or lessons, one per line, from a photo of a printed page (nothing saved) |
| POST | `/api/library/{item_id}/schedule/preview` | parent | Schedule one book on its own: what it would do, per child, at the chosen pace; saves nothing |
| POST | `/api/library/{item_id}/schedule` | parent | Put one book on the calendar on its own (`DELETE /api/planner/courses/{course_id}` takes it off) |
| PUT | `/api/library/{item_id}/chapters` | parent | Replace chapters (books, workbooks) |
| PUT | `/api/library/{item_id}/lessons` | parent | Replace a textbook's lesson list |
| POST | `/api/library/{item_id}/lessons/generate` | parent | Add numbered lessons to fill in |
| POST / GET / DELETE | `/api/library/{item_id}/cover` | parent | Upload, view or remove an uploaded cover image |

## Curriculum planner
See [Product spine: Curriculum planner](../6-planning/product-spine.md#curriculum-planner-a-textbook-and-what-goes-with-it). Changes to a curriculum also update its community catalog contribution (once it's fully built).

| Method | Path | Who | Handler |
|---|---|---|---|
| GET / POST | `/api/planner/curricula` | parent | List (single books scheduled on their own aren't in it); start one from a textbook (`textbook_id`) or, without a textbook, from any item (`first_item_id`) |
| POST | `/api/planner/curricula/from-community` | parent | Start from a curriculum other families built (`entry_ids` leaves pieces out) |
| GET / PATCH / DELETE | `/api/planner/curricula/{planned_curriculum_id}` | parent | Read (items, readiness, courses), edit, delete (only when unscheduled) |
| POST | `/api/planner/curricula/{planned_curriculum_id}/items` | parent | Add a library item in a role: textbook, workbook, online, reading, teacher |
| DELETE | `/api/planner/curricula/{planned_curriculum_id}/items/{item_id}` | parent | Take a library item out (it stays in the library) |
| POST | `/api/planner/curricula/{planned_curriculum_id}/schedule/preview` | parent | What scheduling would do, per child; saves nothing. Without a textbook, one pace: `pages_per_day`, `chapters_per_day` or `finish_by` (none: the rest of the school year) |
| POST | `/api/planner/curricula/{planned_curriculum_id}/schedule` | parent | A course and dated lessons for each child. Optional `minutes_per_lesson`: the course's default minutes. Its books to read join each child's reading list |
| DELETE | `/api/planner/courses/{course_id}` | parent | Unschedule (finished lessons stay) |

## Reading lists and activities
Feature pages: [Reading lists](../2-features/24-reading-lists.md), [Activities](../2-features/25-activities.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/reading-list` | parent | Reading-list entries, filtered by `student_id`, `library_item_id` or `school_year_id`: reading now, up next, then finished |
| POST | `/api/reading-list` | parent | Put a library book on a child's list for this school year (409 if it's there) |
| PATCH | `/api/reading-list/{reading_id}` | parent | Status, dates, or what it counts toward; dates fill in with today when left out |
| DELETE | `/api/reading-list/{reading_id}` | parent | Take it off the list (lessons on the calendar stay) |
| GET | `/api/activities` | parent | Activities, newest first; `student_id`, `from`, `to` |
| POST | `/api/activities` | parent | Log one: title, `on_date`, `student_ids`, `subject_codes`, optional minutes, notes and `link_url` |
| GET / PATCH / DELETE | `/api/activities/{activity_id}` | parent | Read, change (only the fields sent), delete |
| POST | `/api/activities/{activity_id}/evidence` | parent | Add a photo or PDF (served by `GET /api/evidence/files/{path}`) |
| DELETE | `/api/activities/{activity_id}/evidence/{activity_evidence_id}` | parent | Remove one |

## Community catalog
See [Product spine: Community catalog](../6-planning/product-spine.md#community-catalog-built-by-every-family). Shared data: nothing about any family.

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/community/entries/{entry_id}` | parent | An entry's details, chapters and lesson list, before adding it |
| GET | `/api/community/entries/{entry_id}/cover` | parent | An approved uploaded cover |
| GET | `/api/community/suggestions?library_item_id=` | parent | "Other families built a similar curriculum": the curricula built around this textbook, and what's often used with it |
| GET | `/api/admin/community/contributions` | admin parent | The review queue (`?status=open` by default, `all`, or one status; `?kind=item` or `curriculum`) |
| GET | `/api/admin/community/contributions/{contribution_id}` | admin parent | One contribution: its flags, the entry it changes or repeats, what changed, the book lookup |
| GET | `/api/admin/community/contributions/{contribution_id}/cover` | admin parent | Its uploaded cover |
| POST | `/api/admin/community/contributions/{contribution_id}/approve` | admin parent | Approve, or approve with edits (`include_cover: false` keeps the cover out) |
| POST | `/api/admin/community/contributions/{contribution_id}/merge` | admin parent | Count it toward an existing entry (`replace_details` takes its details as a new version) |
| POST | `/api/admin/community/contributions/{contribution_id}/reject` | admin parent | Reject with a reason (the family is told) |
| POST | `/api/admin/community/contributions/{contribution_id}/ask` | admin parent | Ask the family; their next edit brings it back |
| GET | `/api/admin/community/entries` | admin parent | Catalog entries (`?q=`, `?status=`) |
| GET | `/api/admin/community/entries/{entry_id}` | admin parent | An entry with its versions |
| POST | `/api/admin/community/entries/{entry_id}/rollback` | admin parent | Back to an older version (added as a new version) |
| POST | `/api/admin/community/entries/{entry_id}/retire` / `publish` | admin parent | Hide from search, or show again |

## Home
Feature page: [Home](../2-features/03-home.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/dashboard/stats` | parent | Get dashboard stats |

## Calendar and lessons
Feature page: [Calendar and lessons](../2-features/04-calendar-and-lessons.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/assignments` | parent | Create assignment |
| DELETE | `/api/assignments/{assignment_id}` | parent | Delete assignment |
| GET | `/api/assignments/{assignment_id}` | signed in | Get assignment |
| PUT | `/api/assignments/{assignment_id}` | parent | Update a lesson (dates, status, `minutes`) |
| POST | `/api/assignments/{assignment_id}/evidence` | parent | Upload assignment evidence |
| PUT | `/api/assignments/{assignment_id}/grade` | parent | Upsert assignment grade |
| PATCH | `/api/assignments/{assignment_id}/status` | signed in | Check off a lesson or change its status; a parent can also send `minutes` |
| GET | `/api/students/{student_id}/assignments` | signed in | List student assignments |
| GET | `/api/students/{student_id}/courses` | parent | List student courses |
| GET | `/api/calendar` | parent | List shared assignments |

## Stuck? nudges
Feature page: [Stuck? nudges](../2-features/07-stuck-nudges.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/homework-help/assignments/{assignment_id}/unlock` | parent | Unlock help |
| GET | `/api/homework-help/sessions` | signed in | List sessions |
| POST | `/api/homework-help/sessions` | signed in | Start session |
| GET | `/api/homework-help/sessions/{session_id}` | signed in | Get session |
| POST | `/api/homework-help/sessions/{session_id}/nudge` | signed in | The one nudge, built from the lesson (no AI) |
| POST | `/api/homework-help/sessions/{session_id}/outcome` | signed in | Record outcome |

## Library and books
Feature page: [Library and books](../2-features/08-library-and-books.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/books/isbn/{isbn}` | parent | Get book by isbn |
| POST | `/api/books/resolve` | parent | Resolve book |
| GET | `/api/books/{book_id}` | parent | Get book |
| POST | `/api/catalog/from-isbn` | parent | Create curriculum from isbn |
| POST | `/api/catalog/lookup-isbn` | parent | Lookup isbn |
| GET | `/api/curricula` | parent | List curricula |
| POST | `/api/curricula` | parent | Create curriculum |
| POST | `/api/curricula/import` | parent | Import curriculum |
| DELETE | `/api/curricula/{curriculum_id}` | parent | Delete curriculum |
| GET | `/api/curricula/{curriculum_id}` | parent | Get curriculum |
| GET | `/api/curricula/{curriculum_id}/resources` | parent | Get curriculum resources |
| DELETE | `/api/curricula/{curriculum_id}/schedule` | parent | Unschedule curriculum |
| GET | `/api/curricula/{curriculum_id}/tree` | parent | Get curriculum tree |

## Pacing and lesson plans
Feature page: [Pacing and lesson plans](../2-features/09-pacing-and-lesson-plans.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/curriculum/import-csv` | parent | Import curriculum csv |
| POST | `/api/curriculum/import-paper` | parent | Import paper |
| POST | `/api/curriculum/import-pdf` | parent | Import curriculum pdf |
| GET | `/api/curriculum/paper-template` | parent | Paper template |
| GET | `/api/curriculum/plans` | parent | List curriculum plans |
| POST | `/api/curriculum/plans` | parent | Create curriculum plan |
| DELETE | `/api/curriculum/plans/{plan_id}` | parent | Delete curriculum plan |
| GET | `/api/curriculum/plans/{plan_id}` | parent | Get curriculum plan |
| PUT | `/api/curriculum/plans/{plan_id}` | parent | Update curriculum plan |
| POST | `/api/curriculum/plans/{plan_id}/apply` | parent | Apply plan to calendar |
| POST | `/api/curriculum/plans/{plan_id}/archive` | parent | Archive curriculum plan |
| POST | `/api/pacing/commit` | parent | Commit syllabus |
| POST | `/api/pacing/generate-preview` | parent | Generate preview |

## Recalibrate
Feature page: [Recalibrate](../2-features/10-recalibrate.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/recalibrate/{student_id}/execute` | parent | Recalibrate execute |
| GET | `/api/recalibrate/{student_id}/options` | parent | Recalibrate options |

## School year and days off
Feature page: [School year and days off](../2-features/11-school-year-and-days-off.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/exceptions` | parent | List exceptions |
| POST | `/api/exceptions` | parent | Create exception |
| GET | `/api/exceptions/dates` | parent | List exception dates |
| POST | `/api/exceptions/import-holidays` | parent | Import holidays |
| POST | `/api/exceptions/toggle` | parent | Toggle exception |
| GET | `/api/school-years` | parent | List school years |
| POST | `/api/school-years` | parent | Create school year |
| GET | `/api/school-years/{school_year_id}` | parent | Get school year |
| PATCH | `/api/school-years/{school_year_id}` | parent | Update school year |
| PUT | `/api/school-years/{school_year_id}/terms` | parent | The family's own terms: named, in order, inside the year, not overlapping (up to 12) |
| POST | `/api/school-years/{school_year_id}/terms/reset` | parent | Back to four even quarters |

## Attendance
Feature page: [Attendance](../2-features/12-attendance.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/attendance` | parent | List attendance |
| POST | `/api/attendance` | parent | Upsert attendance |

## Evidence and capture
Feature page: [Evidence and capture](../2-features/13-evidence-and-capture.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/evidence/files/{file_path:path}` | signed in | Get evidence file |
| POST | `/api/evidence/link` | parent | Link staged evidence |
| GET | `/api/evidence/staging` | parent | List staged evidence |
| POST | `/api/evidence/staging` | parent or capture token | Stage evidence |

## Portfolios and reports
Feature page: [Portfolios and reports](../2-features/14-portfolios-and-reports.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| POST | `/api/portfolios/email` | parent | Email portfolio |
| POST | `/api/portfolios/generate` | parent | Generate portfolio report |
| POST | `/api/portfolios/preview` | parent | Preview portfolio report |
| GET | `/api/portfolios/report` | parent | Get portfolio report |
| GET | `/api/reports/weekly-manifest` | parent | Weekly manifest |

## Notifications
Feature page: [Notifications](../2-features/15-notifications.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/api/notifications` | parent | Get notifications |
| POST | `/api/notifications/read-all` | parent | Read all notifications |
| POST | `/api/notifications/{notification_id}/read` | parent | Read notification |

## App shell and health
See [App shell and health](../4-operations/monitoring.md)

| Method | Path | Who | Handler |
|---|---|---|---|
| GET | `/` | public | App shell |
| GET | `/sw.js` | public | Service worker |
| GET | `/api/health` | public | Health |
