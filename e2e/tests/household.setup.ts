import {
  HOUSEHOLD,
  INVITE_KEY,
  apiAs,
  completeWizard,
  openSignIn,
  expect,
  isoDay,
  saveHouseholdState,
  test,
  type Student,
} from "./support";

// Registers the suite's one real household. Invite keys are single-use, so
// e2e/run.sh starts a fresh app (empty tmpfs databases) for every run.
test("register a household and give the first kid a PIN", async ({ page }) => {
  await openSignIn(page);
  await page.getByRole("button", { name: "Create Account" }).click();
  const form = page.locator("#register-form");
  await form.getByLabel("Email").fill(HOUSEHOLD.email);
  await form.getByLabel("Create Password").fill(HOUSEHOLD.password);
  await form.getByLabel("Verify Password").fill(HOUSEHOLD.password);
  await form.getByLabel("Invite Key").fill(INVITE_KEY);
  await form.getByRole("button", { name: "Create Account" }).click();

  await completeWizard(page, HOUSEHOLD.name, HOUSEHOLD.kid);

  await page.goto("/#/settings/students");
  await page.getByRole("button", { name: HOUSEHOLD.kid.name }).click();
  await page.locator("#student-pin-input").fill(HOUSEHOLD.kid.pin);
  await page.getByRole("button", { name: "Set PIN" }).click();
  await expect(page.locator("#flash")).toHaveText("Student PIN saved.");

  const [kid] = await apiAs<Student[]>(page, "GET", "/students");
  const lessons: [number, string, string, string?][] = [
    [-1, "Math facts practice", "assigned"],
    [0, "Read The Hobbit, chapter 2", "completed"],
    [0, "Fractions worksheet", "assigned", "Pages 14–15 in the blue workbook."],
    [1, "Science: states of matter", "assigned"],
  ];
  for (const [offset, title, status, notes] of lessons) {
    await apiAs(page, "POST", "/assignments", {
      student_id: kid.id,
      title,
      scheduled_date: isoDay(offset),
      status,
      notes,
    });
  }
  const { code } = await apiAs<{ code: string }>(page, "GET", "/auth/family-code");
  saveHouseholdState({ studentId: kid.id, familyCode: code });
});
