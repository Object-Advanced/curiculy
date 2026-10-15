import type { Page } from "@playwright/test";

import { FROZEN_NOW, HOUSEHOLD, expect, loadHouseholdState, openSignIn, test } from "./support";

async function openStudentSignIn(page: Page) {
  await openSignIn(page);
  await page.getByRole("button", { name: "I'm a student" }).click();
  await page.getByLabel("Family code").fill(loadHouseholdState().familyCode.toLowerCase());
  await page.getByRole("button", { name: "Find my name" }).click();
}

const firstName = HOUSEHOLD.kid.name.split(" ")[0];

test("a kid signs in with the family code and a PIN", async ({ page }) => {
  // A kid's screens must not lean on parent-only routes.
  const refused: string[] = [];
  page.on("response", (response) => {
    const path = new URL(response.url()).pathname;
    if (response.status() === 403 && path.startsWith("/api/")) refused.push(path);
  });
  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await expect(page.locator("#page-title")).toHaveText("My work");
  await expect(page.locator("#view")).toContainText("Fractions worksheet");
  await expect(page.locator(".nav-parent").first()).toBeHidden();
  await expect(page.locator("html")).toHaveAttribute("data-persona", "kid");
  await page.waitForLoadState("networkidle");
  expect(refused).toEqual([]);
});

test("a kid's list points to the family's own materials, with the puzzle as an extra", async ({ page }) => {
  // The seeded lessons are dated around the suite's frozen "today".
  await page.clock.setFixedTime(FROZEN_NOW);
  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await expect(page.getByRole("heading", { name: `Hi ${firstName}!` })).toBeVisible();
  await expect(page.locator(".kid-hello-progress")).toHaveText("1 of 2 done today");
  await expect(page.getByRole("img", { name: "1 of 2 stars earned today" })).toBeVisible();
  await expect(page.locator(".kid-note")).toHaveText("Note: Pages 14–15 in the blue workbook.");
  await expect(page.getByRole("heading", { name: "Just for fun" })).toBeVisible();
});

test("the sign-in screen shows first names only", async ({ page }) => {
  await openStudentSignIn(page);
  const chips = page.locator("#student-name-chips");
  await expect(chips.getByRole("button")).toHaveText([firstName, "Ben"]);
  await expect(chips).not.toContainText("Okafor");
});

test("a remembered device goes straight to the names", async ({ page }) => {
  await openStudentSignIn(page);
  await expect(page.getByRole("button", { name: firstName, exact: true })).toBeVisible();

  await openSignIn(page);
  await page.getByRole("button", { name: "I'm a student" }).click();
  await expect(page.getByRole("button", { name: firstName, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Use a different family code" }).click();
  await expect(page.getByLabel("Family code")).toBeVisible();
});

test("a wrong PIN is refused", async ({ page }) => {
  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill("0000");
  await pinForm.getByRole("button", { name: "Log In" }).click();
  await expect(page.locator("#login-error")).toBeVisible();
  await expect(page.locator("#student-view")).toBeVisible();
});

async function parentToken(page: Page): Promise<string> {
  const response = await page.request.post("/api/auth/token", {
    form: { username: HOUSEHOLD.email, password: HOUSEHOLD.password },
  });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { access_token: string }).access_token;
}

test("stuck? gives one nudge, then sends the kid to a grown-up", async ({ page }) => {
  await page.clock.setFixedTime(FROZEN_NOW);
  // Start from a fresh nudge even on a retry: the parent allows another one.
  const parent = await parentToken(page);
  const { studentId } = loadHouseholdState();
  const listing = await page.request.get(
    `/api/students/${studentId}/assignments?start_date=2026-10-01&end_date=2026-10-31`,
    { headers: { Authorization: `Bearer ${parent}` } },
  );
  const { assignments } = (await listing.json()) as { assignments: { id: number; title: string }[] };
  const lesson = assignments.find((row) => row.title === "Math facts practice");
  expect(lesson).toBeTruthy();
  await page.request.post(`/api/homework-help/assignments/${lesson!.id}/unlock`, {
    headers: { Authorization: `Bearer ${parent}` },
  });

  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();
  await page.getByRole("button", { name: /^Math facts practice/ }).click();

  await expect(page.getByRole("heading", { name: "Stuck?" })).toBeVisible();
  // Nothing to type: no AI reads it. The nudge comes from the lesson itself;
  // this one has no book or note, so it's the general nudge.
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await page.getByRole("button", { name: "Give me a nudge" }).click();
  await expect(page.getByRole("heading", { name: "Here’s a nudge" })).toBeVisible();
  await expect(page.locator(".stuck-nudge")).toContainText("Read the directions one more time");
  await expect(page.getByRole("button", { name: "Give me a nudge" })).toHaveCount(0);

  await page.getByRole("button", { name: "Still stuck? Get a grown-up" }).click();
  await expect(page.getByRole("heading", { name: "Time to find a grown-up" })).toBeVisible();

  const inbox = await page.request.get("/api/notifications", {
    headers: { Authorization: `Bearer ${parent}` },
  });
  const { notifications } = (await inbox.json()) as { notifications: { title: string }[] };
  expect(notifications.map((row) => row.title)).toContain(`${firstName} needs you`);
});

test("My trail: a kid follows today's stops to camp", async ({ page }) => {
  await page.clock.setFixedTime(FROZEN_NOW);
  // Ben's day is the one tests change. Start from a known day even on a retry.
  const parent = await parentToken(page);
  const headers = { Authorization: `Bearer ${parent}` };
  const { secondStudentId } = loadHouseholdState();
  const day = await page.request.get(
    `/api/students/${secondStudentId}/assignments?start_date=2026-10-14&end_date=2026-10-14`,
    { headers },
  );
  const { assignments } = (await day.json()) as { assignments: { id: number; title: string }[] };
  const mapSkills = assignments.find((row) => row.title === "Map skills");
  expect(mapSkills).toBeTruthy();
  await page.request.patch(`/api/assignments/${mapSkills!.id}/status`, { headers, data: { status: "assigned" } });

  await openStudentSignIn(page);
  await page.getByRole("button", { name: "Ben", exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.secondKid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await page.getByRole("link", { name: "My trail" }).click();
  await expect(page).toHaveURL(/\/next\/trail$/);
  await expect(page.getByRole("heading", { name: "Hi Ben!" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Trail map: 1 of 2 stops done." })).toBeVisible();
  const stops = page.getByRole("list", { name: "Today's stops" }).getByRole("listitem");
  await expect(stops).toHaveCount(2);

  await page.getByRole("button", { name: "I did it: Map skills" }).click();
  await expect(page.getByRole("heading", { name: "You reached camp!" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Trail map: 2 of 2 stops done, camp reached." })).toBeVisible();

  // Undo, and wait for the server before leaving so the next run starts clean.
  const saved = page.waitForResponse((r) => r.url().includes("/status") && r.request().method() === "PATCH");
  await page.getByRole("button", { name: "Not done yet: Map skills" }).click();
  expect((await saved).ok()).toBeTruthy();
  await expect(page.getByText("1 stop to camp")).toBeVisible();
  await page.getByRole("link", { name: "My day" }).click();
  await expect(page.locator("#page-title")).toHaveText("My work");
});

test("Sticker journal: this week's stickers and the month's collection", async ({ page }) => {
  await page.clock.setFixedTime(FROZEN_NOW);
  // Read-only: Ada's week never changes during the suite.

  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await page.getByRole("link", { name: "Sticker journal" }).click();
  await expect(page).toHaveURL(/\/next\/journal$/);
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await expect(page.getByText("Oct 12 – 16")).toBeVisible();

  const days = page.getByRole("list", { name: "Stickers by day" }).getByRole("listitem");
  const today = days.filter({ hasText: "Today" });
  await today.getByRole("button", { name: "Reading sticker: Read The Hobbit, chapter 2" }).click();
  await expect(page.getByText("Your Reading sticker is from “Read The Hobbit, chapter 2”, on Wednesday.")).toBeVisible();
  await expect(today.getByRole("link", { name: "1 stop to go" })).toBeVisible();

  const collection = page.getByRole("region", { name: "October collection" });
  await expect(collection.getByText("0 of 8")).toBeVisible();
  await expect(collection.getByText("Today’s prize")).toBeVisible();

  await page.getByRole("navigation", { name: "Pages" }).getByRole("link", { name: "My trail" }).click();
  await expect(page.getByRole("img", { name: "Trail map: 1 of 2 stops done." })).toBeVisible();
});
