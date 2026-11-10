# Screener: built, needs a check on the page

Written and typechecked, not yet seen in the browser. Tick after a look on the page.

| Done | Plan item | Where | Commit |
|---|---|---|---|
| [ ] | Column sets as tabs: Overview, Performance, Valuation, Growth, Health, Technical, Scores, Trust | `kit/DataTable.tsx`, `screener/views.tsx` | table-1 |
| [ ] | Search within results, row count | `kit/DataTable.tsx` | table-1 |
| [ ] | Auto-hide wholly empty columns, muted missing values | `kit/DataTable.tsx` | table-1 |
| [ ] | Sticky median footer | `kit/DataTable.tsx` | table-1 |
| [ ] | Monogram tile on ticker, sector pill, company ellipsis | `kit/DataTable.tsx`, `tables.css` | table-2 |
| [ ] | Multi-sort: shift-click adds a second key, marked "2" | `kit/DataTable.tsx`, `tableView.ts` | table-2 |
| [ ] | Bulk select with checkbox column; Watchlist, Alert, Rank, Test, ML, copy tickers, CSV | `kit/DataTable.tsx`, `screener/RowActions.tsx`, `screenerLab.ts` | table-2 |
| [ ] | Ticker column stays frozen beside the checkbox column | `tables.css` | table-2 |
| [ ] | Strategies (sc04) page under Rank: picks table with bulk actions, strategy select | `screenerLab.ts` | strategies |
| [ ] | Piotroski nine-check matrix: pass, fail, unknown, score out of known | `rank/StrategyViews.tsx` | strategies |
| [ ] | Altman zone pills and strip with 1.81 and 2.99 cut lines; dots open the drawer | `rank/StrategyViews.tsx` | strategies |
| [ ] | Altman Z 8-quarter line renders (data often null for recent quarters) | `screenerLab.ts` | strategies |
| [ ] | Test: monthly return heatmap with year total and SPY year, beat marks | `test/TearSheet.tsx` | tearsheet |
| [ ] | Test: daily return histogram vs SPY, median and 5% worst day | `test/TearSheet.tsx` | tearsheet |
| [ ] | Test: underwater drawdown strip, worst and current | `test/TearSheet.tsx` | tearsheet |
| [ ] | Same output key used by several cards on one page renders each | `screenerLab.ts` | tearsheet |
| [ ] | Live pass count "N of M pass" in the filter bar, debounced 350 ms | `filters/Preview.tsx`, `UniverseBar.tsx`, `POST /filters/preview` | filters-1 |
| [ ] | Removed count on each active pill | `UniverseBar.tsx` | filters-1 |
| [ ] | Pill editor: real distribution histogram, kept names in blue, two-handle slider, median, known count | `filters/Preview.tsx` | filters-1 |
| [ ] | Preview panel cache: first edit about 3 s on 200 names, later edits instant | `core/explain.py` | filters-1 |
| [ ] | Add-filter overlay: search, groups (Market, Valuation, Profitability, Growth, Health, Dividends, Performance, Technical, Score), recent, starred; pick opens the histogram editor | `filters/AddFilter.tsx` | filters-2 |
| [ ] | Exact values and top N still reachable under the overlay | `UniverseBar.tsx` | filters-2 |
| [ ] | Category pills in the bar: Sector, Industry, Country, Exchange, Currency with searchable checklist and counts; live pass count updates | `UniverseBar.tsx`, `InFilter.tsx` | filters-3 |
| [ ] | Pill editor footer: removed and left counts, Clear | `UniverseBar.tsx` | funnel |
| [ ] | Funnel: shrinking bars per filter, removed count, bottleneck in amber | `views.tsx`, `screen.css` | funnel |
| [ ] | Drawer: strength radar beside score bars; unknown axes dashed | `kit/QuickLook.tsx`, `quicklook.css` | drawer-1 |
| [ ] | Drawer statements: trend sparkline and YoY per line (quarterly compares 4 back) | `kit/QuickLook.tsx` | drawer-2 |
| [ ] | Not built yet: common-size toggle on statements (plan line ticked for sparklines and YoY only) | — | drawer-2 |
| [ ] | Monitor: alert feed with severity edge, direction, type pill, ticker opens drawer | `monitor/MonitorViews.tsx` | monitor-1 |
| [ ] | Monitor: hit-rate scorecards per alert type at 1d, 5d, 21d with 50% mark and n | `monitor/MonitorViews.tsx` | monitor-1 |
| [ ] | Monitor layout: Alerts and Track record tabs; watchlist table tinted with row actions | `screenerLab.ts` | monitor-1 |
| [ ] | Saved: card grid, search, sort, schedule pill (manual, interval, error), settings as pills; open card spans full width | `saved/SavedPage.tsx`, `saved.css` | saved-1 |
| [ ] | Chart grid view (View menu on results and rankings): card per name with 3M trend, 1M move, price, score; opens drawer; first 120 | `views.tsx`, `screen.css` | grid-1 |
| [ ] | Open: Backtest 61 s on 12 names (405 point-in-time panels across 14 sensitivity runs); needs a vectorised multi-date panel | backend | — |
| [ ] | F opens the filter picker (not while typing) | `UniverseBar.tsx` | keys-1 |
| [ ] | Valuation: four gauges (history, sector, peers, universe), multiples grid, re-rating pill | `valuation/ValuationViews.tsx` | valuation-1 |
| [ ] | Valuation: card grid for every name, sortable by each frame | `valuation/ValuationViews.tsx` | valuation-1 |
| [ ] | Valuation layout: Focus, Universe, Peers tabs | `screenerLab.ts` | valuation-1 |
| [ ] | Gauge direction: confirm whether a high percentile means cheap or expensive and label it | `valuation/ValuationViews.tsx` | valuation-1 |
| [ ] | Composite: ranking as stacked factor bars (weight × score), legend with weights, effective factors | `rank/FactorStack.tsx` | composite-1 |
| [ ] | Composite: Table tab, redundancy alerts and weight training on Weights, new Breakdown tab (sector, regime) | `screenerLab.ts` | composite-1 |
| [ ] | Sector composite average is null for some sectors (seen on Communication Services, 26 names): check backend | backend | composite-1 |
| [ ] | Formula: template gallery cards, Use puts the expression in the formula box, current marked | `formula/FormulaViews.tsx` | formula-1 |
| [ ] | Formula: status list (ok, warn, error) above results; Backtest tab with drawdown; table with bulk actions | `screenerLab.ts` | formula-1 |
| [ ] | Test Holdings tab: attribution diverging bars (best and worst 12), holdings Gantt (open ones marked), trade log | `test/TearSheet.tsx`, `screenerLab.ts` | test-2 |
| [ ] | Test Rebalancing tab now includes weekday sensitivity | `screenerLab.ts` | test-2 |
