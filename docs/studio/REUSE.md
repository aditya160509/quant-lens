# Studio v3: what to reuse

Date: 2026-11-15. Rule: copy or import what already works in Screener, Research and ML; write new code only where nothing fits. Paths checked in the repo on this date. "Import" = use as is; "Lift" = move to a shared place first, then import from both; "Pattern" = copy the shape, write Studio's own.

## 1. Frontend: the lab shell (import, no new shell)

Studio is the fourth lab on the shared workspace, configured like `screener/screenerLab.ts`.

| What | Path | Use |
|---|---|---|
| Lab config (pages, nav, palette, submit) | `modules/research/lab.ts`, `modules/screener/screenerLab.ts` | Pattern: `studioLab.ts` with pages Home, Build, Test, Validate, Understand, Live, Chart |
| Workspace app (panels, phone branch, inspector host, dock, runs) | `modules/research/ResearchApp.tsx`, `workspace/WorkspaceShell.tsx`, `workspace/layout.ts`, `workspace/panels.ts` | Import |
| Feature page (hero, run header, tabs, sticky glass bar, print, palette entries) | `modules/research/FeatureView.tsx` | Import |
| Inspector + study form (inputs from manifest, Customised marker, defaults menu, undo/redo) | `modules/research/Inspector.tsx`, `StudyForm.tsx`, `Customised.tsx`, `formHistory.ts` | Import |
| Output cards (menu, duplicate, chart settings, table view, maximise) | `modules/research/OutputCard.tsx`, `cardPrefs.ts`, `layouts.ts` | Import |
| Output registry and explore controls (range, mark a level, one colour) | `modules/research/outputs/registry.tsx`, `outputs/explore.tsx` | Import; register Studio views with `registerViews` |
| Hero (figure, versus, lines, bars, stack) | `modules/research/Hero.tsx` | Import; add a `fan` (bands) kind for Monte Carlo |
| Compare runs (settings changed, numbers, curves overlaid) | `modules/research/RunCompare.tsx` | Import |
| Share page and embed | `app/share/[token]/` | Pattern: `/share/<token>` already renders screens; extend for strategies |
| Run API hooks, job polling, runs store, manifest | `modules/research/api.ts`, `store.ts` | Import |
| Formatting (labels, acronyms, %, fractions) | `modules/research/format.ts` | Import; add Studio acronyms (MAE, MFE, WFE, PBO, DSR, PSR, SQN, CAGR already) |

## 2. Frontend: views and charts (import)

| What | Path | Studio output |
|---|---|---|
| DataTable (virtual rows, column sets, freeze, bars, status pills, row cache, compare, CSV) | `kit/DataTable.tsx`, `kit/tableView.ts` | Trade list, windows table, top sets, signals today |
| KPI strip | `kit/KpiStrip.tsx` | Key stats |
| Compare view (tick rows, press C) | `kit/Compare.tsx` | Compare strategies |
| Quick look drawer | `kit/QuickLook.tsx` | Click a symbol anywhere |
| Monthly heatmap, return histogram, underwater, drawdown story, horizon table, yearly vs benchmark, weekly heatmap | `modules/screener/test/TearSheet.tsx` | st01 returns, drawdown |
| Drawdown strip, holdings timeline | `charts/Backtest.tsx` | st01 holdings |
| Backtest replay ★, funnel story, sorting field | `modules/screener/Story.tsx` | st01 replay, st09 map |
| Heatmap, Distribution, Forest, Dendrogram, Treemap, Waterfall, XYPlot, TimeSeries, StackedArea, SpecCurve, PointRange, Radar, CalendarHeatmap | `charts/*.tsx` | st02 map, st04 histograms, st05 bands, st06 forest, st08 correlation |
| Robustness views | `modules/research/outputs/robustness.tsx` | st04 tiles (pattern) |
| Specification curve | `modules/research/outputs/plots.tsx` (`SpecificationCurveView`) | st02 equity fan / sorted outcomes |
| Formula bar (autocomplete, status, templates) | `modules/screener/formula/*` | Build → Formula |
| Palette actions | `modules/screener/palette.ts`, `search/SearchOverlay.tsx` | Studio actions |
| Saved page (cards, mini result, folders, schedule pill) | `modules/screener/saved/SavedPage.tsx` | Studio Home |
| Alert feed, hit rates | `modules/screener/monitor/*` | Paper drift alerts |
| Price chart (candles, SMA, volume) | `charts/PriceChart.tsx` | Mini preview in Build until the chart rebuild lands |
| Monaco | `@monaco-editor/react` (installed) | Build → Python |

## 3. Frontend: the chart engine (dissect, keep the maths)

| Keep | Path | Into |
|---|---|---|
| 71 indicators | `components/chart_engine/IndicatorEngine/registry.ts` | `charts/studio/indicators/` as pure functions, unit-tested against the backend versions |
| Drawing geometry (lines, fib, gann, patterns, measurement, text, projections, volume) | `components/chart_engine/DrawingEngine/*` | `charts/studio/drawings/` as lightweight-charts primitives |
| Candlestick pattern detectors | `PatternScanner/candlestickPatterns.ts` | `charts/studio/patterns.ts` |
| Pane renderer ideas | `IndicatorPaneRenderer.tsx` | Rewritten on lightweight-charts panes |
| Not kept | `q360_chart_core.tsx`, `ChartCanvas/index.tsx`, `DataAdapter/*` (yfinance), `AlertEngine` (`localStorage`), `StrategyEngine/strategies.ts` (replaced by the spec) | Deleted in phase 7 |

## 4. Backend (import or lift)

| What | Path | Studio use |
|---|---|---|
| Price and fundamentals loader, PIT, currency | `services/screener_v2/core/data_loader.py`, `fundamentals.py`, `currency.py` | `studio_v3/core/data.py` wraps it |
| Portfolio backtest (next-close execution, drifted weights, delisted → cash, costs) | `services/screener_v2/core/backtest.py` | Cross-check for the vector engine; portfolio mode of st01 |
| Validation panel cache, score cache | `services/screener_v2/core/validation.py` | Pattern for caching signals across sweep runs |
| Formula language (safe `ast`, whitelist, time-series and cross-sectional ops, PIT fields) | `services/research_v2/core/signal_lang.py` | Lift to `services/shared/formula/`; Studio and Research import it |
| Screener formula + plain English → formula | `services/screener_v2/core/formula.py`, `nl_formula.py` | Build → Plain English |
| Regimes | `services/research_v2/core/regime.py`, `ml_v2/core/regimes.py` | st07 |
| Hold-out, placebo, robustness, specification curve | `services/research_v2/core/holdout.py`, `placebo.py`, `robustness.py`, `specification.py` | st04 vs random, st06 hold-out log |
| CPCV, purged splits | `services/ml_v2/core/cpcv.py`, `validation.py` | st06 |
| Stats (PSR/DSR if present, bootstrap) | `services/research_v2/core/stats.py`, `ml_v2/core/stats.py`, `screener_v2/core/stats.py` | `core/overfit.py`; check for duplicates first and keep one |
| Performance metrics | `services/screener_v2/core/performance.py`, `research_v2/core/performance.py`, `ml_v2/core/performance.py` | One canonical `core/metrics.py`; the three labs then import it (merge, not a fourth copy) |
| Allocation (inverse vol, risk parity, HRP) | `services/ml_v2/core/allocation.py`, `portfolio_v2/` | st08 |
| Jobs, state DB, shares, exports PDF, scheduler, alerts, notify, snapshots | `services/screener_v2/core/state.py`, `shares.py`, `exports.py`, `scheduler.py`, `alerts.py`, `notify.py`, `snapshots.py` | Saved strategies, share, certify PDF, paper schedule, drift alerts |
| Registry and manifest pattern | `services/screener_v2/registry.py`, `features/inputs.py` (`_label`, input specs) | `studio_v3/registry.py` |
| Docker sandbox idea | `services/studio/execution.py` | Rewritten in `core/sandbox.py` (idea only) |

## 5. Tests and tooling (import)

- Backend tests: `backend/tests/test_screener_v2_math.py` style: tiny hand-built price frames with exact expected numbers.
- Visual baselines: add Studio pages to `PAGES` in `frontend/e2e/research.spec.ts`.
- Benchmarks: the scratch scripts used for Screener (table scroll frames, click-to-paint, screen job timing) become `frontend/e2e/perf/` checks for Studio's trade list and sweep page.

## 6. Merge first (one-time, before Studio uses them)

Three copies exist of performance metrics and stats across labs. Studio must not add a fourth. Phase 1 starts by choosing one canonical `metrics.py` and pointing the other labs at it, with each lab's tests green.
