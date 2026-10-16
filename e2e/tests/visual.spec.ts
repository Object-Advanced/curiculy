import type { Page } from "@playwright/test";

import {
  FROZEN_NOW,
  HOUSEHOLD,
  apiAs,
  expect,
  loadHouseholdState,
  openRoute,
  openSignIn,
  seedLibrary,
  seedRecords,
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
    ["settings", "#/settings", "Settings"],
  ];
  for (const [name, hash, title] of screens) {
    await openRoute(page, hash, title);
    await settle(page);
    // "School today?" follows the server's real date (shown on school days,
    // hidden on others), so it stays out of the picture; the smoke tests cover it.
    await page.addStyleTag({ content: "#home-school-today { display: none !important; }" });
    await expect.soft(page).toHaveScreenshot(`${name}.png`, { mask: serverDateDriven(page) });
  }

  await openRoute(page, "#/assignments", "Calendar");
  await page.getByRole("button", { name: "Month", exact: true }).click();
  await expect(page.locator("#calendar-range-label")).toHaveText("October 2026");
  await settle(page);
  await expect.soft(page).toHaveScreenshot("calendar-month.png");
});

test("library and planner", async ({ page }) => {
  await startDemo(page);
  const { textbook, workbook, novel } = await seedLibrary(page);
  const curriculum = await apiAs<{ id: number }>(page, "POST", "/planner/curricula", { textbook_id: textbook });
  await apiAs(page, "POST", `/planner/curricula/${curriculum.id}/items`, { library_item_id: workbook, role: "workbook" });
  await apiAs(page, "POST", `/planner/curricula/${curriculum.id}/items`, { library_item_id: novel, role: "reading" });

  await page.goto("/next/library");
  await expect(page.getByRole("list", { name: "Your shelf" }).getByRole("listitem")).toHaveCount(4);
  await page.waitForLoadState("networkidle");
  await expect.soft(page).toHaveScreenshot("library.png");

  await page.goto("/next/library?add=1");
  await expect(page.getByRole("dialog", { name: "Add to your library" })).toBeVisible();
  await expect.soft(page).toHaveScreenshot("library-add.png");

  await page.goto(`/next/planner/${curriculum.id}`);
  await expect(page.getByText("Everything is ready. Put it on the calendar below.")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect.soft(page).toHaveScreenshot("curriculum.png", { fullPage: true });
});

test("reading lists and activities", async ({ page }) => {
  await startDemo(page);
  const { novel } = await seedLibrary(page);
  await seedRecords(page, novel);

  await page.goto("/next/reading");
  await expect(page.getByRole("heading", { name: "The Hobbit" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect.soft(page).toHaveScreenshot("reading.png", { fullPage: true });

  await page.goto("/next/activities");
  await expect(page.getByRole("heading", { name: "5K race" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect.soft(page).toHaveScreenshot("activities.png", { fullPage: true });
});

test("kid's own work list", async ({ page }) => {
  const { studentId, familyCode } = loadHouseholdState();
  const response = await page.request.post("/api/auth/student-token", {
    data: { family_code: familyCode, student_id: studentId, pin: HOUSEHOLD.kid.pin },
  });
  expect(response.ok()).toBeTruthy();
  const { access_token: token } = (await response.json()) as { access_token: string };

  // Store the token before the app boots; a hash change alone would not
  // re-run sign-in.
  await page.addInitScript((value) => window.localStorage.setItem("auth_token", value), token);
  await openRoute(page, "#/my-work", "My work");
  await settle(page);
  await expect(page).toHaveScreenshot("kid-my-work.png");

  await page.goto("/next/trail");
  await expect(page.getByRole("img", { name: /^Trail map/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveScreenshot("kid-my-trail.png", { fullPage: true });

  await page.goto("/next/journal");
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(page).toHaveScreenshot("kid-sticker-journal.png", { fullPage: true });
});
