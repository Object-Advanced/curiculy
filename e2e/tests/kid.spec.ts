import type { Page } from "@playwright/test";

import { HOUSEHOLD, expect, loadHouseholdState, openSignIn, test } from "./support";

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
