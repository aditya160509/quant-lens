# Screener checklist

Open-source picks for every batch: [Screener open source](../references/2026-11-screener-open-source.md).

Tick Screener items here only. Spec: [product review](../reviews/product/SCREENER_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 2](PLAN.md). Numbers in brackets are parity rows; U numbers are our own features.

This is the one list of everything to build. The review stays the spec and has no ticks.

Tags: `E` easy, up to a few hours. `M` medium, about a session. `H` hard, several sessions or real risk. Work batches in order; within a batch, top to bottom.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. Screener.in, Tickertape and others set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank
- Every result prints its limits: 90-day statement lag, survivorship, 2021+ fundamentals
- Nothing is capped silently

## Batch 1: Foundation

The workspace and fast data everything else sits on. E3 M5 H1

- [x] `E` `Exhibit`, `KpiStrip`, `DataTable v2`, `RankList` shared
- [x] `M` Test-setup type errors fixed, so the commit hook passes
- [x] `M` `/screener` on `LabConfig`, four pages from the backend manifest: Screen, Rank, Test, Monitor
- [x] `M` Panels close, auto-close and give their space to content
- [x] `M` Shared per-ticker price loader; an NSE name screens (9)
- [x] `H` Every passing name reaches the table, sorted and counted; no silent cap (48). DuckDB waits until rows outgrow the browser
- [x] `M` 4,158 names scroll smoothly
- [x] `E` Result header: count, universe, as-of, updated, data hash
- [x] `E` Limits on results, backtests and exports (U10)

## Batch 2: Core screen

A usable screener: every filter, live counts, real table. E18 M8 H1

- [x] `E` Filter by sector, industry, exchange, market-cap range (1)
- [x] `E` Price, volume and dollar-volume floors, penny-stock exclusion (3)
- [x] `E` Valuation: P/E, P/B, P/S, P/CF, EV/EBIT, EV/EBITDA, earnings and FCF yield (15)
- [x] `E` Profitability and quality: ROE, ROIC, margins, GP/A, interest coverage (16)
- [x] `E` Growth: revenue and EPS YoY, 3-year CAGR (17)
- [x] `E` Health and payout: debt/equity, debt/EBITDA, current ratio, dividend yield, payout (18)
- [x] `E` Piotroski F-score (9 checks, unknowns kept) and Altman Z (19)
- [x] `E` Momentum, 52-week high proximity, SMA distance, cross flags (20)
- [x] `E` Technicals: RSI, MACD, ADX, stochastic, Bollinger, ATR, OBV (21)
- [x] `E` Risk: realised volatility, beta, drawdown, idiosyncratic volatility, max daily return (22)
- [x] `E` Liquidity: Amihud percentile, volume ratio (23)
- [x] `E` Percentile versus sector or universe as a filter (24)
- [x] `M` Chips with greater, less, between, in, top N, and live counts (37) (untested)
- [x] `E` Live count after each filter, with the bottleneck filter shown (42)
- [x] `E` Market-cap buckets with counts (2)
- [x] `M` Country and currency filter (8) (untested)
- [x] `M` Custom universe: pasted tickers, CSV upload, saved universes (4) (untested)
- [x] `M` Watchlists as universe and filter (5) (untested)
- [x] `E` Run as of a past date (6)
- [x] `E` Coverage per metric (7)
- [x] `M` 1D and 1M returns, quarterly profit and sales variance, sparkline (untested)
- [x] `M` Row actions: watchlist, alert, ML, Research (59) (untested)
- [x] `M` Undo, redo, disable a filter (47) (untested)
- [x] `H` AND/OR groups and nesting, round-trip with formula (38) (untested)
- [x] `E` Sector-relative percentile bars in rows (51)
- [x] `M` Trust badge per result and row; hatched unknowns (U1) (untested)
- [x] `E` Export CSV, Excel, JSON, ticker list (56)

## Batch 3: Search and quick look

Find any name and read it without leaving. E10 M11 H1

- [x] `E` Fuzzy search library chosen after a spike, licence checked: uFuzzy (MIT)
- [x] `E` Ticker, company name; confirm name coverage for all symbols
- [x] `M` Large overlay from anywhere by keyboard
- [x] `M` Tabs: Symbols, Screens, Runs, Docs (untested)
- [x] `E` Type chips only where we hold data
- [x] `E` Rows: monogram, ticker, name, type, exchange
- [x] `M` Hover and arrow actions: chart, overview, add to screen, run in a lab
- [x] `E` Recent and popular before typing
- [x] `M` Universe selector rebuilt to the same standard (untested)
- [x] `H` Quick-look drawer, shared with ML
- [x] `M` Chart, key stats, percentile bars, score profile
- [x] `E` Price chart with ranges 1M to 10Y (60)
- [x] `E` Ratios with sector percentile and own-history percentile (61)
- [x] `E` Score summary: valuation, quality, momentum, low vol, thesis line (62)
- [x] `E` Peer comparison table (64)
- [x] `E` Piotroski 9-check grid, Altman zone (66)
- [x] `M` Piotroski and Altman, peers, statements with drill-down (63)
- [x] `M` Pros, cons and red flags from rules on our metrics (65)
- [x] `M` One-page PDF with Typst (67)
- [x] `M` Compare up to 6 to 25 names side by side (55)
- [x] `M` Compare basket: pick names from any table and open them side by side
- [x] `M` Peer mode: from any name, open its sector path, peers and a median row

## Batch 4: Formula

One language, usable as filter, column and rank. E1 M2 H3

- [ ] `H` CodeMirror formula bar on `signal_lang`, with autocomplete and preview
- [ ] `H` `core/formula.py` reduced to a thin adapter
- [ ] `E` Query or formula language with custom ratios (39)
- [ ] `M` Historical functions (lag, change, rolling rank, cross above) (41)
- [ ] `M` Named custom metrics (40)
- [ ] `H` Type a formula as a new column; it can then be filtered, sorted, ranked and charted (40)

## Batch 5: Freedom

Any output, any way. E2 M8 H4

- [ ] `H` Every output opens as table, bars, scatter, heatmap, treemap, ranked list, distribution or mini-chart grid, where the data fits (extend `Explore`)
- [ ] `M` Any column can be the x, y, size, colour, group or facet
- [ ] `M` Add any metric to the table by typing its name, from any row or header (49)
- [ ] `M` Absolute or percentile per column: within universe, sector or own history (50)
- [ ] `H` Group by and pivot on any column, with count, median, mean and sum rows
- [ ] `M` Conditional formats per column: bars, heat, signed colour, rules
- [x] `E` Density, column order, width, pinning and hiding
- [ ] `M` Exhibits can be resized, reordered, hidden, expanded or sent to the workspace
- [ ] `H` Save any arrangement as a view: for this screen or all screens; share it; reset to our default (49)
- [ ] `H` The whole state lives in the URL, so any view can be linked
- [ ] `M` Export any view as CSV, Excel, Markdown, SVG, PNG or PDF
- [ ] `M` Every action has a keyboard path and a palette entry
- [ ] `M` Scatter lens (53) and mini-chart grid (54)
- [x] `E` Treemap and heatmap lens (52)

## Batch 6: Trust

Why people stay. E0 M6 H0

- [ ] `M` Why-here expander: filter, value, threshold, margin, sector percentile (U2)
- [ ] `M` Near-miss explorer with "relax this filter" (U3)
- [ ] `M` Evidence badge per filter, with citation (U8)
- [ ] `M` Reproducible run: id, as-of, data hash, formula (U9)
- [ ] `M` Screen diff: compare two screens, two dates or two runs; see who entered, left or moved (U9)
- [ ] `M` Explain the difference: why did name A pass and name B fail?

## Batch 7: Rank

E2 M2 H1

- [x] `M` Composite, weights and waterfall (untested)
- [x] `E` Composite score and ranking system with weights (43) (untested)
- [x] `E` Pre-built screens and templates (44) (untested)
- [x] `M` About 30 templates, named by formula (untested)
- [x] `H` ML hand-off; rules and learned ranks side by side (81, U6) (untested)

## Batch 8: Test

One honest proof path. E4 M4 H3

- [x] `M` Golden fixtures for validation statistics
- [ ] `H` `services/shared/` with one PBO and one deflated Sharpe
- [x] `H` Purged CV and Monte Carlo in ML Validate
- [x] `H` Trial ledger on the Research store; counter on screen (U5) (untested)
- [ ] `E` Backtest a screen with rebalances (78)
- [ ] `E` Compare with benchmark (79)
- [x] `M` Overfitting tests: deflated Sharpe, PBO, bootstrap, controls (80) (untested)
- [x] `M` One-click proof through ML Validate (U4) (untested)
- [x] `M` Rolling start dates (83) (untested)
- [x] `E` Data banner (untested)
- [ ] `E` Old S4 leaderboard, S2 factor zoo and S5 duplicates removed

## Batch 9: Monitor

E3 M5 H1

- [x] `E` Saved screens, rename, duplicate (70) (untested)
- [x] `M` Saved screens and schedules on the shared scheduler (untested)
- [x] `E` Scheduled re-runs (72) (untested)
- [x] `M` Run history with entries, exits and rank shifts (71) (untested)
- [x] `M` Email, push and webhook with Apprise (73, 74) (untested)
- [x] `M` End-of-day price and indicator alerts (75) (untested)
- [x] `M` Fundamental-change alerts (results out) (76) (untested)
- [x] `E` Digest (untested)
- [x] `H` Delivered-alert tracking and precision scoreboard (U7) (untested)

## Batch 10: Signature ideas

E0 M0 H4

- [ ] `H` Filter from a chart: brush a scatter, click a treemap sector or drag a histogram to create a chip
- [ ] `H` Live funnel: move a threshold and see counts and names change, with the bottleneck filter marked
- [ ] `H` Sensitivity strip: how much the result set and its return change if each threshold moves
- [ ] `H` Time machine: drag an as-of date to see what the screen would have shown then (fundamentals 2021+)

## Batch 11: Extras

E0 M4 H2

- [x] `M` Crypto, forex and futures, price-only (14) (untested)
- [x] `M` Hourly screens (26) (untested)
- [x] `M` Share links and public screens (45) (untested)
- [x] `M` API keys and limits (57) (untested)
- [x] `H` Plain English writes an editable formula (46) (untested)
- [x] `H` Chart patterns, labelled weak evidence, last (25) (untested)

## Batch 12: Ship

E2 M3 H0

- [ ] `M` Verified pages and palette actions
- [ ] `M` Phone layout
- [ ] `M` Accessibility pass
- [ ] `E` Visual baselines
- [ ] `E` Tag `screener-v1`

## Later: free data

E2 M5 H1

- [ ] `E` Nifty index lists (12)
- [ ] `E` Logos (69)
- [ ] `M` Full India universe (10)
- [ ] `M` Earnings calendar and surprises (29)
- [ ] `M` Delivery, deals, open interest, flows (31)
- [ ] `M` Insider trades (32)
- [ ] `M` 13F holdings (33)
- [ ] `H` Shareholding (30)

## Later: paid data

Business decision after `screener-v1`. E0 M2 H2

- [ ] `M` 10 to 30 years of statements (36)
- [ ] `M` Analyst estimates and revisions (28)
- [ ] `H` Real-time prices and minute screens (27)
- [ ] `H` Point-in-time data with delisted names (82)
