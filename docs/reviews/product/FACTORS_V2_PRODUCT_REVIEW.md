# Factors V2 product review: what to keep, merge, cut and add

Date: 2026-11-06. This follows the method of `docs/SCREENER_V2_PRODUCT_REVIEW.md`. It reviews Factors V2 as it stands in the code after the backend rebuild (`backend/app/services/factors_v2/DONE.md`, updated 2026-10-07), and plans the product that comes after the ML cinema kit (`docs/ML_CINEMA_PLAN.md`).

**Inputs read**
- `docs/reviews/FACTORS_V2_REVIEW.md` (dated 2026-09-29, with a rebuild addendum on 2026-10-07). Its blockers B1 and B2 are now stale; see §2.
- `docs/reviews/SELL_10_SCREENER_FACTORS_RESEARCH.md`, `docs/reviews/PLATFORM_CODE_10_BY_10_COMPLETE_SPEC.md`, `docs/ML_CINEMA_PLAN.md`
- Code: `backend/app/services/factors_v2/` (registry, `features/inputs.py`, `core/data_loader.py`, `core/panel.py`), `backend/app/api/factors_v2.py`, `frontend/src/lib/api.js`, `frontend/src/components/factors-v2/`, `frontend/src/app/labs/factors-v2/`
- Measured data: parquet and CSV headers and row counts under `backend/data/` and `factors/data/`
- Live manifest: `feature_manifest()` run from `backend/`
- Tests: the four `backend/tests/test_factors_v2_*.py` files, run in this pass (see §3)
- Web search and fetch on competitor prices, complaints and method evidence (sources in §14)

---

## Contents
1. Method and criteria
2. Verdict
3. Data reality and build status
4. Competitors and prices
5. Evidence per method
6. Scored feature table
7. Final page cut and what makes each page a 5
8. New A++ features
9. Shared with other modules
10. Inputs pruned
11. UI on the ML cinema kit
12. Pricing
13. Build order
14. Sources and what could not be verified

---

## 1. Method and criteria

Each feature and output is scored 1–5. The scores are reviewer judgment, based on the code, the measured data and the cited sources. They are not statistical results. The criteria are those of the screener review:
- **Demand:** who pays, how often the pain appears, and what they use now.
- **Evidence:** academic support and whether the method is honest about its data.
- **Differentiation:** whether a named competitor already does it.
- **Decision value:** whether the output changes a decision.
- **Recurring value:** whether users come back to it.
- **Build cost:** 5 means cheap.

**Keep rule:** a feature keeps its own page only if it can reach 5 on Demand, Evidence, Differentiation, Decision value and Recurring value after upgrades. Otherwise it merges into another page, becomes a lens, or moves to a shared engine.

**Module rule (from the brief):** Factors stays a module with its own pages. Features merge only where they duplicate another feature, either inside Factors or in Vol, Portfolio or Screener. A merge means one shared engine behind two pages, not one page for two modules.

**Build order formula:** (Demand × Differentiation × Decision value) ÷ Build cost.

---

## 2. Verdict

**Factors V2 is a module worth keeping, and its backend is now honest.** The B1 envelope bug from the old review is fixed: `api.js` posts `{payload}` through the job endpoint, and the router rejects flat bodies (`backend/app/api/factors_v2.py`, `envelope()`). The B2 look-ahead is mostly fixed: characteristics use a 90-day statement lag and the formation universe is chosen on each formation date (`core/panel.py:115`, `:39`). Silent-empty fallbacks now return 422 on unknown symbols.

**The frontend is the gap.** A sine-driven sparkline is still on the metric cards (`frontend/src/components/factors-v2/customPagePrimitives.jsx:206-215`, rendered at `:1072` and `:1570`). The hub's demo arrays are gone (`page.js` `pctWave` now returns null), but the page still needs a data banner. Forms still come from `registry.js`, not from `GET /features`.

**Per-page verdicts (two lines each):**
- **Factors page set:** keep 5 pages (Value and exposure, Regime and timing, Test and capacity, Risk and construction, Monitor) plus the report as plumbing. Seven features keep their own page; six merge into shared engines or lenses.
- **What blocks selling it:** the sparkline and hero literals come out, the data banner ships on every result (survivorship, 90-day lag, 2021+ statement history), and the test suite runs green on the Python the team actually uses (§3).

**The honest product position:** a factor lab that shows its own limits. It is not a survivorship-free institutional backtester. It should be sold as "run it on your own universe, with the caveats printed", not as "Barra at a retail price".

---

## 3. Data reality and build status

### 3.1 Measured data (this pass)

| Dataset | Measured coverage | Consequence |
|---|---|---|
| `backend/data/market_universe.parquet` | 4,158 tickers, 1996-03-18 to 2026-07-06, 10,779,173 rows, columns `Ticker, Date, Open, High, Low, Close, Volume` | Prices and momentum run 30 years. No delisted names, no adjusted-price provenance, no shares. Survivorship must be printed on every result. |
| `backend/data/fundamentals/master_fundamentals.parquet` | 3,833 tickers, `reportDate` 2021-01-31 to 2025-12-31; annual rows 16,524 (2021–2025), quarterly rows 20,599 (2024–2025); 364 columns | Fundamental screens are usable. The screener review said annual data ends 2023; this count shows 2025, so use the measured dates. History before 2021 is absent. |
| `backend/data/canonical/fx_daily.parquet` | 29 currency pairs (for example `EURUSD=X`, `GBPJPY=X`), 2015-01-01 to 2026-02-22, 83,894 rows | Non-USD names convert on exact dates. The FX file stops in February 2026, so later non-USD returns are missing. |
| `factors/data/processed/category7_macro_regime.parquet` | 12,368 rows, 1990-01-01 to 2026-09-25; includes `vix_close`, `vixcls`, `vix3m`, `vix6m`, `dgs10`, `dgs2`, `bamlh0a0hym2` and others | Macro conditioning and VIX regimes are available. |
| `backend/data/factors_us/*.csv` (FF3, FF5, momentum, daily) | Present; the files carry a "CRSP 202608" copyright line. Date range not measured in this pass (the CSV has preamble text). | Standard factor returns exist. Verify the date range before quoting it. |
| `factors/data/processed/aqr_csv/` | 36 CSV files (BAB, QMJ, HML Devil and others) | Present. The DONE.md says AQR was not in the checkout during its validation run. Treat AQR as opt-in until verified. |

### 3.2 Build status (checked)

- **Router and envelope:** mounted at `/api/labs/factors/v2` (`backend/main.py:133`). `POST /feature/{id}/run` and `POST /feature/{id}/jobs` require `{payload}`. The frontend sends the payload through the job route (`frontend/src/lib/api.js:1013-1019`).
- **Manifest:** `feature_manifest()` returns 14 features. Inputs per feature: F01 14, F02 18, F03 11, F04 12, F05 13, F06 16, F07 21, F08 17, F09 19, F10 26, F11 15, F12 17, F13 16, F14 27. Outputs per feature: F01 14, F02 7, F03 4, F04 6, F05 5, F06 3, F07 9, F08 21, F09 3, F10 7, F11 11, F12 6, F13 5, F14 2.
- **Tests (run in this pass with local `python3`, which is Python 3.9.6):** the four files contain 27 test functions. Result: **37 passed, 3 failed**. The three failures are `test_api_envelope_errors_and_input_roundtrip`, `test_upload_sandbox_and_jobs` and `test_export_produces_csv_and_bad_batch_inputs_are_rejected`. Each fails with `TypeError: __init__() got an unexpected keyword argument 'app'`. That error comes from the TestClient and httpx versions in this environment, not from the factor math. The DONE.md reports 40 passing on Python 3.11 in a virtualenv under `/tmp`, which no longer exists. **The 3.11 result is unverified in this pass.** Fix the environment (pin Starlette and httpx) before quoting any test count.
- **Frontend tests:** `frontend/src/components/factors-v2/__tests__/factorsV2.test.ts` exists. Not run in this pass.

### 3.3 Known open frontend defects (checked)

| Defect | Where | Status |
|---|---|---|
| Sine sparkline on metric cards | `frontend/src/components/factors-v2/customPagePrimitives.jsx:206-215`, used at `:1072` and `:1570` | Open |
| Hub demo visuals | `frontend/src/app/labs/factors-v2/page.js` (`pctWave` returns null) | Mostly fixed; the page still needs a "live or illustrative" label |
| Form controls from `registry.js` | `frontend/src/components/factors-v2/registry.js` | Open. The backend already returns the manifest, so the form should render from `GET /features`. |
| Dormant strings | grep for "dormant" in `components/factors-v2` | Not re-checked; the old review listed them |

---

## 4. Competitors and prices

Prices were checked in this pass with TinyFish search and fetch. Entries marked "snippet" come from a search result, not a fetched page. Entries marked "unverified" could not be confirmed.

| Product | Price (checked Nov 2026) | What it does that matters here | Complaint or limit (source) |
|---|---|---|---|
| Finviz Elite | $39.50 per month or $299.50 per year (about $24.96 per month annual). Source: finviz.com FAQ, fetched. | Screener, alerts, export and API | The Elite plan does not include a dedicated factor backtester (no factor-model or capacity tools) |
| Koyfin | Free; Plus $39 per month; Premium $79 per month; Advisor Core $209 per month; annual billing saves up to 30%. Source: koyfin.com plans comparison, fetched. | Global fundamentals and screening | No factor risk model or attribution in the plan text checked (unverified beyond the plan list) |
| Portfolio123 | Screener $25 per month; Pro $83 per month. Sources: liberatedstocktrader (Aug 2026), fool.com (Dec 2024), snippets. | Ranking, backtests, point-in-time data (per vendor claims) | "Steep learning curve" in community threads and a 2026 review (greatworklife, community.portfolio123.com) |
| Stock Rover | Official FAQ: Premium $34 per month or $348 per year; Premium Plus $70 per month or $588 per year. Two review sites print lower figures ($29 and $49 on annual billing). Conflict; the official FAQ is used here. | 800+ metrics, screens | Official support page: "we do not currently have a dedicated backtesting feature" (stockrover.com, fetched). |
| TradingView | Essential $14.95 per month (about $12.95 annual); Plus $29.95; Premium $59.95; Ultimate $199.95 (monthly list). Sources: stockbrokers.com (Aug 2026), tradingview.com pricing (snippet). Billing varies by source. | Charts, Pine screener, alerts | Reddit: screener "never returns the correct results" (r/TradingView 1dextsi); same parameters give different results (r/TradingView 1jid5aa) |
| Screener.in | ₹4,999 per year for Premium. Source: screener.in/premium (snippet). | Ratio builder and screens (India) | India only |
| QuantConnect | Researcher seat $10 per user per month; Team from $24 per user per month. Sources: trendspider (snippet), quantconnect pricing (snippet). Some pages show higher tiers. | Cloud backtests with fees and slippage | No factor-risk or capacity product surface claimed by vendor (unverified) |
| Bloomberg Terminal | List about $31,980 per year for one seat; about $28,320 per seat with two or more. Sources: investopedia (2026, fetched), bluegamma (Oct 2026, snippet). | PORT and factor risk analytics | Price |
| MSCI Barra | Enterprise licence. A third-party site says "can exceed $100,000 per year" (genesis-rm.com, snippet). **Unverified:** no vendor price was found. | Factor risk models, attribution | Price |
| Axioma (SimCorp) | **Unverified.** One Reddit comment quotes a rep at $35K–$50K for a bundled integration package. This is anecdote, not a price list. | Factor risk models | Price |
| alphalens / pyfolio | Free, open source (github.com/quantopian/alphalens, snippet). | IC, quantile returns, tear sheets | Less maintained as a product; not a risk model |
| Riskfolio-Lib, skfolio | Free, BSD-3-Clause (github.com/dcajasn/Riskfolio-Lib; skfolio.org). | Optimizers, HRP, CVaR, Black-Litterman | Libraries, not products |
| V-Lab (NYU Stern) | Public site with GARCH and DCC volatility pages (vlab.stern.nyu.edu, fetched landing page). **Unverified:** the page checked does not state a price, so "free" is not confirmed here. | Volatility and correlation monitor | No portfolio tools (from the site description) |

### 4.1 Demand and complaint evidence

- **Screen dumps are not decisions.** A Reddit thread in r/StockMarket (posted about four months before the page date, published 2026-07-10 per metadata) describes a screen that returned 187 names, and the user closed the laptop. Replies ask for a "kill pass" and for a way to get from a list to decisions. Fetched: reddit.com/r/StockMarket/comments/1uso0yz. The screener review cites the same thread.
- **Trust in screener results is fragile.** TradingView threads complain of false positives and omitted names (r/TradingView 1dextsi, 1jid5aa, v9kclk). Snippets only, not fetched.
- **Backtest bias is a known pain.** Survivorship and look-ahead bias come up repeatedly in r/algotrading threads and in vendor blogs (algoseek, Aug 2026, snippet). These threads support the "print the caveat" rule. They do not give a market size.

### 4.2 Positioning

Factors cannot win on breadth against Koyfin or Finviz, and it cannot match Barra or Axioma data. It can win on three things the cited products do not offer together: a factor lab that runs on the user's own universe, a visible list of what the data cannot support, and a backtest that uses next-close execution and the cost model (per DONE.md). Stock Rover says it has no backtester. Portfolio123 has backtests but no factor-risk or capacity lab in the sources checked.

---

## 5. Evidence per method

Grade: 5 = replicated and matches our data; 3 = supported with caveats; 1–2 = weak or a proxy in our data.

| Method (module feature) | Original or main reference | Out-of-sample and replication | Data fit here | Grade |
|---|---|---|---|---|
| Anomaly screening in general (F01, F05) | McLean and Pontiff (2016), Journal of Finance | Returns are 26% lower out of sample and 58% lower after publication. The paper estimates a 32-point gap from publication-informed trading. Source: onlinelibrary.wiley.com (abstract, snippet). | Holds in general. Use it as a warning on every decay chart. | Context |
| Replication of 452 anomalies (F05, F13) | Hou, Xue and Zhang (2020), Review of Financial Studies | 65% of the 452 anomalies fail a |t| ≥ 1.96 test with NYSE breakpoints and value weighting. Source: global-q.org PDF (fetched). | Value weighting and microcap handling must match this paper. | Context |
| Value (F01) | Fama and French (1992) | Robust over the long run; weaker in some periods (per the screener review; not re-verified here) | Needs the 90-day statement lag. Backtests are capped by the 2021 fundamentals start. | 3 |
| Momentum, 52-week high (F07, F12) | Jegadeesh and Titman (1993); George and Hwang (2004) | Replicated in several papers (the screener review cites them; not re-fetched here) | Price data covers 30 years; this is the strongest backtest the data supports. | 4 |
| Factor decay and half-life (F05) | Standard IC decay (alphalens pattern) | Half-life fits are conditional on the curve model (DONE.md, limitation 9) | Needs matured labels; sparse before 2015 | 3 |
| Information coefficient (F05, F13) | Cross-sectional rank IC | Standard. The old return-autocorrelation "IC" is removed (DONE.md). | Labels mature only at the horizon. | 4 |
| Half-life and Chow-type break tests (F13) | Statsmodels residual CUSUM (DONE.md) | A CUSUM statistic and p-value, not a Chow coefficient test | Small sample | 3 |
| Crowding (F06) | Institutional crowding (MSCI) | No calibration: DONE.md removes the institutional score. Left: HHI, persistence and Roll spread. | Volatility and liquidity proxies, not crowding | 2 |
| Covariance and DCC (F08) | Engle (2002); Ledoit and Wolf (2004) | DONE.md says the DCC is an explicit fixed-parameter recursion, not MLE | Fine for research; not a risk model | 3 |
| Capacity and square-root impact (F09) | Standard square-root impact assumption | Declared assumption, not calibrated (DONE.md, limitation 7) | Observed ADV in USD | 3 |
| Optimizer (F10) | Markowitz; Black-Litterman | CLARABEL SOCP with constraints (DONE.md). Views are numeric inputs, not text. | Covariance from the same panel | 4 |
| Stress and VAR IRF (F11) | Sims-style VAR, residual bootstrap | DONE.md: coefficient refit, 90% bands | Macro inputs are not zero-filled | 3 |
| Deflated Sharpe and PBO (cross-module; Test page) | Bailey and López de Prado (2014); Bailey et al. (2016) | DSR corrects selection bias, backtest overfitting and non-normality (ssrn abstract, snippet). PBO is the probability of backtest overfitting (researchgate, snippet). Not implemented in Factors; belongs to the shared Validate engine. | Needs the trial count | 4 (as a shared engine) |

**Implication for the page set:** lead with value, momentum, the 52-week high and the composite. Keep crowding out of the first-class pages until a calibrated measure exists. Keep decay and IC with their caveats in the footnote.

---

## 6. Scored feature table

Scores are 1–5 (judgment). Columns: Dem = Demand, Evid = Evidence, Diff = Differentiation, Dec = Decision value, Rec = Recurring, Cost = Build cost (5 = cheap). "Call" is the decision.

| Feature | Dem | Evid | Diff | Dec | Rec | Cost | Call |
|---|---|---|---|---|---|---|---|
| F01 Valuation spread monitor | 4 | 3 | 3 | 4 | 3 | 3 | **Keep**, Value and exposure page |
| F02 Exposure decomposition (holdings, per-stock OLS, active exposure) | 4 | 3 | 3 | 4 | 3 | 3 | **Keep**, Value and exposure page; absorbs F03 and F12 as tabs |
| F03 Return attribution | 3 | 2 | 2 | 3 | 2 | 3 | **Merge into F02** as an attribution tab. The frontend only has supplied-exposure P&L; no observed portfolio history. |
| F04 Probabilistic regime analysis | 4 | 3 | 3 | 4 | 3 | 3 | **Keep**, Regime page; estimator **shared with Vol V04** |
| F05 Alpha decay and half-life | 3 | 4 | 3 | 3 | 3 | 3 | **Keep**, Regime and timing page with the decay caveat; absorbs F06 |
| F06 Crowding monitor | 3 | 2 | 2 | 2 | 2 | 4 | **Merge into F05** as a persistence panel. The institutional score is cut. |
| F07 Backtest engine | 5 | 4 | 3 | 5 | 3 | 3 | **Keep**, Test page; routes results to the **shared Validate engine** (DSR, PBO, controls) |
| F08 Covariance and DCC | 3 | 3 | 2 | 3 | 2 | 3 | **Merge with Vol V07** into one covariance engine; both pages remain |
| F09 Capacity analyzer | 3 | 3 | 4 | 3 | 2 | 3 | **Keep**, Test and capacity page (AUM sweep is distinct; the cost model is shared with the Portfolio F11 execution engine) |
| F10 Portfolio optimizer | 3 | 4 | 3 | 4 | 2 | 2 | **Merge into Portfolio F01** construction engine. Factors keeps only a factor-space lens. |
| F11 Stress and reverse stress | 4 | 3 | 3 | 4 | 3 | 2 | **Merge with Vol V08 and Portfolio F04** into one stress engine; Factors keeps the factor-shock page |
| F12 Factor DNA | 3 | 2 | 4 | 3 | 2 | 3 | **Merge into F02** as the DNA radar. The archetype classifier is cut (DONE.md). |
| F13 Live signal monitoring | 4 | 3 | 3 | 4 | 5 | 3 | **Keep**, Monitor page (persistence drift and matured IC drift; alert log in-app only) |
| F14 Allocator report | 3 | 3 | 3 | 3 | 2 | 3 | **Keep as plumbing**: the export button on every page (PDF and CSV). Not a page. |

**Counts (Factors):** 7 keep with their own page (F01, F02, F04, F05, F07, F09, F13); 6 merge (F03, F06, F08, F10, F11, F12); 1 plumbing (F14); 0 features removed outright. Outputs cut are listed in §7.

### 6.1 Output-level calls

| Output | Call | Reason |
|---|---|---|
| F01 `valuation_spreads`, `spread_percentile_timeseries` | Keep | Dated characteristic spreads (DONE.md) |
| F01 `crisis_anchors`, `crisis_anchor_table` | Keep as a table | Prior-only anchors |
| F01 `expected_return_regression` | Keep with HAC interval | Matched forward-return OLS |
| F01 `gauge_panel` | Keep as a KPI strip | — |
| F01 `alert_feed` | Keep | In-app only |
| F01 `cross_sector_table`, `sector_contribution` | Keep | — |
| F02 `exposure_bar`, `characteristic_exposures` | Keep | Core output |
| F02 `static_exposure_heatmap` | Keep as a heat table | — |
| F02 `rolling_exposure_snapshots` | Keep | Only with real holdings history |
| F02 `active_characteristic_exposures` | Keep | Needs a benchmark |
| F02 `return_exposures`, `portfolio_return_exposures` | Keep with label "return-based" | Proxy label |
| F03 `waterfall`, `factor_contribution` | Keep inside F02 | Needs supplied exposures and returns |
| F03 `attribution_reconciliation` | Keep | Identity check |
| F04 `hmm_probability`, `current_regime`, `transition_matrix` | Keep | — |
| F04 `gmm_probability` | Keep, gated to research mode | Per DONE.md |
| F04 `observed_market_rules` | Keep as a diagnostic, not a regime label | Rules are separate |
| F04 `conditional_returns` | Keep | — |
| F05 `ic_decay_curve`, `ic_by_horizon` | Keep | — |
| F05 `decay_model_fits`, `half_life_confidence` | Keep with caveat | Conditional on curve model |
| F06 `crowding_timeseries`, `crowding_metrics` | Merge into F05 as "persistence" | Not a crowding score |
| F06 `bid_ask_detail` | Cut | Roll estimator from close prices is weak |
| F07 `equity_curve`, `drawdown`, `statistics` | Keep | — |
| F07 `monte_carlo_bands` | Keep | Stationary bootstrap |
| F07 `quintile_monotonicity`, `decile_monotonicity` | Keep quintiles; decile table only if measured (DONE.md says measured) | Confirm before showing |
| F07 `transaction_costs`, `turnover_analysis`, `gross_vs_net_by_year` | Keep | Core for the honesty story |
| F08 `correlation_heatmap`, `normal_vs_crisis`, `eigenvalues` | Keep as covariance engine | Shared with Vol V07 |
| F08 `dcc_correlation_heatmap`, `dcc_annualized_covariance` | Keep, labelled as recursion | DONE.md |
| F08 `crisis_preset_comparison` (listed twice in the manifest) | Keep once | Duplicate key in manifest |
| F08 `portfolio_risk_decomposition` (listed twice in the manifest) | Keep once | Duplicate key |
| F08 `matrix_validation` | Keep | PSD and status |
| F09 `capacity_curve`, `slippage_by_aum`, `sensitivity` | Keep | Sweep, not two hand-picked cases |
| F10 `efficient_frontier`, `optimal_weights`, `constraint_binding` | Keep in Portfolio F01 | Shared |
| F10 `fap_diagnostic` | Keep, now a regression (DONE.md) | — |
| F10 `black_litterman_posterior` | Keep, numeric views only | — |
| F11 `scenario_waterfall`, `factor_shocks`, `reverse_stress` | Keep | — |
| F11 `contagion_irf`, `irf_confidence_bands` | Keep | Refitted bootstrap (DONE.md) |
| F11 `hedging_recommendation` | Cut | DONE.md says the invented hedge mapping was removed, but `feature_manifest()` still lists this output. Conflict: fix the manifest or the DONE.md before shipping. |
| F11 `var_lag_selection`, `stress_var_cvar`, `historical_analog` | Keep | — |
| F12 `dna_radar`, `dna_vector`, `concentration` | Keep inside F02 | — |
| F12 `purity_regression`, `correlation_dna` | Keep inside F02 | — |
| F13 `ic_drift`, `signal_health` | Keep | Matured IC (DONE.md) |
| F13 `structural_break_diagnostic` | Keep as CUSUM | Label as CUSUM, not Chow |
| F13 `alert_log`, `alert_policy` | Keep | In-app only |
| F14 `sections`, `aima_ddq_cross_reference` | Keep as export | Broad disclosure topics, not certified DDQ answers (DONE.md) |

---

## 7. Final page cut and what makes each page a 5

Factors ships five pages and one export.

### 7.1 Value and exposure (F01, F02 with F03 and F12 tabs)

| Axis | Upgrade to 5 |
|---|---|
| Demand | Start from "my holdings" or "my universe" and see exposures in one click |
| Evidence | Each exposure carries its data date, the lag and the "return-based" label where used |
| Differentiation | Holdings exposure beside a benchmark; the DNA radar with units, not arbitrary scales |
| Decision value | The bottleneck exposure is named; active exposure is one number |
| Recurring | Re-run on the same holdings as the data refreshes |

### 7.2 Regime and timing (F04, F05 with F06 persistence)

| Axis | Upgrade to 5 |
|---|---|
| Demand | One regime pill and one decay curve per factor |
| Evidence | Every decay chart shows the McLean–Pontiff warning and the matured sample size |
| Differentiation | Regime probabilities plus conditional returns, not a black box |
| Decision value | "Current regime" and "half-life" with the interval |
| Recurring | Regime timeline and half-life tracked on the Monitor page |

### 7.3 Test and capacity (F07, F09)

| Axis | Upgrade to 5 |
|---|---|
| Demand | Test a screen-like factor rule with costs |
| Evidence | Next-close execution, traded-notional costs, borrow cost, Monte Carlo bands |
| Differentiation | Capacity sweep (AUM vs Sharpe and slippage) in one view |
| Decision value | Break-even cost and capacity in USD |
| Recurring | Re-run on each data version; trial counts feed the Validate engine |

### 7.4 Risk and construction (F08, F10, F11 as lenses on shared engines)

| Axis | Upgrade to 5 |
|---|---|
| Demand | Covariance, frontier and stress in one place for a factor book |
| Evidence | PSD checks; constraint-binding table; refitted IRF bands |
| Differentiation | Factor-space optimizer and factor-shock stress on the user's exposures |
| Decision value | Which constraint binds and which shock hurts most |
| Recurring | Risk snapshot on the Monitor page |

### 7.5 Monitor (F13, F14 as export)

| Axis | Upgrade to 5 |
|---|---|
| Demand | A daily signal health view for saved factor rules |
| Evidence | Matured IC drift, CUSUM p-value, stated sample |
| Differentiation | Alert precision (did the alert precede a good forward return?) |
| Decision value | "Retire, watch or keep" by factor |
| Recurring | Alerts land in the notifications centre; email and webhook are not built |

---

## 8. New A++ features

These use only the data we have. Each is a shared engine first, a page second.

1. **Look-ahead audit on every result.** A panel that lists the statement lag, the formation dates used, the universe rule and the survivorship caveat. Reuses the DONE.md facts, so every page shows the same audit. Cheap; trust-critical.
2. **Factor DNA with units.** The DNA radar as percentile and z-score bars with the units printed, not the old arbitrary 1000× scalings. Evidence 4, Differentiation 4.
3. **Alert precision scoreboard.** For each saved factor rule, the matured forward return after each alert against the universe. Needs no new data; reuses F13 alert log and F05 horizons.
4. **Factor lab to Validate hand-off.** One click sends an F07 result to the shared Validate engine (controls, DSR, PBO) with the trial count from a ledger. Reuses the ML engine.
5. **Decay with the warning built in.** Every half-life chart shows the published out-of-sample decay alongside our estimate, so the user sees both.

---

## 9. Shared with other modules

| Shared piece | Factors feature | Also used by | Note |
|---|---|---|---|
| Regime HMM and GMM estimator | F04 | Vol V04 | One core module; two pages |
| Covariance engine (sample, EWMA, Ledoit-Wolf, DCC recursion) | F08 | Vol V07, Portfolio F01 | One engine; labels kept honest |
| Optimizer (CLARABEL SOCP, Black-Litterman) | F10 | Portfolio F01 | Portfolio owns the engine |
| Stress and reverse stress, VAR IRF | F11 | Vol V08, Portfolio F04 | One engine |
| Cost and capacity model | F07, F09 | Portfolio F11 | Square-root impact assumptions in one place |
| Validate engine (DSR, PBO, controls) | F07 | ML, Screener S5, Portfolio F02 | Owned by ML |
| Data loader (prices, fundamentals, FX, macro) | all | all | `factors_v2/core/data_loader.py` should move to a shared module (the platform spec asks for one loader) |
| Cinema kit (Exhibit, KpiStrip, RankList, Dumbbell, Heat table) | all | all | `src/charts/v2/` |

---

## 10. Inputs pruned

Input counts from the live manifest: F14 27, F10 26, F07 21, F08 17, F12 17, F02 18, F06 16, F13 16, F09 19, F11 15, F01 14, F05 13, F04 12, F03 11.

**Remove from the first screen (keep in the API, behind "advanced"):**
- `compute_mode` (appears on 11 features): choose one default per page instead.
- `include_aqr`, `aqr_region`: AQR is opt-in and unverified (§3.1).
- `instrument_metadata`, `snapshot_step`: internal.
- `max_tickers`: replace with a universe picker.
- `rebalancing_history`, `holdings_upload_id`: keep as an upload control, not a text field.
- F14 `custom_narrative`, `fund_disclosures`, `contact_info`, `disclaimer`, `section_order`, `report_version`, `max_pdf_pages`: move to a report settings drawer.
- F10 `robust`, `robust_penalty`, `risk_loadings`, `expected_returns`: keep behind "advanced".

**Keep as first-class controls:** `as_of_date`, `tickers` or universe preset, `start_date`, `end_date`, `factor` or `factors`, `window_days`, `cost_bps`, `rebalance_days`, `long_short`, `holdings` (upload), `states` (F04), `horizons` (F05).

**Remove the duplicate manifest keys:** F08 lists `portfolio_risk_decomposition` and `crisis_preset_comparison` twice in its outputs. Fix in `features/inputs.py`.

---

## 11. UI on the ML cinema kit

- **Page shell:** takeaway title per page (for example "Your book is 1.4 standard deviations value-tilted"); subtitle in the grammar "measure, unit, universe, window"; KPI strip with 4–6 numbers; the data banner under the verdict.
- **Data banner (every result):** "Fundamentals from 2021, 90-day statement lag, current listings only, quotes from [data date]". Removed only when the point-in-time data is bought.
- **Exhibits:** borderless. Use `TimeSeries v2` for decay and regimes (end labels, event annotations for regime switches), `Heat table` for exposures and the plateau, `Dumbbell` for model against benchmark, `Distribution` for Monte Carlo bands (once built), `Waterfall v2` for attribution (once built), `Calendar heatmap` for monthly IC.
- **Unknown values:** hatched cell, never blank or zero. Show coverage per factor ("P/B known for 3,612 of 4,158").
- **Remove:** the sine sparkline, hub literals (if any remain), the `registry.js` form contract, and the "dormant" strings.
- **Phone:** the KPI strip becomes 2 columns; exhibits stack.

---

## 12. Pricing

Prices are proposals, anchored to the checked competitor prices in §4. They are not market facts.

| Tier | Proposed price | Includes | Anchor |
|---|---|---|---|
| Free | $0 | Factor rules on the default universe, end-of-day data, one saved rule, the data banner on every result | Finviz free, Koyfin free |
| Pro | $29 per month | Unlimited saved rules, decay, regime, exposure, CSV export, in-app alerts | Below Finviz Elite $39.50 and Koyfin Plus $39 |
| Quant | $79 per month | Test with Validate (DSR, PBO), capacity, PDF report, webhook (when built), uploads | Matches Koyfin Premium $79; below Portfolio123 Pro $83 |
| Team and institutional | quote | Seats, shared rules, point-in-time data add-on, white-label PDF | Bloomberg about $28,320 per seat is the ceiling |

**Licence before charging:** raw prices and fundamentals shown to paying users need a display or redistribution licence. The earlier review named Twelve Data as a candidate; **its current price is unverified in this pass.** Budget it before launch.

---

## 13. Build order

| Step | Work | Backend | Frontend | Size |
|---|---|---|---|---|
| 1 | Fix the test environment: pin Starlette and httpx so the three envelope/upload/export tests run; confirm on Python 3.11 | test env only | — | S |
| 2 | Remove the sine sparkline and the duplicate manifest keys; add the look-ahead audit and the data banner | duplicate keys fix | sparkline removed, banner | S |
| 3 | Render forms from `GET /features` (manifest-driven); remove the 11 display-only controls from the first screen | none (manifest exists) | forms | M |
| 4 | Cinema-kit page shell and the five pages (Value and exposure, Regime and timing, Test and capacity, Risk and construction, Monitor) | none | pages | M |
| 5 | Merge F03, F06, F12 into their hosts; move F08, F10, F11 to shared engines (with Vol and Portfolio owners) | shared modules | lenses | M |
| 6 | Alert precision scoreboard; decay with McLean–Pontiff reference | small | card | S |
| 7 | Validate hand-off with trial ledger | Validate wiring | button | M |
| 8 | Report export: PDF and CSV from F14 | existing | export menu | S |
| 9 | Move the data loader to a shared module; add FF date-range check and AQR verification | loader | none | M |

**Size:** about 4–6 focused sessions on top of the ML kit, most of it composition.

---

## 14. Sources and what could not be verified

**Competitor pages (fetched or checked by search in this pass)**
- Finviz plans and FAQ: https://finviz.com/help/faq (fetched); https://finviz.com/elite (snippet); https://www.stockbrokers.com/review/tools/finviz (snippet)
- Koyfin plans: https://www.koyfin.com/pricing/plans-comparison/ (fetched); https://www.koyfin.com/pricing-llm-info/ (snippet)
- Portfolio123: https://www.liberatedstocktrader.com/portfolio123-review/ (snippet, Aug 2026); https://discussion.fool.com/t/portfolio123-whats-working-lately/111089 (snippet); https://www.greatworklife.com/portfolio123-review/ (snippet); https://community.portfolio123.com/t/what-now-12345/61852 (snippet)
- Stock Rover: https://www.stockrover.com/features/pricing/premium-plans/ (snippet); https://www.stockrover.com/help-resources/faqs/ (snippet); https://www.stockrover.com/support-database/can-i-use-screeners-for-backtesting/ (snippet, states no backtesting)
- TradingView: https://www.tradingview.com/pricing/ (snippet); https://www.stockbrokers.com/review/tools/tradingview (snippet)
- Screener.in: https://www.screener.in/premium/ (snippet)
- QuantConnect: https://www.quantconnect.com/pricing/ (snippet); https://trendspider.com/learning-center/quantconnect/ (snippet)
- Bloomberg: https://www.investopedia.com/terms/b/bloomberg_terminal.asp (fetched); https://www.bluegamma.io/post/bloomberg-terminal-pricing (snippet)
- MSCI Barra: https://genesis-rm.com/blog/affordable-barra-risk-metrics-alternatives (snippet, third-party)
- alphalens: https://github.com/quantopian/alphalens (snippet); Riskfolio-Lib: https://github.com/dcajasn/Riskfolio-Lib (snippet); skfolio: https://skfolio.org/ (snippet)
- V-Lab: https://vlab.stern.nyu.edu/ (fetched; no price stated)

**Complaints and demand**
- https://www.reddit.com/r/StockMarket/comments/1uso0yz/screener_gave_me_187_companies_and_i_just_closed/ (fetched)
- https://www.reddit.com/r/TradingView/comments/1dextsi/bring_back_the_screener_as_it_was/ (snippet)
- https://www.reddit.com/r/TradingView/comments/1jid5aa/new_screener_doesnt_give_the_same_results_as_old/ (snippet)
- https://www.reddit.com/r/TradingView/comments/v9kclk/tradingview_screener_omits_stocks_all_the_time/ (snippet)
- https://algoseek.com/blog/data-guides/survivorship-bias-in-backtesting-what-to-ask-a-data-vendor/ (snippet)

**Method evidence**
- McLean and Pontiff (2016): https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365 (snippet with the 26%/58% figures)
- Hou, Xue and Zhang (2020): https://global-q.org/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf (fetched; 65% of 452 with NYSE breakpoints and value weights)
- Deflated Sharpe: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 (snippet); PBO: https://www.researchgate.net/publication/318600389_The_probability_of_backtest_overfitting (snippet)
- arch MCS documentation: https://arch.readthedocs.io/en/stable/multiple-comparison/generated/arch.bootstrap.MCS.html (snippet)

**Internal**
- `backend/app/services/factors_v2/DONE.md` (2026-10-07), `backend/app/api/factors_v2.py`, `backend/app/services/factors_v2/features/inputs.py`, `backend/app/services/factors_v2/core/panel.py`, `backend/app/services/factors_v2/core/data_loader.py`, `frontend/src/lib/api.js`, `frontend/src/components/factors-v2/customPagePrimitives.jsx`
- `docs/reviews/FACTORS_V2_REVIEW.md`, `docs/reviews/SELL_10_SCREENER_FACTORS_RESEARCH.md`

**Unverified (not confirmed in this pass)**
- Axioma and MSCI Barra prices (only anecdote and third-party text)
- V-Lab "free" status (not stated on the page checked)
- TradingView exact monthly and annual prices (sources disagree by billing period)
- Stock Rover Premium price (official FAQ and two review sites disagree)
- Portfolio123 point-in-time and delisted data claims (vendor claims, not checked against their data documentation)
- The Twelve Data licence price named in the earlier review
- The Fama-French CSV date range (not measured)
- The DONE.md result of 40 passing tests on Python 3.11 (`backend/venv` is Python 3.11 but has no pytest, so this was not rerun)
- The frontend Jest test (`factorsV2.test.ts`) and any browser behaviour
- Method-evidence grades for value, momentum and the 52-week high were carried from the screener review and not re-fetched here
