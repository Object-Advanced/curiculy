import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "../test/server";
import { activity, renderAt, serveParentBasics, student } from "../test/parent";

const kids = [student(3, "Ada"), student(4, "Ben")];

describe("Activities", () => {
  beforeEach(() => {
    serveParentBasics();
    server.use(http.get("*/api/students", () => HttpResponse.json(kids)));
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 15, 10, 0));
  });

  afterEach(() => vi.useRealTimers());

  it("lists activities by month, for everyone or one child", async () => {
    server.use(
      http.get("*/api/activities", () =>
        HttpResponse.json([
          activity(2, "5K race", "2026-10-10", {
            minutes: 40,
            subjects: [{ code: "pe", name: "Physical education" }],
            students: [
              { student_id: 3, name: "Ada" },
              { student_id: 4, name: "Ben" },
            ],
            link_url: "https://www.youtube.com/watch?v=abc",
          }),
          activity(1, "Piano recital", "2026-09-28", { students: [{ student_id: 4, name: "Ben" }] }),
        ]),
      ),
    );
    const user = userEvent.setup();
    renderAt("/next/activities");

    const october = await screen.findByRole("region", { name: "October 2026" });
    const race = within(october).getByRole("listitem");
    expect(within(race).getByRole("heading", { name: "5K race" })).toBeInTheDocument();
    expect(within(race).getByText(/Ada, Ben · 40 min/)).toBeInTheDocument();
    expect(within(race).getByText("Physical education")).toBeInTheDocument();
    expect(within(race).getByRole("link", { name: "Open the link (youtube.com)" })).toHaveAttribute("target", "_blank");
    const september = screen.getByRole("region", { name: "September 2026" });
    expect(within(september).getByText(/No subject yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Ada/ }));
    expect(screen.queryByRole("region", { name: "September 2026" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "5K race" })).toBeInTheDocument();
  });

  it("logs an activity for two children", async () => {
    let body: unknown = null;
    let listed = 0;
    server.use(
      http.get("*/api/activities", () => {
        listed += 1;
        return HttpResponse.json([]);
      }),
      http.post("*/api/activities", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(activity(5, "Fire station visit", "2026-10-15"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/activities");
    await user.click((await screen.findAllByRole("button", { name: "Log an activity" }))[0]!);

    const dialog = await screen.findByRole("dialog", { name: "Log an activity" });
    const save = within(dialog).getByRole("button", { name: "Log it" });
    expect(save).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/What did you do/), "Fire station visit");
    await user.click(within(dialog).getByRole("button", { name: "Ada" }));
    await user.click(within(dialog).getByRole("button", { name: "Ben" }));
    await user.click(within(dialog).getByRole("button", { name: "English" }));
    await user.type(within(dialog).getByLabelText("Minutes"), "90");
    await user.click(save);

    await waitFor(() =>
      expect(body).toEqual({
        title: "Fire station visit",
        on_date: "2026-10-15",
        student_ids: [3, 4],
        subject_codes: ["english"],
        minutes: 90,
        link_url: null,
        notes: null,
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(listed).toBeGreaterThan(1);
  });

  it("changes an activity", async () => {
    let body: unknown = null;
    server.use(
      http.get("*/api/activities", () => HttpResponse.json([activity(2, "5K race", "2026-10-10")])),
      http.patch("*/api/activities/2", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(activity(2, "5K fun run", "2026-10-10"));
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/activities");
    await user.click(await screen.findByRole("button", { name: "Change 5K race" }));
    const dialog = await screen.findByRole("dialog", { name: "5K race" });
    const title = within(dialog).getByLabelText(/What did you do/);
    await user.clear(title);
    await user.type(title, "5K fun run");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(body).toMatchObject({ title: "5K fun run", student_ids: [3] }));
  });
});
