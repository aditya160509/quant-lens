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
| [ ] | Overview: search box opens the shell search | `home/ScreenerHome.tsx` | overview-1 |
| [ ] | Overview: breadth strip (advancers/decliners bar, near 52w high and low, sector 1M chips that open Screen filtered) from `GET /breadth` | `ScreenerHome.tsx`, `core/explain.py` | overview-1 |
| [x] | Data: market cap filled for only 125 of the top 500 liquid names; fixed to 499 in 4c7539a | backend | overview-1 |
| [ ] | Overview: Your screens (last 6 saved) load into their page | `home/ScreenerHome.tsx` | overview-2 |
| [ ] | Shell nav: coloured icon tile per section, accent bar on active, light theme variant | `workspace/workspace.css` | shell-1 |
| [ ] | Toasts: saved, failed (replaces alert), copied tickers, Markdown, link, view saved, watchlist and alert adds, template used | `SavedPage`, `RowActions`, `DataTable`, `FormulaViews` | shell-2 |
| [ ] | Auto run toggle: re-runs 0.9 s after edits stop, only at 250 names or fewer, remembered on device; disabled above 250 | `UniverseBar.tsx` | run-1 |
| [ ] | Failure card: one-click fixes (remove unavailable filter, raise cap, drop historical sector filter, liquidity universe); then Run | `FeatureView.tsx`, `lab.ts`, `screenerLab.ts` | run-2 |
| [ ] | Universe sector mix as a thin stacked bar beside the pass count (from preview mix) | `filters/Preview.tsx`, `core/explain.py` | universe-1 |
| [ ] | Treemap: open a sector, "Filter to {sector}" sets the Sector filter (live count updates, Run or Auto applies) | `charts/Treemap.tsx`, `screener/views.tsx` | chart-filter-1 |
| [ ] | Phone: filter bar scrolls sideways with a fade cue instead of wrapping | `universe.css` | phone-1 |
| [ ] | Bulk action Universe: selected names become the Screen universe | `RowActions.tsx` | universe-2 |
| [ ] | Context bar: Rebalance (weekly, monthly, quarterly) and Top N (10, 20, 50, 100) segments where the study has them | `UniverseBar.tsx` | period-1 |
| [ ] | Overview sector treemap: size is name count (not market cap yet), colour is median 1M return; opening a sector offers Filter to it | `ScreenerHome.tsx` | overview-3 |
| [ ] | Nav collapses to a 52px icon rail with tooltips; ⌘B still toggles; width remembered | `ResearchApp.tsx`, `panels.ts`, `workspace.css` | shell-1 |
| [ ] | Screen page opens with the inspector shut | `ResearchApp.tsx`, `screenerLab.ts` | shell-2 |
| [ ] | Runs pill bottom-right while the dock is shut; click opens the dock | `ResearchApp.tsx` | shell-3 |
| [ ] | Keys: `[ ]` change page, Esc closes dock then inspector (a maximised card wins Esc), Shift+F filters, F opens table columns | `ResearchApp.tsx`, `FeatureView.tsx`, `UniverseBar.tsx`, `DataTable.tsx` | shell-4 |
| [ ] | Light theme: home icon tiles, filter pill values, universe monograms readable | `home.css`, `universe.css` | shell-5 |
| [ ] | Overview gallery, sector and saved-screen clicks run on arrival (`?go=1` dropped after) | `ScreenerHome.tsx`, `ResearchApp.tsx` | gallery-1 |
| [ ] | Universe picker: rename and delete saved universes, exclude box, Share link, "full" at 1,000 | `UniverseBar.tsx`, `api/screener_v2.py` | universe-3 |
| [ ] | Filter bar: hide/show toggle, Save as screen, preset chips from saved screens | `UniverseBar.tsx` | filters-1 |
| [ ] | Card menu: Copy as Markdown, Export TSV; PDF via Report | `OutputCard.tsx` | export-1 |
| [ ] | Status pill, as-of date and name count beside the page title | `FeatureView.tsx` | header-1 |
| [ ] | Method footnotes on Piotroski, Altman and Proof cards | `screenerLab.ts`, `Exhibit.tsx` | note-1 |
| [ ] | An output returned empty shows "No rows for …" | `OutputCard.tsx` | empty-1 |
| [ ] | Overview: treemap Market cap / Names toggle; Sectors by size matrix (1D/1W/1M); Breadth 1 year (SPY over net advancers and net highs); Recent runs with change | `home/ScreenerHome.tsx`, `home/OverviewCharts.tsx` | overview-4 |
| [ ] | Universe picker: Rank by liquidity, market cap, coverage; Primary listing only; market and cap-band presets toggle; title says "by market cap" | `UniverseBar.tsx` | universe-4 |
| [ ] | Run-time estimate "≈Ns" beside the pass count after one run | `UniverseBar.tsx` | universe-5 |
| [ ] | Period: Max and Custom start and end, names-per-year strip lit for the range | `UniverseBar.tsx`, `/data-range` | period-2 |
| [ ] | Filter popover: On switch keeps bounds (pill struck through), Remove; Cmd+Z and Shift+Cmd+Z undo and redo form edits | `UniverseBar.tsx`, `ResearchApp.tsx` | filters-2 |
| [ ] | Table: number format per column (1.2B, %, 0.00, $) with decimals; Top / bottom N; drag headers to reorder; double-click grip to fit; ticker and company frozen | `DataTable.tsx` | table-2 |
| [ ] | Screen results: Trend sparkline column with 1M/3M/1Y | `views.tsx`, `/sparklines` | table-3 |
| [ ] | Drawer: candles, volume pane, SMA 50/200 (theme colours in light and dark); header price, change, follow, alert, add to screen; ratio cards with Edit ratios | `QuickLook.tsx`, `charts/PriceChart.tsx` | drawer-1 |
| [ ] | Test: By horizon, Losing streaks, Worst drawdowns, Weekly returns, Each year against SPY | `test/TearSheet.tsx` | test-1 |
| [ ] | Saved: schedule segments and every N hours, next run, failure pill; names-passing timeline | `saved/SavedPage.tsx` | saved-2 |
| [ ] | Palette (⌘K): Add filter, saved screens, templates, popular stocks, preferences save/load/export/import | `palette.ts`, `WorkspaceShell.tsx` | palette-1 |
| [ ] | Skeletons on Overview and Saved; no jump when data lands | `ScreenerHome.tsx`, `SavedPage.tsx` | skel-1 |
| [ ] | One-row header: title, status, sub-tabs, Save, Share, Export, Run | `FeatureView.tsx` | header-2 |
| [ ] | Defaults menu: Make these my defaults, Reset to my defaults, Reset to built-in; card menu: Reset this card, Reset every card | `StudyForm.tsx`, `OutputCard.tsx` | defaults-1 |
| [ ] | Phone (later): page no longer blank (`.ws-mobile` had zero height); bottom nav; Settings opens the study form as a bottom sheet; floating section bar shows tabs only. Still to do: virtual tables (>200 rows) as card rows, long `?form=` URL | `ResearchApp.tsx`, `workspace.css`, `Inspector.tsx` | phone-1 |
