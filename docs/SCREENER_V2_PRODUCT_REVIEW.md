# Screener V2 product review: what to keep, cut, merge and add

Date: 2026-10-06. This follows the method of `docs/ML_V2_PRODUCT_REVIEW.md`. It reviews the Screener V2 backend as it stands after the Codex rebuild (commits `3d2270fb` → `8e05a7e8`) and plans the product we build after the ML cinema plan (`docs/ML_CINEMA_PLAN.md`).

**Inputs read**
- `backend/app/services/screener_v2/` (8 features, domain modules, `DONE.md`, `NOT_POSSIBLE_WITH_CURRENT_DATA.md`)
- the original spec `docs/screener features.md`
- `docs/reviews/SCREENER_V2_REVIEW.md` (blockers B1–B4, A1–A12 and their remediation)
- `docs/reviews/SELL_10_SCREENER_FACTORS_RESEARCH.md`
- `docs/evidence/frontend-review/screener-v2/review.md` (frontend score 5.0/10)
- the local data files
- about 30 web searches on competitors, pricing, demand and academic evidence (sources in §13)

---

## Contents
1. Method and criteria
2. Verdict
3. Data reality (what the data can honestly support)
4. Market and competitor matrix
5. Evidence per method
6. Scored feature table
7. Final cut: keep, merge, remove
8. New A++ features
9. Shared with ML and Research (one platform, not three)
10. Inputs: the filter list, pruned
11. UI and experience
12. Pricing, data licence and build order
13. Sources
14. What to add: the full [B] / [F] / [B+F] build list (parity, differentiators, UX, data-swap readiness)

---

## 1. Method and criteria

Each feature and output is scored 1–5 on the criteria below; the ones that decide keep or cut are in bold. Criteria come from the full 34-item set (A–H):
- **A. Demand:** pain frequency, who has it, current workaround, willingness to pay, trend.
- **B. Evidence:** academic support, replication, post-publication decay, failure modes, data fit.
- **C. Competition:** feature matrix, pricing, review complaints, white space.
- **D. Trust:** look-ahead, survivorship, overfitting controls, honest outputs, reproducibility.
- **E. User value:** decision value, time to insight, clarity, actionability.
- **F. UX:** best-in-class benchmark, visual standard, interaction depth, onboarding.
- **G. Business:** recurring value, tier fit, cost to serve, shareability, data licence.
- **H. Engineering:** build cost, maintenance, performance, architecture fit.

**Keep rule (same as ML):** a feature ships as its own surface only if it can reach **5 on Demand, Evidence, Differentiation, Decision value and Recurring value** after its upgrades. Anything else is cut, demoted (to an input, template or lens) or merged.

**Ranking formula for build order:** (Demand × Differentiation × Decision value) ÷ Build cost.

---

## 2. Verdict

**The screener market is crowded and most of it is free.**
- Finviz has 10–25 million monthly visitors, a free screener and Elite at $24.96–39.50/month.
- TradingView's screener is free; Koyfin offers 5,900+ filter criteria from $0 to $79/month.
- Stock Rover has 800+ metrics at $29–149/month.

**We cannot win on filter count, coverage or data depth:**
- 4,158 US tickers
- statement fundamentals only from 2021 to 2025
- no delisted names
- no analyst estimates

**We can win the step after the filter.** Today a user filters, gets "187 companies" (a real Reddit complaint) and has no idea which to trust. The closest product that answers this is Portfolio123 (screen → rank → backtest, $25–83/month, 20 years of point-in-time data). Its users report a steep learning curve and it is not modern.

**The winning product is "Screen → Rank → Prove → Monitor":**
- **Screen fast:** a pruned, evidence-led filter set plus a formula language (Screener.in proved a single formula field can build a product).
- **Rank, don't list:** every result set gets a transparent composite rank, percentile versus sector and a "why this name is here" explanation.
- **Prove it honestly:** one click sends a screen to the ML Validate engine. It gets controls, purged cross-validation, deflated Sharpe, CSCV PBO, bootstrap, the overfitting autopsy and a verified page, with data caveats printed on the result (90-day statement lag, survivorship, 2021+ fundamentals).
- **Monitor:** saved screens re-run daily, with entry and exit alerts, rank changes and a weekly digest. This is what people pay for every month (TradingView gates watchlist alerts to Premium).

**Shape:** 8 spec features become **4 pages**, plus **5 A++ features**:
- **Screen:** S1, with S7 as a lens and quick-look.
- **Rank:** S3, with an optional ML ranker.
- **Test:** S5 engine, with the ML Validate report.
- **Monitor:** S6, with the S8 change report.

S2 (formula) and S4 (academic templates) become the expression bar and template gallery shared by Screen and Rank. S8 export becomes plumbing available on every page.

**Backend quality is strong.** The rebuild fixed every blocker and is the most honest screener backend we have reviewed:
- dated reselection
- next-session execution
- real CSCV
- no fabricated fallbacks
- unknown kept as unknown

The **frontend is the gap** (scored 5.0/10): no virtualisation, a 160-row silent cap, no saved views, no column management, fake demo data, accessibility gaps. It is rebuilt on the ML workspace and cinema kit, not patched.

---

## 3. Data reality (what the data can honestly support)

| Dataset | Coverage | Consequence |
|---|---|---|
| Daily OHLCV (`market_universe.parquet`) | 4,158 tickers, 1996-03 → 2026-07, 10.8M rows | Price and technical screens and backtests can run 30 years, but **survivorship-biased** (no delisted names). Must be labelled on every result. |
| Hourly OHLCV | available | Intraday screens possible later; not a priority (day-traders are Trade Ideas' market). |
| Statement fundamentals (`master_fundamentals.parquet`) | 3,833 tickers, report dates **2021-01 → 2025-12**; annual 2021–23, quarterly 2024+ | Fundamental screens work **today**. Fundamental **backtests are capped at about 4.5 years**, with a conservative +90-day availability lag. Long-history academic claims (Piotroski 1976–96, Magic Formula 1988–2004) cannot be reproduced; show citations, not our history. |
| Macro, FF5 and momentum factors | available | Factor exposure of a screen, regime splits. |
| Analyst estimates, forward P/E, float, historical index membership, historical GICS | **absent** | Remove forward P/E, float and "S&P 500" universe filters (already removed backend-side). Sector-neutral **historical** tests are rejected, which is correct. |
| FX and currency metadata | done (`96ff9f0c`) | Global names convert correctly; non-US remain few. |

**Data unlock (later, paid):** a point-in-time and delisted dataset turns S5 and the academic templates from caveated into first-class. Options were researched earlier: Sharadar and EODHD Custom with display rights by quote, and Norgate for US delisted (individual licence). This is the single biggest quality lever for the Test page, and it is a business decision, not code.

**Licence warning:** a screener **displays raw data** (prices, ratios), unlike ML, which shows derived analytics. Public launch needs a display or redistribution licence (Twelve Data Venture from about $149/month was the cheapest explicit "external display" plan found). Budget it before charging.

---

## 4. Market and competitor matrix

### 4.1 Prices (checked October 2026)

| Product | Price | Strength | Weakness (from reviews) |
|---|---|---|---|
| Finviz | Free; Elite $39.50/mo or $299.50/yr | Speed, heat maps, 10–25M monthly users, basic backtest, alerts, export/API | Basic backtest, US only, no formulas or ranking |
| TradingView | Free; paid from $14.95/mo; watchlist alerts only on Premium (2) and Ultimate | Charts, Pine Screener on custom indicators, alerts | Screener results "never correct" complaints; 40-symbol Pine limits; alerts gated |
| Koyfin | Free (2 screens); Plus $39 (10 custom formulas); Premium $79 | 5,900+ filters, global, historical-value screening, polished dashboards | No backtest, no ranking system |
| Stock Rover | $29–149/mo (annual) | 800+ metrics, equations, percentiles, research reports | No dedicated backtester (the vendor says so) |
| Portfolio123 | Free; Screener $25; Pro about $83 | **Screen + rank + backtest**, 20-yr point-in-time data incl. delistings, AI Factor (ML ranking), FactorMiner | Steep learning curve, dated UI, no mobile |
| Screener.in (India) | Free; Premium ₹4,999/yr (about $60) | Custom ratios and query language built the brand; alerts | India-only |
| Validea | $29–49/mo | Guru strategy screens and model portfolios | Black-box scoring, no custom work |
| Seeking Alpha Quant / Danelfin | SA Premium about $239/yr; Danelfin Pro $79/mo | Graded scores (A–F / 1–10) | Opaque; Danelfin Trustpilot 3.5 |
| Zacks Research Wizard | paid desktop | 650+ screens, 15 built-in strategies, about 6 yrs backtest | Old desktop UX |
| Fiscal.ai (FinChat), AI screeners | freemium to paid | Natural-language research and screens on S&P Global data | Answers not validated; not a testing tool |
| Bloomberg EQS | about $24–32k/yr seat | Institutional ceiling | Price |

### 4.2 Feature matrix (✓ strong · ◐ partial · ✗ none)

| Capability | Finviz | TradingView | Koyfin | Stock Rover | P123 | Screener.in | **Us (target)** |
|---|---|---|---|---|---|---|---|
| Filter breadth | ◐ | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ (pruned, evidence-led) |
| Formula / custom ratio | ✗ | ◐ (Pine) | ◐ (10) | ✓ | ✓ | ✓ | ✓ (shared language) |
| Percentile vs sector | ✗ | ✗ | ◐ | ✓ | ✓ | ◐ | ✓ |
| Transparent ranking system | ✗ | ✗ | ✗ | ◐ | ✓ | ✗ | ✓ |
| Learned (ML) ranker | ✗ | ✗ | ✗ | ✗ | ✓ AI Factor | ✗ | ✓ (via ML Alpha) |
| Backtest with dated reselection | ◐ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Point-in-time and delisted data | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ now (paid unlock) |
| Overfitting tests (DSR, PBO, controls, autopsy) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ only us** |
| Saved screens + scheduled re-runs | ✓ Elite | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (backend done) |
| Entry/exit alerts by email/push | ✓ | ✓ (gated) | ◐ | ✓ | ✓ | ✓ | ◐ (stored, no delivery yet) |
| Alert precision tracking | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ (backend stores matured precision)** |
| Shareable verified result | ✗ | ✓ (public scripts) | ✗ | ✗ | ◐ (public ports) | ✓ (public screens) | ✓ |
| Natural language → screen | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (AI) | ✓ (A++) |
| Modern UX | ✓ | ✓ | ✓ | ◐ | ✗ | ✓ | ✓ (cinema kit) |

**White space nobody fills:** an *honest* screen-to-proof loop (validation with controls, deflated Sharpe, PBO and a plain-English autopsy) with a modern UX at a prosumer price. Portfolio123 has the depth but not the honesty layer or the UX; Koyfin and Finviz have the UX but no proof.

### 4.3 Product principles from competitors' reviews
1. **Rank, don't dump.** Users close the tab at 187 results; give an order and a reason.
2. **Results must be right.** TradingView's "never returns the correct results" complaints show trust is fragile, so show why each name passed, with values.
3. **The learning curve kills power tools** (P123). Defaults must produce something useful in one click; formulas get autocomplete and templates.
4. **Alerts are the habit.** Gating them drives upgrades (TradingView); Screener.in's alerts drive retention.
5. **Formulas are the moat and the viral loop** (Screener.in public screens, TradingView public scripts).
6. **Opaque scores lose trust** (Danelfin 3.5/5). Every score decomposes into visible parts.

---

## 5. Evidence per method (does it work out of sample?)

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

## 6. Scored feature table

Scores are now → reachable after the upgrades in §7. Columns: Dem = Demand, Evid = Evidence, Diff = Differentiation, Dec = Decision value, Rec = Recurring, Cost = Build cost (5 = cheap).

| Feature | Dem | Evid | Diff | Dec | Rec | Cost | Verdict |
|---|---|---|---|---|---|---|---|
| S1 Core screener | 5 | 3→4 | 2→4 | 3→5 | 3→5 | 3 | **Keep as "Screen"**, with ranking-first results, a "why here" explanation and near-misses |
| S2 Formula builder | 5 | 4 | 3→5 | 4→5 | 4→5 | 4 | **Keep as the shared expression bar** (one language with Research and ML); flagship |
| S3 Composite score | 4 | 5 | 3→5 | 4→5 | 3→5 | 4 | **Keep as "Rank"**; IC/ridge weighting moves to the ML Alpha ranker |
| S4 Academic library | 3 | 3 | 2 | 3 | 2 | 4 | **Demote to a template gallery** inside the expression bar, with citations and decay notes; the strategy leaderboard and correlation pages are removed |
| S5 Backtester | 4 | 4 | 3→5 | 4→5 | 2→4 | 3 | **Keep as "Test"**: the S5 simulator feeds ML Validate (one report, one autopsy) |
| S6 Alerts and monitor | 5 | n/a | 2→4 | 4→5 | **5** | 3 | **Keep as "Monitor"**: email/webhook delivery, alert precision, weekly digest |
| S7 Relative valuation | 3 | 3 | 2 | 3 | 2 | 4 | **Merge** into quick-look plus a "Valuation" lens and preset, not a page |
| S8 Export and integration | 3 | n/a | 2 | 3 | 2 | 5 | **Merge** into plumbing on every page (CSV/JSON/tickers, API, send to ML, watchlist); the change report moves to Monitor |

### 6.1 Output-level calls (keep · merge · cut)

| Output | Call | Reason |
|---|---|---|
| S1 ranked table | Keep (primary) | Core job; rebuilt as a virtualised table with ranking and percentile toggles |
| S1 filter funnel | Keep | Highest decision value per pixel: shows the bottleneck filter |
| S1 percentile context | Keep as a table mode | Universe / sector / industry toggle in the table |
| S1 heatmap view | Keep as a treemap lens | Finviz-style map, sized by market cap and coloured by any metric |
| S1 quick-look card | Keep (upgrade) | Becomes the shared ticker drawer (price, ratios with percentile bars, Piotroski/Altman badges, valuation lens) |
| S1 market-cap buckets | Merge | Into a filter control (bucket counts shown inside the slider) |
| S1 saved screens | Keep | Backend done; UI: named, URL state, schedule |
| S2 result table | Merge | It is the Screen table with a formula column |
| S2 validation panel | Keep | Inline preview: coverage, distribution, unknowns |
| S2 historical formula backtest | Merge | Into Test |
| S2 factor-zoo comparison | Cut | External zoo absent (backend removed it); correlation to built-in factors becomes a preview chip |
| S3 composite ranking | Keep (primary of Rank) | — |
| S3 decomposition | Keep | Per-name contribution waterfall; reuse the ML waterfall |
| S3 component IC-IR leaderboard | Keep | Matured-label IC per component |
| S3 correlation heatmap | Keep as a lens | — |
| S3 composite vs factor backtest | Merge | Into Test (controls) |
| S3 regime breakdown (VIX) | Merge | Into Test robustness (regime split) |
| S4 strategy leaderboard | Cut | 4.5-year history; ranking strategies on it invites overfitting |
| S4 per-strategy stock list | Merge | A template applied to Screen |
| S4 Piotroski breakdown | Keep in quick-look | The nine criteria with unknowns shown |
| S4 Altman status | Keep in quick-look | Distress flag |
| S4 strategy correlation | Cut | Same reason as the leaderboard |
| S4 historical strategy table | Cut | Use Test per template instead |
| S5 equity curve | Keep | With SPY and equal-weight controls |
| S5 full performance statistics | Merge | Into Validate's KPI strip |
| S5 rolling performance | Keep | — |
| S5 holding / rebalance sensitivity | Keep | This is the plateau map |
| S5 turnover | Keep | — |
| S5 sector attribution | Keep | — |
| S5 regime conditional | Keep | — |
| S5 Monte Carlo / CSCV | Merge | Into Validate's bootstrap and PBO |
| S5 stock attribution | Keep | — |
| S6 alert feed | Keep | — |
| S6 alert performance tracker | Keep | Unique: does this alert make money? |
| S6 entry/exit log | Keep | — |
| S7 four-dimension card | Merge | Into quick-look |
| S7 sector landscape | Merge | Lens on Screen |
| S7 own-history percentile | Merge | Quick-look sparkline |
| S7 peer table | Merge | Quick-look tab |
| S8 instant export | Keep | Plumbing |
| S8 API metadata | Keep | Plumbing |
| S8 change report | Merge | Into Monitor |

---

## 7. Final cut: 4 pages, and what makes each a 5

### 7.1 Screen (S1, plus S2 bar, S4 templates, S7 lens, quick-look)

| Axis | Upgrade to 5 |
|---|---|
| Demand | Defaults that produce a ranked, useful list in one click (e.g. "Quality value with momentum, US, $1B+, liquid") |
| Evidence | Evidence-led filter groups lead; each filter carries a badge (robust / mixed / weak) with a citation |
| Differentiation | **Ranking-first results**, **"why this name is here"** (each filter's value and margin, percentile vs sector) and **near-misses** (names failing exactly one filter, and by how much) |
| Decision | Live count per filter; funnel shows the bottleneck; one-click "Test this screen" and "Rank it" |
| Recurring | Save, then a daily re-run with entry/exit alerts (Monitor) |

### 7.2 Rank (S3)
- A transparent composite with components, weights (equal / user / IC-IR) and sign conventions.
- Per-name decomposition waterfall.
- Component matured-label IC and correlation.
- **"Train an ML ranker on this"** sends the same universe and features to ML Alpha and returns the result to compare side by side (rules vs learned, the honest comparison).
- Ranking-system presets: Quality-Value-Momentum, Defensive, Shareholder Yield. Each preset is labelled by its formula, not by a guru name.

### 7.3 Test (S5 engine, ML Validate report)
- The dated reselection simulator (next-session execution, traded-notional costs, drift) produces returns.
- These feed **ML Validate**: controls (SPY, equal-weight universe, random screen of the same size), deflated Sharpe at the true trial count (from the trial ledger), CSCV PBO over holding/offset variants, bootstrap, transfer (sectors and later periods) and the **autopsy**.
- Screener-specific exhibits: turnover, sector and stock attribution, holding/rebalance plateau.
- **Mandatory data banner:** "Fundamentals from 2021, 90-day availability lag, current listings only (survivorship)". It is removed only once point-in-time and delisted data are bought.

### 7.4 Monitor (S6, plus S8 change report)
- Saved screens and watchlists, each with a schedule (daily or weekly), entries, exits and rank moves since the last run.
- Alert rules: enters or exits the screen, rank crosses the top N, metric crosses a threshold, percentile shift.
- **Alert precision:** forward return after each alert, matured (backend stores it). Users see whether their alerts make money.
- Delivery: in-app now; **email and webhook next** (needs a provider such as Resend or SES, about a day of work). A weekly digest.

---

## 8. New A++ features (5 on every axis by design)

1. **Near-miss explorer.** For every screen, the names that fail exactly one filter, sorted by how close they came, with a "relax this filter" action. No competitor shows this, and it removes the guesswork from threshold tuning. D5 Diff5 Dec5 R4. Cheap: the funnel data already exists.
2. **"Why is this name here?"** A row expander listing every filter, its value, its threshold, the margin and the sector percentile. It kills the "results are wrong" distrust TradingView suffers from. D5 E5 Diff5 Dec5.
3. **Screen → Proof in one click.** Test plus ML Validate with the autopsy and a **verified share page** (hash-stamped, read-only; shared with ML). This is the honest version of Validea's model portfolios and P123's public portfolios. D5 E5 Diff5 Dec5 R4.
4. **Plain English → formula.** "Profitable small caps getting cheaper with rising margins" becomes an editable formula and filter set, never a black box. The trend leaders here (Fiscal.ai, Screener.in AI) don't validate; we do. Cost: an LLM call per query.
5. **Alert precision scoreboard.** Every alert rule shows its matured hit rate and average forward return against its universe. Recurring 5 by construction, and it differentiates us from TradingView, Finviz and Koyfin (none have it).

---

## 9. Shared with ML and Research (one platform, not three)

| Shared piece | Source | Used by |
|---|---|---|
| Lab workspace (LabConfig, Study/Inspect panels, runs, compare, report) | Research/ML frontend | Screener pages |
| Cinema chart kit v2, DataTable v2 (TanStack + virtual), treemap, waterfall, RankList | `ML_CINEMA_PLAN.md` | All Screener exhibits |
| **Formula language** (`signal_lang`) | Research | Screener expression bar, ML Alpha custom features. Screener's `core/formula.py` should become a thin adapter on it, not a second language |
| Universe presets and secure CSV upload | ML `core/uploads.py`, data_loader presets | Screener universes (sectors, high-vol, ETFs, custom upload) |
| Validate engine and autopsy | ML | Screener Test |
| Verified pages | ML API `/verified` | Screener proof pages |
| Trial ledger | ML A1.6 (open) | Counts every screen variant tried, so the deflated Sharpe is honest |
| Ticker quick-look drawer | New, shared | Screener, ML ranking, Research |
| Scheduler and alert delivery | Screener SQLite schedules | ML daily refresh (ML A3) |
| Strategy studio | ML | A screen becomes a Signal source in the pipeline |

**Inputs reused, not duplicated:** universe, as-of date, costs, horizon, upload id and formulas use the same keys and controls across labs.

---

## 10. Inputs: the filter list, pruned

The spec lists about 60 filters. Keep the ones the data supports and the evidence or demand justifies; move the rest into the formula language.

**First-class filters, grouped:**
- **Universe and liquidity:** universe preset / upload, market-cap buckets (with live counts), price, $1 floor, 20-day dollar volume floors, exchange.
- **Value:** P/E (TTM, negative excluded), P/B, P/S, P/CF, EV/EBIT, EV/EBITDA, earnings yield, FCF yield. Each can be absolute or **sector percentile**.
- **Quality:** gross profit/assets, ROIC, ROE, operating margin, OCF/net income (accruals), interest coverage, Piotroski F, Altman Z (flag).
- **Growth:** revenue, earnings and EPS YoY; 3-year revenue CAGR (from 2024 on).
- **Health and payout:** debt/equity, debt/EBITDA, current ratio, dividend yield, payout ratio.
- **Price signals:** momentum (1M / 3M / 6M / 12-1), 52-week-high proximity, relative strength vs SPY, distance from 50/200-day SMA, golden/death cross within N days.
- **Risk:** realised vol (21/63), beta (252), drawdown from high, ATR %.
- **Composite:** rank and sector percentile from Rank.

**Into the formula language only** (available, not promoted, with a weak-evidence note): RSI, MACD, Stochastic, Williams %R, Bollinger, ADX/DMI, OBV slope, gap %, consecutive up/down days, IVOL, MAX, Amihud (Amihud stays as a liquidity floor option).

**Removed, because the data is absent:** forward P/E, float %, historical index membership, OTC.

Every filter shows its definition and source on hover, its evidence badge, and how many names it removes at the current settings.

---

## 11. UI and experience (built on the ML cinema kit)

- **Layout (TradingView/Koyfin density, cinema look):**
  - a top filter bar of chips with operators (>, <, between, in, top-N%, sector percentile), plus "+ Add filter" with search and grouped catalog
  - a formula bar with autocomplete, inline errors and a coverage preview
  - live match count on every chip change
- **Results table (DataTable v2):**
  - virtualised for 4,000+ rows, server-side sort and page
  - sticky ticker column; column sets (Overview / Value / Quality / Momentum / Risk / Custom); add, remove and reorder columns
  - an absolute/percentile toggle per column; inline bars and sector-percentile ticks
  - row expander for "why here"; keyboard navigation
  - no silent caps, ever
- **Lenses:** table / treemap (size by cap, colour by any metric, sector to industry zoom) / scatter (any two metrics, sector colour) / funnel.
- **Quick-look drawer:** price with event annotations, ratio percentile bars vs sector and own history, Piotroski 9-check grid, Altman zone, peers, alerts on this name, "Add to watchlist / screen / ML ranking".
- **Saved views:** name, URL state, duplicate, recent, schedule. Shareable read-only link.
- **⌘K:** run screen, open saved, add filter by name, jump to ticker.
- **Honesty everywhere:** data banner on Test; "unknown" shown as a hatched cell, never as blank or zero; each filter's coverage shown ("P/B known for 3,612 of 4,158").
- **Remove the old frontend:**
  - demo data (`DEMO_TICKERS`, sine-wave curves, `Math.random`)
  - the decorative `<GO>` hero
  - crosshair cursor, the 160-row cap, hover-only navigation
  - the 8 wrapper pages: replace them with the 4 lab pages under `/screener`

---

## 12. Pricing, data licence and build order

### 12.1 Tiers (anchored to Finviz $25–40, Koyfin $39/79, P123 $25/83, Stock Rover $29–149)

| Tier | Price | Includes |
|---|---|---|
| Free | $0 | Screen (top 50 results shown, full count visible), 2 saved screens, templates, quick-look, end-of-day data |
| Pro | $29/mo ($290/yr) | Unlimited screens and columns, formulas, Rank, CSV export, daily alerts (in-app and email), near-miss and why-here |
| Quant | $79/mo | Test with Validate, autopsy, verified pages, ML ranker, webhooks, API, weekly digests, trial ledger |
| Team / Institutional | quote | Seats, shared screens, white-label reports, point-in-time data add-on |

Pro undercuts Koyfin Plus and Finviz Elite while offering ranking and proof they lack; Quant sits just under Portfolio123 Pro with a far better UX and the honesty layer.

### 12.2 Data licence (before charging)
- A display or redistribution licence is required for raw prices and fundamentals shown to paying users (see the earlier provider research; Twelve Data Venture is the cheapest explicit external-display plan found).
- A point-in-time and delisted dataset is the upgrade that removes the Test banner (Sharadar or EODHD Custom by quote).

### 12.3 Build order (after `ml-design-v1`)

| Step | Work | Backend | Frontend |
|---|---|---|---|
| 1 | Lab wiring: `/screener` on LabConfig (manifest adapter, 4 pages, layouts) | — | ✓ |
| 2 | DataTable v2 virtualised, server sort/page endpoint, column sets, filter chips with live counts | page/sort/count endpoint | ✓ |
| 3 | Formula bar on `signal_lang` (merge `core/formula.py` into an adapter), autocomplete, preview | adapter | ✓ |
| 4 | Why-here and near-miss outputs | small: per-filter margins, one-fail set | ✓ |
| 5 | Quick-look drawer (shared with ML) | reuse S1/S4/S7 outputs | ✓ |
| 6 | Rank page plus "Train ML ranker" hand-off to ML Alpha | artifact hand-off | ✓ |
| 7 | Test: S5 returns → ML Validate; data banner; trial ledger | wire S5 artifact into Validate | ✓ |
| 8 | Monitor: schedules UI, alert rules, precision scoreboard, email/webhook delivery, weekly digest | delivery provider | ✓ |
| 9 | Templates gallery (S4 as formulas with citations and decay notes); plain-English → formula | LLM endpoint | ✓ |
| 10 | Verified share pages, ⌘K actions, onboarding, accessibility, phone, visual baselines; tag `screener-v1` | — | ✓ |

**Removals (with the usual graph and `rg` checks before deleting):**
- S4 leaderboard, correlation and historical-strategy outputs
- S2 factor-zoo output
- the S5 Monte Carlo/PBO duplicates (Validate owns them)
- the old `components/screener-v2` frontend and the `/labs/screener-v2/feature-0x` pages after `/screener` ships
- any filter tied to absent data

**Size:** about 5–7 focused sessions on top of the ML kit (the kit makes most exhibits composition). The backend changes are small, because the Codex rebuild already did the heavy work.

---

## 13. Sources

**Competitors and pricing**
- Finviz Elite: https://finviz.com/elite · https://propfirmapp.com/trading-tools/finviz · https://www.stockbrokers.com/review/tools/finviz · Finviz traffic (Semrush): https://www.semrush.com/website/finviz.com/overview/ · https://trendspider.com/learning-center/finviz-alternative/
- Koyfin: https://www.koyfin.com/pricing/plans-comparison/ · https://www.koyfin.com/pricing-llm-info/ · https://www.koyfin.com/features/stock-screener/ · https://www.koyfin.com/help/release-notes/v3-67-historic-data-in-watchlist-screener/
- TradingView: https://www.tradingview.com/pricing/ · https://www.tradingview.com/support/solutions/43000742436-tradingview-pine-screener-key-features-and-requirements/ · https://www.tradingview.com/support/solutions/43000690941-how-to-get-more-active-alerts-per-subscription/ · https://chartwisehub.com/tradingview-plus-vs-premium/
- Stock Rover: https://www.stockrover.com/support-database/can-i-use-screeners-for-backtesting/ · https://www.portfolioglance.com/investing-apps/stock-rover · https://tickernerd.com/resources/stock-rover-review/
- Portfolio123: https://www.liberatedstocktrader.com/portfolio123-review/ · https://discussion.fool.com/t/portfolio123-whats-working-lately/111089 · https://community.portfolio123.com/t/p123-waste-of-time/70436 · https://www.greatworklife.com/portfolio123-review/ · https://community.portfolio123.com/t/factorminer-is-live-faster-factor-discovery-for-alpha-research-and-ai-feature-engineering/76504
- Screener.in: https://www.screener.in/premium/ · https://www.strike.money/reviews/screener-in
- Validea: https://www.validea.com/ · Danelfin / Seeking Alpha: https://www.therundown.ai/tools/danelfin · https://www.trustpilot.com/review/danelfin.com · https://seekingalpha.com/article/4263303-quant-ratings-and-factor-grades-faq
- Zacks Research Wizard: https://www.zacks.com/researchwizard/ · Fiscal.ai: https://fiscal.ai/screener/ · https://quantbrainai.net/blog/fiscal-ai-review-jul-2026/
- Investopedia best screeners (Oct 2026): https://www.investopedia.com/best-stock-screeners-5120586

**Demand (Reddit)**
- "Screener gave me 187 companies…": https://www.reddit.com/r/StockMarket/comments/1uso0yz/screener_gave_me_187_companies_and_i_just_closed/
- "Why does every screener feel like it was built by…": https://www.reddit.com/r/IndianStockMarket/comments/1p6aske/why_does_every_screener_feel_like_it_was_built_by/
- TradingView screener complaints: https://www.reddit.com/r/TradingView/comments/1dextsi/bring_back_the_screener_as_it_was/ · https://www.reddit.com/r/TradingView/comments/1iecpoo/major_complaint_regarding_premium_plan_user/
- Screener + backtest requests: https://www.reddit.com/r/swingtrading/comments/1ozgjs8/good_screener_with_specific_backtesting/ · https://www.reddit.com/r/ValueInvesting/comments/1dpg6z3/what_are_the_best_stock_screener/
- P123 bias-adjusted backtests in r/quant: https://www.reddit.com/r/quant/comments/1aclel5/i_developed_a_back_test_on_the_market_that/

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
- `backend/app/services/screener_v2/DONE.md` (authoritative backend state)
- `docs/reviews/SCREENER_V2_REVIEW.md`
- `docs/evidence/frontend-review/screener-v2/review.md`
- `docs/reviews/SELL_10_SCREENER_FACTORS_RESEARCH.md`
- Local data audit: 4,158 price tickers 1996–2026; 3,833 fundamentals tickers 2021–2025.

---

## 14. What to add: the full build list

**Tags:** `[B]` backend · `[F]` frontend · `[B+F]` both. Status: `[ ]` open.

**Two rules for this list:**
1. **Parity first.** We do everything the leaders do (Finviz, TradingView, Koyfin, Stock Rover, Portfolio123, Screener.in), because users judge us against them before they see what's different.
2. **Then the things nobody does.**

**Reuse rule:** everything is built from the ML V2 material, as ML reused Research V2:
- the LabConfig workspace (`ResearchApp`, Study/Inspect panels, runs, compare, report)
- chart kit v2, DataTable v2, Exhibit, KpiStrip, RankList, Treemap, Waterfall
- the uploads module, universe presets, Validate engine, verified pages, takeaway generators and hand-offs
- the ⌘K palette, tabs, lenses ("View as") and the e2e screenshot harness

New code is only screener-specific.

**Data-swap rule:** all data access goes through one provider interface (§14.10), so real licensed, point-in-time and delisted data drops in later with no feature code changes. Until then the current local files are used. Their caveats show as banners, but nothing is held back.

### 14.1 Universe and data controls (parity)
1. `[B+F]` Universe presets:
   - all, large / mid / small / micro by cap
   - each sector and industry group, ETFs only, high volatility, dividend payers
   - "same as last run", my watchlists, uploaded CSV, pasted tickers
2. `[B+F]` Market-cap buckets with live counts in the slider (Nano → Mega); continuous range.
3. `[B+F]` Exchange, country and currency filters; ADR toggle; price and $1 floor; dollar-volume floors ($100K → $10M).
4. `[B+F]` "As of" date picker: run any screen as of a past date, using point-in-time values (backend already enforces dated access).
5. `[F]` Universe summary chip: names, sectors, median cap, coverage per data family.
6. `[B]` Coverage per metric ("P/B known for 3,612 / 4,158"), used by chips, columns and the formula preview.

### 14.2 Filters and expression bar (parity plus better)
7. `[F]` Filter chips with operators: >, <, between, =, in, not in, top/bottom N %, top/bottom N names, sector percentile, universe percentile, crossed above/below within N days, rising/falling over N periods.
8. `[F]` "+ Add filter" catalog: search, groups (Valuation, Quality, Growth, Health, Dividends, Momentum, Technicals, Risk, Liquidity, Composite, Custom), definition, unit, evidence badge, coverage, recently used, favourites.
9. `[B+F]` **Live count after each filter** while typing (debounced count endpoint), plus a mini histogram of the metric with the threshold handle draggable on it (Koyfin/Stock Rover-level).
10. `[B+F]` OR groups and nesting: (A and B) or C, as a visual group builder that round-trips to a formula.
11. `[B+F]` Expression bar on `signal_lang`:
    - autocomplete for fields, operators and functions
    - signature help, inline errors with position
    - a preview (distribution, coverage, correlation with known factors)
12. `[B+F]` Custom metrics: name a formula, then it becomes a column, filter, sort key and Rank component everywhere (Stock Rover equations, Screener.in custom ratios).
13. `[B+F]` Historical functions: `lag`, `change`, `ts_mean`, `ts_rank`, `ts_zscore`, `cross_above`, `rising(n)`, `highest/lowest(n)`, plus statement lags by quarter or year.
14. `[B+F]` Cross-sectional functions: `rank`, `zscore`, `sector_rank`, `sector_zscore`, `industry_*`, `winsorize`, `neutralize(by)`.
15. `[F]` Template gallery (S4 strategies plus community-style presets), each with citation, plain-English description, evidence and decay note, and "Use", "Fork" and "Test" buttons.
16. `[B+F]` Plain English → screen (LLM): an editable result, never a black box; it shows the formula it wrote.
17. `[F]` Undo/redo for filters; "reset to template"; filter enable/disable toggle without deleting it.

### 14.3 Results table (parity with TradingView/Koyfin, then beyond)
18. `[B+F]` Virtualised table for every name. Server sort, filter and page; no caps; 60 fps scroll.
19. `[F]` Column sets (Overview, Valuation, Quality, Growth, Momentum, Technicals, Risk, Dividends, Composite, Custom). Plus:
    - an add/remove column picker with search
    - drag to reorder, resize, pin left
    - save as a named column set
20. `[F]` Per-column modes: absolute, universe percentile, sector percentile, z-score, rank, plus change since the last run.
21. `[F]` Cell visuals:
    - inline bars, signed colour, heat tint, percentile ticks
    - sparklines (price 3M, metric history)
    - Piotroski dots, Altman zone pill
    - "unknown" shown as hatched, never blank or zero
22. `[F]` Row actions: quick-look, why-here, add to watchlist, add to compare, alert on this name, open chart, copy ticker.
23. `[F]` Multi-select rows: compare, add to watchlist, export selection, send to ML Allocation / Validate / Alpha.
24. `[F]` Group by sector or industry with subtotals (count, median of each column); collapse and expand.
25. `[F]` Density toggle, zebra on/off, keyboard navigation (arrows, Enter opens quick-look, Space selects).
26. `[F]` Sticky summary row: median and mean of each column for the result vs the universe ("your screen is 40% cheaper on P/E than the universe").
27. `[B+F]` "Changed since last run" column (rank Δ, new / exited badges) on saved screens.

### 14.4 Lenses on the same result (View as)
28. `[F]` Treemap: size by cap, weight or equal; colour by any column; zoom sector → industry → name; breadcrumb; Esc zooms out (like the T3 reference).
29. `[F]` Scatter: any two metrics, sector colours, size by cap, quadrant lines at medians, lasso to filter.
30. `[F]` Sector bars: count, median metric and percentile of the result vs the universe.
31. `[F]` Funnel: per-filter elimination, the bottleneck highlighted, click a step to see who it removed.
32. `[F]` Map by country (when global data arrives).
33. `[F]` Correlation of the result's returns (cluster view, reusing the ML CorrMap).

### 14.5 Quick-look and company pages (parity with Finviz/Koyfin/Stock Rover)
34. `[B+F]` Quick-look drawer:
    - price chart (1M → max) with event annotations (earnings, entering/exiting your screens, alerts fired)
    - key stats strip
    - ratios as percentile bars vs sector and own history
    - Piotroski 9-check grid, Altman zone
    - peers table, valuation lens (S7), and every screen and alert this name is in
35. `[B+F]` Full company page (shared with ML/Research):
    - financial statements (annual/quarterly), ratio history charts
    - segment data when available
    - factor exposures (FF5 betas), ML Alpha rank and drivers, volatility and risk-today card
36. `[F]` Compare up to 6 names side by side: metrics table, normalised price chart, percentile radar.
37. `[B]` Peer finder: same industry plus nearest on size, margin and growth; editable peer set.

### 14.6 Rank (parity with P123 ranking systems, Seeking Alpha grades)
38. `[B+F]` Ranking-system builder: components (any metric or formula), direction, weight, scope (universe/sector), missing-value policy, nested groups (Value 30% = P/E, EV/EBIT, FCF yield …).
39. `[F]` Letter grades A–F per factor group per name (Seeking Alpha style), each clickable to its components.
40. `[B+F]` Per-name decomposition waterfall (reuse the ML waterfall); "what changed in this rank since last week".
41. `[B+F]` Rank performance: buckets (quintiles/deciles) over time, monotonicity, spread, turnover. Reuse the ML Alpha bucket view.
42. `[B+F]` "Train an ML ranker on this": ML Alpha with the same features, then side-by-side rules vs learned, held-out.
43. `[B+F]` Preset ranking systems labelled by formula (Quality-Value-Momentum, Defensive, Shareholder Yield, Low-vol Quality, Growth at a Reasonable Price).

### 14.7 Test (parity with P123/Finviz backtests, then the honesty layer)
44. `[B+F]` Backtest settings:
    - rebalance (weekly/monthly/quarterly), holding count or top %, equal / cap / rank / inverse-vol weights
    - max weight, sector caps, costs and slippage bps, cash yield, benchmark, start/end
45. `[B+F]` Equity curve vs SPY and the equal-weight universe; drawdown; rolling 12M return and Sharpe; calendar heatmap of monthly returns.
46. `[B+F]` Trades and holdings history: every buy and sell with dates and prices; holdings on any date; best and worst contributors.
47. `[B+F]` Attribution: sector, factor (FF5 regression), stock-level.
48. `[B+F]` Robustness: holding/offset plateau, rebalance-day variants, transfer to other sectors and later periods, regime split. All through ML Validate, with the autopsy and verified page.
49. `[B]` Trial ledger: every variant run counts toward the deflated Sharpe (shared with ML/Research).
50. `[F]` Data banner, shown until the data is swapped: point-in-time lag, survivorship, history start.
51. `[B+F]` Live forward-tracking of a saved strategy: frozen on save, scored daily, live vs backtest chart.

### 14.8 Monitor and alerts (parity with TradingView/Finviz Elite/Screener.in, then beyond)
52. `[B+F]` Saved screens: name, description, tags, schedule (daily/weekly/intraday later), owner, created and last run, share link.
53. `[B+F]` Alert rules:
    - screen entry or exit
    - rank crosses top N
    - metric crosses a value or percentile
    - % move, 52-week high or low, volume surge
    - earnings date approaching
    - composite grade change
54. `[B]` Delivery: in-app inbox, email (Resend/SES), webhook, browser push, Telegram/Discord/Slack. Digest mode with per-rule frequency and quiet hours.
55. `[B+F]` Alert precision scoreboard: matured hit rate and average forward return per rule vs its universe.
56. `[B+F]` Watchlists: multiple lists, notes per name, tags, column sets, alerts on the whole list (TradingView watchlist alerts, ungated).
57. `[B+F]` Weekly "what changed" digest: entries, exits, rank movers with reasons, alert outcomes. Email plus an in-app page.
58. `[B+F]` Market overview board:
    - breadth (advancers/decliners, % above 200-day)
    - sector performance treemap, top movers in your universes, new 52-week highs and lows
    - factor performance today/week/month (value, momentum, quality, low-vol)

### 14.9 Sharing, community and growth (what makes users come back and bring others)
59. `[B+F]` Public screen pages: a read-only live result with a "Fork" button. Shareable links, embeds and OG images (like Screener.in public screens and TradingView public scripts).
60. `[B+F]` Verified result pages for tested screens (hash-stamped; reuse ML).
61. `[B+F]` Screen gallery: featured, trending (forks, saves), by style; each with live stats (count, 1M performance, alert precision).
62. `[F]` Share as image: card of the result or a test with key stats (social-ready).
63. `[B+F]` Comments and notes on screens (private first, later team).
64. `[B+F]` Team workspaces: shared screens, watchlists, alerts, roles.

### 14.10 Platform, data and engineering
65. `[B]` **Data provider interface** (`screener_v2/core/provider.py`): `prices()`, `fundamentals(as_of)`, `classifications(as_of)`, `membership(as_of)`, `delistings()`, `estimates()`, `fx()`. The local parquet is the first adapter; a licensed point-in-time vendor is the second. Features never read files directly.
66. `[B]` Nightly precomputed metric panel: every metric × every name × every date, stored as Parquet and partitioned by date, so a screen is a columnar filter in under 300 ms and counts are instant.
67. `[B]` Endpoints:
    - `/screen` (filters/formula → page of rows, sort, columns), `/count`, `/histogram/{metric}`
    - `/explain/{ticker}` (why-here), `/near-miss`, `/quicklook/{ticker}`, `/compare`
    - `/rank`, `/backtest`, `/alerts`, `/watchlists`, `/gallery`, `/share`
68. `[B]` Formula engine unified on `signal_lang`, with `core/formula.py` as a thin adapter and compiled vectorised execution over the panel.
69. `[B]` Job queue reuse (Studio JobStore) for backtests; caching by settings hash; cancel; progress stages.
70. `[B]` Accounts and limits per tier: saved screens, alerts, export rows, backtests per day.
71. `[B]` API and webhooks for Quant tier (keys, rate limits, usage).
72. `[F]` Offline-friendly URL state for every screen (filters, columns, sort, lens), so links reproduce exactly.

### 14.11 UX and UI (cinema kit, applied)
73. `[F]` Page shell from `ML_CINEMA_PLAN.md`:
    - takeaway titles ("Your screen holds 42 names, 38% cheaper than the market on EV/EBIT")
    - KPI strip, borderless exhibits, direct labels, synced crosshair
74. `[F]` Onboarding:
    - 3 starter screens (Quality value, Momentum leaders, Dividend growers) with one-click run
    - a 4-step coach mark tour; an empty state that teaches
75. `[F]` ⌘K: add filter by name, open saved screen, jump to ticker, run, test, share, switch column set.
76. `[F]` Keyboard-first:
    - `/` focuses the filter search; `f` adds a filter; `c` sets columns; `t` runs Test
    - `[` and `]` switch lens; Enter on a row opens quick-look
77. `[F]` Responsive: phone layout with a filter sheet, card list results, swipe to quick-look; tablet two-pane.
78. `[F]` Light and dark themes; colour-blind-safe palettes; reduced motion; full screen-reader labels and table semantics.
79. `[F]` Speed feel: optimistic counts, skeletons shaped like the table, instant column toggles, background prefetch of quick-look on hover.
80. `[F]` Export: CSV, Excel, JSON, tickers list, copy as markdown table; "Export visible columns" vs "all"; PDF report of a screen or test.
81. `[F]` Notifications centre (bell): alerts, finished backtests, digests, with deep links.

### 14.12 Differentiators (nobody does these well)
82. `[B+F]` Near-miss explorer with "relax this filter" (A++).
83. `[B+F]` "Why is this name here" with margins and sector percentiles (A++).
84. `[B+F]` Screen → proof in one click, with the autopsy and verified page (A++).
85. `[B+F]` Alert precision scoreboard (A++).
86. `[B+F]` Plain English → editable formula (A++).
87. `[B+F]` Filter sensitivity: how the result count and test Sharpe change as each threshold moves (a plateau per filter, reusing Validate's plateau).
88. `[B+F]` Crowding and consensus flag: how many gallery screens hold a name (popularity as a risk).
89. `[B+F]` Factor DNA of a screen: FF5 and momentum exposures of the result vs the universe; "your value screen is really a small-cap bet".
90. `[B+F]` Regime-aware view: how this screen did in Calm/Normal/Stress (reuse ML Market state).
91. `[B+F]` Screen diff: compare two screens or two dates (who's in A not B, overlap %, metric deltas).
92. `[B+F]` Strategy studio hook: a screen becomes the Signal step, then ML filter, size, allocate and validate.

### 14.13 Build sequence for this list (on top of §12.3)

| Wave | Items | Why first |
|---|---|---|
| 1 Foundation | 65–69, 72, 18–20, 7–9, 11 | Provider interface, precomputed panel and fast endpoints make everything else instant |
| 2 Parity core | 1–6, 10, 12–14, 21–27, 28–31, 34, 73–80 | Users must find everything they expect from Finviz/Koyfin/TradingView |
| 3 Rank and Test | 38–51 | P123 parity plus the honesty layer |
| 4 Monitor | 52–58, 81 | The recurring habit and upgrade driver |
| 5 Differentiators | 82–92, 16 | Reasons to switch |
| 6 Growth | 59–64, 35–37, 70–71 | Sharing, teams and tiers |

**Definition of done (`screener-v1`):**
- every parity item is shipped
- all A++ items are shipped
- each page passes the cinema rubric (average 4.5 or higher)
- swapping to the licensed data provider requires only a new adapter
