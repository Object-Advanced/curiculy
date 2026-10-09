import type { Page } from "@playwright/test";

import { apiAs, browserToday, expect, openRoute, startDemo, test, type Student } from "./support";

type QueuedChange = { headers: Record<string, string>; status: string; owner: string };

/** The offline queue's rows, read straight from IndexedDB. */
async function queuedChanges(page: Page): Promise<QueuedChange[]> {
  return page.evaluate(
    () =>
      new Promise<QueuedChange[]>((resolve, reject) => {
        const open = indexedDB.open("curiculy-sync");
        open.onerror = () => reject(open.error);
        open.onsuccess = () => {
          const db = open.result;
          if (!db.objectStoreNames.contains("outbox")) {
            db.close();
            resolve([]);
            return;
          }
          const read = db.transaction("outbox", "readonly").objectStore("outbox").getAll();
          read.onsuccess = () => {
            db.close();
            resolve(read.result as QueuedChange[]);
          };
          read.onerror = () => reject(read.error);
        };
      }),
  );
}

/** A demo household with one lesson today, open on the kid's checklist. */
async function lessonOnTheChecklist(page: Page, title: string): Promise<number> {
  await startDemo(page);
  const [kid] = await apiAs<Student[]>(page, "GET", "/students");
  const lesson = await apiAs<{ id: number }>(page, "POST", "/assignments", {
    student_id: kid.id,
    title,
    scheduled_date: browserToday(),
  });
  await openRoute(page, "#/students", /'s day$/);
  await expect(page.getByLabel(`Mark ${title} complete`)).toBeVisible();
  return lesson.id;
}

test("a change made offline is saved once the network is back", async ({ page, context }) => {
  const lessonId = await lessonOnTheChecklist(page, "Offline fractions");

  await context.setOffline(true);
  await page.getByLabel("Mark Offline fractions complete").check();
  await expect(page.locator("#sync-pill")).toHaveText("1 change waiting to sync");

  const [queued] = await queuedChanges(page);
  expect(Object.keys(queued.headers).map((name) => name.toLowerCase())).not.toContain("authorization");
  expect(queued.headers["Idempotency-Key"]).toBeTruthy();
  expect(queued.owner).toMatch(/^DEMO\//);

  await context.setOffline(false);
  await expect(page.locator("#sync-pill")).toBeHidden();
  expect(await queuedChanges(page)).toEqual([]);
  const saved = await apiAs<{ status: string }>(page, "GET", `/assignments/${lessonId}`);
  expect(saved.status).toBe("completed");
});

test("a change the server refuses waits in the couldn't-save list", async ({ page, context }) => {
  const lessonId = await lessonOnTheChecklist(page, "Deleted meanwhile");

  await context.setOffline(true);
  await page.getByLabel("Mark Deleted meanwhile complete").check();
  await expect(page.locator("#sync-pill")).toHaveText("1 change waiting to sync");

  // Another device deletes the lesson while this one is offline. (Playwright's
  // API client is not affected by the browser's offline emulation.)
  await apiAs(page, "DELETE", `/assignments/${lessonId}`);
  await context.setOffline(false);

  const pill = page.locator("#sync-pill");
  await expect(pill).toHaveText("1 change couldn't be saved");
  page.once("dialog", (dialog) => dialog.accept());
  await pill.click();
  await expect(pill).toBeHidden();
  expect(await queuedChanges(page)).toEqual([]);
});

test("logging out discards unsynced changes after asking", async ({ page, context }) => {
  await lessonOnTheChecklist(page, "Unsynced spelling");

  await context.setOffline(true);
  await page.getByLabel("Mark Unsynced spelling complete").check();
  await expect(page.locator("#sync-pill")).toHaveText("1 change waiting to sync");

  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#user-profile").click();
  await page.getByRole("menuitem", { name: "Log out" }).click();

  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  expect(await queuedChanges(page)).toEqual([]);
});
