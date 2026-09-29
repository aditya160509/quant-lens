# Volatility V2 — Brutal World-Class Frontend Review

**Scope (read-only):** `frontend/src/components/volatility-v2/customPagePrimitives.jsx` (1524 lines + styles),
`frontend/src/components/volatility-v2/registry.js` (156 lines),
`frontend/src/app/labs/volatility-v2/page.js` (landing), `layout.js` (strip + palette),
`feature-01..09/page.js` (explicit section manifests).
**Standard:** Bloomberg PORT / TradingView / QuantConnect + vol-desk systems (estimator horse-races, GARCH density
diagnostics, cones/surfaces, regime probability, Diebold-Yilmaz connectedness).
**Verdict: 6.5 / 10.** The strongest v2 shell reviewed so far: typed registry, BBG-style ticker strip, sortable
microbar tables, hover-crosshair heatmaps, percentile cone + forecast bands, draggable network, workspace persistence,
export modal. Capped by one critical failure: **none of the 9 feature pages wires `onRun`, so Run/Compare are dead
ends everywhere**, plus a fake sparkline, a flattened 3D surface, and landing-page fiction (hardcoded "live" pills).

---

## 1. Score justification

| Axis | Score | Note |
|---|---|---|
| Chart truthfulness (cone, bands, heatmap, network, gauge) | 7/10 | Cone/bands/heatmap/probability-stack are genuinely good; `Spark` is fake sine; surface is a flat heatmap |
| Layout / density vs PORT / TradingView | 7/10 | Dock + minimap + cinema + split + density toggle is the best v2 workspace pattern; topbar crowded on small widths |
| Scenario / compare flows | 5/10 | Split/compare chrome exists but duplicates content with no deltas; stress feature has no scenario-side panel |
| States (loading / empty / error / stale) | 7/10 | Progress bar, toasts, per-card `VolEmpty` with available-keys hint; no stale-badge, no per-card retry |
| a11y / keyboard | 5/10 | Esc/`f` shortcuts, dialog roles, labeled strip nav; dock tooltips hover-only, `th` mouse-only, no live region, no reduced-motion guard |
| Primitive vs registry sync | 5/10 | Registry schema is excellent but pages bypass execution entirely; hidden default keys have no fields |
| **Overall** | **6.5/10** | |

---

## 2. Top 10 improvements (ranked by user-visible payoff)

1. **Wire `onRun` on all 9 feature pages (P0, functional outage).** Every page renders
   `<VolatilityV2Workbench featureId="0X" sections={...} />` with no `onRun`/`response`, so `run()` always hits the
   `"intentionally not wired"` branch and Compare only opens an empty lane. Portfolio-v2's internal
   `fetch(/api/labs/.../run)` pattern is the template; until then the workbench is a viewer.
2. **Kill the fake `Spark` or feed it trailing data.** `MetricDeck` decorates every metric with a `sin()` polyline.
   Pass the last-N values (the card usually has the rows) or delete it; `HeaderSparkline` already does the honest version.
3. **Restore a real volatility surface.** `SurfaceGrid` flattens horizon x moneyness into a 2-D heatmap while the
   *landing page* renders a proper 3-D term-structure surface with Plotly. Reuse that surface (or a contour + slice
   selector) inside the workbench; keep the heatmap as the fallback tab.
4. **Label landing fiction as illustration.** `page.js` hardcodes series/forecast/correlation/stress/budget data and
   "live" pills (`V01 Yang-Zhang 18.4%`, `Crisis prob 14%`, `Spillover 72`). Either bind them to the last cached run
   or badge them `ILLUSTRATIVE`. A desk that spots fake-live numbers stops trusting real ones.
5. **Make compare a delta view.** Same defect as portfolio-v2: `compareData || data` duplicates the primary lane and
   `VolOutputCard compare` disables activation. Add estimator-delta lines (e.g. YZ minus PK), forecast-accuracy deltas,
   and a synchronized crosshair; steal quantstats `compare()`.
6. **Unify the two network implementations.** Workbench `NetworkGraph` is a draggable circle; landing
   `ConnectednessVisual` runs real d3-force. Promote the force sim into the workbench (already a dependency of the
   landing page), size nodes by net spillover, cap edges with a threshold slider instead of silent `slice(0, 80)`.
7. **Fix the gauge contract.** `VolGauge` clamps any value to 0-100 and `data-zone` never equals the `"extreme"`
   CSS selector (zones are SERENE/CALM/NERVOUS/STRESSED/CRISIS), so the crisis glow is dead code. Normalize per-metric
   (percentile vs raw vol) and align zone names with styles.
8. **Harden the generic renderers.** `VolChart` auto-plots up to 8 `inferKeys` series (rainbow risk);
   `ComposedBars` hardcodes `eigenvalue/cumulative_variance`; `FrequencyBands` assumes an object payload.
   Cap default series at 3-4 with an explicit series picker, and fail visibly (`VolEmpty` + expected keys) on shape mismatch.
9. **Expose hidden registry params.** Defaults carry keys with no field UI (`compute_mode`, `cross_asset_panel`,
   `lookback_days` on F02, `window_days` vs `rolling_window` duplication on F01). Every default key needs a field or an
   explicit `advanced` group; stop `String()`-ifying numerics in form init so selects compare correctly.
10. **Do the a11y + perf pass.** Dock `<em>` tooltips hover-only; sortable `th` mouse-only; toast rack has
    `aria-live` but run status/progress don't; motion blur entrances need `prefers-reduced-motion` guards; the landing
    page loads Plotly + d3-force + recharts + springs at once and previews embed full feature pages in iframes.
    Lazy-load Plotly, paginate the dock past ~9 sections, replace iframe preview with the static visual.

---

## 3. AI-slop list (`file:line`)

`V` = `frontend/src/components/volatility-v2/customPagePrimitives.jsx`, `R` = `registry.js`,
`LH` = labs `page.js`, `LL` = `layout.js`, `F` = `feature-*/page.js`.

- `V:705-708` — `Spark()`: `sin(i*.7)*5 + (value%7)` polyline, pure decoration inside every `MetricDeck` card.
- `V:1402-1408` — `run()` without `onRun` posts `"intentionally not wired"`; **all 9 `F` pages hit this**
  (`F:feature-01/page.js:167-169`, `feature-06/page.js:104-106`, same pattern in 02-05/07-09: no `onRun`, no `response`).
- `V:1429-1431` — `runComparison()` without handler opens split mode on empty data with a shrug toast.
- `V:1218-1220` — `SurfaceGrid`: "synthetic vol surface" rendered as a flat `Heatmap`; the real 3-D surface only
  exists on the landing page (`LH:503-552`, Plotly surface over synthetic `z`).
- `LH:55-93` — `series()`, `harForecast`, `corrMatrix`, `stressBars`, `budgetRows`: hardcoded fake data driving all
  nine landing visuals, unlabeled as synthetic.
- `LH:961-963` — hero "live" pills with invented values (`18.4%`, `14%`, `72`).
- `V:1139` + styles `data-zone="extreme"` — gauge zone can never be `"extreme"`; crisis glow CSS is dead.
- `V:1232-1246` — `ComposedBars` hardcodes `eigenvalue`/`cumulative_variance`/`rank`; any other payload renders empty axes.
- `V:1222-1225` — `FrequencyBands` assumes `data` is an entries-able object; arrays crash to empty.
- `V:1065` / `V:851` — silent `edges.slice(0, 80)` and unguarded `matrix[ri][ci]` fallbacks hide data loss.
- `V:257` — `inferKeys` auto-plots up to 8 numeric series with cycling `SERIES` colors; rainbow-by-default.
- `V:900-962` — `VolChart` gradient `id`s interpolate raw `key` (`vol-grad-${key}`), breaking on keys with spaces/symbols
  and colliding across cards.
- `R:08-148` — defaults include UI-less keys (`compute_mode` x9, `cross_asset_panel`, `lookback_days` on F02,
  `window_days` + `rolling_window` on F01); `V:1327` stringifies every default, so numeric `select` comparisons rely on
  `String()` coercion.
- `V:438-444` — generic `VolField` fallback renders bare `<input>` with no `type="number"`/validation; presets render
  for a key (`V:441`) whose registry entry may not define them.
- `V:599` / `V:851-859` — drawing canvas and corr-movie controls have no keyboard path; `V:453-475` dock drag-reorder
  is pointer-only with no keyboard alternative or order announcement.

---

## 4. Missing vs best-in-class

| Capability | Best-in-class reference | Volatility-v2 status |
|---|---|---|
| Estimator horse-race + efficiency ranking | quantstats `plots.snapshot` family; Yang-Zhang efficiency literature | Good: 5-estimator overlay + DM tournament + agreement index; weak: no efficiency-ratio panel |
| GARCH density diagnostics (QQ, PIT, Nyblom, NIC) | NYU V-Lab GARCH docs; `arch` package diagnostics | Good: QQ, PIT, NIC ribbon, Nyblom table, aparch-delta; missing: standardized-residual ACF + ARCH-LM panel |
| Volatility cone (realized vs implied) | TradingView IV-vs-RV cone scripts; vol-surface cone literature | Good realized cone with HIGH/LOW/NORMAL strip; missing: implied cone overlay (IV vs RV) |
| 3-D vol surface / term structure | TradingView surface indicators; Plotly surface | Weak in workbench (flat heatmap); full surface only as landing fiction |
| Regime probability stack + transition alerts | Markov-switching GARCH literature; V-Lab regime views | Good: stacked posteriors, dual smoothed/filtered, duration survival, sync index |
| Spillover network (Diebold-Yilmaz) | DY connectedness papers; frequency connectedness | Good: TCI, FEVD heatmap, to/from bars, frequency bands; weak: circle layout, no threshold control |
| Crosshair-quant workflow (crosshair + magnet + navigator) | TradingView lightweight-charts | Partial: good tooltips + `Brush` >252 rows, but no magnet/sync across cards |
| Tear-sheet export | quantstats `reports.html`; Riskfolio-Lib Excel reports | Good: workspace JSON + TSV book + per-card copy; missing: one-click HTML tear-sheet |
| Live updating dashboard | Streamlit/GARCH real-time dashboards | Missing: no polling/refresh; `compute_mode: realtime` default is UI-less and unimplemented |

---

## 5. Concrete steals (adopt, don't admire)

1. **TradingView lightweight-charts** (`github.com/tradingview/lightweight-charts`): crosshair + magnet + time-navigator
   for `VolChart`/`EstimatorComparison`/`ForecastBands`; synchronized crosshair across primary/compare lanes fixes the
   dead compare view. Cheaper than recharts layering and the desk-standard interaction.
2. **TradingView IV-vs-RV cone scripts** (MelangeResearch "IV vs RV Volatility Cones"): overlay an implied cone on the
   existing `VolatilityCone` (`V:785-814`); the percentile-band scaffolding is already there, only the second band set
   is missing.
3. **NYU V-Lab GARCH views** (`vlab.stern.nyu.edu/docs/volatility/GARCH`): standardized-residual ACF + ARCH-LM +
   news-impact asymmetry summary as three small panels next to `news-impact`/`qq-plot`/`pit-test`. Turns the GARCH
   suite from scoreboard into diagnostics.
4. **quantstats `reports.html` / `compare()`** (`github.com/ranaroussi/quantstats`): one-click HTML tear-sheet for
   `ExportModal`, and the overlay-plus-delta-table pattern for compare lanes.
5. **Riskfolio-Lib Excel reporting** (`riskfolio-lib.readthedocs.io`): per-output-sheet workbook export already
   prefigured by the TSV book; add sheet-per-section + parameter cover sheet.
6. **Portfolio-v2's own `CommandPalette` + `InspectorDrawer`** (numeric profile + lineage + raw JSON): the vol
   workspace search finds sections but has no per-card numeric-profile inspector; port it rather than reinventing.
7. **Vol-v2's own landing force layout** (`LH:689-761`, d3-force): promote into workbench `NetworkGraph` with a
   threshold slider replacing `slice(0, 80)`.

---

## 6. Primitive-vs-registry sync plan (minimal, ordered)

1. **Wire execution (P0).** Give every `F` page an `onRun` that POSTs to `/api/labs/volatility/v2/feature/{id}/run`
   (portfolio-v2's `runEngine` is the template) or passes a prefetched `response`. Until this lands, hide/disable
   Run + Compare instead of toasting a dead end.
2. **Registry completeness.** Every `defaults` key gets a field descriptor (add an `advanced` group for
   `compute_mode`-style flags); resolve `window_days` vs `rolling_window`; keep numerics numeric in form init.
3. **Contract assertion.** Assert `VOLATILITY_OUTPUT_BOOKS` keys against the API manifest per feature; `VolEmpty`
   already lists available keys, so surface mismatches instead of silently rendering fallbacks.
4. **Shared kit with portfolio-v2.** One table (vol's `VolTable`), one network (force layout), one inspector
   (portfolio's drawer), one delta-compare lane. Delete the weaker twin in each pair.
5. **Truthfulness sweep.** `Spark` takes trailing series or is deleted; landing pills bind to cached runs or carry an
   `ILLUSTRATIVE` badge; gauge zones/normalization made per-metric explicit.
6. **Renderer hardening.** Cap `inferKeys` auto-series with a picker; type-guard `FrequencyBands`/`ComposedBars`/
   `SurfaceGrid` inputs with visible errors; sanitize gradient IDs.

---

*Review method: static read of all files above, no edits made. Line numbers refer to the repo state at review time.
External benchmarks verified via web search/fetch on 2026-09-29 (quantstats GitHub, Riskfolio-Lib docs, TradingView
lightweight-charts repo + cone scripts, NYU V-Lab GARCH docs).*
