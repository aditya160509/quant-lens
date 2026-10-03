# Research V2: Frontend Design

Status 2026-10-03: phase 1 built (workspace shell, chart core, F02). Live at `/research`. The old `/labs/research-v2` pages stay until every feature has its purpose-built view, then they are deleted and the route redirects. `frontend_mockup.html` was the layout sketch (made-up data). This file decides the layout, look and chart engine. `WORK_LEFT.md` keeps the per-feature output lists and the backend additions.

## 1. Reference level

TakeProfit (takeprofit.com/platform) sets the quality bar: a flat dark surface, 1px hairlines instead of shadows, one neutral grey ladder, colour only for meaning (up, down, warning, focus), monospaced tabular numbers, dense but calm. No gradients, glow or glass, and no decorative icons or emoji.

## 2. Layout: one workspace, not a home page per module

The old pattern (a module home page, then a separate page per feature) makes you leave your work to switch features. The new one is a single persistent workspace shared by every module (Research first, then Screener, Factors, ML, PCA and Portfolio):

| Region | Contents |
|---|---|
| **Top bar** | Brand, breadcrumb, ⌘K command palette (features, runs, tickers, presets), theme toggle |
| **Module rail** (48px) | Icon per module; first item is the cross-module overview |
| **Feature list** (220px) | Features of the current module with a verdict dot (green, amber, red, or grey for not run), plus presets |
| **Results canvas** | Title with study chips and actions (Compare runs, Export, Run study); a **verdict strip** (one plain sentence and four headline numbers); tabs ordered by the feature's reasoning; cards in a 2-column grid |
| **Inspector** (300px) | Study inputs (the form), the selected point or spec in detail, method with formula and citation |
| **Dock** (bottom) | Runs history, live jobs with progress, caveats, log |

- The module **overview** is a card grid of all features with the last verdict. It replaces the per-module home page.
- Hovering any chart updates the inspector, so detail never needs a popup.
- Panels are resizable and collapsible (`react-resizable-panels`); the layout is saved per user.
- URL: `/research/f02?run=0418`. Every view is a shareable link.
- Below 1100px the feature list folds into ⌘K. Below 760px everything stacks into one column.

## 3. Visual system

- **Type:** Inter for UI, JetBrains Mono with tabular numerals for every number. No serif in the app; serif is only used in exported journal tables.
- **Colour tokens:** CSS variables in `oklch`, with a dark set (default) and a light set. Background `#0b0c0e`, panels `#121316`, hairline `#23262c`, text in three steps. Accent blue is only for focus and selection. Up and down are green and red; amber means "mixed". Colour-blind check: significance is also shown by shape and fill, not only hue.
- **Density:** 13px base, 28px controls, 8px card radius, 12px gaps.
- **Motion:** 120–180ms fades and layout transitions only. Results reveal verdict first, then evidence. `prefers-reduced-motion` is respected.

## 4. Chart engine: custom, built in-house

We write our own chart layer instead of styling a library, which is how TakeProfit and TradingView get their look.

- **`@/charts` package:** `d3-scale`, `d3-shape` and `d3-array` for the maths only; rendering is our own React components.
- **SVG** for statistical plots (spec curve, forest, event study, RD, heatmaps): crisp, exportable to SVG and PDF at journal width.
- **Canvas 2D** for long time series and dense clouds (rolling IC, 1,000 placebo paths), with an SVG overlay for axes and the crosshair.
- **WebGL (three.js via react-three-fiber)** only for true 3D views: the robustness surface over two dimensions and the regime × threshold surface. Lazy-loaded, with a 2D heatmap fallback.
- **Shared primitives:** axis, gridlines, CI band, zero line, crosshair with linked hover across charts, direct labels instead of legends, annotation callouts, a source line, and SVG/PNG/CSV export.
- Recharts, ECharts and Plotly are not used in Research V2.

## 5. Build order

1. Shell: workspace, tokens, ⌘K, dock, inspector, routing.
2. Chart primitives and export.
3. F02 (spec curve, as in the mockup), F07, F03 and F06 as the hero views.
4. F01, F04, F05, F08, F09 and F11.
5. Presets, compare runs, share links and the full report.
6. Accessibility, mobile and Playwright screenshot tests per feature.

## 6. Many outputs per feature: how they stay clean

- **Each tab has a fixed composition:** one hero chart full width, then two or three supporting cards. Never a long scroll of equal cards.
- **Outputs outline:** the inspector lists every output of the feature with a status dot; clicking one scrolls to it and highlights it.
- **Maximize:** any card can fill the canvas (like a TakeProfit widget), with Esc to return.
- **Split compare:** pin two outputs, or the same output from two runs, side by side.
- **Linked hover:** one crosshair across every time-based chart on the tab.
- **Tables are compact:** sparklines and CI bars inside rows instead of extra charts.

## 7. Stack

TypeScript, Next.js (already in the repo), React, Tailwind 4 driven by our CSS tokens, Radix headless primitives, our own chart engine (d3 for maths only; SVG, Canvas 2D with devicePixelRatio and crisp 1px lines, three.js via react-three-fiber for 3D), TanStack Table and Virtual, cmdk, react-resizable-panels and Motion. Fonts: Geist or Inter for UI, Geist Mono or JetBrains Mono for numbers. This is the same family of technology TradingView and TakeProfit use; the data is small, so WASM or Rust adds nothing.

## 8. Decisions

- One shell, two layouts (decided 2026-10-03). Every module, Studio included, shares the shell: top bar, module rail, ⌘K, theme, fonts, chart engine, tables, run history and chart notes (`frontend/src/workspace`, `frontend/src/charts`).
  - Analysis modules (Research, Screener, Factors, ML, PCA, Volatility, Portfolio) use the module layout: feature list, results, inspector, runs dock.
  - Studio uses an IDE layout inside the same shell: files, editor, terminal and variables, with results in tabs. Studio's Portfolio and Factors modes call the same backends and reuse the same views as the standalone modules; no duplicate implementations.
- Research is built first.
- Whether to keep `/labs/research-v2` as a redirect once `/research` is live: open.

## 9. Build status

| Part | State | Where |
|---|---|---|
| Workspace shell: rail, ⌘K palette, resizable panels saved per device, dark and light themes | Done | `frontend/src/workspace/` |
| Chart core: crisp SVG primitives, robust axis domains, hover readouts, SVG/PNG/CSV export | Done | `frontend/src/charts/` |
| Research app: feature list with verdict dots, overview grid, study form, run jobs, runs dock, inspector with selection detail and outputs outline, maximize, ⌘↵ to run | Done | `frontend/src/modules/research/` |
| F02 views: specification curve with linked decision ledger, attribution bars, permutation null, robustness matrix with inline CIs, verdict strip | Done | `outputs/robustness.tsx`, `layouts.ts` |
| F01, F03 to F11 purpose-built views | Next. Until then they render through the generic table, key-value and test cards | `outputs/` |
| Strict TypeScript for all new code | `npx tsc -p tsconfig.strict.json` | `frontend/tsconfig.strict.json` |

Backend fixes found while building F02: a control identical to the signal made every monthly regression singular (slopes of about 1e16); the cross-section kernel now skips rank-deficient months instead of returning garbage, and control variants that duplicate the base specification are no longer estimated twice.

## 10. Reference research pass (2026-10-03)

Sources read in full: specr custom-plot vignette, Pixel-Show "Designing data-dense dashboards", Perpetua style guide, synthdid `synthdid_plot` reference, Portfolio Visualizer home, R Psychologist p-value page (the visual itself is JavaScript, so only its controls were readable). modelsummary vignette: section structure only (the page is mostly R code). Observable showcase post: blocked (HTTP 429). App-style sites in WORK_LEFT (QuantConnect, TradingView, Koyfin, Composer, TrendSpider) need screenshots or a logged-in session; not fetched.

What to adopt, by source:

| Source | Pattern | Where it goes |
|---|---|---|
| specr | Sample-size strip under the curve (months or N per spec); "by choice" box plots of estimates per choice value; grouped summary (median, MAD, IQR per choice) | F02 curve card and a new "By choice" view |
| modelsummary | Table controls: statistic under the estimate (SE, t, CI, p), stars on or off with custom thresholds, rename / omit / reorder terms, pick goodness-of-fit rows, stacked panels vs side-by-side columns, title and notes, added rows | Settings popover on every regression and publication table; feeds the LaTeX export |
| Pixel-Show | Drawer for row detail (the list stays put; Esc closes; arrow keys move through rows); two-tier emphasis (bright colour for hero numbers, dimmed colour inside long tables); tables collapse to label-value cards on phones; motion limited to 120 / 200 / 350 ms with no per-row stagger | All tables; tone down card stagger; mobile pass |
| Perpetua | Density as a setting (compact 24px rows vs comfortable 32px); flash a cell for about 600 ms when a value changes; up/down colour inversion for markets that use red for up; ▲ ▼ glyph deltas | Workspace settings; KPI and table cells |
| synthdid | Effect arrow and parallelogram diagram on the treated vs synthetic chart; time-weight strip under the path; labelled spaghetti for top donors; an overlay slider that shifts the control onto the treated path to judge parallel trends; highlight one estimate while dimming others | F09 effect chart; F07 DiD compare |
| R Psychologist | Interactive "simulate the null" explainer: draw samples, watch the statistic's distribution build up, see where the observed value lands | Method drawer for permutation and placebo cards |
