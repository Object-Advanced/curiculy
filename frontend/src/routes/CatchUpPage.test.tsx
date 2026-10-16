import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CatchUpChoice, MovePreview } from "../api/parent";
import { server } from "../test/server";
import { renderAt, serveParentBasics, student } from "../test/parent";

function preview(hash: string, extra: Partial<MovePreview> = {}): MovePreview {
  return {
    summary: "12 lessons move.",
    changes: [
      {
        assignment_id: 1, title: "Saxon 5/4 · Lesson 1", student_id: 3, student_name: "Ada", course_name: "Saxon 5/4",
        from_date: "2026-10-12", to_date: "2026-10-15", skipped: false,
      },
    ],
    courses: [{ course_id: 7, course_name: "Saxon 5/4", student_name: "Ada", finish_before: "2026-12-17", finish_after: "2026-12-17", lessons_moved: 12 }],
    warnings: [],
    notes: [],
    plan_hash: hash,
    ...extra,
  };
}

function choice(option: CatchUpChoice["option"], extra: Partial<CatchUpChoice> = {}): CatchUpChoice {
  return {
    option,
    label: option,
    description: "",
    workable: true,
    why_not: null,
    result: "Finishes Thu, Dec 17, on time",
    recommended: false,
    preview: preview(`hash-${option}`),
    ...extra,
  };
}

const sheet = {
  course_id: 7,
  course_name: "Saxon 5/4",
  student_id: 3,
  student_name: "Ada",
  behind: 3,
  behind_since: "2026-10-12",
  school_year_end: "2027-06-04",
  daily_lesson_limit: null,
  allow_weekends: false,
  choices: [
    choice("use_day_off", { label: "Use a day off", recommended: true }),
    choice("double_up", { label: "Double up", preview: preview("hash-double", { summary: "6 lessons move.", warnings: ["Thu, Oct 15 becomes 4 lessons for Ada (your limit is 3)."] }) }),
    choice("push_back", { label: "Push everything back", result: "Finishes Wed, Dec 23, on time" }),
    choice("push_week", { label: "Push back a whole week" }),
    choice("skip", { label: "Skip it", workable: false, why_not: "Only review lessons are skipped, and “Lesson 1” isn't one.", preview: null, result: null }),
  ],
};

describe("Catch up", () => {
  beforeEach(() => {
    serveParentBasics();
    server.use(http.get("*/api/students", () => HttpResponse.json([student(3, "Ada"), student(4, "Ben")])));
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
  });

  afterEach(() => vi.useRealTimers());

  it("lists who's behind and catches a course up the recommended way, or another", async () => {
    let applied: unknown = null;
    server.use(
      http.get("*/api/moves/behind", () =>
        HttpResponse.json([{ course_id: 7, course_name: "Saxon 5/4", student_id: 3, student_name: "Ada", behind: 3, behind_since: "2026-10-12" }]),
      ),
      http.get("*/api/moves/catch-up/7", () => HttpResponse.json(sheet)),
      http.post("*/api/moves/apply", async ({ request }) => {
        applied = await request.json();
        return HttpResponse.json({ moved: 6, skipped: 0, summary: "6 lessons move." });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/catch-up");

    const behind = await screen.findByRole("region", { name: "Behind" });
    expect(await within(behind).findByText(/Ada: 3 lessons behind, since/)).toBeInTheDocument();
    await user.click(within(behind).getByRole("button", { name: "Catch up Saxon 5/4 for Ada" }));

    const dialog = await screen.findByRole("dialog", { name: "How should Saxon 5/4 catch up?" });
    expect(within(dialog).getByRole("radio", { name: /Use a day off/ })).toBeChecked();
    expect(within(dialog).getByText("Recommended")).toBeInTheDocument();
    expect(within(dialog).getByRole("radio", { name: /Skip it/ })).toBeDisabled();
    expect(within(dialog).getByText(/Not this time: Only review lessons/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("radio", { name: /Double up/ }));
    const changes = within(dialog).getByRole("region", { name: "What changes" });
    expect(within(changes).getByText("6 lessons move.")).toBeInTheDocument();
    expect(within(changes).getByText("Thu, Oct 15 becomes 4 lessons for Ada (your limit is 3).")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Catch up" }));
    await waitFor(() =>
      expect(applied).toEqual({
        request: { kind: "catch_up", course_id: 7, option: "double_up", allow_weekends: false },
        plan_hash: "hash-double",
      }),
    );
    expect(await within(dialog).findByText("Done. 6 lessons move.")).toBeInTheDocument();
  });

  it("moves one lesson after a preview", async () => {
    const previews: unknown[] = [];
    let applied: unknown = null;
    server.use(
      http.get("*/api/moves/behind", () => HttpResponse.json([])),
      http.get("*/api/assignments/42", () =>
        HttpResponse.json({ id: 42, title: "Saxon 5/4 · Lesson 5", scheduled_date: "2026-10-19", status: "assigned", course_id: 7 }),
      ),
      http.post("*/api/moves/preview", async ({ request }) => {
        previews.push(await request.json());
        return HttpResponse.json(preview("hash-lesson", { summary: "2 lessons move." }));
      }),
      http.post("*/api/moves/apply", async ({ request }) => {
        applied = await request.json();
        return HttpResponse.json({ moved: 2, skipped: 0, summary: "2 lessons move." });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/catch-up?move=42");

    expect(await screen.findByText("Nobody's behind: every course's lessons are on today or later.")).toBeInTheDocument();
    const dialog = await screen.findByRole("dialog", { name: "Move Saxon 5/4 · Lesson 5" });
    const day = await within(dialog).findByLabelText(/Move it to/);
    expect(day).toHaveValue("2026-10-20");
    await user.clear(day);
    await user.type(day, "2026-10-21");
    await user.click(within(dialog).getByRole("radio", { name: /Just this one/ }));
    await user.click(within(dialog).getByRole("button", { name: "Preview" }));
    expect(await within(dialog).findByText("2 lessons move.")).toBeInTheDocument();
    expect(previews).toEqual([{ kind: "lesson", assignment_id: 42, to_date: "2026-10-21", mode: "just_this" }]);

    await user.click(within(dialog).getByRole("button", { name: "Move them" }));
    await waitFor(() =>
      expect(applied).toEqual({
        request: { kind: "lesson", assignment_id: 42, to_date: "2026-10-21", mode: "just_this" },
        plan_hash: "hash-lesson",
      }),
    );
    expect(await within(dialog).findByRole("link", { name: "Go to the calendar" })).toHaveAttribute("href", "/#/assignments");
  });

  it("moves a sick day's lessons, pre-filled from Attendance", async () => {
    const previews: unknown[] = [];
    server.use(
      http.get("*/api/moves/behind", () => HttpResponse.json([])),
      http.post("*/api/moves/preview", async ({ request }) => {
        previews.push(await request.json());
        return HttpResponse.json(preview("hash-day", { notes: ["Adds “Sick” on Fri, Oct 16 to Ada's calendar."] }));
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/catch-up?day=2026-10-16&student=3");
    const dialog = await screen.findByRole("dialog", { name: "A day off or a sick day" });
    expect(within(dialog).getByLabelText(/Which day/)).toHaveValue("2026-10-16");
    expect(await within(dialog).findByRole("button", { name: "Ada" })).toHaveAttribute("aria-pressed", "true");
    await user.selectOptions(within(dialog).getByLabelText(/Put it on the calendar/), "sick");
    await user.click(within(dialog).getByRole("button", { name: "Preview" }));
    expect(await within(dialog).findByText("Adds “Sick” on Fri, Oct 16 to Ada's calendar.")).toBeInTheDocument();
    expect(previews).toEqual([{ kind: "day", date: "2026-10-16", student_ids: [3], title: "Sick", add_to_calendar: "sick" }]);
  });
});
