# Screener open source, November 2026

Researched 2026-11-08. Repo facts (licence, stars, last push, latest release) came from the GitHub API on that date. Package facts came from the npm and PyPI registries and bundlephobia. READMEs were fetched with TinyFish for the picks marked "read" below. Nothing was installed and no code was run, so speed claims are unmeasured.

Rules used: no GPL, AGPL, SSPL, Commons Clause or unlicensed code in anything we ship (those are "ideas only"). Libraries are engines. Charts stay ours in `src/charts`. Existing code beats a new dependency. Picks from `PLAN.md` section 5 are kept unless new evidence is listed.

Verdicts: **adopt** (add as a dependency), **copy** (copy code, keep the notice in `THIRD_PARTY.md`), **ideas only**, **have** (already in the repo), **nothing good**.

## Summary

Top picks, by work saved:

1. **DuckDB** (MIT, v2.0.0, 2026-10-21) for server sort, page, count, group by, pivot and CSV upload. It is not in `backend/pyproject.toml` yet. One query returns the page and the total with `count(*) OVER ()`.
2. **TA-Lib** (BSD-3 core, BSD-2 Python wrapper, v0.8.3, Oct 2026): 200+ indicators and candlestick patterns, with a streaming API. Replaces the 134-line `indicators.py` and the hand-rolled technicals.
3. **edgartools** (MIT, v5.62.1, 2026-10-23): Form 4 insider trades, 13F holdings, XBRL statements and 8-K earnings items from SEC EDGAR. Covers three Later items for the US.
4. **nselib** (Apache-2.0): NSE delivery data, bulk and block deals, FII/DII, event calendars. Adopt after a spike. Our bhavcopy parser follows the rules in the third-party checklist below.
5. **CodeMirror 6 and Lezer** (MIT, npm releases Oct 2026) for the formula bar. The GitHub mirrors are archived, but development moved to code.haverbeke.berlin and npm is current. This answers the open question in `PLAN.md`.
6. **react-querybuilder core** (MIT, v8.26.0, 2026-10-27) for the AND/OR tree model, headless. We render chips ourselves.
7. **nuqs** (MIT, 6.5 KB gzip) for whole-state URLs. Peer range includes Next 16.
8. **MiniSearch or uFuzzy** for fuzzy search, chosen by spike. Fuse.js is the fallback.
9. **Apprise**, **XlsxWriter**, **typst-py** for alerts, Excel and PDF. skfolio for validation test oracles and purged CV.
10. **zundo** (undo and redo on zustand), **dnd-kit** (reorder), **react-hotkeys-hook** (keyboard paths), **slowapi** (API limits), **@axe-core/playwright** (accessibility checks, dev only).

Counts: 20 adopt or copy picks (below), 14 ideas-only projects, 14 rejected.

Biggest savings: server data layer (DuckDB), indicators (TA-Lib), and US filings data (edgartools).

Nothing good exists for: shareholding parsers (30), logos (69), analyst estimates (28), real-time prices (27), point-in-time data with delisted names (82), geometric chart patterns (25), Excel-grade pivot UI with our look, and a permissive India fundamentals source.

New evidence against the plan: none changes a pick. Three corrections: DuckDB is planned but absent from `pyproject.toml`; the CodeMirror archive question is resolved; OpenBB's own repo now states Apache-2.0 (see rejected list for why we still do not build on it).

Existing code that already covers checklist items (check these first):

- `frontend/src/charts`: Heatmap, Treemap, XYPlot, Distribution, Beeswarm, BarList, RankList, Waterfall, Dumbbell, TimeSeries, StackedArea, export.ts.
- `frontend/src/kit`: Exhibit, KpiStrip, DataTable. Installed: TanStack Table 8.21.3 and Virtual, cmdk, react-grid-layout, react-resizable-panels, zustand, lightweight-charts 5.1, d3, Monaco, Playwright.
- `backend/app/services/screener_v2/core`: `formula.py` (19.8 KB), `exports.py` (csv, tsv, json, tickers), `backtest.py` (simulate, `cscv_pbo`), `validation.py`, `alerts.py` (precision backtest, fundamental changes, realised precision), `scheduler.py` (thread, 30 s tick, durable claims in `state.py`), `composite.py`, `academic.py` (Piotroski, Altman), `gics.py`, `currency.py`.
- `backend/app/services/research_v2/core/signal_lang.py`: safe `ast` formula language, errors with start and end spans, time-series and cross-sectional operators.
- Installed Python: polars, pyarrow, arch (bootstrap and SPA tests), scipy, numba, reportlab, yfinance, orjson.

## Batch 1: Foundation

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Exhibit, KpiStrip, DataTable v2 | TanStack Table 8.21.3 (installed) | Done | Our `src/kit` | MIT | push 2026-11-02 | have | none |
| Test-setup type errors | none | n/a | Fix in our tests | n/a | n/a | nothing good | none |
| `/screener` on `LabConfig`, four pages | none | n/a | Our manifest and shell | n/a | n/a | have | none |
| Panels close and give space | react-resizable-panels 4.14 installed (latest 4.20.0) | Split, drag, keyboard resize | Auto-close rules, our handles | MIT | push and release 2026-11-08 | have | none |
| Shared per-ticker price loader; NSE name screens (9) | yfinance (installed) for `.NS` history; NSE bhavcopy for official closes | Price fetch and corner cases | Loader, date check (see Later: free data) | Apache-2.0 (yfinance) | yfinance 1.8.0, 2026-11-03 | have | none |
| Server sort, page, count over DuckDB (48) | duckdb Python 2.0.0 | Sort, filter, `count(*) OVER ()`, parquet streaming, `read_csv` | Query builder from filter JSON, "no silent cap" rule, limits header | MIT | push 2026-11-06, release 2026-10-21 | adopt | H to M |
| 4,158 names scroll smoothly | TanStack Virtual (installed) | Row virtualisation | Row renderer, sticky columns | MIT | push 2026-11-08 | have | none |
| Result header: count, universe, as-of, hash | none | n/a | Ours | n/a | n/a | nothing good | none |
| Limits on results and exports (U10) | none | n/a | Ours | n/a | n/a | nothing good | none |

## Batch 2: Core screen

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Sector, industry, exchange, cap range (1); country and currency (8) | `gics.py`, `currency.py` (have); FinanceDatabase as a gap-filler | 300k symbols with sector, industry, country, currency | Mapping, "unknown" handling | MIT | push 2026-11-08, 2.5.1 on 2026-10-12 | have, adopt for gaps | none |
| Price, volume, dollar-volume floors (3) | DuckDB `WHERE` | Filtering | Defaults, penny-stock rule | MIT | see above | adopt | none |
| Valuation, profitability, growth, health (15 to 18) | FinanceToolkit as a formula reference and test oracle | 500+ documented methods, pure functions | Our field names and unknown handling | MIT | v2.3.2, 2026-11-06 | copy (formulas only) | none |
| Piotroski, Altman (19) | `core/academic.py`, `features/feature_04.py` (have); FinanceToolkit `piotroski_model.py`, `altman_model.py` | Cross-check values | Nine checks with unknowns kept | MIT | see above | have | none |
| Momentum, SMA, 52-week high (20) | TA-Lib | SMA, ROC and friends in C | 52-week proximity, cross flags | BSD-3 core, BSD-2 wrapper | core v0.8.3 2026-10-25; wrapper 2026-10-28 | adopt | E |
| Technicals: RSI, MACD, ADX, stochastic, Bollinger, ATR, OBV (21) | TA-Lib | All seven plus 200+ more, streaming updates | Parameter defaults, columns | BSD-3 / BSD-2 | see above | adopt | E |
| Risk (22), liquidity (23), percentile (24) | `performance.py`, `stats.py` (have); DuckDB `percent_rank()` window | Percentile over sector or universe in SQL | Definitions, coverage rules | MIT | see above | have | none |
| Chips: greater, less, between, in, top N (37) | none; chips are our design. react-querybuilder core for the rule model | Rule types, validation | Chip UI | MIT | see AND/OR row | have | none |
| Live count and bottleneck (42) | DuckDB `count(*) FILTER (WHERE ...)` per filter | One pass for all counts | Bottleneck marker | MIT | see above | adopt | none |
| Cap buckets, coverage, as-of, custom universe, watchlists (2, 4 to 7) | DuckDB `read_csv` for pasted or uploaded files | CSV sniffing | Validation, saved universes | MIT | see above | adopt | none |
| 1D and 1M returns, quarterly variance, sparkline | Our `TimeSeries` chart | n/a | Sparkline variant (not confirmed to exist) | Ours | n/a | have | none |
| Row actions (59) | cmdk (installed) | Menu and keyboard | Actions | MIT | per plan, last push Oct 2025 | have | none |
| Undo, redo, disable a filter (47) | zundo (zustand middleware) | History stack, under 1 KB | Which state is tracked | MIT | push 2026-01-30; release v2.3.0 2024-11-17 | adopt | none |
| AND/OR groups, nesting, round trip with formula (38) | `@react-querybuilder/core` (react-querybuilder 8.26.0). Alternative: react-awesome-query-builder | Tree operations, move, validate, import and export for SQL, CEL, JSONLogic, SpEL | Chip renderer, mapping to `signal_lang` | MIT | push 2026-11-06, release 2026-10-27 | adopt, after a spike | H to M |
| Sector-relative percentile bars (51) | Our `Bars`, `RankList` | n/a | Row cell | Ours | n/a | have | none |
| Trust badge, hatched unknowns (U1) | none | n/a | Ours | n/a | n/a | nothing good | none |
| Export CSV, Excel, JSON, list (56) | `exports.py` (csv, tsv, json, tickers) plus XlsxWriter | Number formats, freeze panes, column widths | Excel adapter, limits sheet | BSD-2 | push 2026-10-28; PyPI 3.3.1 | adopt | none |

Notes: DuckDB can write `.xlsx` with `COPY ... (FORMAT xlsx)` (excel extension, read from the DuckDB docs today), but with no styling and a 1,048,576 row cap. Use XlsxWriter for the real export.

## Batch 3: Search and quick look

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Fuzzy search library after a spike | Spike three: MiniSearch (5.7 KB gzip), uFuzzy (4.0 KB), Fuse.js (9.4 KB). Fallback: match-sorter | Prefix, fuzzy, field boost, ranking | Ticker-first scoring, index build | MIT / MIT / Apache-2.0 | MiniSearch push 2025-09-16 (stable, slow); uFuzzy push 2026-09-08; Fuse v7.5.0 2026-07-13 | adopt (after spike) | E |
| Ticker, company name; name coverage | FinanceDatabase to find missing names | Name table | Gap report | MIT | see above | adopt | none |
| Overlay from anywhere by keyboard | cmdk (installed) and react-hotkeys-hook | Palette, hotkeys (3.0 KB gzip) | Tabs, actions | MIT | hotkeys-hook v5.3.3, 2026-06-26 | have, adopt hotkeys | none |
| Tabs, type chips, rows, hover actions, recents | none | n/a | Ours | n/a | n/a | nothing good | none |
| Universe selector rebuilt | none | n/a | Ours | n/a | n/a | nothing good | none |
| Quick-look drawer shared with ML (H) | none | n/a | Ours on Base UI dialog | n/a | n/a | nothing good | none |
| Chart, price chart 1M to 10Y (60) | lightweight-charts 5.1 (installed; latest v5.2.1, 2026-08-12) | Candles, ranges, crosshair | Our theme, range chips | Apache-2.0 | push 2026-11-06 | have | none |
| Ratios with percentiles (61), score summary (62), peers (64), Piotroski grid (66) | Ours; FinanceToolkit as reference | n/a | Ours | MIT | see above | have | none |
| Statements with drill-down (63) | edgartools for US (standardised rows, quarters, TTM); yfinance for India | US statements without scraping | Drill-down UI | MIT | v5.62.1, 2026-10-23 | adopt (US) | none |
| Pros, cons, red flags (65) | none | n/a | Rules on our metrics | n/a | n/a | nothing good | none |
| One-page PDF with Typst (67) | typst-py (Typst 0.15.x); reportlab (installed) as fallback | Compiles `.typ` to PDF in process | Template, chart images | Apache-2.0 | Typst v0.15.1 2026-07-17; typst-py v0.15.0 2026-06-16; PyPI typst 0.15.2 2026-11-05 | adopt | none |
| Compare 6 to 25, compare basket, peer mode (55) | none | n/a | Ours | n/a | n/a | nothing good | none |

## Batch 4: Formula

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| CodeMirror formula bar on `signal_lang`, autocomplete, preview (H) | `codemirror`, `@codemirror/view`, `@codemirror/autocomplete`, `@lezer/lr`, `@lezer/generator` | Editor core, completion popup, lint markers, Lezer grammar tooling. Bundlephobia reads about 80 KB (view) and 98 KB (autocomplete) gzip, with shared dependencies, so confirm with `size-limit` | Lezer grammar for `signal_lang`; function catalogue endpoint; lint from `SignalError` start and end spans (already returned) | MIT | npm: view 6.43.15 on 2026-10-19; lr 1.4.12 on 2026-10-30. GitHub repos archived 2026-04-15 | adopt | H to M (bar only) |
| `core/formula.py` reduced to a thin adapter | none | n/a | Merge `formula.py` (19.8 KB) into `signal_lang` | Ours | n/a | have | H |
| Query or formula language with custom ratios (39) | `signal_lang.py` (have) | Parser, whitelist, spans | Screen-specific fields | Ours | n/a | have | none |
| Historical functions (41) | `signal_lang.py` time-series operators (have). Qlib expression names as a naming guide | Operator names | Rolling rank, cross above | MIT (Qlib) | Qlib v0.9.8 2026-10-08 | have | none |
| Named custom metrics (40); formula as new column | none | n/a | Store and column plumbing | n/a | n/a | nothing good | H stays |

Monaco is installed (`@monaco-editor/react`). `PLAN.md` keeps it for Studio only; the formula bar should not load it.

## Batch 5: Freedom

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Every output opens as table, bars, scatter, heatmap, treemap, ranked list, distribution, mini-chart grid (H) | Our `src/charts` (Heatmap, Treemap, XYPlot, Distribution, BarList, RankList, Beeswarm exist). Graphic Walker for ideas | Form switcher and encoding-channel model as ideas | `Explore` switcher | Apache-2.0 (Graphic Walker) | push 2026-11-07; v0.5.0 2025-11-27 | have; Graphic Walker ideas only (1.4 MB gzip, ships its own look) | H stays |
| Any column as x, y, size, colour, group, facet | Vega-Lite encoding names as our option schema (no runtime) | Channel vocabulary | Option panel | BSD-3 | v6.5.0, 2026-10-08 | ideas only | none |
| Add any metric by typing (49); absolute or percentile per column (50) | TanStack Table column API; DuckDB `percent_rank()` | Column state | Metric picker | MIT | see above | have | none |
| Group by and pivot with count, median, mean, sum (H) | DuckDB `GROUPING SETS`, `ROLLUP`, `PIVOT` (PIVOT read in docs today) plus TanStack Table grouping. Fallback: Perspective client (WASM) | Aggregation in SQL | Group UI, summary rows | MIT / Apache-2.0 | Perspective v5.8.0, 2026-11-06 | adopt DuckDB | H to M |
| Conditional formats; density, order, width, pinning, hiding | TanStack Table column features | Pin, order, size, visibility state | Formats, our look | MIT | see above | have | none |
| Exhibits resized, reordered, hidden, expanded | react-grid-layout 2.2 (installed; latest 2.3.0), dnd-kit for list reorder | Grid drag and resize; sortable lists | Exhibit chrome | MIT | rgl release 2026-10-05; dnd-kit push 2026-10-31 | have, adopt dnd-kit | none |
| Save any arrangement as a view; share; reset (49) | zustand `persist` (installed) for local; own table for server views | Local persistence | Schema, share, reset | MIT | zustand v5.1.0, 2026-11-06 | have | H stays |
| Whole state in the URL | nuqs 2.10.2 | Typed search-param state, 6.5 KB gzip | Serialise filters, sorts, view | MIT | push 2026-11-03; release 2026-10-08. Peer: next >=14.2, react 18 or 19 | adopt | H to M |
| Export any view as CSV, Excel, Markdown, SVG, PNG, PDF | `charts/export.ts` (have), XlsxWriter, typst-py | SVG and PNG exist; Excel and PDF from picks above | Markdown writer, view-to-file glue | see above | see above | have, adopt | none |
| Every action has a keyboard path and palette entry | react-hotkeys-hook; cmdk | Bindings | Action registry | MIT | see above | adopt | none |
| Scatter lens (53), mini-chart grid (54), treemap and heatmap lens (52) | Our `XYPlot`, `Treemap`, `Heatmap`, `TimeSeries` | n/a | Lenses | Ours | n/a | have | none |

## Batch 6: Trust

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Why-here, near-miss, evidence badge, reproducible run, screen diff, explain the difference (U2, U3, U8, U9) | none for logic. DuckDB `EXCEPT` and full outer join for diffs; sha256 for data hash | Set difference in SQL | All of it | MIT | see above | nothing good (own) | none |

OpenTerminalUI (MIT, 387 stars, v0.9.0 on 2026-11-01) labels every quote as live, delayed, cached or synthetic and says why a metric is blank. Same idea as our "unknown stays unknown". Ideas only.

## Batch 7: Rank

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Composite, weights, waterfall; ranking system (43) | `composite.py` (have); our `Waterfall` chart | n/a | UI | Ours | n/a | have | none |
| Pre-built screens, about 30 templates (44) | PKScreener scanner rules (MIT) and xang1234/stock-screener presets (Apache-2.0) for definitions of Minervini, CANSLIM-style and breakout screens | Starting rule sets to review | Name by formula, fix to our fields, label weak evidence | MIT / Apache-2.0 | PKScreener push 2026-10-02 (408 stars); xang1234 push 2026-11-08 (416 stars) | copy (rules, after reading each) | none |
| ML hand-off, rules versus learned ranks (81, U6) | none | n/a | Ours | n/a | n/a | nothing good | H stays |

## Batch 8: Test

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Golden fixtures for validation statistics | skfolio (changelog lists probabilistic and deflated Sharpe), empyrical-reloaded, alphalens-reloaded as test oracles (dev only) | Independent numbers to compare with | Fixture files | BSD-3 / Apache-2.0 | skfolio v1.12.7 2026-11-06; empyrical-reloaded 0.7.2 2026-11-05; alphalens-reloaded 0.5.1 2026-10-26 | adopt (dev) | none |
| `services/shared/` with one PBO and one deflated Sharpe | Our code. Three PBO copies exist now: `research_v2/core/ledger_math.py` (`pbo_cscv`), `ml_v2/core/stats.py` (`cscv_pbo`), `screener_v2/core/backtest.py` (`cscv_pbo`). Two DSR copies | Nothing to download | Merge into one | Ours | n/a | have | H stays |
| Purged CV and Monte Carlo in ML Validate | skfolio `CombinatorialPurgedCV` (in `model_selection/_combinatorial.py`); arch bootstrap (installed) | Splitter, bootstrap | Wire into ML Validate | BSD-3 / NCSA | see above | adopt | H to M |
| Trial ledger and counter (U5) | none | n/a | Ours | n/a | n/a | nothing good | H stays |
| Backtest a screen (78), benchmark (79), overfitting tests (80), rolling starts (83) | `backtest.py`, `validation.py` (have) | Simulate with costs, PBO | UI, rolling start grid | Ours | n/a | have | none |
| One-click proof via ML Validate (U4); data banner; remove old S4, S2, S5 | none | n/a | Ours | n/a | n/a | nothing good | none |

## Batch 9: Monitor

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Saved screens, rename, duplicate (70); schedules and re-runs (72) | `state.py`, `scheduler.py` (have). APScheduler 3.11.3 only if we need cron strings | Cron triggers if wanted | Rename and copy UI | MIT | APScheduler release 2026-06-28 | have | none |
| Run history with entries, exits, rank shifts (71) | DuckDB set difference | Diff | UI | MIT | see above | adopt | none |
| Email, push, webhook (73, 74) | Apprise; ntfy server optional | One call to email, Telegram, webhook, ntfy | Templates, settings, retries | BSD-2 / Apache-2.0 | Apprise v2.2.0 2026-11-08; ntfy v2.37.2 2026-11-04 | adopt | none |
| End-of-day price and indicator alerts (75) | TA-Lib plus `alerts.py` | Indicator values | Alert rules | BSD | see above | adopt | none |
| Fundamental-change alerts (76) | `alerts.py` `fundamental_change_rows` (have) | n/a | Delivery | Ours | n/a | have | none |
| Digest | Apprise plus Typst or HTML | Delivery | Layout | see above | see above | adopt | none |
| Delivered-alert tracking, precision scoreboard (U7) | `alerts.py` `realized_alert_precision` (have). xang1234's forward-return scoreboard for the idea | Backend exists | Scoreboard UI | Apache-2.0 | push 2026-11-08 | have; ideas | H to M |

## Batch 10: Signature ideas

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Filter from a chart: brush, click, drag to create a chip | d3-brush (d3 installed, v7.9.2 on 2026-11-03). Mosaic selections for the pattern | Brush behaviour | Chip creation, our marks | ISC / BSD-3 | Mosaic v0.35.0 2026-11-03 | have; Mosaic ideas | H to M |
| Live funnel | DuckDB `count(*) FILTER` per step | One query | UI | MIT | see above | adopt | H stays |
| Sensitivity strip | DuckDB re-count at shifted thresholds | Fast re-runs | Strip chart, return delta | MIT | see above | adopt | H stays |
| Time machine (as-of date) | none | n/a | Ours (fundamentals 2021+) | n/a | n/a | nothing good | H stays |

Mosaic pushes filtering into DuckDB and uses pre-aggregated indexes for cross-filters (read from its docs and paper). With 4,158 rows, plain client-side filtering is fast enough, so we take the selection idea and skip the framework (core is 78 KB gzip).

## Batch 11: Extras

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Crypto, forex, futures, price-only (14) | yfinance (installed). ccxt only if exchange data is needed | Symbols like `BTC-USD`, `EURUSD=X` | Price-only flags | Apache-2.0 / MIT | ccxt v4.5.92 2026-11-04 | have | none |
| Hourly screens (26) | `data/intraday_hourly_v5` (have) | Store | Screen on hourly | Ours | n/a | have | none |
| Share links and public screens (45) | nuqs for state; own short ids | URL state | Storage, public flag | MIT | see above | adopt | none |
| API keys and limits (57) | slowapi | Rate limits per key | Key issue and storage | MIT | v0.1.10, 2026-06-13 | adopt | none |
| Plain English writes an editable formula (46) | Model API with a tool schema; `signal_lang` parser rejects bad output; send the error back once | Validator and spans exist | Function catalogue prompt, retry loop. instructor (MIT) or outlines (Apache-2.0) only if we run local models | MIT / Apache-2.0 | instructor v1.17.0 2026-09-09; outlines 1.3.3 2026-08-06 | nothing good (own) | H to M |
| Chart patterns, weak evidence, last (25) | TA-Lib candlestick patterns (BSD). Geometric patterns: scipy `find_peaks` (installed) | Candlestick set | Geometric rules, evidence label | BSD-3 | see above | adopt (candles); nothing good (geometric) | H stays for geometric |

## Batch 12: Ship

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Verified pages; palette actions | Playwright (installed) | Routes and screenshots | Specs | Apache-2.0 | 1.60 in `package.json` | have | none |
| Phone layout; visual baselines | Playwright viewport and `toHaveScreenshot` | Baselines | Layouts | Apache-2.0 | see above | have | none |
| Accessibility pass | `@axe-core/playwright` (dev only) | Rule engine | Fixes | MPL-2.0 (file-level; fine as a dev tool) | v4.14.0, 2026-10-15 | adopt (dev) | none |
| Tag `screener-v1` | none | n/a | n/a | n/a | n/a | nothing good | none |

## Later: free data

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| Nifty index lists (12) | Official CSV: `niftyindices.com/IndexConstituent/ind_nifty500list.csv` (columns: company name, industry, symbol, series, ISIN) | The list itself | Fetch, snapshot, as-of | NSE data; terms not checked | page live 2026-11-08 | adopt (data) | E |
| Logos (69) | none | n/a | Keep monogram. Logo repos (nvstly/icons, ticker-logos) show no licence in the API and logos are trademarks | n/a | n/a | nothing good | E stays |
| Full India universe (10) | NSE `sec_bhavdata_full` (prices and delivery) plus UDiFF bhavcopy (ISIN). Parser rules from a third-party post | URL patterns, known traps | Own parser: browser User-Agent, 2 s pause, strip spaces from names and values, read `DATE1` and drop stale holiday files, keep every series, key on symbol and series | NSE data; terms not checked | blog dated 2026-10-13 | adopt (own parser) | M |
| Earnings calendar and surprises (29) | edgartools: 8-K Item 2.02 for US. nselib `Corporate Filings` event calendars and results for India | Filing feed and parsed earnings tables | Calendar, surprise maths | MIT / Apache-2.0 | edgartools 2026-10-23; nselib push 2026-07-18 | adopt (spike nselib) | M |
| Delivery, deals, open interest, flows (31) | nselib (README lists delivery, bulk and block deals, FII/DII, participant OI) | Endpoint wrappers | Storage, schema, date checks | Apache-2.0 | 181 stars, PyPI 2.5.1 on 2026-05-01 | adopt after a spike | M |
| Insider trades (32) | edgartools Form 3/4/5 (US). India: SEBI PIT feed, nothing packaged | Form 4 to DataFrame | India reader | MIT | see above | adopt (US); nothing good (India) | M |
| 13F holdings (33) | edgartools `13F-HR` holdings | Parser | Holder tables | MIT | see above | adopt | M |
| Shareholding (30) | none. satwikbasu/indian-market-data-endpoints (MIT, 3 stars) documents BSE LODR and NSE shareholding endpoints, not a parser | Endpoint notes | Own XBRL parser | MIT | push 2026-06-02 | ideas only | H stays |

## Later: paid data

| Checklist item | Pick | What it saves us | What we build on top | Licence | Last activity | Verdict | Effort |
|---|---|---|---|---|---|---|---|
| 10 to 30 years of statements (36) | edgartools for US filers (free, standardised). India: nothing free | US depth without a vendor | India stays paid | MIT | see above | adopt (US only) | M |
| Analyst estimates and revisions (28) | none | n/a | n/a | n/a | n/a | nothing good | M |
| Real-time prices, minute screens (27) | none | n/a | n/a | n/a | n/a | nothing good | H |
| Point-in-time with delisted names (82) | none. SEC filing dates give US point-in-time fundamentals; delisted prices have no free source | Filing dates | n/a | n/a | n/a | nothing good | H |

## Third-party code checklist

- Add each copied file to `THIRD_PARTY.md` with project, licence, commit and file path.
- Copy only MIT, BSD, ISC or Apache-2.0 code. Keep the licence header in the file.
- FinanceToolkit needs a FinancialModelingPrep key for data. We copy formulas only and feed our data.
- PKScreener and xang1234 presets are rule ideas; recheck every rule against our field definitions before use.

## Ideas only (not shipped, learn from)

| Project | Licence | Why only ideas |
|---|---|---|
| Graphic Walker | Apache-2.0 | Usable licence, but 1.4 MB gzip and its own look. Take the encoding-channel UX |
| Perspective viewer | Apache-2.0 | Ships its own grid and chart look. Client engine is a fallback for pivot |
| Mosaic / vgplot | BSD-3 | Pattern for cross-filter. Too heavy for 4,158 rows |
| Huey (DuckDB-WASM pivot app) | MIT | Pivot UX reference |
| OpenTerminalUI | MIT | Full terminal with its own look. Provenance labels, keyboard shell |
| xang1234/stock-screener | Apache-2.0 | Forward-return scoreboard, 12 markets, relative rotation graph |
| OpenBB (`openbq-org/OpenBB`) | Apache-2.0 per its LICENSE and README today (API shows NOASSERTION); earlier versions were AGPL | Data-provider layer, huge. We need a few fetchers, not a platform. Recheck the licence file at the commit before any copy |
| jugaad-data | none in GitHub; PyPI says "YOLO" | Unclear licence. Endpoint ideas only |
| nsepython | GPL-3.0 | Ideas only |
| vectorbt | Apache-2.0 with Commons Clause | Not open source for our use. Ideas for vectorised sweeps |
| cinar/indicator (Go) | AGPL-3.0 | Ideas only |
| stock-pattern (BennyThadikaran) | GPL-3.0 | Pattern rules as ideas |
| Ghostfolio | AGPL-3.0 | Portfolio app |
| pypbo | AGPL-3.0 | Can serve as an offline check of our PBO |

## Rejected

| Project | Reason |
|---|---|
| Orama | Apache-2.0 but 24 KB gzip and vector features we do not need |
| FlexSearch | Larger API than needed; MiniSearch covers prefix and fuzzy |
| nucleo (MPL-2.0), frizbee (MIT), fzf-for-js | Fast, but a WASM bridge or older code for a 4k-name list |
| exceljs (last push 2025-01-21), SheetJS CE (last push 2024-04-18) | Stale in the browser; Excel is built on the server |
| technicalindicators (JS, last push 2022-11-03), tuneta (archived) | Stale |
| pandas-ta original | GitHub repo returns 404; PyPI latest is a 2025 beta. The `pandas-ta-classic` fork (MIT, 488 stars) is live but TA-Lib is the reference |
| polars-anta (Apache-2.0) | 32 stars, v0.3.1 on 2026-11-01. Too young. Recheck in 2027 |
| TradingView-Screener, finvizfinance | Wrap other sites' private or scraped endpoints; terms risk |
| mlfinlab | Proprietary; no push since 2023-10 |
| backtesting.py | AGPL-3.0 |
| Maybe finance | AGPL-3.0 and archived 2025-07-24 |
| ag-grid, MUI X Premium, Syncfusion | Paid features or unclear licences; TanStack covers us |
| Dockview | Licence not reported by the API |
| hello-pangea/dnd | Licence not reported by the API; dnd-kit is MIT |

## Unverified

- Speed of every fuzzy search library on our names. No benchmark was run. Sizes come from bundlephobia.
- Bundle sizes after tree-shaking for react-querybuilder core (49.6 KB gzip as listed), CodeMirror and Lezer.
- That TA-Lib 0.8.3 installs as a wheel on macOS arm64 and Python 3.12. It states `>=3.9` on PyPI. Run a spike.
- nselib endpoint coverage and reliability. Its README lists them; nothing was called.
- NSE and BSE terms of use for storing or showing their files and CSV lists. Not read.
- The bhavcopy URL patterns and traps come from one third-party blog post (2026-10-13), not from NSE.
- DuckDB `jaro_winkler` and other fuzzy functions, and DuckDB ROLLUP and GROUPING SETS behaviour, were taken from the docs navigation, not read in full.
- TanStack Table pinning, ordering, sizing and grouping features, and react-resizable-panels collapse API: known from earlier versions; not re-read.
- Free India fundamentals. yfinance `.NS` fundamentals coverage was not tested.
- That edgartools XBRL statements go back far enough to count as "10 to 30 years".
- Qlib expression names: from memory, not re-read.
- PKScreener rule quality. Not reviewed.

## Sources

Fetched 2026-11-08 unless noted.

- GitHub API (repo, licence, release): github.com/duckdb/duckdb, duckdb/duckdb-wasm, TA-Lib/ta-lib, TA-Lib/ta-lib-python, dgunning/edgartools, RuchiTanmay/nselib, JerBouma/FinanceToolkit, JerBouma/FinanceDatabase, skfolio/skfolio, stefan-jansen/alphalens-reloaded, caronc/apprise, agronholm/apscheduler, binwiederhier/ntfy, typst/typst, messense/typst-py, jmcnamara/XlsxWriter, 47ng/nuqs, react-querybuilder/react-querybuilder, lucaong/minisearch, leeoniya/uFuzzy, krisk/Fuse, oramasearch/orama, perspective-dev/perspective, Kanaries/graphic-walker, uwdata/mosaic, rpbouman/huey, charkour/zundo, clauderic/dnd-kit, JohannesKlauss/react-hotkeys-hook, laurentS/slowapi, dequelabs/axe-core-npm, pkjmesra/PKScreener, xang1234/stock-screener, Hitheshkaranth/OpenTerminalUI, openbq-org/OpenBB, polakowo/vectorbt, aeron7/nsepython, jugaad-py/jugaad-data.
- Read with TinyFish: https://github.com/TA-Lib/ta-lib, https://github.com/dgunning/edgartools, https://github.com/openbq-org/OpenBB, https://codemirror.net/, https://duckdb.org/docs/current/core_extensions/excel, https://duckdb.org/docs/current/sql/statements/pivot, https://hikmahtechnologies.com/blog/nse-bhavcopy-python/
- Search results used for discovery: https://github.com/topics/stock-screener, https://react-querybuilder.js.org/docs/tips/comparison, https://idl.uw.edu/mosaic/core/, https://perspective-dev.github.io/, https://platform.kanaries.net/graphic-walker/client-side/use-duckdb-wasm-as-computation, https://www.pkgpulse.com/guides/fusejs-vs-flexsearch-vs-orama-client-side-search-2026, https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv, https://github.com/satwikbasu/indian-market-data-endpoints
- npm and PyPI registries: registry.npmjs.org and pypi.org/pypi for versions and licences; bundlephobia.com/api/size for gzip sizes.
