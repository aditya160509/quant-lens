# Studio v3: frontend plan

Date: 2026-11-15. From scratch, on the shared lab workspace. Style: Outputs v2 (fewer, bigger, cinematic; one lead figure per card; limits in one pill). Every page, input and output is listed in [FEATURES_AND_OUTPUTS.md](FEATURES_AND_OUTPUTS.md); what is imported is in [REUSE.md](REUSE.md). This file covers the screens, the interaction and the budgets.

## 1. Shape

Studio is the fourth lab, configured by `frontend/src/modules/studio/studioLab.ts` the way `screenerLab.ts` configures Screener. It gets the workspace for free: left nav, center results, right inspector, bottom dock (runs and log), palette (⌘K), runs pill, share, export, phone branch.

Routes, nav and every page's tabs and heroes: [PAGES.md](PAGES.md) §0 (one entry `frontend/src/app/studio/[[...slug]]/page.tsx`). Nav: `Home · Build · Test (Backtest, Optimise, Validate) · Portfolio · Live · Chart · Library`.

Every run page reads `?strategy=<id>@<version>&run=<job>`; the strategy picker sits in the run header so any page can switch strategy without going back to Build.

## 2. The run pages

All use `FeatureView` unchanged: title, status, strategy chip, sub-tabs, Save/Share/Export/Run; hero; KPI strip; limits and freshness pills; My limits strip; section tabs; cards. New hero kinds go into `modules/research/Hero.tsx` (shared): `heatmap`, `tiles`, `fan`, `gauge`, `grade`, each with a still render for Reduce motion and print.

## 3. Build

Three panes inside the center island; inspector closed by default (Settings button opens run settings).

```
┌ Strategy name · v7 · saved 2m ago · 1,840 trials ───────── Versions ▾  Run backtest ⌘↵ ┐
│ [ Blocks | Formula | Python | Plain English ]                                          │
│ ┌ editor ─────────────────────────────┐ ┌ preview ─────────────────────────────────┐   │
│ │ When  [SMA 50] crosses above [SMA 200]│ │ AAPL · 2 years · signals on price         │   │
│ │ Then  Buy  [10% of equity]            │ │ ▲ ▼ markers, entry/exit lines             │   │
│ │ Exit  Trailing stop [8%]              │ │ 14 trades · +31% · updates as you type    │   │
│ │ + Add rule                            │ └───────────────────────────────────────────┘   │
│ └───────────────────────────────────────┘ ┌ checks ─────────────────────────────────┐    │
│ Parameters: fast 50 [20–100] · slow 200 [100–300] · stop 8% [3–15]  │ ✓ No look-ahead (repaint check, 50 cuts) │
│                                                                      │ ⚠ Exits fire on 3% of bars │
└──────────────────────────────────────────────────────────────────────└──────────────────────────┘
```

- **Blocks:** rows, not a node graph ("when … then …", "exit …", groups with and/or). Each block is a combobox (indicator, field, operator, value or parameter). Drag to reorder. Keyboard: Tab through slots, Enter adds a row.
- **Formula:** reuse the Screener formula bar (autocomplete, inline errors, templates); one line per rule role (entry long, exit long, entry short, exit short, size).
- **Python:** Monaco with a typed `ctx` (`ctx.close[-1]`, `ctx.position`, `ctx.order(...)`), snippets, format on save; errors from the server compile map to Monaco markers.
- **Plain English:** a text box; the result appears as formula and blocks for review; nothing runs until the user accepts it.
- **Switching:** Blocks ⇄ Formula both ways; Formula → Python one way (generated code shown, original kept).
- **Preview:** the mini chart (current `charts/PriceChart.tsx` until the chart rebuild lands), throttled to 300 ms after typing stops; shows the first symbol of the universe, last 2 years.
- **Checks:** the repaint check, lint and the trial counter, each a row with a fix link.
- **Versions:** drawer; every save immutable; diff any two (rules or code side by side, results side by side).

## 4. Trade list (the most-asked-for view)

- DataTable, virtualised, all trades (no trimming).
- Column sets: Overview (entry, exit, side, P&L, %, bars), Excursion (MAE, MFE, edge ratio), Costs (commission, slippage, borrow), Context (regime at entry, signal value).
- Row click: opens the trade on the Chart page, zoomed to entry−20 bars … exit+20 bars, with stops and targets drawn.
- "Carried by" strip above the table: top 1/5/10 trades' share of profit; toggle "hide top 5" recomputes the KPI strip client-side.
- Compare: tick trades, press C: overlay their price paths aligned at entry (new `TradePaths` view).

## 5. Chart (rebuilt)

One component, `charts/studio/StudioChart.tsx`, on lightweight-charts 5 panes. Fed only by `/api/studio-v3/bars`.

| Part | Plan |
|---|---|
| Layout | Price pane + volume + up to 4 indicator panes; resizable; 1–4 chart grid with synced crosshair and time |
| Indicators | Ported from `chart_engine/IndicatorEngine/registry.ts` as pure functions; a picker with search and favourites; each indicator's values testable against the backend formula engine |
| Drawings | Ported geometry from `chart_engine/DrawingEngine/*` as lightweight-charts primitives; toolbar with the 12 most used, the rest in a menu; drawings saved per symbol on the server |
| Strategy overlay | Entry/exit arrows, stop and target lines, position shading, signal pane; toggle per strategy; two strategies at once in two colours |
| Trade navigator | ← → steps through trades; trade card floats with P&L, MAE, MFE, exit reason |
| Replay ★ | Bar-by-bar play, pause, speed 1×–20×, scrub; equity and position update live under the chart |
| Patterns | Ported candlestick detectors; a legend lists every pattern looked for and says "not found" (TrendSpider idea) |
| Alerts | Created on the chart, stored and evaluated on the server (Screener alerts + notify) |
| Compare symbols | Rebased overlay, % scale |
| Timeframes | 1d, 1h where held, weekly and monthly resampled; multi-timeframe badge on indicators |

## 6. The cinematic set (Studio)

Each one is real data, has a still fallback and respects Reduce motion.

| # | Moment | Where |
|---|---|---|
| S1 | Equity draws left to right against the benchmark, drawdowns shade as they happen | Backtest hero (C1 pattern) |
| S2 | Replay on price: trades pop in at their bars, holdings fly in and out | Backtest hero action (`R`), Chart |
| S3 | Monte Carlo fan blooms from the original curve, percentile labels settle | Backtest > Paths |
| S4 | Walk-forward windows sweep across the timeline (optional) | Validate > Walk-forward |
| S5 | Heatmap plateau outline draws in; 3D surface lazy, off by default | Optimise |
| S6 | Robustness tiles flip to pass or fail one by one as the jobs finish (live, from SSE) | Validate > Robustness |
| S7 | Grade reveal: tests feed the dial, the letter lands with its one-line reason | Validate > Verdict |

## 7. Interaction rules

- **Keyboard:** ⌘↵ run; ⌘S save version; `[` `]` previous and next section; `C` compare picked rows; `R` replay; `T` jump to trades; `G` go to the chart for the selected trade; Esc closes drawers.
- **Palette (⌘K):** every page, every saved strategy, "new strategy from template…", "run robustness on this strategy", "compare with previous run", "copy link with these settings", "export one-page PDF".
- **Compare:** any two runs, versions or strategies (RunCompare); up to 8 strategies (Compare view).
- **Long jobs:** stages with counts ("Noise test 312 / 500"), cancel, and a stale marker when settings change after the run (FeatureView already does this).
- **Skipped:** a test that cannot run shows "skipped, because …" (no data, too few trades), never a blank card.
- **Unknown stays unknown:** a metric we cannot compute shows "—" with the reason in the tooltip.

## 8. Budgets (tested, not hoped)

| Action | Budget | How measured |
|---|---|---|
| Compile on keystroke | < 100 ms server, < 150 ms round trip | API timing test |
| Build preview refresh | < 300 ms after typing stops | Playwright, in-page timing |
| Backtest, 1 symbol 10 years daily | < 1 s end to end | `screen_time.sh` pattern |
| Backtest, 500 names 10 years | < 5 s cold | same |
| Trade list 10,000 rows | scroll median ≤ 16.7 ms a frame | `tablebench.mjs` pattern |
| Chart 10 years daily + 3 indicators | first paint < 400 ms | Playwright |
| Tab switch, menu, palette | < 70 ms click to paint | `tablebench.mjs` in-page timing |

## 9. New components (everything else is imported)

`modules/studio/`: `studioLab.ts`, `build/BlockEditor.tsx`, `build/CodeEditor.tsx` (Monaco wrapper), `build/Checks.tsx`, `build/Versions.tsx`, `views/*.tsx` (Studio output views: `CarriedBy`, `FillCheck`, `CrisisEvents`, `ParamMap`, `ParamSurface`, `WindowsSweep`, `WfMatrix`, `RobustTiles`, `McFan`, `PboView`, `GradeCard`, `RegimeBars`, `TradePaths`), `charts/studio/*` (chart rebuild).

## 10. Phone (phase 8; Live is phone-first from phase 5)

Shared with Screener's phone-1 item: bottom nav, settings as a bottom sheet, card rows for tables. Build on phone is Formula and Plain English only (blocks and Monaco are desktop).

## 11. Tests

- Visual baselines: every Studio route in `frontend/e2e/research.spec.ts` `PAGES`, dark and light.
- Interaction: Build → run → trades → click trade → chart shows that trade (one e2e flow).
- Budgets in section 8 as Playwright checks under `frontend/e2e/perf/`.
