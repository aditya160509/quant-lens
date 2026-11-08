# Screener product review: one-stop screener, redone against the feature rule

Redone 2026-11-08 against the feature rule in `docs/plans/PLAN.md` section 1b. It replaces the 2026-10-06 version. Competitor findings, prices and sources are in `docs/references/2026-11-screener-competitors.md`. Backend claims below were checked against `backend/app/services/screener_v2/` on the same date.

## Contents
1. Verdict
2. Data we hold, and its limits
3. Competitors in one page
4. Parity table
5. Information on the screen
6. What only we do
7. Cut list
8. Global search
9. Pages and build order
10. Tiers and data licence
11. Evidence per method
12. Sources

---

## 1. Verdict

Every screener people pay for does the same four things: filter, show a table, save and alert, and export. India's paid tools (Screener.in, Trendlyne, Tickertape, Chartink, StockEdge) add shareholding, estimates and fast technical scans. Global ones add estimates, long history and charts. Almost none of them tell the user whether a result can be trusted. Portfolio123 comes closest and is hard to learn.

Our position follows the platform rule: **the screener that tells you whether to trust the answer.**

- **Parity first.** Section 4 lists 83 features people pay for. 35 exist in the backend, 29 are builds on data we hold, and 19 need data we do not have.
- **Then what only we do.** Section 6: trust on every result, why-here, near-miss, proof in one click, ML hand-off, alert precision.
- **Cut the rest.** Section 7 lists 20 things we will not build, with reasons.
- **Do not fake data.** Estimates, shareholding, long history, delisted names and real-time prices are marked "needs data".

Two facts change the earlier plan:

1. **India is half-reachable today.** The Screener loads only `market_universe.parquet` (4,158 tickers, 4,147 of them US-style). But `master_fundamentals.parquet` already holds 333 NSE and 98 BSE tickers, and `backend/data/prices/` holds 335 `.NS` price files. A loader change (merge-map decision 16) would open about 400 Indian names. Full coverage (Tickertape lists 6,033) needs a vendor.
2. **The old review overstated alerts.** It said the backend stores matured alert precision. It does not. `core/alerts.py::alert_precision_backtest` replays two conditions (golden cross, RSI extreme) over history and says in its own text that this is "not delivered-alert precision". Delivered-alert tracking is a build.

---

## 2. Data we hold, and its limits

| Data | Coverage (checked 2026-11-08) | Consequence |
|---|---|---|
| Daily prices, `market_universe.parquet` | 4,158 tickers, 1996-03 to 2026-07, 10.8M rows; 4,147 US-style, 11 with exchange suffixes | Price screens and backtests run 30 years. No delisted names (survivorship bias) |
| Per-ticker price files, `backend/data/prices/` | About 3,000 files incl. 335 `.NS`, Hong Kong, Japan, Korea, China, Germany and index files (`_IDX_NSEI`, `_IDX_NSEBANK` and others) | Not read by the Screener loader today |
| Hourly prices, `market_universe_hourly.parquet` | Present | Hourly screens possible. Minute or real-time: no |
| Statement fundamentals, `master_fundamentals.parquet` | 37,123 rows, 3,833 tickers, report dates 2021-01-31 to 2025-12-31; 20,599 quarterly and 16,524 annual rows; 364 columns; currencies USD 14,713 rows, INR 3,736, EUR 2,483, KRW 1,986, AUD 1,152 | Fundamental screens work now. Backtests cap at about 4.5 years with a +90-day availability lag |
| Tickers in fundamentals by market | 1,407 US-style, 333 NSE, 199 Korea, 171 Australia, 115 Saudi, 106 Taiwan, 105 Israel, 100 Indonesia, 99 Tokyo, 98 BSE | Global fundamentals exist beyond what the Screener loads |
| Current vendor snapshot columns | `marketCap`, `trailingPE`, `forwardPE`, `priceToBook`, `dividendYield`, `debtToEquity`, `returnOnEquity`, `grossMargins`, `currentRatio`, sector, industry | Snapshots, not history. Never used as history (backend rule). `forwardPE` is not an analyst-estimate history |
| FX, crypto, futures daily | `canonical/fx_daily`, `crypto_daily`, `futures_daily` | Exact-date FX conversion done. Price-only screens for crypto and futures possible |
| Macro, FF factors, VIX | Present | Regime split and factor exposure of a screen |
| Not held | Analyst estimates and targets, shareholding, insider trades, 13F, earnings calendar, news, filings, transcripts, dividend history, segment data, ISIN, logos, mutual-fund and ETF holdings, historical index membership, historical sector codes, delisted names, real-time prices, options chains | Marked "needs data" in section 4 |

Backend rules that stay: reports become available 90 days after period end; unknown stays unknown; no forward-filled prices; a missing held price invalidates a backtest rather than being guessed.

**Display licence.** A screener shows raw prices and ratios, so public launch needs a display or redistribution licence. Cost not re-checked on 2026-11-08; the 2026-10 note named Twelve Data Venture from about $149 per month as the cheapest explicit external-display plan found. Budget it before charging.

---

## 3. Competitors in one page

Prices as listed 2026-11-08; details and marks of what is unverified are in the reference file.

| Product | Paid tiers and prices | What the money buys |
|---|---|---|
| Screener.in | ₹0; Premium ₹4,999 per year | Columns (800), screens (75), alerts, unlimited company views, Excel export, prioritised email |
| Trendlyne | GuruQ ₹390 per month (₹2,190 per year); StratQ ₹5,900 per year; Pro ₹8,900 per year; Pro Plus ₹11,900 per year | 1,758 to 3,512 parameters, DVM scores, consensus estimates, screener alerts (75 daily or 300 every 15 min), backtests (200 or 1,200 per year), 15-minute technicals, Excel Connect |
| Tickertape | Free; Pro ₹399 per month, ₹2,999 per year | Custom filters and universes, forecasts, scorecards, red flags, 100+ benchmark metrics, data export, pro alerts |
| Chartink | Free; Premium ₹780 per month, ₹8,500 per year | 1 to 3 minute real-time scans, alerts (desktop, SMS, email), custom columns, auto refresh |
| StockEdge | Premium ₹399, Pro ₹1,499, Club ₹2,499 per month | 500+ scans, custom and combination scans, chart patterns, scores, sector rotation, downloads |
| Moneycontrol Pro | About ₹99 per month on the app store (unverified) | Stock score, scanners, research picks |
| Finviz | Free; Elite $39.50 per month | Real-time, 100 rows, 50 vs unlimited presets, alerts, export |
| TradingView | $0 to $199.95 per month | 500+ fields, Pine Screener, chart and heatmap views, alerts and webhooks, AI screener requests, backtest in Pine |
| Koyfin | $0, $39, $79 per month | 5,900+ filter criteria, global, estimates, formulas (1, 10, unlimited), 10-year statements |
| Stock Rover | $29, $49, $79, $149 per month | 300 to 800 metrics, equations, ranked and percentile screening, research reports, scores |
| Stockopedia | $395 to $600 per year | StockRanks, 350+ ratios, 65 guru screens, folios, alerts |
| Seeking Alpha | Premium $299 per year; Pro about $2,400 | Quant rating, factor grades A to F, ratings screener |
| Simply Wall St | $10.95 and $21.50 per month | Snowflake summary, 10 or unlimited saved screens |
| GuruFocus | $549, $1,398, $2,448 per year | All-in-one screener, 30-year financials, 13F trades, backtest 5 years or to 2006, delisted stocks (Pro) |
| Zacks | Premium $249; Ultimate $2,995 per year | Zacks Rank, premium screens, Research Wizard |
| TIKR | $24.95, $54.95, $119.95 per month | Global screener, 10 to 30 years of data, transcripts, guru holdings |
| Fiscal.ai | About $39 to $99 per month (sources conflict) | AI research, screener, API and MCP |
| YCharts | About $3,600 per seat per year | Advisor screens, 4,500+ metrics, natural-language builder |
| Portfolio123 | From about $25 up to $250 per month (unverified) | Screen, rank, rolling backtest, 4,300+ factors, point-in-time data, AI Factor |
| QuantConnect | Free and node tiers | Code-first universe selection and honest backtests |
| Bloomberg EQS | About $32,000 per seat per year | Institutional ceiling |
| LSEG Workspace | Not published | Companies, deals and funds screener, Python library |

**Where nobody is honest.** None of these show data limits on a result, none count how many screens the user tried before a backtest looked good, and none show a name that missed by one filter.

**What users say.** Too many results with no order; numbers differ across tools; backtests that do not match real returns; alerts and exports locked behind tiers; dated interfaces; survivorship bias. Sources in the reference file section 4.

---

## 4. Parity table

Status values: **have backend** (code exists and was read), **build** (data in hand; code or UI is new), **needs data** (we do not hold it; source and cost given). "Tier" is the cheapest paid tier that shows the feature, where known. Competitor abbreviations: SI Screener.in, TL Trendlyne, TT Tickertape, CK Chartink, SE StockEdge, MC Moneycontrol, FV Finviz, TV TradingView, KF Koyfin, SR Stock Rover, SO Stockopedia, SA Seeking Alpha, SW Simply Wall St, GF GuruFocus, ZK Zacks, TK TIKR, FA Fiscal.ai, YC YCharts, P123 Portfolio123, QC QuantConnect, BB Bloomberg, LS LSEG.

### 4.1 Universe and data

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 1 | Filter by sector, industry, exchange, market-cap range | All | have backend | `sector`, `industry`, `industry_group`, `exchange`, `market_cap` filters in `features/inputs.py`. Industry group is a static mapping, not company-level GICS |
| 2 | Market-cap buckets with counts | FV, TV, TT, SE | build | Bucket logic exists only inside peer scope (`valuation.py`); counts per bucket are new |
| 3 | Price, volume and dollar-volume floors, penny-stock exclusion | All | have backend | `price`, `dollar_volume`, `exclude_penny_stocks` |
| 4 | Custom universe: pasted tickers, CSV upload, saved universes | SR Ultimate, TT Pro, TV, KF | have backend | Uploads (2 MB, UUID-named, validated) and `/universes` |
| 5 | Watchlists as universe or filter | TV (Plus), SR, TT, FV | build | Saved universes serve as watchlists; add star and list UI |
| 6 | Run as of a past date | P123, SR Plus historical, TL rewind (StratQ weekly) | have backend | `as_of_date` with the 90-day availability lag |
| 7 | Coverage per metric ("P/B known for N of M") | None (we add) | build | Small count endpoint |
| 8 | Country and currency filter | TV, KF, TK, GF | build | Currency metadata and FX conversion exist; country from exchange suffix |
| 9 | India NSE and BSE coverage | SI, TL, TT, CK, SE, MC | build | About 400 names reachable by loader change (decision 16). Full list needs data below |
| 10 | Full India listed universe (about 6,000) | TT 6,033 | needs data | Source: NSE and BSE master and bhavcopy files (public, redistribution terms unverified) or a vendor. Cost: not checked |
| 11 | Global exchanges (150+ exchanges from 50+ countries) | TV, KF, TK, GF | needs data | We hold fundamentals for about 20 markets but prices and listings are partial. Vendor needed. Cost: by quote |
| 12 | Index constituents as a universe (Nifty 50, S&P 500) | All | needs data | Current lists: NSE index files are public; S&P lists are licensed. Historical membership: Norgate or Sharadar. Cost: by quote |
| 13 | Mutual fund and ETF screener | TT (MF 50+ filters), TV, KF, SR, SA | needs data | We hold some ETF prices, no holdings or expense ratios. India MF: AMFI NAV files are public. Cost: not checked |
| 14 | Crypto, forex and futures screens (price only) | TV | build | `crypto_daily`, `fx_daily`, `futures_daily` held. Technical filters only |

### 4.2 Filters

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 15 | Valuation: P/E, P/B, P/S, P/CF, EV/EBIT, EV/EBITDA, earnings and FCF yield | All | have backend | `core/fundamentals.py`; negative P/E handling in filters |
| 16 | Profitability and quality: ROE, ROIC, margins, GP/A, interest coverage | All | have backend | |
| 17 | Growth: revenue and EPS YoY, 3-year CAGR | All | have backend | 3-year CAGR needs three adjacent fiscal years, so only recent names qualify |
| 18 | Health and payout: debt/equity, debt/EBITDA, current ratio, dividend yield, payout | All | have backend | |
| 19 | Piotroski F-score (9 checks, unknowns kept) and Altman Z | SO, GF, TT, SR | have backend | `core/academic.py`; unknown when inputs are missing |
| 20 | Momentum, 52-week high proximity, SMA distance, cross flags | All | have backend | `prox52`, `high_proximity`, `momentum_jt`, SMA and MACD flags |
| 21 | Technicals: RSI, MACD, ADX, stochastic, Bollinger, ATR, OBV | TV, CK, SE, FV | have backend | Exposed in formula and some filters. Evidence is weak (section 11) |
| 22 | Risk: realised volatility, beta, drawdown, idiosyncratic volatility, max daily return | SR, KF, TV | have backend | `ivol`, `max_factor`, `beta_252`, `yang_zhang_vol` |
| 23 | Liquidity: Amihud percentile, volume ratio | SE, FV | have backend | |
| 24 | Percentile versus sector or universe as a filter | SR Ultimate, SO, SA | have backend | Percentiles computed in the panel; filter UI is new (see 51) |
| 25 | Candlestick and chart-pattern recognition | SE Pro (15+ patterns), TV, FV | build | Pure OHLCV maths. Weak evidence; ships last and labelled |
| 26 | Hourly-timeframe screens | TL StratQ, TV, CK | build | Hourly file held. Rules identical to daily |
| 27 | Minute-level and real-time screens | CK (1 to 3 min), TL StratQ (15 min), FV, TV | needs data | Source: exchange real-time licence. NSE and US feeds are paid. Cost: not checked |
| 28 | Analyst consensus: targets, ratings, EPS and revenue estimates, revisions | TL, TT Pro, KF, TK, SA, ZK, SR, GF | needs data | Largest paid feature in the market. Source: LSEG, FactSet or a mid-price API. Cost: by quote |
| 29 | Earnings calendar, surprises, results dashboard | TL, KF, SR, TK | needs data | Source: same vendors, or exchange filings (India) and SEC (US). Cost: free for filings, parsing effort |
| 30 | Shareholding: promoter, FII, DII, pledge, change over quarters | SI, TL, TT, SE Pro | needs data | Source: NSE and BSE quarterly shareholding filings (public). Cost: free, parsing effort |
| 31 | Delivery percentage, bulk and block deals, F&O open interest, FII and DII flows | SI (delivery chart), SE, TL | needs data | Source: NSE bhavcopy and deal files (public). `services/nse_direct.py` exists; coverage unverified |
| 32 | Insider trades | SI, TL, FV, GF, KF | needs data | US: SEC Form 4 (free). India: SEBI disclosures (public) |
| 33 | Institutional and guru holdings (13F) | GF, TK, SO | needs data | US: SEC 13F (free) |
| 34 | Dividend history (5 to 30 years) | SR Ultimate, KF, GF | needs data | Statements start 2021. Source: corporate-actions vendor |
| 35 | Segment results, credit ratings | SI, TL | needs data | Source: exchange filings, rating agencies. Cost: not checked |
| 36 | Statement depth of 10 to 30 years | SI 10y, KF 10Y, SR 20Y, TK 30Y, GF 30y | needs data | We hold 2021 to 2025 only. Source: Sharadar, EODHD or a similar vendor. Cost: by quote |

### 4.3 Expression, ranking and templates

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 37 | Filter chips with operators (greater, less, between, in, top N) | All | build | Frontend |
| 38 | AND/OR groups and nesting | P123, SR, TV | build | Round-trip to formula |
| 39 | Query or formula language with custom ratios | SI (all tiers), SR Plus, KF (1, 10, unlimited), TL, P123 | have backend | `core/formula.py` (own parser). Becomes an adapter on `signal_lang` (merge step 16) |
| 40 | Named custom metrics reused as column, filter, sort and rank input | SR (up to 30, unlimited), SI, KF | build | |
| 41 | Historical functions (lag, change, rolling rank, cross above) | P123, SR historical screening | have backend | Formula supports observed OHLCV and fundamental lags |
| 42 | Live count after each filter, with the bottleneck filter shown | None strong (TT shows count) | have backend | `apply_filters` returns stage counts (the funnel). Debounced count endpoint is a build |
| 43 | Composite score and ranking system with weights | P123, SR Plus (ranked screening), SO, ZK, SA, TL (DVM), MC | have backend | `core/composite.py`: equal, IC-IR and ridge weights trained on matured labels |
| 44 | Pre-built screens and templates | TT 50+, SE 500+, SO 65, ZK 50+, GF, KF, TL | have backend | About 15 academic strategies in `core/academic.py`. A gallery of about 30 labelled by formula is a build |
| 45 | Shareable screen link, public screens | SI, CK (200,000 scans), TV, TL | build | Verified share pages exist in ML; screen links reuse them. Public gallery waits on moderation |
| 46 | Plain-English to screen | FA, YC Fast Track, TV (AI requests), SE Club | build | LLM call writes an editable formula, never a black box |
| 47 | Undo, redo, disable a filter | Rare | build | Frontend |

### 4.4 Results screen

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 48 | Sort and page every result, no silent cap | FV (100 rows paid), SR (250 to 5,000 rows by tier), SI | build | Today `top_n` caps at 5,000 and the frontend capped at 160. Server sort, page and count over DuckDB |
| 49 | Column picker, column sets, saved views | SI (800 columns), FV views, KF, CK | build | |
| 50 | Per-column absolute or percentile toggle | SR percentile screening | build | Percentiles exist in the panel |
| 51 | Sector-relative percentile bars in rows | SO, SA, SR | have backend | `valuation_percentile`, `quality_percentile`, `momentum_percentile`, `low_vol_percentile` |
| 52 | Treemap and heatmap lens | FV maps, TV heatmap | have backend | Sector heatmap exists (`heatmap_view`). Ticker-level treemap sized by cap is a build |
| 53 | Scatter lens (any two metrics) | KF | build | |
| 54 | Chart view of results (grid of mini charts) | FV, TV, SE | build | |
| 55 | Compare up to 6 to 25 names side by side | SA 6, FV 25, SR | have backend | Peer table in `core/valuation.py`; UI is a build |
| 56 | Export CSV, Excel, JSON, ticker list | FV Elite, KF, SR, SI, TT Pro, GF | have backend | `core/exports.py`, `/export`; Excel file type is a build |
| 57 | API access and spreadsheet add-in | GF, TL (Excel Connect), FV, FA (API, MCP), TV (MCP) | build | Internal REST routes exist; keys, limits and docs are new. MCP later |
| 58 | Auto-refresh every 10 seconds | FV, TV | needs data | Needs real-time prices (see 27). End-of-day only today |
| 59 | Add to watchlist, to alert, to ML or Research from a row | FV, TV, SR | build | |

### 4.5 Stock quick-look and detail

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 60 | Price chart with ranges 1M to 10Y | All | have backend | `quick_look` returns windows 1M, 3M, 1Y, 3Y, 10Y |
| 61 | Ratios with sector percentile and own-history percentile | SR, SO, KF | have backend | `relative_valuation` (252, 756 or 2,520 sessions) |
| 62 | Score summary: valuation, quality, momentum, low vol, thesis line | SA, SO, SW, MC, TL, SR | have backend | `quick_look`; our own five-axis profile is a build |
| 63 | Statements with line-item drill-down | SI (schedules), SA (10 years), KF | build | 2021 to 2025 only until row 36 is bought |
| 64 | Peer comparison table | SI, SE Pro, SR, KF | have backend | |
| 65 | Automatic pros, cons and red flags | SI x-ray, TT red flags | build | Rules on metrics we hold |
| 66 | Piotroski 9-check grid, Altman zone | SO, GF | have backend | |
| 67 | One-page stock report (PDF) | SR research reports, SA | build | Typst, from data we hold |
| 68 | Fair value or DCF | SR, GF, SW | needs data | Needs estimates (row 28). A DCF on our own assumptions would be a guess, so it is not built |
| 69 | Logos | TV, TT, KF | needs data | No logo source held. Monogram fallback. Licence: not checked |

### 4.6 Monitor

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 70 | Saved screens, rename, duplicate | All; SW limits to 10 | have backend | `/screens`; definitions are immutable per id |
| 71 | Run history with entries, exits and rank shifts | GF (daily additions and deletions), SI | have backend | `core/state.py::compare_and_store` |
| 72 | Scheduled re-runs | SI, TL, GF, CK, FV | have backend | In-process interval scheduler. Not an external cron; a crash can miss one interval |
| 73 | Email and push delivery of screen changes | SI, TL, GF, FV, CK (SMS) | build | Apprise (email, Slack, Telegram, ntfy). Backend has no provider today |
| 74 | Webhook alerts | TV (paid) | build | Same layer |
| 75 | Price and indicator alerts on one stock | TV, KF, SR, TL, FV | build | End-of-day conditions. Intraday needs row 27 |
| 76 | Fundamental-change alerts (results out) | SI, TL | have backend | `fundamental_change_rows` |
| 77 | Alert frequency of 1 to 15 minutes | CK, TL StratQ | needs data | Real-time feed (row 27) |

### 4.7 Test and learn

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| 78 | Backtest a screen with rebalances | TL (200 to 1,200 per year), P123, GF (5 years or to 2006), ZK, CK (hits only) | have backend | `core/backtest.py::simulate`: dated reselection, next-session execution, costs on traded notional, drift |
| 79 | Compare with benchmark | TL, P123, GF | have backend | SPY required; random-screen and equal-weight controls are in ML Validate |
| 80 | Overfitting tests: deflated Sharpe, PBO, bootstrap, controls | None | have backend | CSCV PBO in `core/backtest.py`; the rest lives in ML Validate (merge steps 0 to 4). Trial counting is a build (section 6) |
| 81 | ML ranking on the same features | P123 AI Factor | build | Hand-off to ML Alpha |
| 82 | Point-in-time data with delisted names | P123, GF Pro | needs data | Source: Sharadar, EODHD Custom or Norgate. Cost: by quote. Removes the Test banner |
| 83 | Rolling screen backtests over many start dates | P123, TL | build | Loop over `simulate` with different offsets |

**Counts.** 83 rows: have backend 35, build 29, needs data 19. By group: universe and data 4 / 6 / 4; filters 10 / 2 / 10; expression and templates 5 / 6 / 0; results screen 4 / 7 / 1; quick-look 5 / 3 / 2; monitor 4 / 3 / 1; test 3 / 2 / 1 (have / build / needs data).

---

## 5. Information on the screen

Every element the market shows, with what we have. "Trust" elements are ours.

### 5.1 Results screen

| Element | Seen at | Ours |
|---|---|---|
| Result count, universe name, as-of date, last-updated time | TT, SI | Show all four. Add data version hash |
| Active filter chips with per-chip live count | FV, TT, KF | Show; mark the bottleneck chip |
| Rank, ticker, company name, sector or sub-sector | All | Have in `top_table` |
| Price, 1D and 1M return | TT, FV | Price and `return_6m` held; 1D and 1M are simple additions |
| Market cap in local currency | All | Have, with FX note |
| Core ratios: P/E, P/B, ROE | TT, SI | Have |
| Quarterly profit and sales with variance | SI | Have statements; quarterly variance is a build |
| Dividend yield | SI, FV | Have |
| Volume, relative volume | FV, CK | Have `vratio`, `dollar_volume_20d` |
| Composite score and percentile bars | SO, SA, TL | Have four percentiles and `core_quant_score` |
| Sparkline | TV, FV | Build from price history |
| Score badges (grade, rank) | SA, SO, SR | Own badges; no guru names |
| Trust flag per row: data basis, unknown inputs, survivorship, statement age | None | Build (section 6) |
| Why-here expander | None | Build |
| Near-miss list below the table | None | Build |
| Row actions | FV, TV | Build (row 59) |
| Export, save, alert, share, test | All | Build and have |

### 5.2 Quick-look drawer and detail

| Element | Seen at | Ours |
|---|---|---|
| Price chart with ranges | All | Have |
| Key stats grid | All | Have |
| Sector and own-history percentile bars | SR, KF | Have |
| Score profile (value, quality, momentum, low vol, growth) | SW, SA | Have four; build the profile chart |
| Piotroski nine checks and Altman zone | SO, GF | Have |
| Peers | SI, SE | Have |
| Statements and trends | SI, SA | 2021 to 2025 only |
| Pros, cons and red flags | SI, TT | Build |
| Shareholding, insiders, estimates, news | SI, TL, SA | Needs data |
| Alerts on this name, add to watchlist, screen or lab | FV, TV | Build |
| Data note: sources, lag, missing inputs | None | Build |

---

## 6. What only we do

Each of these is a reason to pay that no product in section 3 offers.

| # | Feature | What it does | Status |
|---|---|---|---|
| U1 | Trust on every result | A badge per result set and per row: data basis (fundamentals 2021 to 2025, 90-day lag, no delisted names), unknown inputs, price basis. Hatched cell for unknown, never zero or blank | build; the facts are in the backend response |
| U2 | Why is this name here | Row expander listing every filter, the value, the threshold, the margin and the sector percentile | build; `apply_filters` already runs stage by stage, margins are new |
| U3 | Near-miss explorer | Names that fail exactly one filter, sorted by miss size, with a "relax this filter" action | build; funnel data exists, one-fail set is new |
| U4 | Screen to proof in one click | Test sends returns to ML Validate: controls, deflated Sharpe, PBO, bootstrap, autopsy, verified page | have backend (S5 engine, ML Validate); wiring is a build |
| U5 | Trial counter | Every screen variant tried counts as a trial, so the deflated Sharpe uses the true number. Shown on the screen itself | build; needs the trial ledger (merge step 15, decision 4) |
| U6 | ML hand-off | "Train a ranker on this" sends the universe and features to ML Alpha and compares rules against learned ranks | build |
| U7 | Alert precision | Forward return after each delivered alert, matured, per rule | build; backend has only a replay of two conditions today |
| U8 | Evidence badge per filter | Robust, mixed or weak with a citation, from section 11 | build |
| U9 | Reproducible run | A run id, as-of date, data hash and formula text stored with every result; two runs can be diffed | have backend (dated runs in SQLite); data hash and diff are builds |
| U10 | Data limits printed, not hidden | Limits show on results, backtests and exports | build |

---

## 7. Cut list

Reason codes: **N** not a screener job; **E** weak evidence or invites overfitting; **R** regulatory or advice risk; **D** needs data we will not buy now; **S** scope (belongs to another module).

| # | Cut | Offered by | Reason |
|---|---|---|---|
| C1 | News, articles, transcripts, concalls | SA, SI roadmap, MC, KF | N: not screening |
| C2 | Community, chat, live sessions, education | SE Club, SO, TV | N |
| C3 | Broker connect and order placement | SE, TT, P123 | R, S |
| C4 | Stock picks and model portfolios | ZK Ultimate, SA Alpha Picks, Validea, SE Club | R: advice, and unvalidated |
| C5 | Guru-name strategy screens | GF, SO | E, R: keep the formula, drop the name; templates labelled by formula |
| C6 | Options chain and F&O analytics | SE, TL Pro Plus | D, S |
| C7 | Short and hedged strategy books | P123 | S: belongs to Studio |
| C8 | Parameter optimizer over screens | P123 | E: invites overfitting. CSCV in Validate is the honest version |
| C9 | Strategy leaderboard and strategy correlation (old S4) | Internal | E: 4.5 years of history |
| C10 | Factor-zoo comparison (old S2) | Internal | D: no external zoo |
| C11 | Duplicate Monte Carlo and PBO pages (old S5) | Internal | S: Validate owns them |
| C12 | Oscillators promoted as first-class filters | TV, CK | E: weak after data-snooping correction. They stay in the formula language |
| C13 | Native mobile app | TT, SE, MC | S: responsive web first |
| C14 | SMS alerts | CK | N: cost per message; use push and email |
| C15 | Auto-refresh every 10 seconds | FV, TV | D: no real-time feed |
| C16 | DCF on invented assumptions | SW, GF | E: false precision without estimates |
| C17 | Forward P/E, float, "S&P 500" universe, OTC | Many | D: already removed from the backend |
| C18 | 800 columns on day one | SI | N: a pruned set with the formula bar covers it |
| C19 | Seats, shared workspaces, white-label reports | KF Advisor, YC | N for now: team tier comes later |
| C20 | Crypto and forex fundamentals | TV | D: price-only screens only (row 14) |

---

## 8. Global search

Spec (from `docs/plans/PLAN.md`, shared by every module and built first for the Screener). The current `/symbols` route matches substrings on price file names only, so it needs replacing.

| Item | Spec |
|---|---|
| Open | Keyboard from anywhere; a large overlay |
| Finds | Ticker, company name, ISIN. Tolerant of typos. Instant |
| ISIN | Needs data. We hold none; source: exchange and depository master files or a vendor. Cost: not checked |
| Tabs | Symbols, Screens, Runs, Docs |
| Chips | Stocks, Funds, Indices, Forex and others, shown only where we hold data (stocks, indices, FX, crypto and futures today; funds not) |
| Row | Logo (monogram until logos are sourced), ticker, full name, type, exchange |
| Actions | On hover or arrow keys: open chart, see overview, add to screen, run in a lab |
| Before typing | Recent and popular symbols |
| Index | About 7,000 symbols fit in memory; ship a compact index to the client. Rank: exact ticker, ticker prefix, name word prefix, then fuzzy |
| Library | cmdk is installed for the shell. Fuzzy matching library chosen after a short spike (MiniSearch or Fuse.js; licences to confirm) |
| Names | `company_name` appears in the results table; confirm its source covers all symbols before relying on it |
| Done when | Any symbol opens from anywhere by keyboard (PLAN stage 2.6) |

---

## 9. Pages and build order

Four pages, as before, plus the global shell.

| Page | Carries | Key parity rows |
|---|---|---|
| Screen | Chips, formula bar, table, lenses, quick-look, why-here, near-miss, templates, plain English | 1 to 9, 15 to 24, 37 to 59, 60 to 69 |
| Rank | Composite, weights, waterfall, ML ranker hand-off | 43, 81 |
| Test | Backtest, Validate hand-off, data banner, trial counter | 78 to 80, 83 |
| Monitor | Saved screens, schedules, alert rules, precision scoreboard, digest | 70 to 77 |

Build order matches PLAN step 2 (stages 2.1 to 2.11). Merges Screener carries are in `docs/architecture/CROSS_MODULE_MERGE_MAP.md` section 0 and in PLAN section 6a.

Backend changes needed, all small:

1. Server sort, page and count endpoint over DuckDB (row 48).
2. Per-filter margins and the one-fail set (U2, U3).
3. Coverage per metric (row 7).
4. Delivery layer on Apprise (rows 73, 74, 75).
5. Delivered-alert tracking (U7).
6. Loader change for the per-ticker price store (decision 16).
7. Formula adapter on `signal_lang` (row 39).

Removals, with the usual graph and `rg` checks first: S4 leaderboard, correlation and historical-strategy outputs; S2 factor-zoo output; S5 Monte Carlo and PBO duplicates once Validate owns them; any filter tied to absent data.

---

## 10. Tiers and data licence

Proposed, not decided. Payments are PLAN stage 9.4.

| Tier | Anchor | Includes |
|---|---|---|
| Free | $0 | Screen with full count and 50 rows shown, 2 saved screens, templates, quick-look, end-of-day data, data banner |
| Pro | About $29 per month; India price near Tickertape and Trendlyne annual plans (₹2,190 to ₹5,900 per year) | Unlimited screens and columns, formulas, Rank, export, daily alerts by email and push, why-here, near-miss |
| Quant | About $79 per month | Test with Validate, autopsy, verified pages, ML ranker, webhooks, API, trial ledger |
| Team | Quote | Seats, shared screens, white-label reports, point-in-time add-on |

Pro sits below Koyfin Plus-to-Premium and Finviz Elite on price while adding ranking and proof they lack. Quant sits below Portfolio123 Professional.

Data licence: see section 2. Point-in-time and delisted data is the biggest quality lever for Test. Both are business decisions, not code.

---

## 11. Evidence per method (does it work out of sample?)

| Method | Original | Out-of-sample and replication | Data fit here | Grade |
|---|---|---|---|---|
| Anomaly screening in general | — | McLean & Pontiff (2016): returns **26% lower out-of-sample and 58% lower post-publication**. Hou, Xue & Zhang (2020): **65% of 452 anomalies fail** with value-weighting and NYSE breakpoints; 96% of trading-friction ones fail | Value-weight and microcap handling are mandatory | Context for everything |
| Value (B/M, E/P, EV/EBIT) | Fama-French 1992 | Robust long-run, weak 2007–2020, recovered since 2021 | 2021+ statements: fine for screens, short for backtests | 4 |
| Gross profitability (GP/A) | Novy-Marx 2013 | Replicated; works best combined with value | Available | 5 |
| Piotroski F-score | Piotroski 2000 | Still predictive internationally 2000–2018 (Walkshäusl 2020); strongest in small or neglected value stocks | Needs prior-year statements: 2022+ usable | 4 |
| Magic Formula | Greenblatt 2005 | Positive but degraded post-publication; underperformed the S&P in the 5 years to 2024 | Usable as a template, not as a promise | 3 |
| Altman Z | Altman 1968 | Distress classifier, 75–90% accuracy historically, declining; not a return signal | Use as a risk flag | 3 (as flag) |
| Momentum 12-1 | Jegadeesh-Titman 1993 | One of the most robust; crash risk | 30 years of prices | 5 |
| 52-week-high proximity | George-Hwang 2004 | Replicated in 18 countries; helps against momentum crashes | Prices | 5 |
| Short-term reversal | Jegadeesh 1990 | Real but cost-sensitive | Prices | 3 |
| Low volatility / IVOL / MAX | Ang et al. 2006; Bali et al. 2011 | Low-vol robust; IVOL and MAX weaken under value-weighting (trading-friction class in HXZ) | Prices | 4 low-vol / 2 IVOL-MAX |
| Amihud illiquidity | Amihud 2002 | Mostly fails in value-weighted tests (HXZ) | Prices | 2 (keep as a tradability filter, not a signal) |
| Technical oscillators (RSI, MACD, Stochastic, Williams %R, consecutive days, gaps) | — | Data-snooping-corrected tests (Sullivan-Timmermann-White 1999; later re-tests) find little to no edge after costs; a 2026 sweep of 14M tests found RSI "produced nothing" | Prices | **1–2** |
| Composite multi-factor | MSCI, AQR | Combining value, momentum and quality raises the information ratio (MSCI: IR to 1.17); factors fail at different times | Supported | 5 |
| Relative valuation (vs sector and own history) | Practitioner | Weak academic support for own-history mean reversion; sector-relative is standard practice | Own history only 2021+ | 3 |
| Learned weights (IC-IR, ridge) | — | Helps when trained on matured labels; overfits with short histories | Short fundamentals history makes it fragile | 3 (better done in ML Alpha) |

**Implication:** the filter list should lead with what survives (value, profitability, momentum, 52-week high, low volatility, composite). Oscillators move out of the first-class filter list into the formula language, available but not promoted.

---

## 12. Sources

Competitor and pricing sources, with access dates and what is unverified: `docs/references/2026-11-screener-competitors.md`.

**Evidence**
- McLean & Pontiff (2016): https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
- Hou, Xue & Zhang (2020): https://academic.oup.com/rfs/advance-article/doi/10.1093/rfs/hhy131/5236964 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275496
- Novy-Marx (2013): https://www.sciencedirect.com/science/article/pii/S0304405X13000044
- Piotroski international (Walkshäusl 2020): https://link.springer.com/article/10.1057/s41260-020-00157-2 · https://www.econstor.eu/bitstream/10419/288746/1/s41260-020-00157-2.pdf
- Magic Formula out of sample: https://quantpedia.com/out-of-sample-test-of-formula-investing-strategies/ · https://journals.ue.poznan.pl/REF/article/download/2790/1711
- 52-week high: https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf · https://www.sciencedirect.com/science/article/abs/pii/S0261560610001099 · https://epublications.marquette.edu/cgi/viewcontent.cgi?article=1168&context=fin_fac
- Technical rules and data snooping: https://www.kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf · https://homepage.ntu.edu.tw/~ckuan/pdf/snoop01.pdf · https://www.tradingview.com/chart/ES1!/cWRegl0n-What-14-Million-Tests-Say-About-MACD/
- Altman Z accuracy: https://www.mdpi.com/1911-8074/18/8/465 · https://research.cbs.dk/en/studentProjects/predicting-bankruptcy-an-investigation-of-the-applicability-of-al/
- Multi-factor combination: http://info.msci.com/how-can-factors-be-combined · https://alphaarchitect.com/diversifying-your-value-portfolio-quality-works-but-have-you-heard-of-momentum/
- Relative P/E: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2782945_code2486804.pdf?abstractid=2782945&mirid=1
- Survivorship and point-in-time: https://powakadata.com/survivorship-bias-backtesting.html

**Internal**
- `backend/app/services/screener_v2/DONE.md` (authoritative backend state) and `NOT_POSSIBLE_WITH_CURRENT_DATA.md`
- `docs/reviews/code/SCREENER_V2_REVIEW.md`
- `docs/evidence/frontend-review/screener-v2/review.md`
- `docs/reviews/code/SELL_10_SCREENER_FACTORS_RESEARCH.md`
- Data audit of 2026-11-08: counts in section 2 read from the parquet files.
