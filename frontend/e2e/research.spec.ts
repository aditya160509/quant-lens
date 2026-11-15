import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve, join } from "node:path";
import { expect, test } from "playwright/test";

/**
 * Visual smoke tests for the lab workspace (Research, Machine learning and Screener) in dark and light.
 * Run with `npm run test:e2e:labs` (one worker: parallel first loads on the dev server race the page switch).
 * Update baselines with: npm run test:e2e:labs -- --update-snapshots
 */
const PAGES = ["/research", "/research/signal", "/research/report", "/research/canonical", "/ml", "/ml/cpcv", "/ml/validate", "/ml/studio", "/screener", "/screener/screen", "/screener/composite", "/screener/backtest", "/screener/alerts", "/screener/saved", "/screener/more"];

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

// Synthetic contract fixture uses counts to check the normalized denominator.
const cinemaManifest = { features: [
  { id: "06", title: "Market state", inputs: [], outputs: [{ id: "regime_probability_time_series", title: "Regime probabilities", path: "charts.regime_probability_time_series", type: "chart" }] },
  ...["validate", "02", "03"].map((id) => ({ id, title: id, inputs: [], outputs: [] })),
] };
const cinemaResult = { feature_id: "06", status: "ok", summary_cards: [], tables: {}, meta: { state_labels: { state_1: "Calm", state_2: "Stress" } }, charts: {
  regime_probability_time_series: [
    { date: "2026-01-01", state_1: 60, state_2: 40 },
    { date: "2026-02-01", state_1: 20, state_2: 80 },
    { date: "2026-03-01", state_1: 75, state_2: 25 },
  ],
} };
for (const scheme of ["dark", "light"] as const) {
  for (const width of [375, 1440]) {
    test(`cinema fixture ${scheme} ${width}: accessible normalized chart`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.addInitScript((s) => localStorage.setItem("ws-theme", s), scheme);
      await page.route("**/ml/v2/features", (route) => route.fulfill({ json: cinemaManifest }));
      await page.route("**/ml/v2/jobs/cinema-fixture", (route) => route.fulfill({ json: { job_id: "cinema-fixture", status: "completed", result: cinemaResult } }));
      await page.goto("/ml/regimes?run=cinema-fixture");
      const chart = page.getByRole("img", { name: /Composition over time/ });
      await expect(chart).toBeVisible();
      await chart.focus();
      await chart.press("Home");
      await expect(page.getByRole("status").filter({ hasText: "Total (absolute)" })).toContainText("60.0%");
      await chart.press("ArrowRight");
      await expect(page.getByRole("status").filter({ hasText: "Total (absolute)" })).toContainText("80.0%");
      await page.getByRole("button", { name: "Absolute", exact: true }).click();
      await chart.focus();
      await chart.press("Home");
      await expect(page.getByRole("status").filter({ hasText: "Total (absolute)" })).toContainText("100");
      await chart.press("Escape");
      await expect(page.getByRole("status").filter({ hasText: "Total (absolute)" })).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await expect(page).toHaveScreenshot(`cinema-regimes-${scheme}-${width}.png`, { animations: "disabled", maxDiffPixelRatio: 0.01 });
    });
  }
}

test("cinema onboarding survives dismissal and does not complete on a page visit", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: cinemaManifest }));
  await page.goto("/ml");
  await expect(page.getByRole("region", { name: "Quick start" })).toContainText("0 of 3 done");
  await page.getByRole("link", { name: "1. Validate a strategy", exact: true }).click();
  await page.goto("/ml");
  await expect(page.getByRole("region", { name: "Quick start" })).toContainText("0 of 3 done");
  await page.getByRole("button", { name: "Dismiss quick start" }).click();
  await page.reload();
  await expect(page.getByRole("region", { name: "Quick start" })).toHaveCount(0);
});

test("cinema studio passes actual artifacts and completes every stage", async ({ page }) => {
  const sent: { id: string; body: Record<string, unknown> }[] = [];
  const features = ["02", "04", "03", "05", "validate"].map((id) => ({ id, title: id, outputs: [], inputs: [
    { key: "artifact_id", type: "text", group: "Data", label: "Artifact" },
    { key: "alpha_artifact_id", type: "text", group: "Data", label: "Alpha" },
  ] }));
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features } }));
  await page.route("**/ml/v2/features/*/jobs", async (route) => {
    const id = route.request().url().split("/").at(-2)!;
    sent.push({ id, body: route.request().postDataJSON() });
    await route.fulfill({ json: { job_id: `pipeline-${id}`, status: "queued" } });
  });
  await page.route("**/ml/v2/jobs/pipeline-*", (route) => {
    const id = route.request().url().split("pipeline-")[1];
    return route.fulfill({ json: { job_id: `pipeline-${id}`, status: "completed", result: { feature_id: id, status: "ok", tables: {}, charts: {}, meta: { artifact_id: `artifact-${id}` } } } });
  });
  await page.goto("/ml/studio");
  await page.getByRole("button", { name: "Run the whole pipeline" }).click();
  await expect(page.getByRole("status").filter({ hasText: "All five studies completed" })).toBeVisible();
  expect(sent.map((s) => s.id)).toEqual(["02", "04", "03", "05", "validate"]);
  expect(sent[1].body.artifact_id).toBe("artifact-02");
  expect(sent[3].body.alpha_artifact_id).toBe("artifact-02");
  expect(sent[4].body.artifact_id).toBe("artifact-05");
});

test("cinema studio stops on a missing hand-off instead of substituting data", async ({ page }) => {
  let submissions = 0;
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: ["02", "04", "03", "05", "validate"].map((id) => ({ id, title: id, inputs: [], outputs: [] })) } }));
  await page.route("**/ml/v2/features/*/jobs", (route) => { submissions++; return route.fulfill({ json: { job_id: "no-artifact", status: "queued" } }); });
  await page.route("**/ml/v2/jobs/no-artifact", (route) => route.fulfill({ json: { job_id: "no-artifact", status: "completed", result: { feature_id: "02", status: "ok", tables: {}, charts: {}, meta: {} } } }));
  await page.goto("/ml/studio");
  await page.getByRole("button", { name: "Run the whole pipeline" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "no hand-off artifact" })).toBeVisible();
  expect(submissions).toBe(1);
});

test("cinema allocation treemap drills into names and switches size measures", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "05", title: "Allocation", inputs: [], outputs: [] }] } }));
  await page.route("**/ml/v2/jobs/weights", (route) => route.fulfill({ json: { job_id: "weights", status: "completed", result: { feature_id: "05", status: "ok", charts: {}, meta: {}, tables: {
    weight_stability: [{ asset: "AAPL", weight: 0.6, low: 0.5, high: 0.7 }, { asset: "MSFT", weight: 0.4, low: 0.3, high: 0.5 }],
    hrp_weight_vector: [{ asset: "AAPL", sector: "Technology", weight: 0.6 }, { asset: "MSFT", sector: "Technology", weight: 0.4 }],
    risk_contribution_decomposition: [{ asset: "AAPL", risk_contribution: 0.7 }, { asset: "MSFT", risk_contribution: 0.3 }],
  } } } }));
  await page.goto("/ml/allocation?run=weights");
  await page.locator("#out-weight_stability").hover();
  await page.getByRole("button", { name: "View as" }).click();
  await page.getByRole("menuitem", { name: "Sector treemap" }).click();
  await page.getByRole("button", { name: /Technology: Weight.*Open group/ }).press("Enter");
  await expect(page.getByRole("button", { name: /AAPL: Weight 60.0%/ })).toBeVisible();
  await page.getByRole("button", { name: "Risk share", exact: true }).click();
  await expect(page.getByRole("button", { name: /AAPL: Risk share 70.0%/ })).toBeVisible();
  await page.getByRole("button", { name: /AAPL: Risk share 70.0%/ }).press("Escape");
  await expect(page.getByRole("button", { name: /Technology: Risk share.*Open group/ })).toBeVisible();
});

test("cinema calendar preserves missing months and exports a real SVG", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "02", title: "Alpha", inputs: [], outputs: [{ id: "rolling_monthly_ic_series", title: "Monthly IC", path: "charts.rolling_monthly_ic_series", type: "chart" }] }] } }));
  await page.route("**/ml/v2/jobs/calendar", (route) => route.fulfill({ json: { job_id: "calendar", status: "completed", result: { feature_id: "02", status: "ok", tables: {}, meta: {}, charts: { rolling_monthly_ic_series: [{ date: "2026-01-01", ic: 0.2 }, { date: "2026-03-01", ic: -0.1 }] } } } }));
  await page.goto("/ml/alpha?run=calendar");
  await expect(page.getByRole("img", { name: /Information coefficient by month/ })).toBeVisible();
  const data = page.getByRole("table", { name: "Information coefficient by month" });
  await expect(data.getByTitle("Feb 2026: No observation")).toHaveText("–");
  const card = page.locator("#out-rolling_monthly_ic_series");
  await card.hover();
  const download = page.waitForEvent("download");
  await card.getByRole("button", { name: "Download SVG", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.svg$/);
  await page.getByRole("button", { name: "Bars", exact: true }).click();
  await expect(page.getByRole("img", { name: /Information coefficient by month/ })).toHaveCount(0);
});

test("cinema unavailable saved results offer recovery instead of an endless skeleton", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("research-runs", JSON.stringify({ state: { runs: [{ featureId: "ml02", featureName: "Alpha", jobId: "expired", startedAt: 1767225600000, status: "completed" }] }, version: 1 })));
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: cinemaManifest }));
  await page.route("**/ml/v2/jobs/expired", (route) => route.fulfill({ status: 404, json: { detail: "Expired run" } }));
  await page.goto("/ml");
  await expect(page.getByText("This result is unavailable. Open the study and run it again.")).toBeVisible();
});

test("cinema large tables keep later rows reachable with bounded rendering", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "02", title: "Alpha", inputs: [], outputs: [{ id: "heldout_predictions", title: "Held-out predictions", path: "tables.heldout_predictions", type: "table" }] }] } }));
  await page.route("**/ml/v2/jobs/large-table", (route) => route.fulfill({ json: { job_id: "large-table", status: "completed", result: { feature_id: "02", status: "ok", meta: {}, charts: {}, tables: { heldout_predictions: Array.from({ length: 950 }, (_, i) => ({ ticker: `Name${String(i).padStart(4, "0")}`, score: i })) } } } }));
  await page.goto("/ml/alpha?run=large-table");
  await page.getByRole("tab", { name: /^Data/ }).click();
  const table = page.locator("#out-heldout_predictions");
  await expect(table.getByRole("status")).toContainText("Rows 1–400 of 950");
  expect(await table.locator("tbody tr").count()).toBeLessThan(60);
  await table.getByRole("button", { name: "Next", exact: true }).click();
  await expect(table.getByRole("status")).toContainText("Rows 401–800 of 950");
  await expect(table.getByText("Name0400", { exact: true })).toBeVisible();
  await table.getByRole("button", { name: "Next", exact: true }).click();
  await expect(table.getByRole("status")).toContainText("Rows 801–950 of 950");
  await table.getByRole("button", { name: "Score", exact: true }).click();
  await table.getByRole("button", { name: "Score", exact: true }).click();
  await expect(table.getByText("Name0949", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 900 });
  await expect(table.locator(".tbl-wrap")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("cinema distribution changes lenses without inventing samples", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "01", title: "Purged CV", inputs: [], outputs: [{ id: "path_sharpe_distribution", title: "Path Sharpes", path: "charts.path_sharpe_distribution", type: "bar", encoding: { x: "sharpe", bin: true } }] }] } }));
  await page.route("**/ml/v2/jobs/distribution", (route) => route.fulfill({ json: { job_id: "distribution", status: "completed", result: { feature_id: "01", status: "ok", meta: {}, tables: {}, charts: { path_sharpe_distribution: [0, 1, 2, 3].map((sharpe) => ({ sharpe })) } } } }));
  await page.goto("/ml/cpcv?run=distribution");
  await expect(page.getByRole("button", { name: "Box", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Box", exact: true }).click();
  await expect(page.getByText(/whiskers: 5th–95th/)).toBeVisible();
  await page.getByRole("button", { name: "Ridge", exact: true }).click();
  await expect(page.getByText(/not a fitted probability density/)).toBeVisible();
  await page.getByRole("button", { name: "Strip", exact: true }).click();
  await expect(page.getByRole("img", { name: /4 observations/ })).toBeVisible();
});

test("cinema cluster cut links the tree and correlation matrix", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "05", title: "Allocation", inputs: [], outputs: [{ id: "cluster_dendrograms", title: "Clusters", path: "charts.cluster_dendrograms", type: "chart" }] }] } }));
  await page.route("**/ml/v2/jobs/clusters", (route) => route.fulfill({ json: { job_id: "clusters", status: "completed", result: { feature_id: "05", status: "ok", meta: {}, tables: { hrp_weight_vector: ["A", "B", "C"].map((asset) => ({ asset, weight: 1 / 3 })) }, charts: {
    cluster_dendrograms: [{ left: 0, right: 1, distance: 1 }, { left: 3, right: 2, distance: 3 }],
    quasi_diagonalized_covariance_heatmap: ["A", "B", "C"].flatMap((row) => ["A", "B", "C"].map((col) => ({ row, col, value: row === col ? 1 : 0.25 }))),
  } } } }));
  await page.goto("/ml/allocation?run=clusters");
  const slider = page.getByRole("slider", { name: "Cluster cut height" });
  await slider.fill("1");
  await expect(page.getByRole("img", { name: "C, cluster 1", exact: true })).toBeVisible();
  await slider.fill("0");
  await expect(page.getByRole("img", { name: "C, cluster 3", exact: true })).toBeVisible();
  await page.getByRole("img", { name: "A, cluster 1", exact: true }).focus();
  await expect(page.locator('.corr-l[data-on="true"]')).toHaveText("A");
  const cell = page.getByRole("button", { name: "A × A: 1.000", exact: true });
  await cell.focus();
  await cell.press("ArrowRight");
  await expect(page.getByRole("button", { name: "A × B: 0.250", exact: true })).toBeFocused();
});

test("cinema waterfall opens the selected feature's observed values", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "02", title: "Alpha", inputs: [], outputs: [{ id: "shap_waterfall_top_signal", title: "Contributions", path: "charts.shap_waterfall_top_signal", type: "chart" }] }] } }));
  await page.route("**/ml/v2/jobs/contributions", (route) => route.fulfill({ json: { job_id: "contributions", status: "completed", result: { feature_id: "02", status: "ok", meta: {}, tables: { ticker_contributions: [{ ticker: "AAA", rank: 1, prediction: 0.03, base_value: 0.01, contributions: { momentum: 0.02 } }] }, charts: { shap_waterfall_top_signal: [{ feature: "momentum", shap_value: 0.02 }], shap_beeswarm: [{ ticker: "AAA", feature: "momentum", feature_value: 2, shap_value: 0.02 }, { ticker: "BBB", feature: "momentum", feature_value: 1, shap_value: 0.01 }] } } } }));
  await page.goto("/ml/alpha?run=contributions");
  await page.getByRole("button", { name: /Inspect Momentum, contribution/ }).press("Enter");
  await expect(page.getByRole("img", { name: /Momentum across names: 2 observations/ })).toBeVisible();
  await expect(page.getByText(/AAA 2.00 · 50.0% as extreme/)).toBeVisible();
  await page.getByRole("button", { name: "Close feature details" }).click();
  await expect(page.getByRole("img", { name: /Momentum across names/ })).toHaveCount(0);
});

test("cinema dense scatter bins observations and supports keyboard selection", async ({ page }) => {
  await page.route("**/ml/v2/features", (route) => route.fulfill({ json: { features: [{ id: "02", title: "Alpha", inputs: [], outputs: [{ id: "scatter_audit", title: "Predicted and realised", path: "charts.scatter_audit", type: "scatter", encoding: { x: "predicted", y: "realised" } }] }] } }));
  await page.route("**/ml/v2/jobs/scatter", (route) => route.fulfill({ json: { job_id: "scatter", status: "completed", result: { feature_id: "02", status: "ok", meta: {}, tables: {}, charts: { scatter_audit: Array.from({ length: 2500 }, (_, i) => ({ predicted: i % 50, realised: Math.floor(i / 50) })) } } } }));
  await page.goto("/ml/alpha?run=scatter");
  const plot = page.getByRole("img", { name: /hexagonal density/ });
  await expect(plot).toBeVisible();
  expect(await plot.locator("circle").count()).toBeLessThan(10);
  await plot.focus();
  await plot.press("Home");
  await plot.press("Space");
  await expect(page.getByRole("status").filter({ hasText: "1 selected" })).toBeVisible();
  await page.getByRole("button", { name: "Select all 2500" }).click();
  await expect(page.getByRole("button", { name: "CSV · 2500 selected" })).toBeVisible();
  expect(await plot.locator("circle").count()).toBeLessThan(10);
  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await page.getByRole("button", { name: "Lasso", exact: true }).click();
  const bounds = (await plot.boundingBox())!;
  await page.mouse.move(bounds.x + 60, bounds.y + 20);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + 20, { steps: 6 });
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2, { steps: 6 });
  await page.mouse.move(bounds.x + 60, bounds.y + bounds.height / 2, { steps: 6 });
  await page.mouse.move(bounds.x + 60, bounds.y + 20, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: /CSV · \d+ selected/ })).toBeVisible();
  await plot.focus();
  await plot.press("Escape");
  await expect(page.getByRole("button", { name: /CSV · \d+ selected/ })).toHaveCount(0);
});


// Opt-in replay of local saved results. Never substitute generated data for this audit.
if (process.env.ML_CINEMA_REAL_RESULTS) {
  const root = resolve(process.env.ML_CINEMA_REAL_RESULTS);
  const saved = new Map<string, { filename: string; result: Record<string, unknown> }>();
  for (const filename of readdirSync(root).filter((name) => name.endsWith(".json")).sort((a, b) => statSync(join(root, b)).mtimeMs - statSync(join(root, a)).mtimeMs)) {
    const result = JSON.parse(readFileSync(join(root, filename), "utf8"));
    if (!saved.has(result.feature_id)) saved.set(result.feature_id, { filename, result });
  }
  for (const [id, slug] of [["01", "cpcv"], ["02", "alpha"], ["03", "volatility"], ["04", "barriers"], ["05", "allocation"], ["06", "regimes"], ["validate", "validate"]]) {
    for (const scheme of ["dark", "light"] as const) for (const width of [375, 1440]) {
      test(`cinema real ${slug} ${scheme} ${width}`, async ({ page }, info) => {
        const fixture = saved.get(`feature_${id}`);
        expect(fixture, `Saved result required for ${id}`).toBeDefined();
        await info.attach("source", { body: fixture!.filename, contentType: "text/plain" });
        await page.setViewportSize({ width, height: 1000 });
        await page.addInitScript((s) => localStorage.setItem("ws-theme", s), scheme);
        const errors: string[] = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.route(`**/ml/v2/jobs/real-${id}`, (route) => route.fulfill({ json: { job_id: `real-${id}`, status: "completed", result: fixture!.result } }));
        await page.goto(`/ml/${slug}?run=real-${id}`);
        await expect(page.locator(".results .card").first()).toBeVisible();
        const tabs = page.locator(".results .sticky-bar [role=tab]");
        const count = await tabs.count();
        for (let index = 0; index < count; index++) {
          await tabs.nth(index).click();
          await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
          await expect(page.locator(".results .card").first()).toBeVisible();
          await expect(page.locator('.results [aria-busy="true"]')).toHaveCount(0);
          await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
          expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
          const invalid = await page.locator(".results svg").evaluateAll((svgs) => svgs.some((svg) => Array.from(svg.querySelectorAll("path,circle,rect")).some((el) => ["d", "cx", "cy", "x", "y", "width", "height"].some((key) => /NaN|Infinity/.test(el.getAttribute(key) ?? "")))));
          expect(invalid).toBe(false);
          const cards = page.locator(".results .card");
          for (let card = 0; card < await cards.count(); card++) {
            await cards.nth(card).screenshot({ path: info.outputPath(`section-${index}-exhibit-${card}.png`), animations: "disabled" });
          }
        }
        expect(errors).toEqual([]);
      });
    }
  }
}
