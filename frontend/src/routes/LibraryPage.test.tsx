import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { server } from "../test/server";
import { item, readingEntry, renderAt, student, summary, serveParentBasics } from "../test/parent";

describe("Library", () => {
  beforeEach(() => serveParentBasics());

  it("shows every kind on one shelf, with filters and what's left to do", async () => {
    server.use(
      http.get("*/api/library", () =>
        HttpResponse.json([
          summary(1, "reading_book", "Charlotte's Web"),
          summary(2, "workbook", "Spectrum Math", { ready: false, missing_count: 1, subject_code: "math", subject_name: "Math" }),
          summary(3, "textbook", "BJU Reading 4"),
        ]),
      ),
    );
    const user = userEvent.setup();
    renderAt("/next/library");

    const shelf = await screen.findByRole("list", { name: "Your shelf" });
    expect(within(shelf).getAllByRole("listitem")).toHaveLength(3);
    expect(within(shelf).getByText("1 thing to finish")).toBeInTheDocument();
    expect(within(shelf).getAllByText("Ready to schedule")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute("aria-current", "page");

    await user.click(screen.getByRole("button", { name: /Workbooks/ }));
    expect(within(shelf).getAllByRole("listitem")).toHaveLength(1);
    expect(within(shelf).getByRole("button", { name: /Spectrum Math/ })).toBeInTheDocument();
  });

  it("explains the four kinds when the shelf is empty", async () => {
    server.use(http.get("*/api/library", () => HttpResponse.json([])));
    renderAt("/next/library");
    expect(await screen.findByRole("heading", { name: "Your shelf is empty, for now" })).toBeInTheDocument();
    expect(await screen.findByText("The main book you teach a subject from.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add your first book" })).toBeInTheDocument();
  });

  it("walks through adding a book by hand, one step at a time", async () => {
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([])),
      http.get("*/api/library/search", () => HttpResponse.json({ query: "x", results: [], notice: "Nothing matched. You can add it yourself." })),
      http.post("*/api/library", async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(item(9, "reading_book", "The Hobbit", { author: "J. R. R. Tolkien" }), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/library?add=1");

    const dialog = await screen.findByRole("dialog", { name: "Add to your library" });
    await user.type(within(dialog).getByRole("searchbox"), "The Hobbit");
    await user.click(within(dialog).getByRole("button", { name: "Search" }));
    expect(await within(dialog).findByText("Nothing matched. You can add it yourself.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Add it yourself" }));

    const basics = await screen.findByRole("dialog", { name: "The basics" });
    expect(within(basics).getByLabelText(/Title/)).toHaveValue("The Hobbit");
    await user.click(within(basics).getByRole("button", { name: "Next: what is this?" }));

    const kind = await screen.findByRole("dialog", { name: "What is this?" });
    await user.click(within(kind).getByRole("radio", { name: /Book A book to read/ }));
    await user.click(within(kind).getByRole("button", { name: "Next: the details" }));

    const details = await screen.findByRole("dialog", { name: "About this book" });
    await user.type(within(details).getByLabelText(/Author/), "J. R. R. Tolkien");
    await user.type(within(details).getByLabelText(/Total pages/), "310");
    await user.click(within(details).getByRole("button", { name: "Save, then add chapters" }));

    const chapters = await screen.findByRole("dialog", { name: "Chapters" });
    expect(created).toMatchObject({ kind: "reading_book", title: "The Hobbit", author: "J. R. R. Tolkien", total_pages: 310 });
    await user.click(within(chapters).getByRole("button", { name: "Skip for now" }));

    const done = await screen.findByRole("dialog", { name: "Added to your library" });
    expect(within(done).getByText("Ready to schedule.")).toBeInTheDocument();
    expect(within(done).getByText(/Shared with the Curiculy catalog/)).toBeInTheDocument();
  });

  it("adds a catalog entry in one step, and offers to plan a textbook", async () => {
    let adopted: unknown = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([])),
      http.get("*/api/library/search", () =>
        HttpResponse.json({
          query: "bju",
          results: [
            {
              source: "community",
              title: "BJU Reading 4",
              authors: [],
              guessed_kind: "textbook",
              guessed_kind_label: "Textbook",
              catalog_entry_id: 44,
              families_count: 3,
              detail: "170 lessons, 300 pages, entered by 3 families",
            },
          ],
        }),
      ),
      http.get("*/api/community/suggestions", () =>
        HttpResponse.json({ textbook: null, families_count: 0, curricula: [], often_used_with: [], message: "None yet." }),
      ),
      http.post("*/api/library/from-community", async ({ request }) => {
        adopted = await request.json();
        return HttpResponse.json(
          item(12, "textbook", "BJU Reading 4", { community: { status: "in_catalog", label: "In the Curiculy catalog, used by 4 families." } }),
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    const router = renderAt("/next/library?add=1");
    const dialog = await screen.findByRole("dialog", { name: "Add to your library" });
    await user.type(within(dialog).getByRole("searchbox"), "bju");
    await user.click(within(dialog).getByRole("button", { name: "Search" }));
    expect(await within(dialog).findByText("In the Curiculy catalog: ready to use")).toBeInTheDocument();
    expect(within(dialog).getByText(/170 lessons, 300 pages, entered by 3 families/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Add to my library" }));

    const done = await screen.findByRole("dialog", { name: "Added from the catalog" });
    expect(adopted).toEqual({ entry_id: 44 });
    expect(within(done).getByText("In the Curiculy catalog, used by 4 families.")).toBeInTheDocument();
    await user.click(within(done).getByRole("button", { name: "Plan a curriculum with it" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/next/planner/new"));
    expect(router.state.location.search).toBe("?textbook=12");
  });

  it("opens an item to finish its lesson list, with what's missing and why", async () => {
    const textbook = item(5, "textbook", "Saxon Math 5/4", {
      ready: false,
      readiness: {
        ready: false,
        missing: [{ field: "lessons", label: "The lesson list", reason: "The calendar places each lesson in order." }],
        problems: [],
        lessons_total: 0,
        lessons_with_pages: 0,
        lessons_with_names: 0,
      },
    });
    let saved: unknown = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([summary(5, "textbook", "Saxon Math 5/4", { ready: false, missing_count: 1 })])),
      http.get("*/api/library/5", () => HttpResponse.json(textbook)),
      http.put("*/api/library/5/lessons", async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json({ ...textbook, ready: true, readiness: { ...textbook.readiness, ready: true, missing: [] } });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/library?item=5");
    const panel = await screen.findByRole("dialog", { name: "Saxon Math 5/4" });
    expect(within(panel).getByText("Still needed: The lesson list.")).toBeInTheDocument();
    expect(within(panel).getByText("The calendar places each lesson in order.")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Paste a lesson list" }));
    await user.type(within(panel).getByLabelText("Paste a lesson list"), "1 Adding 1-4{enter}2 Subtracting 5-8");
    await user.click(within(panel).getByRole("button", { name: "Add these" }));
    expect(within(panel).getByText("2 lessons, 2 with pages.")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Save the lesson list" }));
    await waitFor(() =>
      expect(saved).toEqual([
        { number: 1, name: "Adding", type: "lesson", start_page: 1, end_page: 4, minutes: null },
        { number: 2, name: "Subtracting", type: "lesson", start_page: 5, end_page: 8, minutes: null },
      ]),
    );
    expect(await within(panel).findByText("Ready to schedule.")).toBeInTheDocument();
  });

  it("scans a barcode from a photo and searches for the exact book", async () => {
    let searched = "";
    server.use(
      http.get("*/api/library", () => HttpResponse.json([])),
      http.post("*/api/library/read-barcode", () => HttpResponse.json({ isbn: "9780064400558", message: "Found ISBN 9780064400558." })),
      http.get("*/api/library/search", ({ request }) => {
        searched = new URL(request.url).searchParams.get("q") ?? "";
        return HttpResponse.json({ query: searched, results: [], notice: "No book with that ISBN was found. You can add it yourself." });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/library?add=1");
    const dialog = await screen.findByRole("dialog", { name: "Add to your library" });
    await user.click(within(dialog).getByRole("button", { name: "Scan the barcode" }));
    const scanner = within(dialog).getByRole("region", { name: "Scan a barcode" });
    expect(within(scanner).getByText(/Take a photo of the barcode on the back cover/)).toBeInTheDocument();
    await user.upload(within(scanner).getByLabelText("Take a photo of the barcode"), new File(["jpeg"], "back.jpg", { type: "image/jpeg" }));
    expect(await within(dialog).findByText("No book with that ISBN was found. You can add it yourself.")).toBeInTheDocument();
    expect(searched).toBe("9780064400558");
    expect(within(dialog).getByRole("searchbox")).toHaveValue("9780064400558");
  });

  it("reads a lesson list from a photo, for the parent to check", async () => {
    const textbook = item(5, "textbook", "Saxon Math 5/4", { ready: false });
    server.use(
      http.get("*/api/library", () => HttpResponse.json([summary(5, "textbook", "Saxon Math 5/4", { ready: false, missing_count: 1 })])),
      http.get("*/api/library/5", () => HttpResponse.json(textbook)),
      http.post("*/api/library/read-page", () =>
        HttpResponse.json({ text: "1 Adding 1-4\n2 Subtracting 5-8", lines: 2, left_out: 1, message: "Read 2 lines from the photo. Check them against the page (photos aren't always read perfectly), then add them." }),
      ),
    );
    const user = userEvent.setup();
    renderAt("/next/library?item=5");
    const panel = await screen.findByRole("dialog", { name: "Saxon Math 5/4" });
    await user.click(within(panel).getByRole("tab", { name: "Lesson list" }));
    await user.upload(within(panel).getByLabelText("Read a photo of the page"), new File(["png"], "plan.png", { type: "image/png" }));
    expect(await within(panel).findByText(/Read 2 lines from the photo/)).toBeInTheDocument();
    expect(within(panel).getByLabelText("Paste a lesson list")).toHaveValue("1 Adding 1-4\n2 Subtracting 5-8");
    await user.click(within(panel).getByRole("button", { name: "Add these" }));
    expect(within(panel).getByText("2 lessons, 2 with pages.")).toBeInTheDocument();
  });

  it("schedules one book on its own, at the parent's pace", async () => {
    const book = item(9, "reading_book", "Charlotte's Web", { total_pages: 184 });
    let previewed: unknown = null;
    let scheduled: unknown = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([summary(9, "reading_book", "Charlotte's Web")])),
      http.get("*/api/library/9", () =>
        HttpResponse.json(
          scheduled
            ? { ...book, courses: [{ id: 4, curriculum_id: 2, student_id: 3, student_name: "Ada", start_date: "2026-10-19", end_date: "2026-10-30", weekdays: [0, 1, 2, 3, 4], lessons_scheduled: 10 }] }
            : book,
        ),
      ),
      http.get("*/api/students", () =>
        HttpResponse.json([{ id: 3, name: "Ada", grade: "4", color_hex: "#000000", grade_confirmed_on: null, grade_needs_confirming: false, has_iep: false, has_login: false, household_id: 1, notes: null }]),
      ),
      http.post("*/api/library/9/schedule/preview", async ({ request }) => {
        previewed = await request.json();
        return HttpResponse.json({
          pace: "20 pages of Charlotte's Web a day", start_date: "2026-10-19", weekdays: [0, 1, 2, 3, 4],
          weekday_names: ["Mon", "Tue", "Wed", "Thu", "Fri"], school_year_end: "2027-06-04", warnings: [],
          students: [{ student_id: 3, student_name: "Ada", finish_date: "2026-10-30", lessons: 10,
            items: [{ library_item_id: 9, title: "Charlotte's Web", role: "reading", summary: "184 pages over 10 days", count: 10, first_date: "2026-10-19", last_date: "2026-10-30" }] }],
        });
      }),
      http.post("*/api/library/9/schedule", async ({ request }) => {
        scheduled = await request.json();
        return HttpResponse.json({
          courses: [{ id: 4, curriculum_id: 2, student_id: 3, student_name: "Ada", start_date: "2026-10-19", end_date: "2026-10-30", weekdays: [0, 1, 2, 3, 4], lessons_scheduled: 10 }],
          lessons_created: 10, calendar_url: "/#/assignments?from=planner&date=2026-10-19",
        }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/library?item=9");
    const panel = await screen.findByRole("dialog", { name: "Charlotte's Web" });
    await user.click(within(panel).getByRole("button", { name: "Schedule it" }));
    expect(within(panel).getByText(/without building a curriculum/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("radio", { name: "A number of pages a day" }));
    const pages = within(panel).getByLabelText("Pages a day");
    await user.clear(pages);
    await user.type(pages, "20");
    await user.click(within(panel).getByRole("button", { name: "Preview the dates" }));
    expect(await within(panel).findByText("20 pages of Charlotte's Web a day", { exact: false })).toBeInTheDocument();
    expect(previewed).toMatchObject({ student_ids: [3], pages_per_day: 20, weekdays: null });
    await user.click(within(panel).getByRole("button", { name: "Put it on the calendar" }));
    expect(await within(panel).findByText(/Done: 10 lessons on the calendar/)).toBeInTheDocument();
    expect(scheduled).toMatchObject({ pages_per_day: 20, weekdays: [0, 1, 2, 3, 4] });
    // The item refreshes with its new course; the "Done" message stays.
    expect(await within(panel).findByRole("region", { name: "On the calendar" })).toHaveTextContent("Ada: Oct 19 to Oct 30, 10 lessons");
    expect(within(panel).getByText(/Done: 10 lessons on the calendar/)).toBeInTheDocument();
  });

  it("puts a book on a child's reading list", async () => {
    let added: unknown = null;
    server.use(
      http.get("*/api/library", () => HttpResponse.json([summary(9, "reading_book", "Charlotte's Web")])),
      http.get("*/api/library/9", () => HttpResponse.json(item(9, "reading_book", "Charlotte's Web"))),
      http.get("*/api/students", () => HttpResponse.json([student(3, "Ada"), student(4, "Ben")])),
      http.get("*/api/reading-list", () =>
        HttpResponse.json(
          added
            ? [readingEntry(1, 3, "Charlotte's Web"), readingEntry(2, 4, "Charlotte's Web", { student_name: "Ben" })]
            : [readingEntry(1, 3, "Charlotte's Web")],
        ),
      ),
      http.post("*/api/reading-list", async ({ request }) => {
        added = await request.json();
        return HttpResponse.json(readingEntry(2, 4, "Charlotte's Web", { student_name: "Ben" }), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/library?item=9");
    const panel = await screen.findByRole("dialog", { name: "Charlotte's Web" });
    await user.click(within(panel).getByRole("tab", { name: "Reading list" }));
    const readers = await within(panel).findByRole("list", { name: "Who's reading it" });
    expect(await within(readers).findByRole("link", { name: "Open Ada's list" })).toHaveAttribute("href", "/next/reading?child=3");
    await user.click(within(readers).getByRole("button", { name: "Add to Ben's list" }));
    await waitFor(() => expect(added).toEqual({ student_id: 4, library_item_id: 9, status: "up_next" }));
    expect(await within(readers).findByRole("link", { name: "Open Ben's list" })).toBeInTheDocument();
  });
});
