import { defineConfig } from "@playwright/test";

import type { Theme } from "./tests/support";

const desktop = { width: 1280, height: 800 };
const tablet = { width: 768, height: 1024 };
const phone = { width: 375, height: 812 };
const visual = /visual\.spec\.ts/;

/**
 * Projects:
 * - "setup" registers one real household (signup, onboarding, kid PIN) and
 *   saves its credentials for the kid tests. Invite keys are single-use, so
 *   this runs once per throwaway app.
 * - "functional" runs smoke, kid sign-in, accessibility, and metrics once.
 * - "visual-*" captures the main screens at phone, tablet, and desktop widths,
 *   in light and dark, against a frozen clock.
 */
export default defineConfig<{ theme: Theme }>({
  testDir: "./tests",
  outputDir: "./test-results",
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled", caret: "hide" },
  },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  workers: process.env.CI ? 2 : undefined,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3040",
    browserName: "chromium",
    locale: "en-US",
    timezoneId: "UTC",
    // The app's service worker caches the shell; tests measure and exercise
    // the network directly unless a test opts back in.
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /\.setup\.ts/, use: { viewport: desktop } },
    {
      name: "functional",
      testIgnore: [visual, /\.setup\.ts/],
      dependencies: ["setup"],
      use: { viewport: desktop },
    },
    {
      name: "visual-desktop-light",
      testMatch: visual,
      dependencies: ["setup"],
      use: { viewport: desktop, theme: "light" },
    },
    {
      name: "visual-desktop-dark",
      testMatch: visual,
      dependencies: ["setup"],
      use: { viewport: desktop, theme: "dark", colorScheme: "dark" },
    },
    {
      name: "visual-tablet-light",
      testMatch: visual,
      dependencies: ["setup"],
      use: { viewport: tablet, theme: "light" },
    },
    {
      name: "visual-phone-light",
      testMatch: visual,
      dependencies: ["setup"],
      use: { viewport: phone, isMobile: true, hasTouch: true, theme: "light" },
    },
    {
      name: "visual-phone-dark",
      testMatch: visual,
      dependencies: ["setup"],
      use: { viewport: phone, isMobile: true, hasTouch: true, theme: "dark", colorScheme: "dark" },
    },
  ],
});
