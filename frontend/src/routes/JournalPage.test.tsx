import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RouterProvider, createMemoryRouter } from "react-router";

import type { Lesson } from "../api/client";
import { routes } from "../router";
import { server } from "../test/server";

function lesson(id: number, title: string, scheduled: string, done: boolean, completed: string | null = null): Lesson {
  return {
    id,
    student_id: 3,
    title,
    scheduled_date: scheduled,
    completion_date: completed,
    status: done ? "completed" : "assigned",
    notes: null,
    curriculum_resource_id: null,
    curriculum_unit_id: null,
    subject_taxonomy_id: null,
    subject_name: null,
    resource_title: null,
    unit_title: null,
    curriculum_id: null,
    shared_group_uuid: null,
    color_hex: null,
    grade: null,
    evidence_count: 0,
  };
}

// Wednesday 14 October 2026.
const LESSONS: Lesson[] = [
  lesson(7, "Nature walk", "2026-10-01", true, "2026-10-01"),
  lesson(6, "Saxon Math Lesson 39", "2026-10-09", true, "2026-10-13"),
  lesson(1, "Saxon Math Lesson 40", "2026-10-12", true, "2026-10-12"),
  lesson(2, "Spelling list 6", "2026-10-13", false),
  lesson(3, "Read The Hobbit, chapter 2", "2026-10-14", true),
  lesson(4, "Fractions worksheet", "2026-10-14", false),
  lesson(5, "Science: states of matter", "2026-10-15", false),
];

function renderJournal(path = "/next/journal") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path], basename: "/next" });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Sticker journal", () => {
  let ranges: string[];

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 14, 10, 0));
    window.localStorage.setItem("auth_token", "test-token");
    ranges = [];
    server.use(
      http.get("*/api/auth/me", () =>
        HttpResponse.json({ email: "k@kids", tenant_uuid: "t", is_demo: false, is_admin: false, role: "child", student_id: 3, display_name: "Ada Okafor", grade: "4" }),
      ),
      http.get("*/api/students/3/assignments", ({ request }) => {
        const url = new URL(request.url);
        const from = url.searchParams.get("start_date")!;
        const to = url.searchParams.get("end_date")!;
        ranges.push(`${from}..${to}`);
        const rows = LESSONS.filter((row) => row.scheduled_date >= from && row.scheduled_date <= to);
        return HttpResponse.json({ student_id: 3, period: null, start_date: from, end_date: to, count: rows.length, assignments: rows });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows this week's stickers by day, with camp tents", async () => {
    renderJournal();
    expect(await screen.findByRole("heading", { name: "This week" })).toBeInTheDocument();
    expect(screen.getByText("Oct 12 – 16")).toBeInTheDocument();
    expect(screen.getByText("3 stickers this week")).toBeInTheDocument();
    expect(ranges).toEqual(["2026-08-31..2026-10-31"]);

    const days = within(screen.getByRole("list", { name: "Stickers by day" })).getAllByRole("listitem");
    expect(days.map((day) => day.textContent?.slice(0, 5))).toEqual(["Mon12", "Tue13", "Today", "Thu15", "Fri16"]);
    expect(within(days[0]!).getByRole("button", { name: "Math sticker: Saxon Math Lesson 40" })).toBeInTheDocument();
    expect(days[0]).toHaveTextContent("Camp!");
    // Last week's lesson, finished on Tuesday, counts on Tuesday.
    expect(within(days[1]!).getByRole("button", { name: "Math sticker: Saxon Math Lesson 39" })).toBeInTheDocument();
    expect(within(days[2]!).getByRole("button", { name: "Reading sticker: Read The Hobbit, chapter 2" })).toBeInTheDocument();
    expect(within(days[2]!).getByRole("link", { name: "1 stop to go" })).toHaveAttribute("href", "/next/trail");
    expect(days[3]).toHaveTextContent("Coming up");
    expect(days[4]).toHaveTextContent("Coming up");
  });

  it("tells which lesson earned a sticker", async () => {
    const user = userEvent.setup();
    renderJournal();
    await user.click(await screen.findByRole("button", { name: "Math sticker: Saxon Math Lesson 39" }));
    expect(screen.getByText("Your Math sticker is from “Saxon Math Lesson 39”, finished on Tuesday.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reading sticker: Read The Hobbit, chapter 2" }));
    expect(screen.getByText("Your Reading sticker is from “Read The Hobbit, chapter 2”, on Wednesday.")).toBeInTheDocument();
  });

  it("fills the month's collection from camp days", async () => {
    renderJournal();
    const collection = await screen.findByRole("region", { name: "October collection" });
    expect(within(collection).getByText("2 of 8")).toBeInTheDocument();
    expect(within(collection).getByText("Acorn")).toBeInTheDocument();
    expect(within(collection).getByText("Owl")).toBeInTheDocument();
    expect(within(collection).getByText("Today’s prize")).toBeInTheDocument();
    expect(within(collection).getAllByText("Mystery")).toHaveLength(5);
  });

  it("pages back through earlier weeks, but not into the future", async () => {
    const user = userEvent.setup();
    renderJournal();
    expect(await screen.findByRole("button", { name: "Week after ›" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "‹ Week before" }));
    expect(await screen.findByRole("heading", { name: "That week" })).toBeInTheDocument();
    expect(screen.getByText("Oct 5 – 9")).toBeInTheDocument();
    // Friday's lesson was finished the next Tuesday: camp on Friday, sticker on Tuesday.
    expect(screen.getByText("No stickers that week.")).toBeInTheDocument();
    const days = within(screen.getByRole("list", { name: "Stickers by day" })).getAllByRole("listitem");
    expect(days.at(-1)).toHaveTextContent(/^Fri9No stickers on this dayCamp!$/);
    expect(days[0]).toHaveTextContent("Rest day");
    expect(screen.getByRole("button", { name: "Week after ›" })).toBeEnabled();
  });

  it("links between My trail and the journal", async () => {
    renderJournal();
    const tabs = await screen.findByRole("navigation", { name: "Pages" });
    expect(within(tabs).getByRole("link", { name: "My trail" })).toHaveAttribute("href", "/next/trail");
    expect(within(tabs).getByRole("link", { name: "Sticker journal" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "My day" })).toHaveAttribute("href", "/#/my-work");
  });
});
