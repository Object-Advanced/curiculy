import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { expect, test as base, type Page } from "@playwright/test";

export type Theme = "light" | "dark";

/** Wednesday 14 October 2026, mid-afternoon: an ordinary school day. */
export const FROZEN_NOW = new Date("2026-10-14T15:00:00Z");
export const FROZEN_TODAY = "2026-10-14";

export const INVITE_KEY = process.env.E2E_INVITE_KEY ?? "e2e-invite-key";

export interface Kid {
  name: string;
  grade: string;
}

export const FIRST_KID: Kid = { name: "Sam Rivera", grade: "3" };

/** The one real (non-demo) household, registered by household.setup.ts. */
export const HOUSEHOLD = {
  email: "parent@e2e.example.com",
  password: "correct-horse-battery",
  name: "The Okafor family",
  kid: { name: "Ada Okafor", grade: "4", pin: "2468" },
};

export interface HouseholdState {
  studentId: number;
  familyCode: string;
}

const STATE_FILE = join(__dirname, "..", ".state", "household.json");

export function saveHouseholdState(state: HouseholdState): void {
  mkdirSync(dirname(STATE_FILE), { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

export function loadHouseholdState(): HouseholdState {
  return JSON.parse(readFileSync(STATE_FILE, "utf8")) as HouseholdState;
}

/** Applies the project's theme before the app's inline theme script runs. */
export const test = base.extend<{ theme: Theme }>({
  theme: ["light", { option: true }],
  page: async ({ page, theme }, use) => {
    await page.addInitScript((value) => {
      try {
        window.localStorage.setItem("theme", value);
      } catch {
        // about:blank has no storage; the next navigation sets it.
      }
    }, theme);
    await use(page);
  },
});

export { expect };

/** ``YYYY-MM-DD`` that many days from ``from`` (the frozen school day by default). */
export function isoDay(offsetDays: number, from: string = FROZEN_TODAY): string {
  const date = new Date(`${from}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

/** Today's date as the browser sees it (UTC in this suite). */
export function browserToday(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Walks the first-run wizard: welcome, household name, school year, first kid. */
export async function completeWizard(page: Page, household: string, kid: Kid = FIRST_KID) {
  const step = (n: number) => page.locator(`[data-wizard-step="${n}"]`);
  await expect(step(1)).toBeVisible();
  await step(1).getByRole("button", { name: "Next" }).click();
  await step(2).getByLabel("Household name").fill(household);
  await step(2).getByRole("button", { name: "Next" }).click();
  await expect(step(3)).toBeVisible();
  await step(3).getByRole("button", { name: "Next" }).click();
  await expect(step(4)).toBeVisible();
  await step(4).getByLabel("Name").fill(kid.name);
  await step(4).getByLabel("Grade").fill(kid.grade);
  await step(4).getByRole("button", { name: "Finish" }).click();
  await expect(page.locator("#onboarding-wizard")).toBeHidden();
}

/**
 * Opens the sign-in page once boot has finished. Boot checks /api/health and
 * then resets the sign-in view, so a click that lands earlier can be undone.
 * (Known app race; it goes away when boot stops resetting the view.)
 */
export async function openSignIn(page: Page) {
  await page.goto("/");
  await expect(page.locator("#health-pill")).toHaveText(/^API /);
}

/** Starts a fresh demo household and finishes onboarding. */
export async function startDemo(page: Page, household = "The Rivera family", kid: Kid = FIRST_KID) {
  await openSignIn(page);
  await page.getByRole("button", { name: "Try Demo" }).click();
  await completeWizard(page, household, kid);
  await expect(page.locator("#page-title")).toHaveText("Curriculum catalog");
}

/** Calls the API with the signed-in user's token. Throws on any non-2xx. */
export async function apiAs<T = unknown>(
  page: Page,
  method: string,
  path: string,
  data?: unknown,
): Promise<T> {
  const token = await page.evaluate(() => window.localStorage.getItem("auth_token"));
  if (!token) throw new Error("Not signed in: no auth_token in localStorage");
  const response = await page.request.fetch(`/api${path}`, {
    method,
    data,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`${method} ${path} failed: ${response.status()} ${await response.text()}`);
  }
  return (response.status() === 204 ? undefined : await response.json()) as T;
}

export interface Student {
  id: number;
  name: string;
}

type Lesson = readonly [kid: number, offsetDays: number, title: string, status: string];

/**
 * A believable school week around the frozen day: two kids, a book in the
 * library, finished and open lessons (one overdue), and a holiday coming up.
 */
export async function seedSchoolWeek(page: Page): Promise<Student[]> {
  const [sam] = await apiAs<Student[]>(page, "GET", "/students");
  const maya = await apiAs<Student>(page, "POST", "/students", { name: "Maya Rivera", grade: "1" });
  await apiAs(page, "POST", "/curricula", { title: "Saxon Math 3", subject: "Math" });
  const lessons: Lesson[] = [
    [sam.id, -1, "Spelling list 7", "assigned"],
    [sam.id, 0, "Saxon Math Lesson 42", "completed"],
    [sam.id, 0, "Read The Wild Robot, chapter 3", "assigned"],
    [sam.id, 1, "Saxon Math Lesson 43", "assigned"],
    [maya.id, 0, "Phonics: short a", "assigned"],
    [maya.id, 0, "Count by twos", "completed"],
    [maya.id, 2, "Nature walk journal", "assigned"],
  ];
  for (const [studentId, offset, title, status] of lessons) {
    await apiAs(page, "POST", "/assignments", {
      student_id: studentId,
      title,
      scheduled_date: isoDay(offset),
      status,
    });
  }
  await apiAs(page, "POST", "/exceptions", {
    kind: "holiday",
    title: "Thanksgiving Break",
    start_date: "2026-11-25",
    end_date: "2026-11-27",
  });
  return [sam, maya];
}

/** Navigates by hash and waits for the route's title. */
export async function openRoute(page: Page, hash: string, title: string | RegExp) {
  await page.goto(`/${hash}`);
  await expect(page.locator("#page-title")).toHaveText(title);
}

/** Waits until the view has fetched its data and replaced its placeholders. */
export async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator("#view .empty", { hasText: /^Loading/ })).toHaveCount(0);
}
