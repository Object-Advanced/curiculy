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
  await openStudentSignIn(page);
  await page.getByRole("button", { name: firstName, exact: true }).click();
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await expect(page.locator("#page-title")).toHaveText("My work");
  await expect(page.locator("#view")).toContainText("Fractions worksheet");
  await expect(page.locator(".nav-parent").first()).toBeHidden();
  await expect(page.locator("html")).toHaveAttribute("data-persona", "kid");
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
  await expect(page.locator("#student-name-chips")).toHaveText(firstName);
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
