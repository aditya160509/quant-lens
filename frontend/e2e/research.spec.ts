import { expect, test } from "playwright/test";

/**
 * Visual smoke tests for the lab workspace (Research and Machine learning) in dark and light.
 * Update baselines with: npx playwright test e2e/research.spec.ts --update-snapshots
 */
const PAGES = ["/research", "/research/signal", "/research/report", "/research/canonical", "/ml", "/ml/cpcv"];

for (const scheme of ["dark", "light"] as const) {
  test.describe(`research ${scheme}`, () => {
    test.use({ colorScheme: scheme });
    for (const path of PAGES) {
      test(`${path} renders`, async ({ page }) => {
        await page.addInitScript((s) => { try { localStorage.setItem("theme", s); } catch { /* ignore */ } }, scheme);
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        await expect(page.locator("body")).not.toContainText("Application error");
        await expect(page).toHaveScreenshot(`${path.replace(/\W+/g, "_") || "root"}-${scheme}.png`, { maxDiffPixelRatio: 0.02, animations: "disabled", fullPage: false });
      });
    }
  });
}
