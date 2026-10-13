import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { ContributionDetail, ContributionSummary } from "../api/parent";
import { server } from "../test/server";
import { renderAt, summary, serveParentBasics } from "../test/parent";

const row: ContributionSummary = {
  id: 21,
  kind: "item",
  item_kind: "reading_book",
  kind_label: "Book",
  title: "ADA'S READING LOG",
  isbn: null,
  status: "pending",
  needs_review: true,
  is_correction: false,
  has_cover: false,
  contributor_label: "Family 3f9a2c",
  review_flags: 1,
  notes: 1,
  created_at: "2026-10-12T10:00:00Z",
  updated_at: "2026-10-12T10:00:00Z",
};

const detail: ContributionDetail = {
  ...row,
  data: { kind: "reading_book", title: "ADA'S READING LOG", author: "Someone", total_pages: 120, chapters: [{ name: "One", start_page: 1 }], lessons: [] },
  flags: [
    { code: "first_time", group: "behavior", level: "note", where: "Contributor", message: "A first-time contributor." },
    { code: "child_name", group: "privacy", level: "review", where: "Title", message: "Contains the first name of a child in the contributing family." },
  ],
  compare_entry: null,
  changes: null,
  lookup: null,
  cover_url: null,
  contributor: { label: "Family 3f9a2c", accepted: 0, rejected: 0, total: 1 },
  review_note: null,
  reviewed_by: null,
  reviewed_at: null,
  result_entry_id: null,
  result_curriculum_id: null,
};

describe("Catalog review", () => {
  it("is for admins only", async () => {
    serveParentBasics();
    server.use(http.get("*/api/library", () => HttpResponse.json([summary(1, "reading_book", "Holes")])));
    const router = renderAt("/next/admin/catalog");
    await waitFor(() => expect(router.state.location.pathname).toBe("/next/library"));
    expect(await screen.findByRole("button", { name: /Holes/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Catalog review" })).not.toBeInTheDocument();
  });

  it("shows the flags, needs a reason to reject, and approves with a tidier title", async () => {
    serveParentBasics({ is_admin: true });
    let approved: unknown = null;
    let rejected = false;
    let current: ContributionDetail = detail;
    server.use(
      http.get("*/api/admin/community/contributions", () => HttpResponse.json([row])),
      http.get("*/api/admin/community/contributions/21", () => HttpResponse.json(current)),
      http.post("*/api/admin/community/contributions/21/reject", () => {
        rejected = true;
        return HttpResponse.json({ contribution: detail });
      }),
      http.post("*/api/admin/community/contributions/21/approve", async ({ request }) => {
        approved = await request.json();
        current = { ...detail, status: "approved", reviewed_by: "admin@example.com", result_entry_id: 9 };
        return HttpResponse.json({ contribution: current, entry_id: 9, left_out: [] });
      }),
    );
    const user = userEvent.setup();
    renderAt("/next/admin/catalog");

    const article = await screen.findByRole("article", { name: "ADA'S READING LOG" });
    const flags = within(article).getByRole("region", { name: "Flags" });
    const items = within(flags).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Privacy · Title: Contains the first name of a child");
    expect(items[1]).toHaveTextContent("Behavior · Contributor: A first-time contributor.");
    expect(screen.getByRole("link", { name: "Catalog review" })).toHaveAttribute("aria-current", "page");

    await user.click(within(article).getByRole("button", { name: "Reject" }));
    const send = within(article).getAllByRole("button", { name: "Reject" }).at(-1)!;
    expect(send).toBeDisabled();
    expect(rejected).toBe(false);

    await user.click(within(article).getByRole("button", { name: "Approve" }));
    const title = within(article).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "A Reading Log");
    await user.click(within(article).getAllByRole("button", { name: "Approve" }).at(-1)!);
    await waitFor(() => expect(approved).toEqual({ edits: { title: "A Reading Log" }, include_cover: true, note: null }));
    expect(await within(article).findByText(/Approved by admin@example.com/)).toHaveTextContent("Catalog entry #9.");
  });
});
