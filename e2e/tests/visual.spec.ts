import type { Page } from "@playwright/test";

import {
  FROZEN_NOW,
  HOUSEHOLD,
  expect,
  loadHouseholdState,
  openRoute,
  openSignIn,
  seedSchoolWeek,
  settle,
  startDemo,
  test,
} from "./support";

/**
 * Screenshots of the main screens, one folder per project (width x theme)
 * under tests/__screenshots__. The browser clock is frozen so greetings,
 * month moods, countdowns, and calendars are stable. Elements computed from
 * the server's real date (the dashboard's stats) are masked.
 *
 * Regenerate after an intended visual change: e2e/run.sh --update-snapshots
 */

function serverDateDriven(page: Page) {
  return [page.locator(".kpi-dashboard"), page.locator("#home-lessons-today"), page.locator("#home-lessons-week")];
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(FROZEN_NOW);
});

test("sign-in screen", async ({ page }) => {
  await openSignIn(page);
  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  await expect(page).toHaveScreenshot("sign-in.png");
});

test("parent screens", async ({ page }) => {
  await startDemo(page);
  await seedSchoolWeek(page);

  const screens: [string, string, string | RegExp][] = [
    ["home", "#/dashboard", "Home"],
    ["calendar-week", "#/assignments", "Calendar"],
    ["kids", "#/students", /'s day$/],
    ["catalog", "#/curricula", "Curriculum catalog"],
    ["settings", "#/settings", "Settings"],
  ];
  for (const [name, hash, title] of screens) {
    await openRoute(page, hash, title);
    await settle(page);
    await expect.soft(page).toHaveScreenshot(`${name}.png`, { mask: serverDateDriven(page) });
  }

  await openRoute(page, "#/assignments", "Calendar");
  await page.getByRole("button", { name: "Month", exact: true }).click();
  await expect(page.locator("#calendar-range-label")).toHaveText("October 2026");
  await settle(page);
  await expect.soft(page).toHaveScreenshot("calendar-month.png");
});

test("kid's own work list", async ({ page }) => {
  const { studentId } = loadHouseholdState();
  const response = await page.request.post("/api/auth/student-token", {
    data: { email: HOUSEHOLD.email, student_id: studentId, pin: HOUSEHOLD.kid.pin },
  });
  expect(response.ok()).toBeTruthy();
  const { access_token: token } = (await response.json()) as { access_token: string };

  // Store the token before the app boots; a hash change alone would not
  // re-run sign-in.
  await page.addInitScript((value) => window.localStorage.setItem("auth_token", value), token);
  await openRoute(page, "#/my-work", "My work");
  await settle(page);
  await expect(page).toHaveScreenshot("kid-my-work.png");
});
