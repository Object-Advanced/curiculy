import { HOUSEHOLD, expect, openSignIn, test } from "./support";

async function openStudentSignIn(page: import("@playwright/test").Page) {
  await openSignIn(page);
  await page.getByRole("button", { name: "I'm a student" }).click();
  await page.getByLabel("Household email").fill(HOUSEHOLD.email);
  await page.getByRole("button", { name: "Find my name" }).click();
  await page.getByRole("button", { name: HOUSEHOLD.kid.name }).click();
}

test("a kid signs in with a PIN and sees their own work", async ({ page }) => {
  await openStudentSignIn(page);
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill(HOUSEHOLD.kid.pin);
  await pinForm.getByRole("button", { name: "Log In" }).click();

  await expect(page.locator("#page-title")).toHaveText("My work");
  await expect(page.locator("#view")).toContainText("Fractions worksheet");
  await expect(page.locator(".nav-parent").first()).toBeHidden();
});

test("a wrong PIN is refused", async ({ page }) => {
  await openStudentSignIn(page);
  const pinForm = page.locator("#student-pin-form");
  await pinForm.getByLabel("PIN").fill("0000");
  await pinForm.getByRole("button", { name: "Log In" }).click();
  await expect(page.locator("#login-error")).toBeVisible();
  await expect(page.locator("#student-view")).toBeVisible();
});
