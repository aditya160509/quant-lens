# Screener checklist

Tick Screener items here only. Spec: [product review](../reviews/product/SCREENER_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 2](PLAN.md). Numbers in brackets are parity rows; U numbers are our own features.

This is the one list of everything to build. The review stays the spec and has no ticks.

## Standard

- [ ] Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- [ ] Competitors teach features only. Screener.in, Tickertape and others set what to include, never how it looks
- [ ] Every number is real. Unknown is shown as unknown, never zero or blank
- [ ] Every result prints its limits: 90-day statement lag, survivorship, 2021+ fundamentals
- [ ] Nothing is capped silently

## Freedom: any output, any way

- [ ] Every output opens as table, bars, scatter, heatmap, treemap, ranked list, distribution or mini-chart grid, where the data fits (extend `Explore`)
- [ ] Any column can be the x, y, size, colour, group or facet
- [ ] Add any metric to the table by typing its name, from any row or header (49)
- [ ] Type a formula as a new column; it can then be filtered, sorted, ranked and charted (40)
- [ ] Absolute or percentile per column: within universe, sector or own history (50)
- [ ] Group by and pivot on any column, with count, median, mean and sum rows
- [ ] Conditional formats per column: bars, heat, signed colour, rules
- [ ] Density, column order, width, pinning and hiding
- [ ] Exhibits can be resized, reordered, hidden, expanded or sent to the workspace
- [ ] Save any arrangement as a view: for this screen or all screens; share it; reset to our default (49)
- [ ] The whole state lives in the URL, so any view can be linked
- [ ] Export any view as CSV, Excel, Markdown, SVG, PNG or PDF
- [ ] Every action has a keyboard path and a palette entry

## Our own ideas

- [ ] Filter from a chart: brush a scatter, click a treemap sector or drag a histogram to create a chip
- [ ] Live funnel: move a threshold and see counts and names change, with the bottleneck filter marked
- [ ] Time machine: drag an as-of date to see what the screen would have shown then (fundamentals 2021+)
- [ ] Screen diff: compare two screens, two dates or two runs; see who entered, left or moved (U9)
- [ ] Sensitivity strip: how much the result set and its return change if each threshold moves
- [ ] Compare basket: pick names from any table and open them side by side
- [ ] Peer mode: from any name, open its sector path, peers and a median row
- [ ] Explain the difference: why did name A pass and name B fail?

## Workspace and kit

- [x] `Exhibit`, `KpiStrip`, `DataTable v2`, `RankList` shared
- [ ] `/screener` on `LabConfig`, four pages from the backend manifest: Screen, Rank, Test, Monitor
- [ ] Panels close, auto-close and give their space to content
- [ ] Quick-look drawer, shared with ML

## Global search

- [ ] Large overlay from anywhere by keyboard
- [ ] Fuzzy search library chosen after a spike, licence checked
- [ ] Ticker, company name; confirm name coverage for all symbols
- [ ] Tabs: Symbols, Screens, Runs, Docs
- [ ] Type chips only where we hold data
- [ ] Rows: monogram, ticker, name, type, exchange
- [ ] Hover and arrow actions: chart, overview, add to screen, run in a lab
- [ ] Recent and popular before typing
- [ ] Universe selector rebuilt to the same standard

## Table and data

- [ ] Shared per-ticker price loader; an NSE name screens (9)
- [ ] Server sort, page and count over DuckDB; no silent cap (48)
- [ ] 4,158 names scroll smoothly
- [ ] Market-cap buckets with counts (2)
- [ ] Watchlists as universe and filter (5)
- [ ] Coverage per metric (7)
- [ ] Country and currency filter (8)
- [ ] Crypto, forex and futures, price-only (14)
- [ ] Hourly screens (26)
- [ ] 1D and 1M returns, quarterly profit and sales variance, sparkline
- [ ] Result header: count, universe, as-of, updated, data hash
- [ ] Row actions: watchlist, alert, ML, Research (59)
- [ ] Scatter lens (53) and mini-chart grid (54)

## Filters and formula

- [ ] Chips with greater, less, between, in, top N, and live counts (37)
- [ ] AND/OR groups and nesting, round-trip with formula (38)
- [ ] Undo, redo, disable a filter (47)
- [ ] CodeMirror formula bar on `signal_lang`, with autocomplete and preview
- [ ] `core/formula.py` reduced to a thin adapter
- [ ] Named custom metrics (40)
- [ ] Chart patterns, labelled weak evidence, last (25)
- [ ] Share links and public screens (45)
- [ ] Plain English writes an editable formula (46)

## Trust

- [ ] Trust badge per result and row; hatched unknowns (U1)
- [ ] Why-here expander: filter, value, threshold, margin, sector percentile (U2)
- [ ] Near-miss explorer with "relax this filter" (U3)
- [ ] Evidence badge per filter, with citation (U8)
- [ ] Reproducible run: id, as-of, data hash, formula (U9)
- [ ] Limits on results, backtests and exports (U10)

## Quick look and report

- [ ] Chart, key stats, percentile bars, score profile
- [ ] Piotroski and Altman, peers, statements with drill-down (63)
- [ ] Pros, cons and red flags from rules on our metrics (65)
- [ ] One-page PDF with Typst (67)

## Rank

- [ ] Composite, weights and waterfall
- [ ] About 30 templates, named by formula
- [ ] ML hand-off; rules and learned ranks side by side (81, U6)

## Test

- [ ] Golden fixtures for validation statistics
- [ ] `services/shared/` with one PBO and one deflated Sharpe
- [ ] Purged CV and Monte Carlo in ML Validate
- [ ] Trial ledger on the Research store; counter on screen (U5)
- [ ] One-click proof through ML Validate (U4)
- [ ] Rolling start dates (83)
- [ ] Data banner
- [ ] Old S4 leaderboard, S2 factor zoo and S5 duplicates removed

## Monitor

- [ ] Saved screens and schedules on the shared scheduler
- [ ] Email, push and webhook with Apprise (73, 74)
- [ ] End-of-day price and indicator alerts (75)
- [ ] Delivered-alert tracking and precision scoreboard (U7)
- [ ] Digest
- [ ] API keys and limits (57)

## Backend ready: put on screen

- [ ] Filter by sector, industry, exchange, market-cap range (1)
- [ ] Price, volume and dollar-volume floors, penny-stock exclusion (3)
- [ ] Custom universe: pasted tickers, CSV upload, saved universes (4)
- [ ] Run as of a past date (6)
- [ ] Valuation: P/E, P/B, P/S, P/CF, EV/EBIT, EV/EBITDA, earnings and FCF yield (15)
- [ ] Profitability and quality: ROE, ROIC, margins, GP/A, interest coverage (16)
- [ ] Growth: revenue and EPS YoY, 3-year CAGR (17)
- [ ] Health and payout: debt/equity, debt/EBITDA, current ratio, dividend yield, payout (18)
- [ ] Piotroski F-score (9 checks, unknowns kept) and Altman Z (19)
- [ ] Momentum, 52-week high proximity, SMA distance, cross flags (20)
- [ ] Technicals: RSI, MACD, ADX, stochastic, Bollinger, ATR, OBV (21)
- [ ] Risk: realised volatility, beta, drawdown, idiosyncratic volatility, max daily return (22)
- [ ] Liquidity: Amihud percentile, volume ratio (23)
- [ ] Percentile versus sector or universe as a filter (24)
- [ ] Query or formula language with custom ratios (39)
- [ ] Historical functions (lag, change, rolling rank, cross above) (41)
- [ ] Live count after each filter, with the bottleneck filter shown (42)
- [ ] Composite score and ranking system with weights (43)
- [ ] Pre-built screens and templates (44)
- [ ] Sector-relative percentile bars in rows (51)
- [ ] Treemap and heatmap lens (52)
- [ ] Compare up to 6 to 25 names side by side (55)
- [ ] Export CSV, Excel, JSON, ticker list (56)
- [ ] Price chart with ranges 1M to 10Y (60)
- [ ] Ratios with sector percentile and own-history percentile (61)
- [ ] Score summary: valuation, quality, momentum, low vol, thesis line (62)
- [ ] Peer comparison table (64)
- [ ] Piotroski 9-check grid, Altman zone (66)
- [ ] Saved screens, rename, duplicate (70)
- [ ] Run history with entries, exits and rank shifts (71)
- [ ] Scheduled re-runs (72)
- [ ] Fundamental-change alerts (results out) (76)
- [ ] Backtest a screen with rebalances (78)
- [ ] Compare with benchmark (79)
- [ ] Overfitting tests: deflated Sharpe, PBO, bootstrap, controls (80)

## Ship

- [ ] Verified pages and palette actions
- [ ] Phone layout
- [ ] Accessibility pass
- [ ] Visual baselines
- [ ] Test-setup type errors fixed, so the commit hook passes
- [ ] Tag `screener-v1`

## Later: free data

- [ ] Full India universe (10)
- [ ] Nifty index lists (12)
- [ ] Earnings calendar and surprises (29)
- [ ] Shareholding (30)
- [ ] Delivery, deals, open interest, flows (31)
- [ ] Insider trades (32)
- [ ] 13F holdings (33)
- [ ] Logos (69)

## Later: paid data

- [ ] Real-time prices and minute screens (27)
- [ ] Analyst estimates and revisions (28)
- [ ] 10 to 30 years of statements (36)
- [ ] Point-in-time data with delisted names (82)
