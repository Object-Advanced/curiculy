import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { server } from "../test/server";
import { readingEntry, renderAt, serveParentBasics, student, summary } from "../test/parent";

const kids = [student(3, "Ada"), student(4, "Ben")];

describe("Reading lists", () => {
  beforeEach(() => {
    serveParentBasics();
    server.use(http.get("*/api/students", () => HttpResponse.json(kids)));
  });

  it("shows each child's books by where they are", async () => {
    const asked: string[] = [];
    server.use(
      http.get("*/api/reading-list", ({ request }) => {
        const child = new URL(request.url).searchParams.get("student_id") ?? "";
        asked.push(child);
        if (child === "4") return HttpResponse.json([readingEntry(9, 4, "The Hobbit", { student_name: "Ben" })]);
        return HttpResponse.json([
          readingEntry(1, 3, "Charlotte's Web", {
            status: "reading",
            status_label: "Reading",
            started_on: "2026-10-12",
            source: "scheduled",
            scheduled: true,
            lessons_total: 10,
            lessons_done: 3,
          }),
          readingEntry(2, 3, "Johnny Tremain", {
            status: "finished",
            status_label: "Finished",
            started_on: "2026-09-01",
            finished_on: "2026-09-20",
            counts_toward: "us_history",
            counts_toward_name: "U.S. and state history",
          }),
        ]);
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/reading");

    const now = await screen.findByRole("region", { name: "Reading now" });
    expect(within(now).getByRole("heading", { name: "Charlotte's Web" })).toBeInTheDocument();
    expect(within(now).getByText("On the calendar: 3 of 10 readings done")).toBeInTheDocument();
    expect(within(now).getByText(/^Started /)).toBeInTheDocument();
    const finished = screen.getByRole("region", { name: "Finished" });
    expect(within(finished).getByText(/Counts toward U.S. and state history/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Up next" })).getByText("Nothing waiting.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ben" }));
    expect(await screen.findByRole("heading", { name: "The Hobbit" })).toBeInTheDocument();
    expect(asked).toEqual(["3", "4"]);
  });

  it("moves a book along in one tap", async () => {
    let body: unknown = null;
    server.use(
      http.get("*/api/reading-list", () => HttpResponse.json([readingEntry(1, 3, "Charlotte's Web")])),
      http.patch("*/api/reading-list/1", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(readingEntry(1, 3, "Charlotte's Web", { status: "reading", status_label: "Reading" }));
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/reading");
    await user.click(await screen.findByRole("button", { name: "Started it" }));
    await waitFor(() => expect(body).toEqual({ status: "reading" }));
  });

  it("adds a book from the Library, read last month", async () => {
    let body: unknown = null;
    server.use(
      http.get("*/api/reading-list", () => HttpResponse.json([readingEntry(1, 3, "Charlotte's Web")])),
      http.get("*/api/library", () =>
        HttpResponse.json([
          summary(101, "reading_book", "Charlotte's Web"),
          summary(102, "reading_book", "Johnny Tremain", { author: "Esther Forbes" }),
          summary(5, "textbook", "BJU Reading 4"),
        ]),
      ),
      http.post("*/api/reading-list", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(readingEntry(2, 3, "Johnny Tremain"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/reading");
    await user.click(await screen.findByRole("button", { name: "Add a book" }));

    const dialog = await screen.findByRole("dialog", { name: "Add a book to Ada's list" });
    const book = within(dialog).getByRole("combobox", { name: /Book/ });
    // Only books to read, and not ones already on the list.
    await waitFor(() => expect(within(book).getAllByRole("option").map((o) => o.textContent)).toEqual(["Choose a book…", "Johnny Tremain (Esther Forbes)"]));
    await user.selectOptions(book, "102");
    await user.click(within(dialog).getByRole("button", { name: "Finished" }));
    await user.type(within(dialog).getByLabelText("Finished"), "2026-09-20");
    await user.click(within(dialog).getByRole("button", { name: "Add it" }));

    await waitFor(() =>
      expect(body).toEqual({
        student_id: 3,
        library_item_id: 102,
        status: "finished",
        counts_toward: null,
        started_on: null,
        finished_on: "2026-09-20",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("explains an empty list", async () => {
    server.use(http.get("*/api/reading-list", () => HttpResponse.json([])));
    renderAt("/next/reading?child=4");
    expect(await screen.findByRole("heading", { name: "Nothing on Ben's list yet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ben" })).toHaveAttribute("aria-pressed", "true");
  });
});
