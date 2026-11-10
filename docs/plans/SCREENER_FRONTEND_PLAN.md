# Screener frontend plan

Date: 2026-11-09. Scope: every Screener page, component and output. Status is tracked by the boxes. A box is ticked only after it is seen working on the page with real results.

## 1. What we want

The best screener a serious investor can use: as fast to start as Finviz, as flexible as TradingView, as deep as Koyfin and Portfolio123, and more honest than any of them. Dark, alive, dense, and every result can be reshaped by the user.

Quality bar: the fintech dashboard reference from the owner. Near-black canvas, bordered rounded cards, big confident numbers, a small real graphic in each card, coloured status pills, labelled navigation, one vivid blue action.

Rules:
- Real data only. A missing value is shown as missing, never invented.
- Filters and universe are the page. They are never hidden in a side panel.
- Every output answers one question at a glance, then opens up for detail.
- Colour carries meaning: blue action, green and red direction, heat for rank, amber caution, purple and teal for categories.
- No taglines, helper paragraphs or question subtitles. Labels only; depth goes in tooltips.
- Every number states its as-of date somewhere on the result.
- Default 500 names, hard cap 1,000.
- Speed targets: page load under 1 s, Screen on 50 names about 1 s, on 500 names under 3 s, Composite on 50 names under 2 s.

## 2. What we learned from the market

| Source | Take | Do not take |
|---|---|---|
| TradingView screener | Filter pills above the table, `+` and Shift+F to add, clickable screen title holding open/save/recent/export, market picker with multi-select, primary-listing toggle, column sets, per-column interval settings, base currency, auto-refresh, hide filters, chart-grid view | Forecast and extended-hours sets: we have no such data |
| Finviz | Filter groups as tabs, view tabs over one table, coloured numbers, Add to / Compare / Set Alert / Export above the table, sector treemap | Dated visual style |
| Koyfin | Historical values inside filters and formulas, custom formula columns, save a screen as a watchlist, templates | 5,900 filters: we have about 70 |
| Stock Rover, Portfolio123 | Many pre-built screens, custom views, ranking systems, rank tolerance, a screen as a backtestable strategy | |
| Simply Wall St | One picture of a company's strengths, filter by that picture | Fixed one-size scoring |
| StockAnalysis | Clean paging and rows-per-page, large popular-screens access | Light theme |
| Screener.in | Screens gallery by theme, sector chips, company page with ratio grid and range-tab chart, add a ratio to a table, plain query language | Light theme |
| QuantStats, QuantConnect reports | Tear sheet: cumulative, drawdown, monthly heatmap, return distribution, rolling metrics | |
| Table UX guidance (NN/g, Setproduct and others) | Find, compare, view a row, act on rows; frozen identity column, density, bulk actions | |

Our own advantage, shown everywhere: why a stock passed or failed, near misses, point-in-time backtests, overfitting checks, data coverage on each result.

## 3. Shell

- [x] Near-black palette, blue primary, KPI cards
- [x] Left nav open by default with Overview, Screen, Rank, Test, Monitor, Saved, More
- [x] Coloured icon tile per section; active item with accent bar; run status dot
- [ ] Collapsible to icons, with tooltips; width remembered
- [ ] One-row page header: icon, title, sub-tabs, Save, Share, Export, Run
- [ ] Inspector closed by default on Screen; opens for advanced settings only
- [ ] Runs dock collapsed to a status pill until opened
- [ ] Command palette: run, add filter, open any screen or stock, change theme
- [ ] Keyboard: Cmd+Enter run, Shift+F filter, F column, `/` search, `[ ]` pages, Esc close
- [ ] Skeletons matching final layout; no layout shift; no page-wide dim on navigation
- [x] Toasts for saved, failed, copied
- [ ] Phone layout: bottom nav, filter sheet, card rows
- [ ] Light theme kept working, dark the default

## 4. Overview page

- [x] Stat cards with real graphics: last screen, valuation ready, stocks covered, runs
- [x] Screens gallery by theme with colour per theme
- [x] Sector tiles with counts
- [ ] Check gallery and sector clicks end to end, and run on arrival
- [ ] Each gallery row shows live match count and top three names after first load
- [x] Search box as the page's main element
- [ ] Recent screens and saved screens with last result and change since last run
- [x] Market breadth strip: advancers, new highs, sector returns
- [ ] Sector treemap by market cap coloured by return
- [ ] Biggest entrants and exits across saved screens
- [ ] Pinned board of outputs, in cards

## 5. Control bar, every study page

### Universe picker
- [x] Clickable universe title opening a large search overlay
- [x] Search and add stocks, size 25 to 1,000, saved universes, watchlists, paste, save
- [x] Top N ranked by USD liquidity
- [ ] Rank basis: liquidity, market cap, or data coverage
- [ ] Presets: country, exchange, sector, industry, currency, market cap band
- [ ] Multi-select markets; primary listing only toggle
- [ ] CSV upload, exclude list, rename and delete saved universes
- [ ] Live name count and estimated run time before running
- [ ] Sector and country mix of the chosen universe as a small bar
- [ ] Share a universe by link; a screen's result becomes a universe
- [ ] Clear disabled state at the cap, with count

Index membership stays out until we have data for it; it must not be faked.

### Period
- [x] 6M to 10Y presets and as-of date
- [ ] Max and custom start and end with date picker
- [ ] Data availability shown on the range
- [ ] Rebalance frequency and holding period as segmented controls on Test
- [ ] Compare as-of dates

### Filters
- [x] Pill row with min and max and `+ Filter`
- [x] Add-filter overlay with groups, search, recently used and favourites: Identity, Market, Technical, Valuation, Profitability, Growth, Health, Dividends, Score
- [x] Pill editor: slider over the real distribution histogram, percentile mode, greater, less, between, in, top N
- [x] Live pass count and removed count on each pill; bottleneck marked
- [ ] Toggle, remove, reorder, duplicate; undo and redo
- [x] Category filters as searchable checklists: sector, industry, country, exchange, currency
- [ ] AND/OR groups, editable as tree and as formula
- [ ] Compare to another field: P/E below sector median, price above SMA 200
- [ ] Historical conditions: 5-year average, change over N periods
- [ ] Filter from a chart: brush a scatter, click a treemap sector, drag a histogram
- [ ] Natural language box producing editable filters
- [ ] Hide or show filters; save as a screen; preset chips

### Run
- [ ] One blue Run; auto-run option when a filter changes, debounced, on universes up to 250
- [ ] Progress by stage, cancel, stale marker
- [ ] Failure card with the reason and one-click fix

## 6. Table, used by every tabular output

- [x] Column sets as tabs: Overview, Performance, Valuation, Profitability, Growth, Health, Dividends, Technical, Scores, Trust, Custom; add own
- [ ] Column picker with search, groups and drag order; per-column interval where data supports it
- [ ] Frozen rank, ticker and company; sticky header; resize; reorder by drag; auto-fit
- [x] Multi-sort; sort by distance from a value
- [x] Monogram tile, ticker badge, company, sector pill
- [ ] Number format per column: compact, percent, decimals, currency; base currency switch
- [ ] Conditional formats per column: heat, bars, signed colour, rule, top and bottom N
- [ ] Sparkline columns with range choice
- [x] Muted missing values; auto-hide wholly empty columns; coverage in header
- [ ] Group by and pivot on any column, with count, median, mean, sum rows
- [x] Footer: median and universe median, sector median toggle
- [x] Bulk select: add to watchlist, compare, alert, send to Rank, Test, ML, export
- [ ] Row hover actions; row expand shows why it passed
- [ ] Density, rows per page, infinite or paged; virtual scroll to 1,000 rows without lag
- [x] Search within results; column quick filter from the header adds a pill
- [x] Chart-grid view of mini price charts
- [ ] CSV, Excel, TSV, tickers, copy, Markdown, PDF
- [ ] Save view for this screen or all; share by link; reset

## 7. Output card, every output

- [ ] Title, as-of and coverage in one row, status pill
- [ ] View menu with the alternatives below; choice remembered
- [ ] Settings: scale, range, colours, labels, benchmark, annotations
- [ ] Maximise, pin to board, change width, reorder, hide, duplicate
- [ ] Copy image, download PNG, SVG, CSV
- [ ] Hover crosshair; click drills into rows; brush filters
- [ ] Footnote naming the method, only where it matters
- [ ] Empty, partial and failed states with the reason

## 8. Stock drawer and compare

- [ ] Header: monogram, price, change, exchange, follow, alert, compare, add to screen
- [ ] Ratio grid with add ratio and edit ratios, percentile tick against sector
- [ ] Price chart with range tabs, Price and P/E modes, volume, moving averages, entry and exit marks
- [x] Strength profile: quality, value, momentum, health, growth as a radar we compute, with filter by shape
- [ ] Why here: filter, value, threshold, margin, sector percentile
- [ ] Peers, quarters, profit and loss, balance sheet, cash flow, ratios as tabs
- [x] Statement rows with sparklines, YoY, common-size toggle
- [ ] Compare up to 8 names: overlaid chart, side-by-side table, differences highlighted
- [ ] Full page with its own URL; PDF

## 9. Screen group

### Screen (sc01)

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| ranked_screener_table | Section 6 table, hero | Chart grid, scatter, treemap | Rank shift, trust badge |
| filter_funnel_waterfall | Horizontal funnel with removed count and bottleneck highlight | Table | Click a step to see what it removed; toggle a filter from the step |
| run_changes | Entered and left columns with pills | Table | Rank moves as arrows |
| metric_coverage | Coverage bars sorted worst first | Table | Warn on filters using weak fields |
| cross_sectional_percentile_context | Percentile strip per metric for the selected stock | Table, radar | Stock selector |
| heatmap_view | Sector × metric heatmap | Table, treemap | Metric picker, diverging scale |
| quick_look_card | Stock card | Key values | Opens drawer |
| market_cap_bucket_distribution | Bars by bucket | Donut, table | Click to filter |
| saved_screens | Card list | Table | Run, edit, schedule |

Added on the Results tab: scatter lens with x, y, size, colour; sector treemap; near-miss list with "relax this"; sensitivity strip.

### Formula (sc02)

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| formula_result_table | Section 6 table with score bar | Scatter, histogram | Formula as a new column |
| historical_formula_backtest | Equity against SPY with drawdown strip | Log scale, table | Same as Test card |
| formula_validation_panel | Inline editor errors, plus status list | Table | Jump to the error |
| formula_template_library | Gallery cards | Table | Insert into editor |

Editor: CodeMirror with autocomplete, field docs on hover, live preview count, named metrics, saved formulas, history, plain English to formula.

### Valuation (sc07)

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| four_dimension_valuation_card | Four gauges: vs history, sector, peers, universe | Key values | Hero, stock selector |
| own_history_percentile_time_series | Line with percentile bands, today marked | Table | P/E, P/B, EV/EBITDA, P/S switch |
| sector_valuation_landscape_heatmap | Sector × multiple heatmap | Table | Stock's sector outlined |
| peer_comparison_table | Table, focus stock pinned, median row | Scatter | Edit peers |
| universe_percentile_table | Table with percentile bars | Scatter | |
| universe_wide_four_dimension_cards | Small card grid, sortable | Table | Cheapest first |

## 10. Rank (sc03 and Strategies)

Composite

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| composite_score_universe_ranking | Table with stacked factor bar | Scatter | Hero |
| per_stock_score_decomposition | Waterfall from base to score | Table | Stock selector |
| score_transparency_decomposition | Factor contribution bars | Table | |
| composite_vs_spy_backtest | Equity against SPY, drawdown strip | Table | |
| factor_correlation_heatmap | Heatmap ordered by cluster | Table | Annotated values |
| factor_correlation_redundancy_alerts | Pair list with severity pills | Heatmap | Lower a weight in one click |
| sector_composite_breakdown | Bars by sector with spread | Table, treemap | Click to filter |
| historical_weight_training | Stacked share over time | Table | |
| effective_number_of_factors | Gauge | Line | |
| macro_regime_attribution | Bars by regime | Table | |

Weights: sliders that sum to 100, lock, equal, IC, ridge, presets, live re-rank without a full run.

- [x] Add Strategies (sc04): it runs in the backend but has no page in the catalog today

| Output | Default | Alternatives |
|---|---|---|
| per_strategy_stock_list | Table with strategy switcher | Scatter |
| piotroski_breakdown | Nine-check matrix with tick, cross, unknown | Table |
| altman_z_score_status | Zone pills and distribution | Table |
| altman_z_score_8q_trend | Line with safe, grey, distress bands | Table |

## 11. Test (sc05)

A tear sheet in the order an investor asks: did it make money, how bad did it get, is it real, what did it hold.

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| full_performance_statistics | KPI cards against benchmark | Table | CAGR, Sharpe, max drawdown, hit rate first |
| equity_curve | Equity against benchmark, underwater strip, log toggle | Table | Regime and rebalance marks |
| rolling_performance | Rolling Sharpe and return, window picker | Table | |
| (add from curve) | Monthly return heatmap, yearly bars, return histogram | Table | Compute in frontend from the curve |
| cscv_pbo | PBO gauge with logit histogram | Table | Verdict pill |
| holding_period_sensitivity | Bars with chosen value marked | Table | |
| rebalancing_date_sensitivity | Dot range by start offset | Table | Spread shown |
| rebalancing_date_sensitivity_by_weekday | Five small bars | Table | |
| turnover_report | Bars over time, cost drag | Table | |
| stock_level_attribution | Diverging bars, top and bottom | Treemap, table | Opens drawer |
| position_trade_log | Table with P/L pills | Timeline | Filter by name |
| position_entry_exit_log | Gantt of holdings | Table | |

Also: side-by-side compare of runs, cost and top-N sweeps, trial ledger counter, proof through ML Validate, data limits shown once in a compact banner, and the count of names dropped from mixed-currency universes.

## 12. Monitor (sc06, sc08)

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| alert_feed | Timeline with type pills | Table | Mark read, open stock |
| watchlist_live_monitoring_dashboard | Table with sparklines and change heat | Chart grid | |
| alert_performance_tracker | Precision scorecards | Table | |
| alert_performance_tracker_historical | Precision over time | Table | |
| screen_entry_exit_log | Entered and left timeline | Table | |
| change_report | Diff view between two runs | Table | Choose the two |
| instant_download | Export panel | | Format and column pickers |
| screen_result_api_endpoint | Copyable request | Table | |

Alert builder: condition from any filter or formula, frequency, channel with Apprise (email, push, webhook), test send, snooze.

## 13. Saved and More

- [ ] Saved: cards with mini result, last run, change, schedule pill; rename, duplicate, tag, folder, search, sort, archive
- [ ] Schedule picker and history timeline
- [ ] More: Markets tabs with the table of section 6, hourly, plain English, share links, API keys; patterns labelled weak evidence
- [ ] Share page and embed use the same design

## 14. Full customisation list

| Area | User controls |
|---|---|
| Universe | Size, rank basis, markets, sectors, listings, stocks in and out, saved lists, paste, CSV |
| Period | Lookback, as-of, range, rebalance, holding period |
| Filters | Any metric, operator, percentile, comparison with a field, group logic, order, on/off, formula |
| Metrics | Named custom metrics, periods for each indicator, formula columns |
| Scores | Components, weights, method, scale, winsorise, neutralisation, presets |
| Backtest | Score, top N, long or long-short, weights, costs, rebalance, sweeps |
| Table | Column sets, order, width, freeze, sort, format, conditional rules, group, pivot, density, rows, footer, currency |
| Charts | Type, axes, size, colour, group, facet, scale, range, benchmark, annotations |
| Cards | Layout, width, order, hide, pin, default view per output |
| Workspace | Panels, theme, accent colour, density, line weight, up/down colour swap, reduced motion, shortcuts, home page |
| Saving | Screens, views, universes, formulas, presets; this screen or all; link; reset to default |
| Alerts | Rule, frequency, channel, digest, snooze |
| Export | Format, columns, limits header, API |

## 15. Backend needed by this plan

- [x] 500 default, 1,000 cap, USD liquidity ranking
- [x] Composite runs on default settings
- [ ] Composite under 2 s on 50 names (now 8 s on 26)
- [x] Distribution endpoint for filter sliders
- [x] Live filter counts without a full run, from a cached panel
- [ ] Rank basis choices; market, industry and market cap presets
- [x] Mount sc04 in the Screener catalog
- [ ] Exchange labels for US names, which show Unknown today
- [ ] Faster job polling and smaller result payloads

Result-changing fixes wait for approval: SPY inside percentiles, rebalance stats, risk-free handling.

## 16. Order of work

Each step ends with screenshots on real results and a commit.

1. Composite speed, so Rank is usable
2. Table: column sets, heat, pills, frozen columns, empty columns, action row
3. Output card and KPI finish
4. Control bar depth: filter editor, histogram sliders, live counts
5. Screen outputs, then Valuation and Formula
6. Rank, including Strategies
7. Test tear sheet
8. Stock drawer and compare
9. Monitor, Saved, More
10. Overview depth
11. Keyboard, phone, accessibility, speed
12. Check every box on the page; apply the same shell to other labs

## 17. Data we cannot show yet

Analyst estimates, shareholding, index membership, company logos, extended hours and real-time quotes. These are marked "needs data" and are not faked.
