/** Shared fixtures for the parent screens' tests. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";

import type { Curriculum, LibraryItem, LibrarySummary, Reference } from "../api/parent";
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
