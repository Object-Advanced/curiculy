import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import type { Page } from "@playwright/test";

import { expect, openRoute, seedSchoolWeek, startDemo, test } from "./support";

/**
 * Records what loading the app costs, so each modernization PR can compare
 * against it (e2e/reports/metrics.json). No thresholds yet.
 *
 * - firstVisit: a new browser (empty cache) opening the sign-in page.
 * - homeOpen: a signed-in parent reopening Home, with a warm cache.
 */
type Row = { url: string; type: string; bytes: number };

function trackRequests(page: Page): () => Promise<Row[]> {
  const pending: Promise<Row>[] = [];
  const listener = (request: import("@playwright/test").Request) => {
    pending.push(
      request.sizes().then((sizes) => ({
        url: request.url(),
        type: request.resourceType(),
        bytes: sizes.responseHeadersSize + sizes.responseBodySize,
      })),
    );
  };
  page.on("requestfinished", listener);
  return async () => {
    page.off("requestfinished", listener);
    return Promise.all(pending);
  };
}

async function largestContentfulPaint(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        new PerformanceObserver((list) => {
          const entries = list.getEntries();
          resolve(entries.length ? entries[entries.length - 1].startTime : 0);
        }).observe({ type: "largest-contentful-paint", buffered: true });
        setTimeout(() => resolve(0), 2000);
      }),
  );
}

function summarize(rows: Row[], lcp: number) {
  const api = rows.filter((row) => new URL(row.url).pathname.startsWith("/api/"));
  const kb = (list: Row[]) => Math.round(list.reduce((sum, row) => sum + row.bytes, 0) / 1024);
  return {
    totalRequests: rows.length,
    apiRequests: api.length,
    totalKilobytes: kb(rows),
    apiKilobytes: kb(api),
    largestContentfulPaintMs: Math.round(lcp),
    requests: rows,
  };
}

test("cost of a first visit and of reopening Home", async ({ page }) => {
  const firstVisitRows = trackRequests(page);
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  const firstVisit = summarize(await firstVisitRows(), await largestContentfulPaint(page));

  await startDemo(page);
  await seedSchoolWeek(page);
  await openRoute(page, "#/dashboard", "Home");
  const homeRows = trackRequests(page);
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("#home-lessons-today")).not.toHaveText("…");
  const homeOpen = summarize(await homeRows(), await largestContentfulPaint(page));

  const metrics = { firstVisit, homeOpen };
  const dir = join(__dirname, "..", "reports");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "metrics.json"), `${JSON.stringify(metrics, null, 2)}\n`);
  await test.info().attach("metrics.json", {
    body: JSON.stringify(metrics, null, 2),
    contentType: "application/json",
  });
  for (const [name, row] of Object.entries(metrics)) {
    console.log(
      `${name}: ${row.totalRequests} requests (${row.apiRequests} API), ` +
        `${row.totalKilobytes} KB (${row.apiKilobytes} KB API), LCP ${row.largestContentfulPaintMs} ms`,
    );
  }
  expect(homeOpen.apiRequests).toBeGreaterThan(0);
});
