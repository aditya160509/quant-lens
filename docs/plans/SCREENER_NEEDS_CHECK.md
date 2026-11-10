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
