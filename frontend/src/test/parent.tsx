/** Shared fixtures for the parent screens' tests. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";

import type { Student } from "../api/client";
import type {
  Activity,
  AttendanceChild,
  AttendanceDay,
  Curriculum,
  LibraryItem,
  LibrarySummary,
  ReadingEntry,
  Reference,
} from "../api/parent";
import { routes } from "../router";
import { server } from "./server";

export const parentMe = {
  email: "parent@example.com",
  tenant_uuid: "t-1",
  is_demo: false,
  is_admin: false,
  role: "parent",
  student_id: null,
  display_name: "Parent",
  grade: null,
};

export const reference: Reference = {
  states: [],
  grades: [
    { code: "3", label: "3rd grade" },
    { code: "4", label: "4th grade" },
  ],
  subjects: [
    { code: "english", name: "English", group: "core", covers: "" },
    { code: "math", name: "Math", group: "core", covers: "" },
  ],
  library_kinds: [
    { code: "reading_book", label: "Book", hint: "A book to read." },
    { code: "textbook", label: "Textbook", hint: "The main book you teach a subject from." },
    { code: "workbook", label: "Workbook", hint: "A book your child writes in." },
    { code: "online_program", label: "Online site", hint: "Lessons done on a website." },
  ],
  curriculum_roles: [
    { code: "textbook", label: "Textbook", hint: "Its lessons set the pace." },
    { code: "workbook", label: "Workbook", hint: "Pages spread across the same days." },
    { code: "online", label: "Online site", hint: "On its own days a week." },
    { code: "reading", label: "Book to read", hint: "Read alongside." },
    { code: "teacher", label: "For the parent", hint: "Never on the calendar." },
  ],
  community_notice: "The book details you enter (never anything about your family) help every family using the same book.",
};

const ready = { ready: true, missing: [], problems: [], lessons_total: 0, lessons_with_pages: 0, lessons_with_names: 0 };

export function summary(id: number, kind: string, title: string, extra: Partial<LibrarySummary> = {}): LibrarySummary {
  const labels: Record<string, string> = { reading_book: "Book", textbook: "Textbook", workbook: "Workbook", online_program: "Online site" };
  return {
    id,
    kind,
    kind_label: labels[kind] ?? kind,
    title,
    author: null,
    subject_code: "english",
    subject_name: "English",
    grade: "4",
    cover: { url: null, source: null, review: null },
    ready: true,
    missing_count: 0,
    problems_count: 0,
    ...extra,
  };
}

export function item(id: number, kind: string, title: string, extra: Partial<LibraryItem> = {}): LibraryItem {
  return {
    ...summary(id, kind, title),
    publisher: null,
    series: null,
    edition: null,
    isbn: null,
    reading_kind: null,
    total_pages: 184,
    answer_key_start_page: null,
    lesson_count: null,
    measure: null,
    minutes_per_session: null,
    days_per_week: null,
    usual_pages_per_day: null,
    consumable: false,
    for_parent: false,
    website_url: null,
    login_note: null,
    notes: null,
    chapters: [],
    lessons: [],
    readiness: ready,
    curriculum_ids: [],
    courses: [],
    community: { status: "in_review", label: "Shared with the Curiculy catalog. An admin reviews it before other families see it." },
    ...extra,
  };
}

export function curriculum(id: number, extra: Partial<Curriculum> = {}): Curriculum {
  return {
    id,
    name: "BJU Reading 4",
    subject_code: "english",
    subject_name: "English",
    grade: "4",
    days_per_week: 4,
    notes: null,
    items: [
      {
        id: 1,
        library_item_id: 5,
        role: "textbook",
        role_label: "Textbook",
        role_hint: "Its lessons set the pace.",
        item: summary(5, "textbook", "BJU Reading 4"),
      },
    ],
    readiness: { ready: true, missing: [], problems: [] },
    courses: [],
    community_curriculum_id: null,
    solo: false,
    paced_by: {
      kind: "textbook",
      library_item_id: 5,
      title: "BJU Reading 4",
      total_pages: 300,
      chapters: 0,
      lessons: 170,
      usual_pages_per_day: null,
      measure: null,
    },
    ...extra,
  };
}

/** The handlers every parent screen needs: who's signed in, and the reference lists. */
export function serveParentBasics(me: Partial<typeof parentMe> = {}) {
  window.localStorage.setItem("auth_token", "test-token");
  server.use(
    http.get("*/api/auth/me", () => HttpResponse.json({ ...parentMe, ...me })),
    http.get("*/api/reference", () => HttpResponse.json(reference)),
  );
}

export function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path], basename: "/next" });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

export function student(id: number, name: string): Student {
  return {
    id,
    name,
    grade: "4",
    grade_label: "4th grade",
    color_hex: "#000000",
    grade_confirmed_on: null,
    grade_needs_confirming: false,
    has_iep: false,
    has_login: false,
    household_id: 1,
    notes: null,
  };
}

export function readingEntry(id: number, studentId: number, title: string, extra: Partial<ReadingEntry> = {}): ReadingEntry {
  return {
    id,
    student_id: studentId,
    student_name: "Ada",
    school_year_id: 1,
    book: summary(100 + id, "reading_book", title, { author: "E. B. White" }),
    status: "up_next",
    status_label: "Up next",
    started_on: null,
    finished_on: null,
    counts_toward: "english",
    counts_toward_name: "English",
    source: "tracked",
    scheduled: false,
    lessons_total: 0,
    lessons_done: 0,
    pages: 184,
    ...extra,
  };
}

export function activity(id: number, title: string, onDate: string, extra: Partial<Activity> = {}): Activity {
  return {
    id,
    title,
    on_date: onDate,
    minutes: null,
    notes: null,
    link_url: null,
    subjects: [],
    students: [{ student_id: 3, name: "Ada" }],
    evidence: [],
    ...extra,
  };
}

export function attendanceChild(studentId: number, name: string, extra: Partial<AttendanceChild> = {}): AttendanceChild {
  return {
    student_id: studentId,
    name,
    status: null,
    source: null,
    suggestion: null,
    reasons: [],
    expected: true,
    lessons_planned: 0,
    lessons_done: 0,
    activities: [],
    minutes: null,
    minutes_from_work: 0,
    lessons_without_minutes: 0,
    ...extra,
  };
}

export function attendanceDay(date: string, weekday: string, children: AttendanceChild[], extra: Partial<AttendanceDay> = {}): AttendanceDay {
  return { date, weekday, school_day: true, day_off: null, children, ...extra };
}
