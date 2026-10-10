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
| PATCH | `/api/household` | parent | Update household route |
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
| GET | `/api/students/{student_id}/spark` | parent | Get student spark |

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
| PUT | `/api/assignments/{assignment_id}` | parent | Update assignment |
| POST | `/api/assignments/{assignment_id}/evidence` | parent | Upload assignment evidence |
| PUT | `/api/assignments/{assignment_id}/grade` | parent | Upsert assignment grade |
| PATCH | `/api/assignments/{assignment_id}/status` | signed in | Update assignment status |
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
| POST | `/api/homework-help/sessions/{session_id}/messages` | signed in | Ask for nudge |
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
