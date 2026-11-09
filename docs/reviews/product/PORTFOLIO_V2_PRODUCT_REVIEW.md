# Portfolio product review: 13 engines, one honest workspace

Written 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. Backend claims were checked by reading the code under `backend/app/services/portfolio_v2/` (registry, `features/inputs.py`, all 13 `features/feature_*.py`, and the `core/` engines) and `backend/app/api/portfolio_v2.py`. Prices, licences and feature lists come from pages fetched with TinyFish on the same date. Anything not read or fetched is marked **unverified**.

## Contents
1. Verdict
2. What is real and what is hollow in the code
3. Data we hold, and its limits
4. Paid-feature parity table
5. Keep, build, later or cut, per feature
6. Our own ideas for freedom and customisation
7. Open-source picks and licences
8. Build checklist
9. Sources

---

## 1. Verdict

Portfolio V2 is a strong **backend with no product**. It has 13 engines, each returning measured numbers and a list of what it could not compute. The old frontend was removed on 2026-11-06, and the only portfolio UI left is the legacy Studio `PortfolioView.jsx`, which calls `/portfolio/optimize` and `/portfolio/versions` in `backend/app/routers/studio.py`. Neither of those is a v2 route. So the rebuild starts from zero UI.

Paid tools in this space sell four things: a **portfolio tracker** (holdings, dividends, tax, performance), a **risk view** (exposures, scenario losses, volatility), a **backtest and optimiser** (weights, rebalancing, Monte Carlo), and **institutional attribution and stress** (Bloomberg PORT, Axioma, Aladdin, which are priced by enterprise quote). Retail tools do the first and a shallow version of the second. None of the retail tools show whether a backtest is overfit, and none show the data limits of a result.

Our position follows the platform rule: **a portfolio tool that shows how far each number can be trusted.** The backend already does this better than any tool in section 4. The product task is to surface it.

- **Lead with three pages:** Construct (F01, with F10 sizing as a lens), Test (F02, honest backtest), Stress (F04, reverse stress and scenarios). These match the step 6 plan in `docs/plans/PLAN.md`.
- **Keep five more as lenses or panels:** F03 attribution, F05 macro exposure, F07 liquidity, F08 correlation, F06 regimes.
- **Later, because they need user data:** F09 signal decay, F11 execution, F12 systemic, F13 multi-strategy.
- **Cut the one output that overclaims:** the Kelly ruin probability in F10 (section 5).
- **Do not fake data.** Historical index membership, delisted returns, point-in-time sectors and measured spreads are absent. The backend already refuses or discloses them. The UI must show the same limits.

---

## 2. What is real and what is hollow in the code

Read from function bodies, 2026-11-09.

**Real: measured and tested.**

- **Honest backtest (F02).** `walk_forward` in `core/backtest.py` re-estimates before each holding date. The DSR in `core/stats.py::deflated_sharpe_ratio` uses cross-trial variance when more than one variant exists. `pbo_cscv` enumerates half-splits, sampling deterministically at 5,000 when the count is larger, and reports the sample size. The Harvey-Liu output is named honestly as a **Bonferroni** one-sided test (`harvey_liu_correction`), not HLZ, which the old spec claimed.
- **Reverse stress (F04).** `minimum_mahalanobis_reverse_stress` in `core/stress.py` uses the closed-form minimum-Mahalanobis shock `d = Σw(target − wᵀμ)/(wᵀΣw)`. It is correct and small. The historical replay uses trailing FF5 betas times observed crisis factor sequences, and says so in its `method` field. It is a factor replay, not realised holdings P&L.
- **Constrained optimisation (F01).** `solve_portfolio` in `core/construction.py` dispatches to CLARABEL-convex solves for GMV, MVO, growth-optimal, Black-Litterman and CVaR, with constraint checks and a `constraint_report`. The covariance dispatch in `core/covariance.py` raises on an unknown method rather than falling back to equal weights.
- **Attribution (F03).** Brinson-Fachler and BHB are computed separately. Carino, Menchero and GRAP linking are computed in `core/attribution.py`. Brinson runs only when long-only benchmark weights are supplied, and the code says so when they are not.
- **Liquidity (F07).** `liquidity_table` refuses any symbol that is not a USD equity with share volume (`ValueError`). This is a real gate, not a silent proxy.
- **Uploads and jobs.** CSVs are capped at 2 MB, content-addressed, validated and stored under a sandboxed path (`core/uploads.py`). Jobs refuse to publish if the source version changed during estimation (`_execute` in the router).
- **Tests.** 55 test functions across four `backend/tests/test_portfolio_v2_*.py` files. `DONE.md` reports 71 passing cases, or 84 with real data enabled. These are backend-only checks. No frontend test exists for v2.

**Hollow or limited: works, but the output is weaker than its name.**

- **Amihud definition (F07).** `liquidity_table` uses open-to-close absolute return over dollar volume (`(Close/Open − 1)/(Close × Volume)`). The standard Amihud uses close-to-close returns. The label says "open-to-close", so it is honest, but it is not the number a researcher expects. Decide before the UI shows it as "Amihud".
- **Stress verdict thresholds (F04).** `feature_04.py` sets the verdict to red at a 5% tail of −20% and amber at −10%, fixed in code. Make these user-set in the UI or label them as fixed.
- **Regime thresholds (F06).** The VIX classifier uses fixed cut-offs at 15, 25 and 35 (`causal_regimes`). That is a rule, not a model. Label it.
- **Macro factors (F05).** The factor list is restricted to nine observed series in `feature_05.py`. The model is market-implied exposure, and the `interpretation` field says it is not a forecasting model. Keep that wording in the UI.
- **Dead helpers.** `rg` over `backend/app` and `backend/tests` finds no caller for `reverse_stress_test`, `weight_stability_index`, `cvar_minimize`, `min_cvar_target`, `black_litterman_weights`, `geometric_growth_rate`, `turnover_optimal_kelly` and `regime_conditional_cov`. They are candidates for deletion. Per `AGENTS.md`, confirm with the codebase graph and an import check before removing any of them. This review does not delete them.
- **Ruin probability (F10).** `feature_10.py` publishes a `ruin_probability_model` from an infinite-horizon arithmetic Brownian approximation. The code labels it "not a drawdown guarantee", but the number is still a probability a non-quant user will read as a risk figure.
- **Empty-by-design features.** F12 (systemic) and F13 (strategies) return a "data requirement" table and no result unless the user supplies peer books or strategy return histories. F09 judgment signals require `signal_scores`.

**Not present at all.**

- Any frontend for v2.
- A survivorship-corrected universe, point-in-time sectors, delisted returns, measured bid-ask spreads.
- A PDF renderer. Exports are JSON, CSV tables and LaTeX source (`/export` route).
- Live data. Data are end-of-day from local parquet files.

---

## 3. Data we hold, and its limits

Source paths are read from `core/data_loader.py`. Counts for the market file come from the Screener review, checked 2026-11-08 (`docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` section 2). Portfolio did not re-count them today.

| Data | Where, per code | Coverage | Consequence |
|---|---|---|---|
| Daily prices | `backend/data/market_universe.parquet` plus canonical `equity_daily`, `fx_daily`, `crypto_daily`, `futures_daily` | About 4,158 tickers, 1996 to 2026 (Screener review count) | Symbol search and backtests cover US-style names. Not the `backend/data/prices/` `.NS` files |
| Indian names | Not read by the portfolio loader | 333 NSE and 98 BSE in fundamentals, but liquidity refuses non-USD symbols | No India in Portfolio v2 today. Liquidity and dollar ADV fail for INR names by design |
| Fundamentals and sectors | `master_fundamentals.parquet` via `load_fundamentals_metadata` | Statements 2021 to 2025; currency metadata | Sector constraints use **current, static** labels. Historical sector caps are refused (`feature_01.py`) |
| Fama-French and momentum | `backend/data/factors_us/ff5_daily.parquet`, `momentum_daily.parquet` | Daily, decimal units | F03, F04, F05 factor work. Monthly and weekly use resampled observed returns |
| Macro | `factors/data/processed/category7_macro_regime.parquet` | VIX, DGS10, DGS2, credit spread, FX | F05 and F06. The slope is recomputed as DGS10 − DGS2, because the archived column is sparse |
| Default universe | `registry.py` | SPY, QQQ, IWM, EFA, EEM | Five ETFs by default. Any other universe is supplied by the user |
| Uploads | `backend/data/portfolio_v2/uploads/` | 2 MB, five kinds | Returns, factor returns, signal scores, strategy trades, peer books |

**Rules the backend enforces (keep them in the UI).** Reports and returns are cut at `as_of_date` before the window is chosen. No forward fill, no zero replacement. A missing held return fails the run. Unknown symbols return 422. Signed weights are preserved. The static-sector and no-survivorship disclosures appear in `meta`.

**What the product cannot promise.** Delisted names, historical index membership, point-in-time shares and caps, measured bid-ask spreads, signed order flow, ETF flows, analyst estimates, dividends in close prices (close-price returns are not claimed to include all dividends or corporate actions), and live prices. Each one is "later" or "cut" in section 5.

---

## 4. Paid-feature parity table

Status: **have** (in the backend and read), **build** (data held, UI or small code needed), **later** (needs data or user input), **cut** (not a portfolio job, or unsound). "Who" names the paid products that offer it. Prices are on the sources in section 9.

| # | Feature | Who offers it (tier) | Our status | Note |
|---|---|---|---|---|
| P1 | Holdings tracker: positions, cost basis, dividends, performance | Sharesight (Starter $7/mo billed annually, Standard $18, Premium $23.25; free 10 holdings) [official]; Morningstar Portfolio (X-Ray yearly $249 per search snippet) [third party] | later | Needs user transactions. Our input is weights, not trades. Trade-history file exists in canonical, but no UI. Cut tax reporting |
| P2 | Asset allocation and sector weights | Morningstar X-Ray; Sharesight | have | Sector weights are static labels (F01) |
| P3 | Fees and overlap of holdings | Morningstar X-Ray | cut | Needs fund holdings and expense ratios, which we do not hold (Screener cut C22) |
| P4 | Backtest with rebalancing | Portfolio Visualizer (Basic $30/mo, Pro $55/mo) [official]; Sharesight Premium (performance reports) | have | F02 with calendar, observed-bar and drift-threshold rebalancing |
| P5 | Monte Carlo of future wealth | Portfolio Visualizer [official, pricing page lists it] | have | F04 uses stationary block bootstrap (not iid). Horizon, paths and block length user-set |
| P6 | Factor regression (FF3, FF5, momentum) | Portfolio Visualizer [official]; Morningstar | have | F03 factor attribution and F05 macro exposures |
| P7 | Optimisation: min variance, max Sharpe, risk parity, Black-Litterman, HRP, CVaR | Portfolio Visualizer; skfolio and Riskfolio (OSS) | have | F01, nine objectives, convex where possible. Expected returns are shrinkage or sample, not analyst estimates |
| P8 | Tactical allocation models | Portfolio Visualizer [official] | later | Needs a rule library. Regime-conditional allocation (F06) is the closest and is a lens |
| P9 | Efficient frontier chart | Portfolio Visualizer, Riskfolio | have | F01 frontier, 2 to 100 points |
| P10 | Risk: volatility, drawdown, VaR and CVaR | Portfolio Visualizer; Bloomberg PORT (enterprise, price not public [unverified]) | have | F02 and F01 risk; VaR has three methods in `stats.py` |
| P11 | Scenario and crisis replay | Bloomberg PORT, Aladdin (enterprise, not fetched [unverified]) | have | F04 with ten crisis windows, all observed |
| P12 | Reverse stress test | Not seen in any retail tool; institutional tools not checked [unverified] | have | F04 closed form. Ours is a differentiator |
| P13 | Attribution: Brinson, factor, selection skill | Enterprise (StatPro, Geneva; from design notes, not fetched [unverified]) | have | F03, with a skill-versus-luck null. Brinson needs constituent weights |
| P14 | Liquidity and days-to-liquidate | Enterprise; not in any retail tool checked | have | F07, USD equities only |
| P15 | Correlation network and contagion | Enterprise; not checked | have | F08 |
| P16 | Multi-strategy allocation and kill switches | Not checked | later | Needs user strategy return histories. F13 is the engine |
| P17 | Signal decay and half-life | Not checked | later | Needs user signal scores. F09 is the engine |
| P18 | Execution cost and schedule | Enterprise trading desks; not checked | later | Impact coefficients are assumptions. F11 |
| P19 | Systemic and peer overlap | Not checked | later | Needs user peer books. F12 |
| P20 | PDF report | Sharesight, Portfolio Visualizer (export) | build | Exports are JSON, CSV and LaTeX today. PDF is a build, using typst (see section 7) |
| P21 | Alerts on drift or breach | Sharesight (price and portfolio email alerts, listed on pricing page) [official] | later | Monitor module, shared with Screener |
| P22 | Trade import from broker or email | Sharesight | cut | Broker links are cut (Screener C3) |
| P23 | Shared or white-label reports for advisers | Enterprise | cut | Team tier is later (Screener C19) |

**Counts.** 23 rows. Have 12 (P2, P4, P5, P6, P7, P9, P10, P11, P12, P13, P14, P15). Build 1 (P20, PDF). Later 7 (P1, P8, P16, P17, P18, P19, P21). Cut 3 (P3, P22, P23). Row P1 is later because tracking needs trades, which the UI does not take.

**Unverified in this table.** Bloomberg PORT, Aladdin, Axioma, StatPro and Geneva prices: no public price was found. Morningstar X-Ray yearly price comes from a search snippet, not a fetched page. Portfolio Visualizer Pro tier (commercial use) comes from a third-party comparison.

---

## 5. Keep, build, later or cut, per feature

Each row gives the call and the reason. "Lens" means it sits inside a page, not on its own page.

| Feature | Call | Reason |
|---|---|---|
| F01 Construction | **Keep, lead (Construct page)** | Covers P7 and P9 and the sizing lens. Default to six objectives in the UI: min variance, max Sharpe, risk parity, HRP, Black-Litterman, MVO. Hide CVaR, maximum diversification and growth-optimal behind "advanced" |
| F02 Backtest | **Keep, lead (Test page)** | Real DSR, PBO and honest walk-forward. The only tool in section 4 that says whether a backtest is overfit. Survivorship warning shown on every result |
| F03 Attribution | **Keep, lens on Test** | Factor attribution works with no extra input. Brinson appears only when constituent weights are supplied. Skill-versus-luck null shown with each period |
| F04 Stress | **Keep, lead (Stress page)** | Reverse stress and crisis replay are unique in this list. Make the verdict thresholds user-set. Monte Carlo horizon and block length in the UI |
| F05 Macro | **Keep, lens on Stress** | Market-implied exposure, not a forecast. Show target versus observed beta, with the warning text from `meta` |
| F06 Regimes | **Later, then keep as lens** | Real HMM and Hamilton paths, but the VIX classifier uses fixed cut-offs. Ship after F01 to F04 work. The refit loop over every date is slow; check run time before exposing it |
| F07 Liquidity | **Keep, lens on Stress** | Days-to-liquidate and capacity are useful for any user with a mid-size book. Restrict to USD equities and say why. Fix the Amihud label or definition before showing it |
| F08 Correlation | **Keep, but merge into Construct and Stress as lenses** | Heatmap, MST and eigenvalue series are useful. Drop the separate network page. Keep the trend-break test with its family adjustment |
| F09 Decay | **Later** | Needs signal scores. Hand-off to ML rather than a page here |
| F10 Kelly sizing | **Keep the fraction table, cut the ruin probability** | The fraction-first sizing with cost drag is useful. The ruin probability is a Gaussian model output that users will read as a real risk number. Cut it from the UI and from the response |
| F11 Execution | **Later** | Needs target weights and impact assumptions. Without measured spreads or order flow, the output is an assumption. Revisit with a broker feed |
| F12 Systemic | **Later** | Empty without peer books. Only useful to a user who holds a fund stack. Revisit with fund holdings data |
| F13 Strategies | **Later, on Monitor** | Needs user return histories. Valuable for a user who runs several strategies. Build after the Monitor exists |
| Trade tracker (P1) | **Later** | Needs trade input UI and cost basis. Trade history file exists but has no UI |
| Tax reporting | **Cut** | Jurisdiction-specific, not a research job |

**Page plan.** Four pages and the global shell, mirroring the Screener plan:

| Page | Carries | Features |
|---|---|---|
| Construct | Objectives, frontier, weights, risk contributions, constraint report, sizing table, covariance lens | F01, F10 table, F08 heatmap |
| Test | Honest performance card, equity and drawdown, walk-forward, PBO and DSR, attribution lens | F02, F03 |
| Stress | Crisis replay, scenario table, reverse stress, Monte Carlo, macro exposures, liquidity lens | F04, F05, F07 |
| Monitor (later) | Saved portfolios, drift alerts, strategy histories | F13, P21 |

---

## 6. Our own ideas for freedom and customisation

Every idea below reuses the existing contract: one `run` per feature, returning `charts` and `tables`, with `meta` holding the limits. The idea is about the view, not new maths.

1. **Any output, any view.** Each output in the manifest already declares a `render` hint (`line`, `bar`, `heatmap`, `network`, `histogram`, `band`, `waterfall`) and a `source` (`charts` or `tables`). Build one switcher per output that changes between table, chart and CSV without a new run. The data is the same, so the switcher is free.
2. **Saved views, not saved runs.** Store the input payload and the chosen views in the URL (nuqs), so any state can be shared as a link. The backend already stores results by job id (`RESULTS` directory), so a link can point to a reproducible run.
3. **Run diff.** Compare two results side by side: weights, risk contributions, drawdowns, DSR. The results are JSON on disk. This is the portfolio version of the Screener's "explain the difference" idea.
4. **Assumption sliders on cached runs.** Risk aversion, kelly fraction, cost bps, participation rate and crisis window are all scalar inputs with bounds in `BOUNDS` (`features/inputs.py`). Let the user drag them and rerun, with progress from the job store.
5. **Show the limit next to the number.** Every number carries its `meta` note (static sectors, no delisted names, assumed impact). A hatched cell means "not computable from our data", never zero. This is the Screener's U1 trust badge applied to portfolios.
6. **One-click proof.** The Test page's DSR uses the trial count the user enters. Let the Construct page count every objective and every rerun as a trial, and feed that count into the Test page automatically. That closes the gap the backend leaves open ("unreported searches cannot be reconstructed", `DONE.md` limitation 6).
7. **Weights from anywhere.** Accept a pasted ticker list with weights, a holdings CSV with market values (the same parsing as the legacy `PortfolioView.jsx`), or a saved universe. Convert market values to weights in one place.
8. **Export that matches the view.** CSV of the current table, LaTeX of the current table, JSON of the full result with its `meta`, and a PDF built from the same view (typst, section 7).

---

## 7. Open-source picks and licences

Rules from `docs/references/2026-11-screener-open-source.md` apply: no GPL, AGPL, SSPL or unlicensed code in anything we ship. Libraries are engines, charts stay ours. Existing code beats a new dependency.

| Library | Use | Licence | Verdict | Evidence |
|---|---|---|---|---|
| cvxpy | Convex solves (already used by `construction.py`) | Apache-2.0 | have | Used in code. Licence from memory, not re-fetched |
| arch | Stationary bootstrap (already used by `stress.py`) | NCSA | have | Used in code. Licence per existing PLAN section 5 |
| statsmodels | OLS and HAC in F05 and rolling regressions | BSD-3-Clause | have | Used in code. Licence from memory |
| skfolio | Golden-test oracle for optimisers and CPCV splitter; dev only | BSD-3-Clause | adopt (dev) | Repo page fetched 2026-11-09: "3-Clause BSD". Already in PLAN section 5 |
| Riskfolio-Lib | Golden-test oracle for risk parity, HRP and CVaR; dev only | BSD-3-Clause | adopt (dev) | Repo page fetched; licence line not extracted. BSD-3 confirmed by conda-forge and PyPI listings in search results |
| QuantStats | Tearsheet metric list as a check, or a copy of metric definitions | Apache-2.0 | ideas only | Repo page fetched: "Apache-2.0 license". We already compute the metrics, so adopt nothing |
| PyPortfolioOpt | Second oracle for Black-Litterman | MIT (from memory) | ideas only | Docs fetched; licence line not on the page. **Unverified** on this date |
| empyrical-reloaded and alphalens-reloaded | Test oracles for performance metrics | Apache-2.0 / BSD (per existing references) | adopt (dev) | Existing reference doc, not re-fetched today |
| Typst (typst-py) | PDF report from the view | Apache-2.0 | adopt | Already in PLAN section 5 and the Screener open-source reference |
| XlsxWriter | Excel export | BSD-2-Clause | adopt | Already in the Screener open-source reference |
| Ghostfolio, Portfolio Performance | Tracker ideas | AGPL-3.0 and GPL-3.0 (from memory, not fetched) | ideas only | Copyleft. Ideas only, never code |

Nothing here is a runtime dependency the backend lacks, except typst-py and XlsxWriter for export. Both are already on the list.

---

## 8. Build checklist

Tags: **E** easy (one file or one component, existing data), **M** medium (new endpoint or page section, some new maths or tests), **H** hard (new data path, new engine, or multi-page UI). Tick items in order. Each stage ends with a golden or smoke check on the real endpoint.

**Stage A: Clean the backend (before any UI)**

- [ ] A1 (E) Make the F04 verdict thresholds request inputs, default 20% and 10%, and show them in `meta`.
- [ ] A2 (E) Remove the Kelly ruin probability from `feature_10.py` output and from `ruin_probability` tables. Keep the fraction table.
- [ ] A3 (E) Confirm the Amihud definition with the owner. Either switch to close-to-close, or rename the output to `open_to_close_amihud` everywhere.
- [ ] A4 (M) Confirm with the codebase graph and an import check, then delete the unused helpers listed in section 2. Do not delete without the check (`AGENTS.md` deletion rule).
- [ ] A5 (E) Add the study-level `meta` warning for survivorship on every backtest result (already in `bias_audit`; surface it in `meta` too).

**Stage B: Workspace shell**

- [ ] B1 (M) Add the `/portfolio` route to the manifest-driven workspace. Forms come from `GET /labs/portfolio/v2/features`, not hand-written.
- [ ] B2 (M) Build the input panel: universe (typed tickers with exact-match validation, or a saved universe), weights, and objective, with defaults from the manifest.
- [ ] B3 (M) Build the output switcher per output (table, chart, CSV), reading `render` and `source` from the manifest.
- [ ] B4 (E) Show the `meta` limits strip on every page, with hatched cells for unknown values.
- [ ] B5 (M) Symbol search: replace the substring match in `GET /symbols` with prefix and exact ranking, reusing the Screener's search index decision.

**Stage C: Construct page**

- [ ] C1 (M) Objective selector showing six default objectives, with advanced objectives behind a toggle (F01 section 5).
- [ ] C2 (M) Frontier chart and weights comparison across objectives (F01 outputs).
- [ ] C3 (M) Constraint report: binding constraints, with the value and margin (`constraint_report`).
- [ ] C4 (E) Sizing lens: Kelly fraction table from F10 with the cost drag, without the ruin column.
- [ ] C5 (E) Covariance diagnostics lens: condition number and out-of-sample variance per estimator (F01 `covariance_diagnostics`).
- [ ] C6 (M) Friendly weights input: paste tickers and weights, or upload a holdings CSV with market values.

**Stage D: Test page**

- [ ] D1 (M) Honest performance card: DSR, PBO, PSR and Sharpe, colour-coded by the thresholds the owner sets. Default thresholds from the literature are stated in the card.
- [ ] D2 (M) Equity curve, drawdown and monthly heatmap (F02 charts).
- [ ] D3 (E) Walk-forward table with the in-sample to out-of-sample ratio.
- [ ] D4 (M) Trial counter: count every objective and rerun, and pass the count to `parameter_trials` (idea 6).
- [ ] D5 (M) Attribution lens: factor attribution always, Brinson when constituent weights exist, with the skill-versus-luck null.

**Stage E: Stress page**

- [ ] E1 (M) Crisis replay chart with the ten windows (F04 `historical_crisis_paths`), with unavailable windows shown as unavailable.
- [ ] E2 (M) Scenario table and reverse-stress card, with the plausibility percentile and asset shocks.
- [ ] E3 (E) Monte Carlo fan chart from `monte_carlo`, with horizon and block length as inputs.
- [ ] E4 (M) Macro exposure lens (F05): target versus observed beta, alerts, and the market-implied warning.
- [ ] E5 (M) Liquidity lens (F07): days-to-liquidate table, with non-USD symbols listed as refused.

**Stage F: Freedom and export**

- [ ] F1 (M) Shareable run link with the input payload and view state in the URL.
- [ ] F2 (M) Run diff for two results (weights, risk contributions, drawdowns, DSR).
- [ ] F3 (M) Assumption sliders that rerun through the job store with progress.
- [ ] F4 (H) PDF one-page report from the current view, with typst.
- [ ] F5 (E) CSV, LaTeX and JSON export from the current view (routes exist; wire the buttons).

**Stage G: Later**

- [ ] G1 (H) F06 regime lens, after run-time check.
- [ ] G2 (H) F13 multi-strategy on Monitor, with user return uploads.
- [ ] G3 (H) F09 signal decay hand-off to ML.
- [ ] G4 (H) F11 execution, with broker feed for measured spreads.
- [ ] G5 (H) F12 systemic, with fund holdings data.
- [ ] G6 (H) P1 holdings tracker with trade input.

**Tests.** For new logic in the UI (switcher, diff, sliders), one Vitest or Playwright smoke check per page. The backend keeps its golden tests. No new test framework.

---

## 9. Sources

Fetched or searched on 2026-11-09 with TinyFish.

**Paid products**
- Portfolio Visualizer pricing, fetched [official]: https://www.portfoliovisualizer.com/pricing (Basic $30 per month, Pro $55 per month, with feature list)
- Portfolio Visualizer tools, search [third party]: https://www.portfoliovisualizer.com/analysis
- Sharesight pricing, fetched [official]: https://www.sharesight.com/us/pricing/ (Free; Starter $7; Standard $18; Premium $23.25 USD per month billed annually)
- Morningstar Portfolio tools, fetched [official]: https://www.morningstar.com/mm/investor/portfolio-management-tools (X-Ray; yearly $249 per search snippet, not confirmed on the fetched page)
- Bloomberg PORT, fetched [official]: https://professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/ (no public price)

**Open-source**
- skfolio, fetched: https://github.com/skfolio/skfolio (BSD-3-Clause)
- Riskfolio-Lib, fetched: https://github.com/dcajasn/Riskfolio-Lib (licence line not extracted; BSD-3 from search results at https://anaconda.org/conda-forge/riskfolio-lib)
- QuantStats, fetched: https://github.com/ranaroussi/quantstats (Apache-2.0)
- PyPortfolioOpt docs, fetched: https://pyportfolioopt.readthedocs.io/ (licence **unverified** on the page)

**Internal**
- `backend/app/services/portfolio_v2/README.md`, `DONE.md`, `docs/portfolio features.md` (design history, not current spec)
- `backend/app/services/portfolio_v2/registry.py`, `features/inputs.py`, `features/feature_01.py` to `feature_13.py`, `core/*.py` as cited above
- `backend/app/api/portfolio_v2.py`, `backend/main.py` (mount at `/api`)
- `backend/app/routers/studio.py` (legacy `/portfolio/optimize` and `/portfolio/versions`)
- `frontend/src/components/studio/PortfolioView.jsx` (legacy, not v2)
- `docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md`, `docs/references/2026-11-screener-open-source.md`, `docs/plans/PLAN.md`, `docs/plans/CHECKLIST.md`, `docs/architecture/CROSS_MODULE_MERGE_MAP.md` section 8

**Unverified, stated once.** Enterprise prices (Bloomberg PORT, Aladdin, Axioma, StatPro, Geneva, FactSet). Morningstar X-Ray yearly price. Portfolio Visualizer commercial tier. PyPortfolioOpt and cvxpy licences. The `use-tinyfish` pass fetched a subset of the pages above, not all of them. Competitor claims not listed here are not used.
