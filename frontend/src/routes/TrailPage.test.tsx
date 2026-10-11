import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RouterProvider, createMemoryRouter } from "react-router";

import type { Lesson } from "../api/client";
import { routes } from "../router";
import { server } from "../test/server";

function lesson(id: number, title: string, extra: Partial<Lesson> = {}): Lesson {
  return {
    id,
    student_id: 3,
    title,
    scheduled_date: "2026-10-14",
    completion_date: null,
    status: "assigned",
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
    ...extra,
  };
}

const childMe = {
  email: "child-3@kids.curiculy",
  tenant_uuid: "t-1",
  is_demo: false,
  is_admin: false,
  role: "child",
  student_id: 3,
  display_name: "Ada Okafor",
  grade: "4",
};

function renderTrail(path = "/next/trail") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path], basename: "/next" });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("My trail", () => {
  let lessons: Lesson[];
  let patches: { id: number; status: string; key: string | null }[];

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 14, 10, 0));
    window.localStorage.setItem("auth_token", "test-token");
    patches = [];
    lessons = [
      lesson(11, "Read The Hobbit, chapter 2", { status: "completed", resource_title: "The Hobbit" }),
      lesson(12, "Fractions worksheet", { notes: "Pages 14–15 in the blue workbook.\n[Homework help] old log line" }),
    ];
    server.use(
      http.get("*/api/auth/me", () => HttpResponse.json(childMe)),
      http.get("*/api/students/3/assignments", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("start_date")).toBe("2026-10-14");
        expect(url.searchParams.get("end_date")).toBe("2026-10-14");
        expect(request.headers.get("Authorization")).toBe("Bearer test-token");
        return HttpResponse.json({ student_id: 3, period: null, start_date: "2026-10-14", end_date: "2026-10-14", count: lessons.length, assignments: lessons });
      }),
      http.patch("*/api/assignments/:id/status", async ({ params, request }) => {
        const { status } = (await request.json()) as { status: Lesson["status"] };
        const id = Number(params.id);
        patches.push({ id, status, key: request.headers.get("Idempotency-Key") });
        lessons = lessons.map((row) => (row.id === id ? { ...row, status } : row));
        return HttpResponse.json(lessons.find((row) => row.id === id));
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows today's lessons as stops, pointing at the family's materials", async () => {
    renderTrail();
    expect(await screen.findByRole("heading", { name: "Hi Ada!" })).toBeInTheDocument();
    expect(screen.getByText("1 stop to camp")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Trail map: 1 of 2 stops done." })).toBeInTheDocument();

    const stops = within(screen.getByRole("list", { name: "Today's stops" })).getAllByRole("listitem");
    expect(stops).toHaveLength(2);
    expect(stops[0]).toHaveTextContent("From The Hobbit");
    expect(stops[0]).toHaveTextContent("Done! Reading sticker earned");
    expect(stops[1]).toHaveAttribute("aria-current", "step");
    expect(stops[1]).toHaveTextContent("Note: Pages 14–15 in the blue workbook.");
    expect(stops[1]).not.toHaveTextContent("[Homework help]");
    expect(screen.getByRole("link", { name: "My day" })).toHaveAttribute("href", "/#/my-work");
  });

  it("checks a stop off and reaches camp", async () => {
    const user = userEvent.setup();
    renderTrail();
    await user.click(await screen.findByRole("button", { name: "I did it: Fractions worksheet" }));

    expect(await screen.findByRole("heading", { name: "You reached camp!" })).toBeInTheDocument();
    expect(screen.getByText(/You earned the Harvest moon sticker/)).toBeInTheDocument();
    expect(screen.getByText("You made it to camp!")).toBeInTheDocument();
    expect(patches).toHaveLength(1);
    expect(patches[0]).toMatchObject({ id: 12, status: "completed" });
    expect(patches[0]?.key).toBeTruthy();
  });

  it("lets a child undo a mistaken check-off", async () => {
    const user = userEvent.setup();
    renderTrail();
    await user.click(await screen.findByRole("button", { name: "Not done yet: Read The Hobbit, chapter 2" }));
    await waitFor(() => expect(patches).toEqual([expect.objectContaining({ id: 11, status: "assigned" })]));
    expect(await screen.findByText("2 stops to camp")).toBeInTheDocument();
  });

  it("puts the daily puzzle in the bonus chest", async () => {
    const user = userEvent.setup();
    renderTrail();
    const chest = await screen.findByRole("button", { name: "Open it" });
    await user.click(chest);
    expect(chest).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Just for fun")).toBeInTheDocument();
  });

  it("shows a rest day when there are no lessons", async () => {
    lessons = [];
    renderTrail();
    expect(await screen.findByText("No stops today. It’s a rest day at camp.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Trail map: no stops today, a rest day at camp." })).toBeInTheDocument();
  });

  it("lets a parent preview each child's trail", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("*/api/auth/me", () => HttpResponse.json({ ...childMe, role: "parent", student_id: null, display_name: "Rivera" })),
      http.get("*/api/students", () =>
        HttpResponse.json([
          { id: 3, name: "Sam Rivera", grade: "3", household_id: 1, color_hex: null, notes: null, has_login: true },
          { id: 4, name: "Maya Rivera", grade: "1", household_id: 1, color_hex: null, notes: null, has_login: false },
        ]),
      ),
      http.get("*/api/students/4/assignments", () =>
        HttpResponse.json({ student_id: 4, period: null, start_date: "2026-10-14", end_date: "2026-10-14", count: 1, assignments: [lesson(21, "Phonics: short a", { student_id: 4 })] }),
      ),
    );
    renderTrail("/next/trail?student=3");
    expect(await screen.findByRole("heading", { name: "Hi Sam!" })).toBeInTheDocument();
    expect(screen.getByText("Parent preview. Checking off here counts for Sam.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Kids" })).toHaveAttribute("href", "/#/students/3");

    await user.click(screen.getByRole("button", { name: "Maya" }));
    expect(await screen.findByRole("heading", { name: "Hi Maya!" })).toBeInTheDocument();
    expect(screen.getByText("Phonics: short a")).toBeInTheDocument();
  });
});
