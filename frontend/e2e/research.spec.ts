import { expect, test } from "playwright/test";

/**
 * Visual smoke tests for the lab workspace (Research and Machine learning) in dark and light.
 * Run with `npm run test:e2e:labs` (one worker: parallel first loads on the dev server race the page switch).
 * Update baselines with: npm run test:e2e:labs -- --update-snapshots
 */
const PAGES = ["/research", "/research/signal", "/research/report", "/research/canonical", "/ml", "/ml/cpcv", "/ml/validate", "/ml/studio"];

for (const scheme of ["dark", "light"] as const) {
  test.describe(`research ${scheme}`, () => {
    test.use({ colorScheme: scheme });
    for (const path of PAGES) {
      test(`${path} renders`, async ({ page }) => {
        await page.addInitScript((s) => { try { localStorage.setItem("ws-theme", s); } catch { /* ignore */ } }, scheme);
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        // The workspace picks the page from the manifest after load; wait until a deep link has left the Overview.
        if (path.split("/").length > 2) await page.waitForFunction(() => document.querySelector(".ws-crumb b")?.textContent !== "Overview", undefined, { timeout: 25_000 });
        await page.waitForLoadState("networkidle");
        await expect(page.locator("body")).not.toContainText("Application error");
        await expect(page).toHaveScreenshot(`${path.replace(/\W+/g, "_") || "root"}-${scheme}.png`, { maxDiffPixelRatio: 0.02, animations: "disabled", fullPage: false });
      });
    }
  });
}
