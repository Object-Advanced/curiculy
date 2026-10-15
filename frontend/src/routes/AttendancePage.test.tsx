import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import type { AttendanceDay } from "../api/parent";
import { server } from "../test/server";
import { attendanceChild, attendanceDay, renderAt, serveParentBasics } from "../test/parent";

const summary = {
  school_year_id: 1,
  school_year_name: "2026–27",
  start_date: "2026-10-05",
  end_date: "2026-10-30",
  today: "2026-10-15",
  count_by: "days",
  children: [
    {
      student_id: 3, name: "Ada", present_days: 5, field_trip_days: 1, sick_days: 1, absent_days: 1,
      unmarked_days: 1, school_days_left: 12, on_track_days: 17, minutes: 370, lessons_without_minutes: 1,
    },
  ],
};

function serveDays(today: AttendanceDay, sweep: AttendanceDay[] = [], countBy = "days") {
  server.use(
    http.get("*/api/attendance/days", ({ request }) => {
      const from = new URL(request.url).searchParams.get("start_date");
      return HttpResponse.json({ today: "2026-10-15", count_by: countBy, days: from ? sweep : [today] });
    }),
    http.get("*/api/attendance/summary", () => HttpResponse.json({ ...summary, count_by: countBy })),
  );
}

describe("Attendance", () => {
  beforeEach(() => serveParentBasics());

  it("pre-fills today from the work done and saves with one tap", async () => {
    let body: unknown = null;
    serveDays(
      attendanceDay("2026-10-15", "Thursday", [
        attendanceChild(3, "Ada", { suggestion: "Present", reasons: ["Finished 2 lessons"], lessons_done: 2 }),
        attendanceChild(4, "Ben", { reasons: ["1 lesson planned, none checked off yet"], lessons_planned: 1 }),
      ]),
    );
    server.use(
      http.post("*/api/attendance/confirm", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/attendance");

    const card = await screen.findByRole("region", { name: "School today?" });
    expect(within(card).getByText("Present (suggested)")).toBeInTheDocument();
    expect(within(card).getByText("Finished 2 lessons")).toBeInTheDocument();
    const ada = within(card).getByRole("group", { name: "Ada on School today?" });
    expect(within(ada).getByRole("button", { name: "Present" })).toHaveAttribute("aria-pressed", "true");
    expect(within(card).getByRole("status")).toHaveTextContent("Ben isn't marked: pick one, or leave it for later.");

    await user.click(within(card).getByRole("button", { name: "Looks right" }));
    await waitFor(() => expect(body).toEqual({ marks: [{ student_id: 3, date: "2026-10-15", status: "Present" }] }));
    expect(await within(card).findByText("Saved.")).toBeInTheDocument();

    const ben = within(card).getByRole("group", { name: "Ben on School today?" });
    await user.click(within(ben).getByRole("button", { name: "Field trip" }));
    await user.click(within(card).getByRole("button", { name: "Looks right" }));
    await waitFor(() =>
      expect(body).toEqual({
        marks: [
          { student_id: 3, date: "2026-10-15", status: "Present" },
          { student_id: 4, date: "2026-10-15", status: "Field trip" },
        ],
      }),
    );
  });

  it("lists the days of the last two weeks that aren't marked, and the year so far", async () => {
    let confirmed: unknown = null;
    server.use(
      http.post("*/api/attendance/confirm", async ({ request }) => {
        confirmed = await request.json();
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    serveDays(
      attendanceDay("2026-10-15", "Thursday", [attendanceChild(3, "Ada", { status: "Present", source: "suggestion" })]),
      [
        attendanceDay("2026-10-13", "Tuesday", [attendanceChild(3, "Ada", { suggestion: "Present", reasons: ["Finished 1 lesson"] })]),
        attendanceDay("2026-10-14", "Wednesday", [attendanceChild(3, "Ada", { status: "Sick" })]),
        attendanceDay("2026-10-11", "Sunday", [attendanceChild(3, "Ada", { expected: false, reasons: ["Not a school day"] })], { school_day: false }),
      ],
    );
    renderAt("/next/attendance");

    const today = await screen.findByRole("region", { name: "School today?" });
    expect(within(today).getByText("Marked Present, as suggested")).toBeInTheDocument();
    expect(within(today).getByRole("status")).toHaveTextContent("Everyone's marked.");

    const sweep = await screen.findByRole("region", { name: "Not marked yet" });
    expect(within(sweep).getByText(/1 day in the last two weeks isn't marked/)).toBeInTheDocument();
    const [tuesday] = within(sweep).getAllByRole("listitem");
    expect(tuesday).toHaveTextContent("Ada: Present (suggested)");
    expect(within(sweep).queryByText(/^Wednesday, /)).not.toBeInTheDocument();
    // One line per day; "Change" opens the day's full card.
    expect(within(sweep).queryByRole("group")).not.toBeInTheDocument();
    await user.click(within(tuesday!).getByRole("button", { name: /^Change Tuesday, / }));
    expect(within(sweep).getByRole("region", { name: /^Tuesday, / })).toBeInTheDocument();
    await user.click(within(tuesday!).getByRole("button", { name: /^Looks right: Tuesday, / }));
    await waitFor(() => expect(confirmed).toEqual({ marks: [{ student_id: 3, date: "2026-10-13", status: "Present" }] }));

    const year = await screen.findByRole("region", { name: "2026–27: the year so far" });
    expect(within(year).getByText("5")).toBeInTheDocument();
    expect(within(year).getByText(/On track for 17 days by/)).toHaveTextContent("12 school days left");
    expect(within(year).getByText("1 school day not marked")).toBeInTheDocument();
    expect(within(year).getByText("1 field trip · 1 sick · 1 absent")).toBeInTheDocument();
  });

  it("asks for minutes in hours mode, and only sends the parent's own number", async () => {
    let body: unknown = null;
    serveDays(
      attendanceDay("2026-10-15", "Thursday", [
        attendanceChild(3, "Ada", {
          suggestion: "Present", reasons: ["Finished 2 lessons"], minutes: 65, minutes_from_work: 65, lessons_without_minutes: 1,
        }),
      ]),
      [],
      "hours",
    );
    server.use(
      http.post("*/api/attendance/confirm", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/attendance");
    const card = await screen.findByRole("region", { name: "School today?" });
    const minutes = within(card).getByLabelText("Minutes of school");
    expect(minutes).toHaveValue(65);
    expect(minutes).toHaveAccessibleDescription("1 h 5 min from lessons and activities; 1 lesson has none");
    await user.clear(minutes);
    await user.type(minutes, "180");
    await user.click(within(card).getByRole("button", { name: "Looks right" }));
    await waitFor(() =>
      expect(body).toEqual({ marks: [{ student_id: 3, date: "2026-10-15", status: "Present", minutes: 180 }] }),
    );
    expect(await screen.findByText("6 h 10 min")).toBeInTheDocument();
  });

  it("folds away a day off until the parent asks", async () => {
    serveDays(
      attendanceDay(
        "2026-10-15",
        "Thursday",
        [attendanceChild(3, "Ada", { expected: false, reasons: ["Day off: Field day"] })],
        { school_day: false, day_off: "Field day" },
      ),
    );
    const user = userEvent.setup();
    renderAt("/next/attendance");
    const card = await screen.findByRole("region", { name: "School today?" });
    expect(within(card).getByText("Day off: Field day", { selector: ".badge" })).toBeInTheDocument();
    expect(within(card).getByText("No school")).toBeInTheDocument();
    expect(within(card).queryByRole("group")).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Mark it anyway" }));
    expect(within(card).getByRole("group", { name: "Ada on School today?" })).toBeInTheDocument();
  });
});
