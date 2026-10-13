import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
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
  seedSchoolWeek,
  settle,
  startDemo,
  test,
} from "./support";

/**
 * Accessibility ratchet. Counts serious + critical axe violations per screen
 * and fails if any screen gets worse than e2e/a11y-baseline.json. Lower the
 * numbers as screens are fixed; run with UPDATE_A11Y_BASELINE=1 to rewrite it.
 */
const BASELINE_FILE = join(__dirname, "..", "a11y-baseline.json");
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

type Counts = { critical: number; serious: number; moderate: number; minor: number };

async function scan(page: Page, screen: string): Promise<{ counts: Counts; rules: string[] }> {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const counts: Counts = { critical: 0, serious: 0, moderate: 0, minor: 0 };
  for (const violation of results.violations) {
    const impact = (violation.impact ?? "minor") as keyof Counts;
    counts[impact] += violation.nodes.length;
  }
  await test.info().attach(`axe-${screen}.json`, {
    body: JSON.stringify(results.violations, null, 2),
    contentType: "application/json",
  });
  return {
    counts,
    rules: results.violations.map((v) => `${v.impact ?? "minor"}: ${v.id} (${v.nodes.length})`),
  };
}

test("serious and critical accessibility issues do not grow", async ({ page }) => {
  const report: Record<string, Counts & { rules: string[] }> = {};

  // Frozen like the visual tests, so what is on screen (and so the counts)
  // does not drift with the real date.
  await page.clock.setFixedTime(FROZEN_NOW);
  await openSignIn(page);
  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  const login = await scan(page, "sign-in");
  report["sign-in"] = { ...login.counts, rules: login.rules };

  await startDemo(page);
  await seedSchoolWeek(page);
  const screens: [string, string, string | RegExp][] = [
    ["home", "#/dashboard", "Home"],
    ["calendar", "#/assignments", "Calendar"],
    ["kids", "#/students", /'s day$/],
    ["portfolios", "#/portfolios", "Portfolios"],
    ["settings", "#/settings", "Settings"],
  ];
  for (const [screen, hash, title] of screens) {
    await openRoute(page, hash, title);
    await settle(page);
    const result = await scan(page, screen);
    report[screen] = { ...result.counts, rules: result.rules };
  }

  // The React parent screens: the Library, its adding walkthrough, and the planner.
  const { textbook } = await seedLibrary(page);
  const curriculum = await apiAs<{ id: number }>(page, "POST", "/planner/curricula", { textbook_id: textbook });
  const parentScreens: [string, string, string][] = [
    ["library", "/next/library", "Library"],
    ["planner", "/next/planner", "Curriculum planner"],
    ["curriculum", `/next/planner/${curriculum.id}`, "BJU Reading 4"],
  ];
  for (const [screen, path, heading] of parentScreens) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    const result = await scan(page, screen);
    report[screen] = { ...result.counts, rules: result.rules };
  }
  await page.goto("/next/library?add=1");
  await expect(page.getByRole("dialog", { name: "Add to your library" })).toBeVisible();
  const adding = await scan(page, "library-add");
  report["library-add"] = { ...adding.counts, rules: adding.rules };

  // The child's own screen, signed in with the household's kid PIN.
  const { studentId, familyCode } = loadHouseholdState();
  const response = await page.request.post("/api/auth/student-token", {
    data: { family_code: familyCode, student_id: studentId, pin: HOUSEHOLD.kid.pin },
  });
  expect(response.ok()).toBeTruthy();
  const { access_token: kidToken } = (await response.json()) as { access_token: string };
  await page.evaluate((value) => window.localStorage.setItem("auth_token", value), kidToken);
  await page.reload();
  await openRoute(page, "#/my-work", "My work");
  await settle(page);
  const kid = await scan(page, "my-work");
  report["my-work"] = { ...kid.counts, rules: kid.rules };

  await page.goto("/next/trail");
  await expect(page.getByRole("img", { name: /^Trail map/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const trail = await scan(page, "my-trail");
  report["my-trail"] = { ...trail.counts, rules: trail.rules };

  await page.goto("/next/journal");
  await expect(page.getByRole("heading", { name: "This week" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const journal = await scan(page, "sticker-journal");
  report["sticker-journal"] = { ...journal.counts, rules: journal.rules };

  if (process.env.UPDATE_A11Y_BASELINE === "1" || !existsSync(BASELINE_FILE)) {
    const baseline = Object.fromEntries(
      Object.entries(report).map(([screen, counts]) => [screen, counts.serious + counts.critical]),
    );
    writeFileSync(BASELINE_FILE, `${JSON.stringify(baseline, null, 2)}\n`);
    console.log("Wrote a11y baseline:", JSON.stringify(report, null, 2));
    return;
  }

  const baseline = JSON.parse(readFileSync(BASELINE_FILE, "utf8")) as Record<string, number>;
  for (const [screen, counts] of Object.entries(report)) {
    expect
      .soft(counts.serious + counts.critical, `${screen}: ${counts.rules.join("; ")}`)
      .toBeLessThanOrEqual(baseline[screen] ?? 0);
  }
});
