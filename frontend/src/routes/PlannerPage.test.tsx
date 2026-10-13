import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "../test/server";
import { curriculum, renderAt, summary, serveParentBasics } from "../test/parent";

const ada = { id: 3, name: "Ada", grade: "4", color_hex: "#000000", grade_confirmed_on: null, grade_needs_confirming: false, has_iep: false, has_login: false, household_id: 1, notes: null };

describe("Curriculum planner", () => {
  beforeEach(() => {
    serveParentBasics();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 14, 10, 0));
  });

  afterEach(() => vi.useRealTimers());

  it("explains how curricula work before the first one", async () => {
    server.use(http.get("*/api/planner/curricula", () => HttpResponse.json([])));
    renderAt("/next/planner");
    expect(await screen.findByRole("heading", { name: "How curricula work" })).toBeInTheDocument();
    expect(screen.getByText(/one textbook/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Plan a curriculum" })).toHaveAttribute("href", "/next/planner/new");
  });

  it("lists curricula with where they are on the calendar", async () => {
    server.use(
      http.get("*/api/planner/curricula", () =>
        HttpResponse.json([
          curriculum(7, {
            courses: [{ id: 1, curriculum_id: 7, student_id: 3, student_name: "Ada", start_date: "2026-10-12", end_date: "2027-05-21", weekdays: [0, 1, 2, 3], lessons_scheduled: 170 }],
          }),
        ]),
      ),
    );
    renderAt("/next/planner");
    const list = await screen.findByRole("list", { name: "Your curricula" });
    expect(within(list).getByRole("link", { name: "BJU Reading 4" })).toHaveAttribute("href", "/next/planner/7");
    expect(within(list).getByText(/On Ada's calendar/)).toHaveTextContent("170 lessons");
  });

  it("starts from a curriculum other families built, with pieces left out", async () => {
    let body: unknown = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([summary(5, "textbook", "BJU Reading 4")])),
      http.get("*/api/community/suggestions", () =>
        HttpResponse.json({
          textbook: { id: 40, kind: "textbook", kind_label: "Textbook", title: "BJU Reading 4", author: null, publisher: null, edition: null, isbn: null, subject_code: "english", subject_name: "English", grade: "4", total_pages: 300, chapters_count: 0, lessons_count: 170, cover_url: null, families_count: 2, detail: "" },
          families_count: 2,
          message: "2 families built a curriculum around BJU Reading 4.",
          curricula: [
            {
              id: 70,
              name: "Reading 4",
              subject_code: "english",
              subject_name: "English",
              grade: "4",
              days_per_week: 4,
              families_count: 2,
              items: [
                { role: "textbook", role_label: "Textbook", library_item_id: 5, families_count: 2, entry: { id: 40, kind: "textbook", kind_label: "Textbook", title: "BJU Reading 4", author: null, publisher: null, edition: null, isbn: null, subject_code: "english", subject_name: "English", grade: "4", total_pages: 300, chapters_count: 0, lessons_count: 170, cover_url: null, families_count: 2, detail: "" } },
                { role: "reading", role_label: "Book to read", library_item_id: null, families_count: 2, entry: { id: 41, kind: "reading_book", kind_label: "Book", title: "Charlotte's Web", author: null, publisher: null, edition: null, isbn: null, subject_code: null, subject_name: null, grade: null, total_pages: 184, chapters_count: 0, lessons_count: 0, cover_url: null, families_count: 2, detail: "" } },
              ],
            },
          ],
          often_used_with: [],
        }),
      ),
      http.post("*/api/planner/curricula/from-community", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(curriculum(8, { community_curriculum_id: 70 }), { status: 201 });
      }),
      http.get("*/api/planner/curricula/8", () => HttpResponse.json(curriculum(8, { community_curriculum_id: 70 }))),
      http.get("*/api/students", () => HttpResponse.json([ada])),
      http.get("*/api/planner/curricula", () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    const router = renderAt("/next/planner/new?textbook=5");

    const option = await screen.findByRole("article", { name: "Reading 4" });
    expect(screen.getByRole("heading", { name: "Other families built a similar curriculum" })).toBeInTheDocument();
    expect(within(option).getByText("Used by 2 families · 4 days a week")).toBeInTheDocument();
    await user.click(within(option).getByRole("button", { name: "Choose pieces" }));
    expect(within(option).getByRole("checkbox", { name: /BJU Reading 4/ })).toBeDisabled();
    await user.click(within(option).getByRole("checkbox", { name: /Charlotte's Web/ }));
    await user.click(within(option).getByRole("button", { name: "Start with these" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/next/planner/8"));
    expect(body).toEqual({ community_curriculum_id: 70, entry_ids: [40] });
  });

  it("previews the dates, then puts it on the calendar", async () => {
    let scheduled: unknown = null;
    const course = { id: 1, curriculum_id: 7, student_id: 3, student_name: "Ada", start_date: "2026-10-19", end_date: "2027-05-20", weekdays: [0, 1, 2, 3], lessons_scheduled: 170 };
    server.use(
      http.get("*/api/planner/curricula/7", () => HttpResponse.json(curriculum(7, { courses: scheduled ? [course] : [] }))),
      http.get("*/api/library", () => HttpResponse.json([summary(5, "textbook", "BJU Reading 4")])),
      http.get("*/api/community/suggestions", () =>
        HttpResponse.json({ textbook: null, families_count: 0, curricula: [], often_used_with: [], message: "" }),
      ),
      http.get("*/api/students", () => HttpResponse.json([ada])),
      http.post("*/api/planner/curricula/7/schedule/preview", async ({ request }) => {
        expect(await request.json()).toEqual({ student_ids: [3], start_date: "2026-10-19", weekdays: null });
        return HttpResponse.json({
          start_date: "2026-10-19",
          weekdays: [0, 1, 2, 3],
          weekday_names: ["Mon", "Tue", "Wed", "Thu"],
          school_year_end: "2027-06-04",
          warnings: [],
          students: [
            {
              student_id: 3,
              student_name: "Ada",
              finish_date: "2027-05-20",
              lessons: 170,
              items: [{ library_item_id: 5, title: "BJU Reading 4", role: "textbook", summary: "170 lessons, one each school day", count: 170, first_date: "2026-10-19", last_date: "2027-05-20" }],
            },
          ],
        });
      }),
      http.post("*/api/planner/curricula/7/schedule", async ({ request }) => {
        scheduled = await request.json();
        return HttpResponse.json(
          {
            courses: [{ id: 1, curriculum_id: 7, student_id: 3, student_name: "Ada", start_date: "2026-10-19", end_date: "2027-05-20", weekdays: [0, 1, 2, 3], lessons_scheduled: 170 }],
            lessons_created: 170,
            calendar_url: "/#/assignments?from=planner&date=2026-10-19",
          },
          { status: 201 },
        );
      }),
      http.get("*/api/planner/curricula", () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    renderAt("/next/planner/7");

    expect(await screen.findByRole("heading", { name: "Put it on the calendar" })).toBeInTheDocument();
    expect(await screen.findByLabelText(/Start date/)).toHaveValue("2026-10-19");
    await user.click(screen.getByRole("button", { name: "Preview the dates" }));
    const preview = await screen.findByRole("region", { name: "Preview" });
    expect(within(preview).getByText(/Ada: 170 lessons, Mon, Tue, Wed, Thu, finishing/)).toBeInTheDocument();
    expect(within(preview).getByText("170 lessons, one each school day")).toBeInTheDocument();

    await user.click(within(preview).getByRole("button", { name: "Put it on the calendar" }));
    expect(await screen.findByText(/Done: 170 lessons on the calendar/)).toBeInTheDocument();
    // The curriculum refreshes with its new course; the message stays.
    expect(await screen.findByRole("region", { name: "On the calendar" })).toHaveTextContent("Ada: Oct 19 to May 20, 170 lessons");
    expect(screen.getByText(/Done: 170 lessons on the calendar/)).toBeInTheDocument();
    expect(scheduled).toEqual({ student_ids: [3], start_date: "2026-10-19", weekdays: [0, 1, 2, 3] });
    expect(screen.getByRole("link", { name: "Go to the calendar" })).toHaveAttribute("href", "/#/assignments?from=planner&date=2026-10-19");
  });
});
