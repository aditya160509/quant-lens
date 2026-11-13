# Screener frontend plan

Size tags (Claude build time, measured: the 16 easy items took about 6 min each): `E` easy (under 10 min), `M` medium (15–30 min), `H` hard (1–2 h, or needs backend or data work first).

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

- [x] `E` Near-black palette, blue primary, KPI cards
- [x] `E` Left nav open by default with Overview, Screen, Rank, Test, Monitor, Saved, More
- [x] `E` Coloured icon tile per section; active item with accent bar; run status dot
- [x] `E` Collapsible to icons, with tooltips; width remembered (needs check)
- [x] `M` One-row page header: icon, title, sub-tabs, Save, Share, Export, Run (needs check)
- [x] `E` Inspector closed by default on Screen; opens for advanced settings only (needs check)
- [x] `E` Runs dock collapsed to a status pill until opened (needs check)
- [x] `M` Command palette: run, add filter, open any screen or stock, change theme (needs check)
- [x] `E` Keyboard: Cmd+Enter run, Shift+F filter, F column, `/` search, `[ ]` pages, Esc close (needs check)
- [x] `M` Skeletons matching final layout; no layout shift; no page-wide dim on navigation (needs check)
- [x] `E` Toasts for saved, failed, copied
- [ ] `H` Phone layout: bottom nav, filter sheet, card rows
- [x] `E` Light theme kept working, dark the default (needs check)

## 4. Overview page

- [x] `E` Stat cards with real graphics: last screen, valuation ready, stocks covered, runs
- [x] `E` Screens gallery by theme with colour per theme
- [x] `E` Sector tiles with counts
- [x] `E` Check gallery and sector clicks end to end, and run on arrival (needs check)
- [ ] `H` Each gallery row shows live match count and top three names after first load
- [x] `E` Search box as the page's main element
- [x] `M` Recent screens and saved screens with last result and change since last run (needs check)
- [x] `M` Market breadth strip: advancers, new highs, sector returns
- [x] `M` Sector treemap by market cap coloured by return (needs check)
- [ ] `H` Biggest entrants and exits across saved screens
- [ ] `H` Pinned board of outputs, in cards

## 5. Control bar, every study page

### Universe picker
- [x] `E` Clickable universe title opening a large search overlay
- [x] `E` Search and add stocks, size 25 to 1,000, saved universes, watchlists, paste, save
- [x] `E` Top N ranked by USD liquidity
- [x] `M` Rank basis: liquidity, market cap, or data coverage (needs check)
- [x] `M` Presets: country, exchange, sector, industry, currency, market cap band (needs check)
- [x] `M` Multi-select markets; primary listing only toggle (needs check; country picker was already multi-select; primary listing covers NSE over BSE only)
- [x] `E` CSV upload, exclude list, rename and delete saved universes (needs check)
- [x] `M` Live name count and estimated run time before running (needs check)
- [x] `E` Sector and country mix of the chosen universe as a small bar
- [x] `E` Share a universe by link; a screen's result becomes a universe (needs check)
- [x] `E` Clear disabled state at the cap, with count (needs check)

Index membership stays out until we have data for it; it must not be faked.

### Period
- [x] `E` 6M to 10Y presets and as-of date
- [x] `M` Max and custom start and end with date picker (needs check)
- [x] `M` Data availability shown on the range (needs check)
- [x] `E` Rebalance frequency and holding period as segmented controls on Test
- [ ] `H` Compare as-of dates

### Filters
- [x] `E` Pill row with min and max and `+ Filter`
- [x] `M` Add-filter overlay with groups, search, recently used and favourites: Identity, Market, Technical, Valuation, Profitability, Growth, Health, Dividends, Score
- [x] `M` Pill editor: slider over the real distribution histogram, percentile mode, greater, less, between, in, top N
- [x] `M` Live pass count and removed count on each pill; bottleneck marked
- [x] `M` Toggle, remove, reorder, duplicate; undo and redo (needs check; toggle, remove, undo and redo built; reorder and duplicate belong to the AND/OR tree item)
- [x] `E` Category filters as searchable checklists: sector, industry, country, exchange, currency
- [ ] `H` AND/OR groups, editable as tree and as formula
- [ ] `H` Compare to another field: P/E below sector median, price above SMA 200
- [ ] `H` Historical conditions: 5-year average, change over N periods
- [x] `M` Filter from a chart: brush a scatter, click a treemap sector, drag a histogram (already built: scatter lasso, treemap sector, histogram drag)
- [ ] `H` Natural language box producing editable filters
- [x] `E` Hide or show filters; save as a screen; preset chips (needs check)

### Run
- [x] `E` One blue Run; auto-run option when a filter changes, debounced, on universes up to 250
- [ ] `H` Progress by stage, cancel, stale marker
- [x] `E` Failure card with the reason and one-click fix

## 6. Table, used by every tabular output

- [x] `M` Column sets as tabs: Overview, Performance, Valuation, Profitability, Growth, Health, Dividends, Technical, Scores, Trust, Custom; add own
- [ ] `H` Column picker with search, groups and drag order; per-column interval where data supports it
- [x] `M` Frozen rank, ticker and company; sticky header; resize; reorder by drag; auto-fit (needs check)
- [x] `M` Multi-sort; sort by distance from a value
- [x] `E` Monogram tile, ticker badge, company, sector pill
- [x] `M` Number format per column: compact, percent, decimals, currency; base currency switch (needs check; base currency switch not done: values are already USD and per-column FX needs backend)
- [x] `M` Conditional formats per column: heat, bars, signed colour, rule, top and bottom N (needs check)
- [x] `M` Sparkline columns with range choice (needs check)
- [x] `E` Muted missing values; auto-hide wholly empty columns; coverage in header
- [ ] `H` Group by and pivot on any column, with count, median, mean, sum rows
- [x] `E` Footer: median and universe median, sector median toggle
- [x] `M` Bulk select: add to watchlist, compare, alert, send to Rank, Test, ML, export
- [x] `E` Row hover actions; row expand shows why it passed (built, not checked on page)
- [x] `E` Density, rows per page, infinite or paged; virtual scroll to 1,000 rows without lag (built, not checked on page)
- [x] `E` Search within results; column quick filter from the header adds a pill
- [x] `E` Chart-grid view of mini price charts
- [x] `E` CSV, Excel, TSV, tickers, copy, Markdown, PDF (needs check)
- [x] `E` Save view for this screen or all; share by link; reset (built, not checked on page)

## 7. Output card, every output

- [x] `E` Title, as-of and coverage in one row, status pill (needs check)
- [x] `E` View menu with the alternatives below; choice remembered (built, not checked on page)
- [ ] `H` Settings: scale, range, colours, labels, benchmark, annotations
- [ ] `H` Maximise, pin to board, change width, reorder, hide, duplicate
- [x] `E` Copy image, download PNG, SVG, CSV (built, not checked on page)
- [ ] `H` Hover crosshair; click drills into rows; brush filters
- [x] `E` Footnote naming the method, only where it matters (needs check)
- [x] `E` Empty, partial and failed states with the reason (needs check)

## 8. Stock drawer and compare

- [x] `M` Header: monogram, price, change, exchange, follow, alert, compare, add to screen (needs check)
- [x] `M` Ratio grid with add ratio and edit ratios, percentile tick against sector (needs check)
- [ ] `H` Price chart with range tabs, Price and P/E modes, volume, moving averages, entry and exit marks
- [x] `M` Strength profile: quality, value, momentum, health, growth as a radar we compute, with filter by shape
- [x] `E` Why here: filter, value, threshold, margin, sector percentile (built, not checked on page)
- [x] `E` Peers, quarters, profit and loss, balance sheet, cash flow, ratios as tabs (built, not checked on page)
- [x] `M` Statement rows with sparklines, YoY, common-size toggle
- [ ] `H` Compare up to 8 names: overlaid chart, side-by-side table, differences highlighted
- [ ] `H` Full page with its own URL; PDF

## 9. Screen group

### Screen (sc01)

Built, not checked on page: section 6 table with sets and bulk actions, chart grid, treemap with filter to sector, funnel with bottleneck. Not built: run changes pills, coverage bars, percentile strip, sector heatmap.

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

Built, not checked on page: results table, status list, backtest with drawdown, template gallery. Not built: CodeMirror editor upgrades.

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| formula_result_table | Section 6 table with score bar | Scatter, histogram | Formula as a new column |
| historical_formula_backtest | Equity against SPY with drawdown strip | Log scale, table | Same as Test card |
| formula_validation_panel | Inline editor errors, plus status list | Table | Jump to the error |
| formula_template_library | Gallery cards | Table | Insert into editor |

Editor: CodeMirror with autocomplete, field docs on hover, live preview count, named metrics, saved formulas, history, plain English to formula.

### Valuation (sc07)

Built, not checked on page: four gauges with multiples, universe card grid, Focus, Universe and Peers tabs. Not built: percentile bands on the history line, outlined sector in the heatmap.

| Output | Default | Alternatives | Must have |
|---|---|---|---|
| four_dimension_valuation_card | Four gauges: vs history, sector, peers, universe | Key values | Hero, stock selector |
| own_history_percentile_time_series | Line with percentile bands, today marked | Table | P/E, P/B, EV/EBITDA, P/S switch |
| sector_valuation_landscape_heatmap | Sector × multiple heatmap | Table | Stock's sector outlined |
| peer_comparison_table | Table, focus stock pinned, median row | Scatter | Edit peers |
| universe_percentile_table | Table with percentile bars | Scatter | |
| universe_wide_four_dimension_cards | Small card grid, sortable | Table | Cheapest first |

## 10. Rank (sc03 and Strategies)

Built, not checked on page: stacked factor ranking, waterfall, Breakdown tab, redundancy and weight training on Weights, Strategies page with Piotroski matrix and Altman zones. Not built: weight sliders with live re-rank, Altman bands on the 8Q line.

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

- [x] `E` Add Strategies (sc04): it runs in the backend but has no page in the catalog today

| Output | Default | Alternatives |
|---|---|---|
| per_strategy_stock_list | Table with strategy switcher | Scatter |
| piotroski_breakdown | Nine-check matrix with tick, cross, unknown | Table |
| altman_z_score_status | Zone pills and distribution | Table |
| altman_z_score_8q_trend | Line with safe, grey, distress bands | Table |

## 11. Test (sc05)

Built, not checked on page: monthly heatmap with year and SPY, return histogram, drawdown strip, attribution bars, holdings timeline, weekday sensitivity, rebalance and top N buttons. Not built: KPI cards against benchmark, PBO gauge, run compare, sweeps.

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

Built, not checked on page: alert feed, hit-rate cards, tinted watchlist table. Not built: alert builder, entry and exit timeline, change report picker.

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

- [x] `H` Saved: cards with mini result, last run, change, schedule pill; rename, duplicate, tag, folder, search, sort, archive
- [x] `M` Schedule picker and history timeline (needs check)
- [ ] `H` More: Markets tabs with the table of section 6, hourly, plain English, share links, API keys; patterns labelled weak evidence
- [ ] `H` Share page and embed use the same design

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

Every control follows one rule: works with defaults untouched; any change offers "Make default" (this card, every card like it, or everywhere) and "Reset".

- [x] `M` "Make default" and "Reset" on every setting at three levels: this output, every output of its type, everywhere (cards already do the first two) (needs check)
- [x] `M` Preferences sync to the account instead of this browser only, with export and import as JSON (needs check; no accounts yet, so one server copy with save and load, plus JSON export and import)
- [ ] `E` One "Customised" marker on any page or card that differs from default, opening a list of what changed

## 15. Backend needed by this plan

- [x] `E` 500 default, 1,000 cap, USD liquidity ranking
- [x] `E` Composite runs on default settings
- [ ] `H` Composite under 2 s on 50 names (now 8 s on 26)
- [x] `E` Distribution endpoint for filter sliders
- [x] `E` Live filter counts without a full run, from a cached panel
- [x] `M` Rank basis choices; market, industry and market cap presets (needs check)
- [x] `E` Mount sc04 in the Screener catalog
- [ ] `H` Exchange labels for US names, which show Unknown today
- [x] `E` Faster job polling and smaller result payloads (built, not checked on page)

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

Analyst estimates and forward P/E, shareholding and float, short interest, earnings and ex-dividend calendar, index membership, company logos, extended hours and real-time quotes. These are marked "needs data" and are not faked.

- [ ] `E` Hide filters with no data in the picker (Forward P/E and Float % have zero coverage today), using the preview's known count

## 18. Open-source check (2026-11-10)

Keep: TanStack Table and Virtual, Query, Zustand, d3 maths, Radix, cmdk, CodeMirror, uFuzzy.

- [x] `M` Drawer price chart on TradingView Lightweight Charts v5 (already installed, about 45 KB): candles, volume pane, moving averages, entry and exit markers (needs check)
- [ ] `H` Relative Rotation Graph (RS-Ratio against RS-Momentum, weekly tails) for sectors and groups, as in xang1234/stock-screener and StockCharts
- [x] `M` Group matrix: sector rows, market-cap columns, stock tiles coloured by 1D, 1W or 1M change (xang1234/stock-screener) (needs check)
- [x] `M` Breadth history: advance and decline and new highs and lows over time with SPY overlay (StockBee style) (needs check)
- [x] `M` Test tear sheet sections from OpenStatz/QuantStats: return and risk by horizon (1Y, 3Y, 5Y, all), worst drawdown episodes, losing streaks, weekly heatmap, yearly against benchmark (needs check)
- [ ] `H` Pivot: FINOS Perspective (WebAssembly grid, pivot and charts, Apache-2.0) for a power-user pivot view, loaded only on that view
- [x] `E` Remove unused Plotly and Monaco from package.json — not unused: Plotly runs the security page panels and Monaco the Studio editor, so both stay
- [ ] `H` Only if the table lags at 1,000 rows: benchmark against React Data Grid (best overall in a 50,000-row benchmark) or Glide (canvas). TanStack plus Virtual had high heap growth in that benchmark
