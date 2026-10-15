import { join } from "node:path";

import {
  FROZEN_NOW,
  apiAs,
  browserToday,
  expect,
  openRoute,
  seedSchoolWeek,
  seedLibrary,
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

test("a demo household finishes onboarding and lands in the Library", async ({ page }) => {
  await startDemo(page, "The Rivera family");
  await expect(page.getByText("Start by adding what you teach from.")).toBeVisible();
  await openRoute(page, "#/dashboard", "Home");
  await expect(page.locator("#household-label")).toHaveText("The Rivera family");
  await expect(page.locator("#health-pill")).toHaveText("API ok · DB ok");
});

test("Home greets the household by family name", async ({ page }) => {
  // 15:00 UTC; the browser in this suite runs on UTC, so it is afternoon.
  await page.clock.setFixedTime(FROZEN_NOW);
  await startDemo(page);
  await openRoute(page, "#/dashboard", "Home");
  // The demo household is named "The Rivera family".
  await expect(page.locator(".home-hero h2")).toHaveText("Good afternoon, Rivera Family");
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
    await expect(page.locator("#calendar-range-count")).toHaveText(/\d+ lessons?/);
  }
});

test("a parent adds a lesson and checks it off", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/assignments", "Calendar");
  await page.getByRole("button", { name: "+ Add lesson" }).click();
  const form = page.locator("#assignment-form");
  await form.getByLabel("Title").fill("Lesson 12 problem set");
  await form.getByRole("button", { name: "Save lesson" }).click();
  await expect(page.locator(".cal-event", { hasText: "Lesson 12 problem set" })).toBeVisible();

  await openRoute(page, "#/students", /'s day$/);
  // The parent's view of a child's day is calm: no kid-voice hero or puzzle.
  await expect(page.getByRole("heading", { name: "Today", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Ask / })).toBeVisible();
  await expect(page.locator("#kid-spark")).toHaveCount(0);
  const checklist = page.locator("#today-checklist");
  await checklist.getByLabel("Mark Lesson 12 problem set complete").check();
  await expect(checklist.locator(".checklist-progress")).toHaveText("1 of 1 complete");
});

test("the older catalog still saves a book", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/curricula", "Curriculum catalog");
  const form = page.locator('form[data-form="curriculum"]');
  await form.getByLabel("Title").fill("Saxon Math 3");
  await form.getByLabel("Subject").fill("Math");
  await form.getByRole("button", { name: "Save curriculum" }).click();
  await expect(page.locator(".list", { hasText: "Saxon Math 3" })).toBeVisible();
});

test("a CSV pacing guide imports and applies to the calendar", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/curricula", "Curriculum catalog");
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

test("a parent opens a child's trail from the Kids page", async ({ page }) => {
  await page.clock.setFixedTime(FROZEN_NOW);
  await startDemo(page);
  await seedSchoolWeek(page);
  await openRoute(page, "#/students", /'s day$/);
  await page.getByRole("link", { name: "See Sam’s trail" }).click();
  await expect(page.getByRole("heading", { name: "Hi Sam!" })).toBeVisible();
  await expect(page.getByText("Parent preview. Checking off here counts for Sam.")).toBeVisible();
  await expect(page.getByRole("list", { name: "Today's stops" }).getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Maya" }).click();
  await expect(page.getByRole("heading", { name: "Hi Maya!" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Kids" })).toBeVisible();

  // The journal keeps the chosen child.
  await page.getByRole("navigation", { name: "Pages" }).getByRole("link", { name: "Sticker journal" }).click();
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hi Maya!" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Math sticker: Count by twos" })).toBeVisible();
});

test("a parent adds a textbook, plans it, and puts it on the calendar", async ({ page }) => {
  await startDemo(page);

  // The Library: add a textbook by hand, one step at a time.
  await page.getByRole("button", { name: "Add to library" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Add it yourself" }).click();
  await dialog.getByLabel("Title").fill("Saxon Math 5/4");
  await dialog.getByRole("button", { name: "Next: what is this?" }).click();
  await dialog.getByText("Textbook", { exact: true }).click();
  await dialog.getByRole("button", { name: "Next: the details" }).click();
  await dialog.getByLabel("Publisher").fill("Saxon");
  await dialog.getByLabel("Edition or year").fill("3rd");
  await dialog.getByLabel("Subject").selectOption("math");
  await dialog.getByLabel("Grade").selectOption("4");
  await dialog.getByLabel("Total pages").fill("600");
  await dialog.getByRole("button", { name: "Save, then add lessons" }).click();
  await dialog.getByRole("button", { name: "Paste a lesson list" }).click();
  await dialog.getByLabel("Paste a lesson list").fill("1 Adding 1-4\n2 Subtracting 5-8\nTest 1, 9-10");
  await dialog.getByRole("button", { name: "Add these" }).click();
  await expect(dialog.getByText("3 lessons, 3 with pages.")).toBeVisible();
  await dialog.getByRole("button", { name: "Save and finish" }).click();
  await expect(dialog.getByText("Ready to schedule.")).toBeVisible();

  // The Curriculum planner: build it around the textbook, then schedule it.
  await dialog.getByRole("button", { name: "Plan a curriculum with it" }).click();
  await page.getByRole("button", { name: "Start with Saxon Math 5/4" }).click();
  await expect(page.getByRole("heading", { name: "Saxon Math 5/4", level: 1 })).toBeVisible();
  await expect(page.getByText("Everything is ready. Put it on the calendar below.")).toBeVisible();
  await page.getByRole("button", { name: "Preview the dates" }).click();
  await expect(page.getByText(/Sam Rivera: 3 lessons/)).toBeVisible();
  await page.getByRole("button", { name: "Put it on the calendar" }).click();
  await expect(page.getByText(/Done: 3 lessons on the calendar/)).toBeVisible();

  // The calendar opens on those lessons, with a short tour.
  await page.getByRole("link", { name: "Go to the calendar" }).click();
  await expect(page.locator("#page-title")).toHaveText("Calendar");
  const tour = page.getByRole("region", { name: "Your new lessons are on the calendar" });
  await expect(tour).toBeVisible();
  await expect(page.locator(".cal-event", { hasText: "Saxon Math 5/4 · Lesson 1: Adding" })).toBeVisible();
  await tour.getByRole("button", { name: "Got it" }).click();
  await expect(tour).toBeHidden();
  expect(page.url()).toMatch(/#\/assignments$/);
});

test("a family's library shows every kind on one shelf", async ({ page }) => {
  await startDemo(page);
  await seedLibrary(page);
  await page.reload();
  const shelf = page.getByRole("list", { name: "Your shelf" });
  await expect(shelf.getByRole("listitem")).toHaveCount(4);
  await page.getByRole("button", { name: /^Workbooks/ }).click();
  await expect(shelf.getByRole("listitem")).toHaveCount(1);
  await shelf.getByRole("button", { name: /BJU Reading 4 Worktext/ }).click();
  await expect(page.getByRole("dialog", { name: "BJU Reading 4 Worktext" })).toBeVisible();
});

test("a parent schedules one book on its own, without a curriculum", async ({ page }) => {
  await startDemo(page);
  const { novel } = await seedLibrary(page);
  await page.goto(`/next/library?item=${novel}`);
  const panel = page.getByRole("dialog", { name: "Charlotte's Web" });
  await panel.getByRole("button", { name: "Schedule it" }).click();
  await panel.getByRole("radio", { name: "A number of pages a day" }).check();
  await panel.getByLabel("Pages a day", { exact: true }).fill("46");
  await panel.getByRole("button", { name: "Preview the dates" }).click();
  await expect(panel.getByText("Pace: 46 pages of Charlotte's Web a day.")).toBeVisible();
  await expect(panel.getByText(/Sam Rivera: 4 lessons/)).toBeVisible();
  await panel.getByRole("button", { name: "Put it on the calendar" }).click();
  await expect(panel.getByText(/Done: 4 lessons on the calendar/)).toBeVisible();

  // It isn't a curriculum to the family: the planner stays as it was.
  const curricula = await apiAs<unknown[]>(page, "GET", "/planner/curricula");
  expect(curricula).toEqual([]);
  await panel.getByRole("link", { name: "Go to the calendar" }).click();
  await expect(page.locator(".cal-event", { hasText: "Read Charlotte's Web, pp. 1–46" })).toBeVisible();

  // Its reading put it on Sam's reading list, where it moves along as it's checked off.
  await page.goto("/next/reading");
  const upNext = page.getByRole("region", { name: "Up next" });
  await expect(upNext.getByRole("heading", { name: "Charlotte's Web" })).toBeVisible();
  await expect(upNext.getByText("On the calendar: 0 of 4 readings done")).toBeVisible();
});

test("a parent tracks a book on a reading list", async ({ page }) => {
  await startDemo(page);
  await seedLibrary(page);
  await page.goto("/next/reading");
  await expect(page.getByRole("heading", { name: "Nothing on Sam Rivera's list yet" })).toBeVisible();
  await page.getByRole("button", { name: "Add a book" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Add a book to Sam Rivera's list" });
  await dialog.getByRole("combobox", { name: "Book", exact: true }).selectOption({ label: "Charlotte's Web (E. B. White)" });
  await dialog.getByRole("button", { name: "Reading now" }).click();
  await dialog.getByRole("button", { name: "Add it" }).click();
  const reading = page.getByRole("region", { name: "Reading now" });
  await expect(reading.getByRole("heading", { name: "Charlotte's Web" })).toBeVisible();
  await reading.getByRole("button", { name: "Finished it" }).click();
  await expect(page.getByRole("region", { name: "Finished" }).getByRole("heading", { name: "Charlotte's Web" })).toBeVisible();
});

test("a parent logs an activity with a photo", async ({ page }) => {
  await startDemo(page);
  await page.goto("/next/activities");
  await expect(page.getByRole("heading", { name: "Nothing logged yet" })).toBeVisible();
  await page.getByRole("button", { name: "Log an activity" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Log an activity" });
  await dialog.getByLabel(/What did you do/).fill("5K race");
  await dialog.getByRole("button", { name: "Physical education" }).click();
  await dialog.getByLabel("Minutes", { exact: true }).fill("40");
  // A 1×1 photo: stored as a work sample like any other.
  await dialog.getByLabel("Photos").setInputFiles({
    name: "finish-line.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
      "base64",
    ),
  });
  await dialog.getByRole("button", { name: "Log it" }).click();
  await expect(dialog).toBeHidden();
  const card = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "5K race" }) });
  await expect(card.getByText("Sam Rivera · 40 min")).toBeVisible();
  await expect(card.getByText("Physical education")).toBeVisible();
  await expect(card.getByRole("link", { name: "Open the photo from 5K race" })).toBeVisible();
});

test("a parent counts the year in hours and sets their own terms", async ({ page }) => {
  await startDemo(page);
  await openRoute(page, "#/settings", "Settings");
  const counting = page.getByRole("group", { name: "Count the school year in" });
  await counting.getByRole("button", { name: "Hours" }).click();
  await expect(counting.getByRole("button", { name: "Hours" })).toHaveAttribute("aria-pressed", "true");
  const household = await apiAs<{ count_by: string }>(page, "GET", "/household");
  expect(household.count_by).toBe("hours");

  await page.getByRole("tab", { name: "School Years" }).click();
  await expect(page.getByText("4 terms: even quarters, which follow the year's dates")).toBeVisible();
  await page.getByRole("button", { name: "Change terms" }).click();
  for (const index of [3, 2]) {
    await page.getByRole("button", { name: `Remove Quarter ${index + 1}` }).click();
  }
  const names = page.locator('form[data-form="year-terms"]').getByLabel("Name", { exact: true });
  await names.first().fill("Fall");
  await names.nth(1).fill("Spring");
  await page.getByRole("button", { name: "Save terms" }).click();
  await expect(page.getByText("2 terms, set by you")).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to even quarters" })).toBeVisible();
});
