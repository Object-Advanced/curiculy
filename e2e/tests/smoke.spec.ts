import { join } from "node:path";

import {
  apiAs,
  browserToday,
  expect,
  openRoute,
  seedSchoolWeek,
  startDemo,
  test,
  type Student,
} from "./support";

test("the sign-in page offers every way in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  for (const name of ["Log In", "I'm a student", "Create Account", "Try Demo"]) {
    await expect(page.getByRole("button", { name })).toBeVisible();
  }
});

test("a demo household finishes onboarding and lands in the catalog", async ({ page }) => {
  await startDemo(page, "The Rivera family");
  await expect(page.locator("#household-label")).toHaveText("The Rivera family");
  await expect(page.locator("#health-pill")).toHaveText("API ok · DB ok");
});

test("Home draws its charts with the vendored Chart.js", async ({ page }) => {
  await startDemo(page);
  await seedSchoolWeek(page);
  await openRoute(page, "#/dashboard", "Home");
  // page.evaluate runs in the browser, so each callback reads window itself.
  type ChartWindow = { Chart?: { version: string; getChart: (id: string) => unknown } };
  expect(await page.evaluate(() => (window as unknown as ChartWindow).Chart?.version)).toBe("4.5.1");
  // The weekly trend draws whenever there are students (today's chart can
  // be legitimately empty).
  await expect(page.locator("#weeklyTrendChart")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        Boolean((window as unknown as ChartWindow).Chart?.getChart("weeklyTrendChart")),
      ),
    )
    .toBe(true);
});

test("the calendar renders day, week, and month", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/assignments", "Calendar");
  const label = page.locator("#calendar-range-label");
  for (const period of ["Day", "Week", "Month"]) {
    await page.getByRole("button", { name: period, exact: true }).click();
    await expect(label).not.toHaveText("Loading…");
    await expect(page.locator("#calendar-range-count")).toHaveText(/\d+ assignments?/);
  }
});

test("a parent adds an assignment and checks it off", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/assignments", "Calendar");
  await page.getByRole("button", { name: "+ Add assignment" }).click();
  const form = page.locator("#assignment-form");
  await form.getByLabel("Title").fill("Lesson 12 problem set");
  await form.getByRole("button", { name: "Save assignment" }).click();
  await expect(page.locator(".cal-event", { hasText: "Lesson 12 problem set" })).toBeVisible();

  await openRoute(page, "#/students", /'s day$/);
  const checklist = page.locator("#today-checklist");
  await checklist.getByLabel("Mark Lesson 12 problem set complete").check();
  await expect(checklist.locator(".checklist-progress")).toHaveText("1 of 1 complete");
});

test("a parent adds a book to the library by hand", async ({ page }) => {
  await startDemo(page);
  const form = page.locator('form[data-form="curriculum"]');
  await form.getByLabel("Title").fill("Saxon Math 3");
  await form.getByLabel("Subject").fill("Math");
  await form.getByRole("button", { name: "Save curriculum" }).click();
  await expect(page.locator(".list", { hasText: "Saxon Math 3" })).toBeVisible();
});

test("a CSV pacing guide imports and applies to the calendar", async ({ page }) => {
  await startDemo(page);
  await page.getByRole("tab", { name: "Structured Pacing Guides" }).click();
  await page
    .locator("#curriculum-csv-input")
    .setInputFiles(join(__dirname, "..", "fixtures", "Nature Study.csv"));
  const plan = page.locator(".list-row", { hasText: "Nature Study" });
  await expect(plan).toContainText("5 lessons");

  await plan.getByRole("button", { name: "Apply this lesson plan" }).click();
  await page.locator("#apply-plan-form").getByRole("button", { name: "Apply to calendar" }).click();
  await expect(page.locator("#flash")).toHaveText(/^5 lessons scheduled/);

  const [kid] = await apiAs<Student[]>(page, "GET", "/students");
  const calendar = await apiAs<{ assignments: { title: string }[] }>(
    page,
    "GET",
    `/students/${kid.id}/assignments?start_date=${browserToday()}`,
  );
  expect(calendar.assignments.map((item) => item.title)).toContain("Leaf rubbings");
});

test("the portfolio preview renders a report for the school year", async ({ page }) => {
  await startDemo(page);
  await seedSchoolWeek(page);
  await openRoute(page, "#/portfolios", "Portfolios");
  await expect(page.locator("#portfolio-canvas")).toContainText("Sam Rivera");
});
