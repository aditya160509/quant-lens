# Volatility V2 product review: what to keep, merge, cut and add

Date: 2026-11-06. This follows the method of `docs/SCREENER_V2_PRODUCT_REVIEW.md`. It reviews Volatility V2 as it stands in the code after the backend follow-up (`backend/app/services/volatility_v2/DONE.md`, updated 2026-10-08), and plans the product that comes after the ML cinema kit (`docs/ML_CINEMA_PLAN.md`).

**Inputs read**
- `docs/reviews/VOLATILITY_V2_REVIEW.md` (2026-09-29, with a 2026-10-08 follow-up note). Its B1 (Run does nothing) and several B2/B3 items are now stale; see §2.
- `docs/reviews/SELL_10_PORTFOLIO_VOL.md`, `docs/reviews/PLATFORM_CODE_10_BY_10_COMPLETE_SPEC.md`, `docs/ML_CINEMA_PLAN.md`
- Code: `backend/app/services/volatility_v2/` (registry, `core/contracts.py`, `core/data_loader.py`, `core/analytics.py`, `core/common.py`, `features/feature_01.py` to `feature_09.py`), `backend/app/api/volatility_v2.py`, `frontend/src/components/volatility-v2/` (`api.js`, `customPagePrimitives.jsx`, `registry.js`), `frontend/src/app/labs/volatility-v2/`
- Measured data: parquet headers, row counts and date ranges under `backend/data/` and `factors/data/`
- Live manifest: `all_contracts()` run from `backend/`
- Tests: the three `backend/tests/test_volatility_v2_*.py` files, run in this pass (see §3)
- Web search and fetch on competitors, prices and method references (sources in §14)

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

Scores are 1–5 and reflect reviewer judgment, based on the code, the measured data and the cited sources. The criteria are those used for the screener and factors reviews: Demand, Evidence, Differentiation, Decision value, Recurring value and Build cost (5 = cheap).

**Keep rule:** a feature keeps its own page only if it can reach 5 on Demand, Evidence, Differentiation, Decision value and Recurring value after upgrades. A feature that does not reach that bar keeps its page if the brief requires it, but its priority is lowered and it is sold as a lens.

**Module rule (from the brief):** Volatility stays a module with its own pages. Features merge only where they duplicate another feature, inside Vol or across Factors, Portfolio and ML. A merge means one shared engine behind two pages.

**Build order formula:** (Demand × Differentiation × Decision value) ÷ Build cost.

---

## 2. Verdict

**The volatility math is the strongest part of the stack, and the backend now refuses to fake results.** The silent SPY substitution is gone from the loader path; `parse_weights` now parses JSON strings (`backend/app/services/volatility_v2/core/analytics.py:339-349`); no `fillna(0)` remains in the module; the synthetic VIX (`yz × 115`) is gone; and the `dcc_proxy` alias is gone. The DM tournament is a full pairwise table with multiple-comparison flags (DONE.md). The old B1 ("Run does nothing") is fixed: `frontend/src/components/volatility-v2/api.js` fetches the manifest and runs jobs, and the workbench calls it when no `onRun` is passed (`customPagePrimitives.jsx:1316-1318`).

**The frontend still shows some things that are not real.**
- The landing hero prints fixed values "V01 · Yang-Zhang 18.4%", "V04 · …" and "V06 · Spillover 72" (`frontend/src/app/labs/volatility-v2/page.js:456-458`). They are literals, not a fetch.
- The `Spark` component now returns null (good), but the feature-01 page still declares cross-type fallback keys: calendar falls back to `annualized_vol_panel` and `five_estimator_comparison`; ridge does the same (`frontend/src/app/labs/volatility-v2/feature-01/page.js:71-73`). Whether the renderer honours them was not traced in this pass.
- The feature-02 page requests `synthetic_vol_surface` (`feature-02/page.js:139`). The backend returns "No observed options surface" for that key (`features/feature_02.py:291`). The page should show that message, not a heatmap.

**Per-page verdicts (two lines each):**
- **Volatility page set:** keep six pages (Estimators, Forecast, Regime, Risk premium, Cross-asset, Budget) and three shared engines (regime, covariance, stress). Sell V03 HAR, V01 estimators and V06 connectedness first; they have the clearest evidence and no close retail equivalent in the sources checked.
- **What blocks selling it:** the hero literals come out, the cross-type fallbacks and the impossible surface request are removed, and the tests run green on the Python the team uses (§3). The 41-input budget form must shrink to something a person can use.

**The honest product position:** a volatility lab where every estimator names its data and says what it cannot do. It competes with free research tools on depth and with terminals on price. It does not claim a trading signal.

---

## 3. Data reality and build status

### 3.1 Measured data (this pass)

| Dataset | Measured coverage | Consequence |
|---|---|---|
| `backend/data/market_universe.parquet` | 4,158 tickers, 1996-03-18 to 2026-07-06, 10,779,173 rows, OHLCV | Yang-Zhang, Parkinson, Garman-Klass, Rogers-Satchell and close-to-close estimators run on OHLC for any ticker in the file |
| SPY, QQQ, GLD, USO, IWM in `market_universe.parquet` | 2,784 rows each, 2015-01-02 to 2026-01-28 | Index ETFs stop in January 2026 and start in 2015. Backtests on these names cannot use 1996 history, and their series end before the other data. |
| `factors/data/processed/category7_macro_regime.parquet` | `vixcls` 9,279 non-null rows, 1990-01-02 to 2026-09-22; `vix_close` 2,735 rows, 2000-01-08 to 2026-04-26; `vix3m` and `vix6m` 2,515 rows, 2016-05-16 to 2026-05-15 | Implied-volatility legs exist for the S&P-style VIX family. Term-structure legs begin in 2016. Non-US and single-stock implied vol are not in the file and need upload (`iv_upload_id`). |
| `backend/data/canonical/cross_asset_hourly.parquet` | 1,148,817 rows, 272 tickers (for example `000001.SS`, `0700.HK`, `1301.TW`, `005930.KS`, plus index series such as `FCHI`, `FTSE`, `GDAXI`), 2023-02-27 to 2026-05-22 | Hourly variation exists for a subset of international names and indices, from 2023 only. Tick-level Bandi-Russell is not supported. SPY has no hourly series here. |
| `backend/data/canonical/fx_daily.parquet` | 29 pairs, 2015-01-01 to 2026-02-22 | Currency conversion for the cross-asset and DCC paths ends in February 2026 |
| `backend/data/canonical/equity_daily.parquet` | 39,008 rows; canonical panels start in 2015 (DONE.md) | Cross-asset canonical panels are 2015+, not 1996 |

The DONE.md says "canonical equity, futures, crypto and FX panels begin in 2015". The measured figures agree for ETFs and canonical panels. The 1996 start applies only to `market_universe.parquet`.

### 3.2 Build status (checked)

- **Router and manifest:** mounted at `/api/labs/volatility/v2` (`backend/main.py:182-183`). `GET /features`, `GET /symbols`, `POST /feature/{id}/run`, `POST /feature/{id}/jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `POST /uploads` and `POST /export/{id}` are defined (`backend/app/api/volatility_v2.py`).
- **Manifest counts (live):** inputs per feature: V01 16, V02 20, V03 17, V04 14, V05 15, V06 21, V07 23, V08 36, V09 41. Outputs per feature: V01 16, V02 11, V03 10, V04 10, V05 11, V06 13, V07 21, V08 20, V09 16.
- **Duplicate output keys in the manifest:** feature 06 lists `connectedness_at_risk` twice. Fix in `features/` before the manifest drives the UI.
- **Stale output keys in the pages:** `vol_calendar`, `vol_ridge`, `volatility_cone` and `vol_signature` are requested by the feature-01 page. They do not appear in any feature's contract outputs (they appear in one backend file only). Remove the requests.
- **Tests (run in this pass with local `python3`, Python 3.9.6):** the three files hold 73 test functions. Result for the full targeted set: **86 passed, 2 failed**. The two failures are `test_api_errors_symbols_and_upload` and `test_exports_cancel_and_source_changes_during_estimation`, both with `TypeError: __init__() got an unexpected keyword argument 'app'`. That error comes from the TestClient and httpx versions in this environment, not from the estimators. The DONE.md reports 88 passing on Python 3.11 in a virtualenv under `/tmp`, which no longer exists. **The 3.11 result is unverified in this pass.**
- **Frontend:** `frontend/src/components/volatility-v2/__tests__/api.test.ts` exists. Not run in this pass.

### 3.3 Open frontend defects (checked)

| Defect | Where | Status |
|---|---|---|
| Hero literals (V01 18.4%, V04, V06 72) | `frontend/src/app/labs/volatility-v2/page.js:456-458` | Open |
| Cross-type fallback keys | `frontend/src/app/labs/volatility-v2/feature-01/page.js:71-73` | Open |
| Synthetic surface request | `feature-02/page.js:139` (`synthetic_vol_surface`) | Open; backend says "No observed options surface" |
| Sine sparkline `Spark` | `customPagePrimitives.jsx:706-708` | Fixed: returns null |
| `SurfaceGrid` renderer | `customPagePrimitives.jsx:1218-1220` | Dead for now: no feature produces the surface |
| Form contract in `registry.js` | `frontend/src/components/volatility-v2/registry.js` | Open; the manifest already carries inputs, so forms should render from `GET /features` |

---

## 4. Competitors and prices

Checked in this pass with TinyFish search and fetch. "Snippet" means the figure comes from a search result. "Unverified" means it could not be confirmed.

| Product | Price (checked Nov 2026) | What it does that matters here | Complaint or limit (source) |
|---|---|---|---|
| Bloomberg Terminal (PORT, VOL, MARS) | List about $31,980 per year for one seat; about $28,320 per seat with two or more (investopedia.com, fetched, 2026; bluegamma.io, Oct 2026, snippet). Module-level prices for PORT and MARS: **unverified**. | Institutional volatility, risk and factor analytics | Price. Investopedia calls it "prohibitively expensive" for many users (hudson-labs, snippet). |
| V-Lab (NYU Stern) | Public site with GARCH, GJR-GARCH and DCC volatility pages (vlab.stern.nyu.edu, fetched landing page; GARCH docs page in search results). **Unverified:** the price and whether the service is free are not stated on the pages checked. | Free volatility and correlation forecasts for many assets, including GARCH-DCC. Academic in use. | No portfolio, trading or budget tools (from the site description) |
| MSCI Barra | Enterprise licence. A third-party site says "can exceed $100,000 per year" (genesis-rm.com, snippet). **Unverified** from a vendor. | Factor risk models, stress and risk attribution | Price |
| Axioma (SimCorp) | **Unverified.** One Reddit comment quotes a rep at $35K–$50K for a bundled integration package (r/quant, snippet). Anecdote only. | Factor risk models, optimisation, multi-asset risk | Price |
| QuantConnect | Researcher seat $10 per user per month; Team from $24 per user per month (trendspider.com snippet; quantconnect.com pricing snippet). | Cloud backtests with fees and slippage | No volatility-budget or VRP product surface (unverified) |
| Riskfolio-Lib | Free, BSD-3-Clause; 1.9M PyPI downloads (github.com/dcajasn/Riskfolio-Lib; pepy.tech). | Optimisers, CVaR, HRP, Black-Litterman | Library |
| skfolio | Free, BSD-3-Clause (skfolio.org) | Portfolio models, risk measures | Library |
| arch (Python) | Free and open source (arch.readthedocs.io, MCS documentation, snippet) | GARCH family estimation, bootstraps, MCS | Library; the product layer is what we add |
| TradingView | Essential from about $12.95–$14.95 per month; Premium $59.95 per month (stockbrokers.com Aug 2026, snippet). Billing varies by source. | Charts and indicators, no volatility model suite | Not a volatility model product |
| Koyfin | Plus $39 per month; Premium $79 per month (koyfin.com, fetched). The sources checked do not show a volatility-model suite. | Market data and charts | No factor or volatility model suite in the plan text checked (unverified beyond the plan list) |

### 4.1 Demand evidence

- **Desks want a model they can defend.** Snippets from vol-desk and quant threads ask for GARCH variants and HAR comparisons with out-of-sample tests. This is not sized here, and it is not a fetched source. Treat demand as **unverified** beyond the existence of the free research tools above.
- **Free tools cover the basics.** V-Lab and arch give GARCH and DCC for free. A paid product has to sell the honesty layer, the regime and budget links, and the comparison tests, not the fitted model.

### 4.2 Positioning

Vol V01 (five estimators), V03 (HAR suite with a model confidence set) and V06 (connectedness) have no close retail equivalent in the sources checked. Bloomberg has the depth at institutional prices. V-Lab has the models, but no portfolio or budget layer. Riskfolio and skfolio are optimisers, not volatility forecasters. The product sits between V-Lab and Bloomberg on price, and wins on the link from forecast to risk budget.

---

## 5. Evidence per method

Grade: 5 = replicated and matches our data; 3 = supported with caveats; 1–2 = weak or a proxy in our data.

| Method (module feature) | Reference | Out-of-sample and replication | Data fit here | Grade |
|---|---|---|---|---|
| Realised-vol estimators: close-to-close, Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang (V01) | Parkinson (1980); Garman and Klass (1980); Rogers and Satchell (1991); Yang and Zhang (2000) | Standard. Efficiency and golden-formula tests in `backend/tests/test_volatility_v2_math.py` (DONE.md). Original papers **not fetched in this pass**. | OHLC for 4,158 names; open-to-close needs the session convention | 5 (estimators), citations unverified |
| Diebold–Mariano comparison of forecasts (V01, V03) | Diebold and Mariano (1995) | Standard test; the module uses a full pairwise table with multiple-comparison flags (DONE.md) | Loss series must be out-of-sample (DONE.md says expanding refit is used) | 4 |
| Model confidence set (V02, V03) | Hansen, Lunde and Nason (2011), Econometrica | The arch library implements the MCS (arch.readthedocs.io, snippet; Econometrica abstract, snippet) | Bootstrap MCS at the declared refit cadence (DONE.md) | 4 |
| GARCH family (V02) | Bollerslev (1986); GJR (1993); EGARCH (Nelson 1991) | arch MLE for five families and four innovation distributions (DONE.md). Original papers **not fetched in this pass**. | Daily returns from 1996 for most names | 4 |
| HAR realised-volatility forecasts (V03) | Corsi (2009) | HAR-type forecasts are widely used; the module's HAR-X uses observed IV minus the physical engine (DONE.md). Corsi paper **not fetched**. | Matured-label OLS with HAC | 4 (citation unverified) |
| Regime detection, Gaussian HMM and statistical jump model (V04) | Hamilton (1989); Bemporad et al. (2018) | Causal filtered HMM on holdout (DONE.md). Statistical jump model reference **not fetched**. | Requires a training window; uses the same engine as Factors F04 | 3 |
| Variance risk premium (V05) | Bollerslev, Tauchen and Zhou (2009), Review of Financial Studies | Predicts returns at horizons of about three to five months (SSRN and Federal Reserve summaries, snippets). Replication in later work reported in snippets. | Needs matched implied vol per asset; S&P-style VIX in file; per-asset IV by upload only | 4 |
| Connectedness (V06) | Diebold and Yilmaz (2009, 2012, 2014) | Generalised FEVD spillover index; used in many papers (metricgate, rdocumentation, Lastrapes 2021 snippets) | Daily OLS or fixed-lag EW VAR; hourly variation only for the 2023+ subset | 4 |
| Stress and VAR contagion (V08) | VAR impulse response; Mahalanobis distance; Clayton copula | DONE.md: refitted residual bootstrap bands at 90%; copula is rotated Clayton (conditional stress) | Macro inputs not zero-filled; scenarios are declared assumptions | 3 |
| Vol targeting and Kelly (V09) | Moreira and Muir (2017) on volatility-managed portfolios | Not fetched in this pass. Kelly sizing is the same as Portfolio F10 (see §9). | Forecast source is causal (DONE.md) | 3 (citation unverified) |
| Deflated Sharpe and PBO (shared with Validate) | Bailey and López de Prado (2014); Bailey et al. (2016) | DSR corrects for selection bias, backtest overfitting and non-normality (ssrn abstract, snippet); PBO defined as the probability of backtest overfitting (researchgate, snippet) | Not implemented in Vol; belongs to the shared Validate engine | 4 (as shared engine) |

**Implication for the page set:** lead with V01 (estimators and the comparison table), V03 (forecasts with a confidence set) and V06 (connectedness). Keep V05 VRP behind the implied-vol data check. Keep V08 and V09 as expert tools with their assumptions printed.

---

## 6. Scored feature table

Scores are 1–5 (judgment). Columns: Dem = Demand, Evid = Evidence, Diff = Differentiation, Dec = Decision value, Rec = Recurring, Cost = Build cost (5 = cheap).

| Feature | Dem | Evid | Diff | Dec | Rec | Cost | Call |
|---|---|---|---|---|---|---|---|
| V01 Multi-estimator daily volatility | 4 | 5 | 3 | 3 | 5 | 4 | **Keep**, Estimators page; lead page |
| V02 GARCH family suite (20 model combinations) | 3 | 4 | 3 | 3 | 3 | 3 | **Keep**, Forecast page; default to 4 models, the rest in research mode |
| V03 HAR forecasting suite | 4 | 4 | 4 | 4 | 3 | 3 | **Keep**, Forecast page; lead page |
| V04 Regime detection engine | 4 | 3 | 3 | 4 | 3 | 3 | **Merge with Factors F04** into one regime engine; Regime page remains |
| V05 Volatility risk premium monitor | 3 | 4 | 4 | 3 | 3 | 3 | **Keep**, Risk premium page, gated on matched implied vol |
| V06 Cross-asset connectedness | 3 | 4 | 4 | 3 | 2 | 3 | **Keep**, Cross-asset page; priority page, not a headline |
| V07 Multivariate and DCC | 3 | 3 | 2 | 3 | 2 | 3 | **Merge with Factors F08** into one covariance engine; Cross-asset page keeps the asset-level view |
| V08 Stress testing engine | 3 | 3 | 3 | 3 | 2 | 2 | **Merge with Factors F11 and Portfolio F04** into one stress engine; Risk page keeps the vol scenarios |
| V09 Volatility budget monitor | 4 | 3 | 3 | 4 | 4 | 3 | **Keep**, Budget page; Kelly sizing moves to the shared sizing engine with Portfolio F10 |

**Counts (Vol):** 6 keep with their own page (V01, V02, V03, V05, V06, V09); 3 merge into shared engines with Factors or Portfolio (V04, V07, V08); 0 cut outright. Kelly sizing inside V09 merges with Portfolio F10 (a sub-feature merge).

### 6.1 Output-level calls

| Output | Call | Reason |
|---|---|---|
| V01 `five_estimator_comparison`, `annualized_vol_panel` | Keep | Core |
| V01 `estimator_efficiency`, `diebold_mariano_tournament` | Keep | Honest comparison |
| V01 `opening_gap_fragility` and `opening_gap_fragility_detector` | Merge into one output | Duplicate in the manifest |
| V01 `vol_adjusted_momentum_panel` and `vol_adjusted_momentum` | Merge into one output | Duplicate in the manifest |
| V01 `multi_window_estimator_panel` and `multi_window_estimator_table` | Keep the table; panel is the same data | Remove one |
| V01 `observed_hourly_variation` | Keep, with the 2023+ coverage note | Hourly data is limited |
| V01 `range_correlation_matrix`, `estimator_disagreement_band`, `estimator_agreement_index` | Keep | — |
| V02 `model_comparison_scoreboard`, `news_impact_curve`, `garch_term_structure` | Keep | — |
| V02 `pit_test` and `pit_diagnostics` | Merge into one output | Duplicate key family |
| V02 `diebold_mariano_pairwise_table` | Keep | DONE.md says full pairwise table |
| V02 `nyblom_stability`, `long_memory_parameter_series` | Keep with the asymptotic caveat | DONE.md |
| V02 `var_backtests`, `conditional_var_series` | Keep | — |
| V02 `aparch_delta_benchmark` | Cut from the first screen | Niche; keep in research mode |
| V03 `directional_dm_tournament`, `model_confidence_set` | Keep | — |
| V03 `causal_forecast_combinations` | Keep | Matured losses only (DONE.md) |
| V03 `forecast_confidence_bands`, `multi_horizon_forecast_chart` | Keep | — |
| V03 `har_parameter_table`, `forecast_accuracy_table`, `walk_forward_accuracy` | Keep | — |
| V03 `acsv_predictive_contribution` | Keep, only with a declared universe | DONE.md |
| V04 `probabilistic_regime_timeline`, `current_regime_dashboard` | Keep (in the shared engine) | — |
| V04 `transition_heatmap` and `regime_transition_heatmap` | Merge into one output | Duplicate |
| V04 `global_vol_regime_sync_index` | Keep | — |
| V04 `statistical_jump_state_timeline`, `regime_duration_survival`, `hmm_bic_k_selection` | Keep in research mode | — |
| V04 `transition_alert_log` | Keep, in-app only | — |
| V05 `vrp_time_series`, `vrp_zscore_panel`, `vrp_term_structure` | Keep, gated | Needs matched IV |
| V05 `vrp_component_attribution`, `btz_expanding_forecasts` | Keep | DONE.md |
| V05 `return_predictability_regression`, `vrp_mean_reversion_speed` | Keep | — |
| V05 `cross_asset_vrp_comparison`, `regime_conditional_btz` | Keep, gated | Needs matched IV per asset |
| V05 `vrp_zscore_lookback_comparison` | Cut from the first screen | Too many knobs; keep in research mode |
| V05 `data_gaps` | Keep | Honesty output |
| V06 `connectedness_index`, `net_spillover_ranking`, `pairwise_fevd_heatmap` | Keep | — |
| V06 `frequency_decomposed_connectedness` | Keep, research mode | — |
| V06 `connectedness_at_risk` (listed twice in the manifest) | Keep once | Duplicate key |
| V06 `spillover_network_graph`, `network_history` | Keep as an exhibit | — |
| V06 `rolling_to_from_decomposition` | Keep | — |
| V06 `var_impulse_response`, `var_impulse_response_bands` | Keep | — |
| V06 `connectedness_regime_alert` | Keep, in-app only | — |
| V06 `estimation_failures` | Keep as a diagnostic | — |
| V07 `dcc_time_series`, `dcc_midas_time_series` | Keep | The real DCC path (DONE.md) |
| V07 `correlation_heatmap`, `correlation_matrices`, `eigenvalue_decomposition` | Keep | — |
| V07 `normal_vs_crisis_correlation`, `probability_weighted_crisis_correlation` | Keep, with crisis definition printed | — |
| V07 `dcc_midas_long_run_correlation` | Keep, research mode | — |
| V07 `minimum_torsion_*` (3 outputs) | Cut from the first screen | Factor labels are indices, not loadings (old review); keep in research mode |
| V07 `fisher_z_crisis_amplification`, `condition_number_history` | Keep, research mode | — |
| V07 `minimum_variance_portfolio`, `portfolio_comparison`, `diversification_ratio` | Keep | — |
| V07 `dcc_parameters`, `dcc_midas_parameters` | Keep as a footnote table | — |
| V08 `vol_shock_bar_chart`, `portfolio_pnl_attribution_waterfall` | Keep | — |
| V08 `historical_stress_path`, `historical_analog_comparison` | Keep | Actual replay (DONE.md) |
| V08 `contagion_impulse_response`, `contagion_impulse_response_bands`, `contagion_irf_bootstrap_bands` | Merge into one output | Three keys for one exhibit |
| V08 `stress_distribution`, `stress_var_cvar`, `risk_capital_change` | Keep | — |
| V08 `analog_volatility_paths`, `analog_volatility_bands`, `historical_analog_glasso` | Keep, research mode for GLASSO | — |
| V08 `macro_precision_matrix` | Keep, research mode | Macro scenarios are declared assumptions |
| V08 `reverse_stress_frontier`, `reverse_stress_scenario`, `reverse_stress_copula` | Keep one reverse-stress exhibit with the copula option | Merge with F11 engine |
| V08 `adversarial_scenario` | Keep, research mode | — |
| V08 `multi_scenario_comparison`, `scenario_correlation` | Keep | — |
| V09 `portfolio_vol_dashboard`, `vol_to_target_gap_gauge` | Keep | — |
| V09 `scaling_factor_history`, `regime_conditional_target_evolution` | Keep | — |
| V09 `kelly_vs_fixed_target`, `kelly_vol_target` | Merge with Portfolio F10 Kelly output | Shared sizing engine |
| V09 `historical_vol_targeting_backtest`, `historical_backtest_performance`, `backtest_cost_comparison` | Merge into one backtest exhibit | Duplicates |
| V09 `transaction_cost_comparison`, `two_step_rebalancing_detail`, `rebalancing_recommendation` | Keep | — |
| V09 `vol_budget_breach_log` | Keep, in-app only | — |
| V09 `regime_probability_input` | Review, then probably cut | Name suggests an input echo; confirm in `feature_09.py` before removing |
| Frontend `synthetic_vol_surface` (feature-02 page) | Cut | Backend says no observed surface exists |
| Frontend `vol_calendar`, `vol_ridge`, `volatility_cone`, `vol_signature` | Cut | Not produced by any contract |

---

## 7. Final page cut and what makes each page a 5

Volatility ships six pages and three shared engines.

### 7.1 Estimators (V01)

| Axis | Upgrade to 5 |
|---|---|
| Demand | One chart of five estimators per ticker, with the efficiency table |
| Evidence | Every estimator links to its formula and its golden test; efficiency disclosed |
| Differentiation | Opening-gap routing named, not hidden; range correlation with the correct normalisation |
| Decision value | Which estimator to use for this name and window, with the reason |
| Recurring | Daily panel updates on the same window |

### 7.2 Forecast (V02, V03)

| Axis | Upgrade to 5 |
|---|---|
| Demand | Forecast band and a model scoreboard in one view |
| Evidence | Out-of-sample only; MCS membership shown; DM pairs with p-values |
| Differentiation | Eight HAR variants and five GARCH families with a confidence set, not one model |
| Decision value | The model in the set and its band at each horizon |
| Recurring | Walk-forward accuracy updated as data arrives |

### 7.3 Regime (V04 shared engine)

| Axis | Upgrade to 5 |
|---|---|
| Demand | One regime pill and a timeline |
| Evidence | Causal filtered probabilities only; training window stated |
| Differentiation | Three methods side by side; synchronisation index across assets |
| Decision value | Regime change alerts with timestamps |
| Recurring | Alert log in-app |

### 7.4 Risk premium (V05, gated)

| Axis | Upgrade to 5 |
|---|---|
| Demand | VRP z-score with the BTZ forecast beside it |
| Evidence | Shows whether matched implied vol exists; otherwise the page says "physical only" and disables VRP |
| Differentiation | BTZ with Hodrick standard errors; regime-conditional BTZ |
| Decision value | Whether the premium is rich or cheap, with the return predictability regression |
| Recurring | Daily z-score on the watchlist |

### 7.5 Cross-asset (V06, V07 shared engine)

| Axis | Upgrade to 5 |
|---|---|
| Demand | One spillover index and the net ranking |
| Evidence | Generalised FEVD with a stated lag order; failures listed |
| Differentiation | Network graph and frequency split (where hourly data exists) |
| Decision value | Which asset transmits and which absorbs |
| Recurring | Rolling connectedness, updated daily (the old ~300-point step is removed per DONE.md) |

### 7.6 Budget (V09, Kelly shared)

| Axis | Upgrade to 5 |
|---|---|
| Demand | "Scale my book to a 10% vol target" in one control, with the gross cap |
| Evidence | Causal forecast; cost netted; the baseline uses the same impact assumption |
| Differentiation | Regime-conditional target and the BTZ-based Kelly return |
| Decision value | The scaling factor and the rebalance amount |
| Recurring | Daily scaling recommendation and breach log |

---

## 8. New A++ features

These use only the data we have.

1. **Estimator choice with the reason.** For each ticker and window, the estimator that is most efficient for that name's data (OHLC completeness, overnight gap share), with the reason printed. Uses the existing efficiency table and opening-gap routing. Cost low.
2. **Forecast with its confidence set.** Every forecast shows the MCS members, not one "best" model. Already computed; needs one exhibit.
3. **Data gap ledger on every page.** A list of what the run could not compute and why (missing IV, hourly coverage, FX end date). Reuses `data_gaps` (V05) and `estimation_failures` (V06) and extends them to every module.
4. **Budget to Validate hand-off.** Send a scaled-book backtest to the shared Validate engine with the trial count. Same hand-off as Factors F07.
5. **Pre-registered vol target.** Save the target, gross cap and forecast source before a run, then score the realised outcome. Uses the existing breach log; the saved record is the new part.

---

## 9. Shared with other modules

| Shared piece | Vol feature | Also used by | Note |
|---|---|---|---|
| Regime HMM and statistical jump estimators | V04 | Factors F04 | One core module; two pages |
| Covariance engine (sample, EWMA, Ledoit-Wolf, DCC) | V07 | Factors F08, Portfolio F01 | One engine |
| Stress and reverse stress (VAR IRF, Mahalanobis, copula) | V08 | Factors F11, Portfolio F04 | One engine |
| Kelly and sizing | V09 | Portfolio F10 | Portfolio owns the engine |
| Volatility estimators (CC, Parkinson, GK, RS, YZ) | V01 | Screener S7 quick-look (optional) | `volatility_v2/core/estimators.py` should move to a shared module |
| Data loader (OHLC, macro, FX, hourly) | all | all | Move to a shared loader (platform spec) |
| Validate engine (DSR, PBO) | V09 (backtests) | ML, Factors F07, Screener S5 | Owned by ML |
| Cinema kit | all | all | `src/charts/v2/` |

**Duplicate with the legacy module:** `backend/app/services/volatility_intelligence.py` still serves older Vol endpoints in `backend/app/api/labs.py` (per the old review). Retire it or link it; do not leave two volatility APIs.

---

## 10. Inputs pruned

Input counts from the live manifest: V09 41, V08 36, V07 23, V06 21, V02 20, V03 17, V01 16, V05 15, V04 14.

**Remove the aliases from the first screen:**
- `asset` and `assets` both appear in most features. Keep `assets`; remove `asset` from the UI (keep as an API alias).

**Remove from the first screen (keep in the API, behind "research mode"):**
- `min_train`, `refit_interval`, `regime_min_train`, `regime_refit_interval`, `btz_min_train`, `hmm_restarts`, `simulations`, `bootstrap_reps`, `irf_bootstrap_reps`, `mc_paths`, `seed`, `midas_k`, `var_max_lag` (keep `var_lag_order`), `clayton_tail_pct`, `sjm_jump_penalty`, `alert_horizon`.
- V09: `breach_threshold`, `rebalance_threshold`, `adv_window`, `volume_units`, `market_impact_gamma`, `explicit_bps`, `kelly_return_horizon`, `forecast_halflife`, `garch_distribution`, `correlation_window`, `regime_targets` (the string form is not parsed; the dict is the backend contract).
- V08: `var_decay`, `irf_window`, `irf_horizons`, `analog_k`, `analog_horizon`, `adversarial_c`, `source_asset`, `macro_scenario` (keep one preset control).
- V07: `crisis_percentile_window`, `crisis_percentile_min_history`, `regime_asset`, `base_currency`, `quote_currencies` (keep only when a currency is needed).

**Keep as first-class controls:** `assets` (universe picker), `as_of_date`, `lookback_days`, `annualization` (252 or 365 with the note), `estimator` (V03), `horizons` (V03), `models` (V02, default 4), `vol_target` and `gross_exposure_cap` (V09), `scenario` (V08), `iv_upload_id` (upload).

**Remove the frontend-only display controls** the code already drops (`compute_mode`, `active_estimators`, `cross_asset_panel`, `network_layout`, `cross_asset_mode`; see `frontend/src/components/volatility-v2/api.js`). Either wire them or delete them.

---

## 11. UI on the ML cinema kit

- **Page shell:** takeaway title per page (for example "Yang-Zhang is 22% more efficient than close-to-close on this window"); subtitle "measure, unit, universe, window"; KPI strip; data-gap banner under the verdict.
- **Data gap banner:** shows what the run could not compute (no matched IV, hourly data missing, FX ends February 2026, ETF history ends January 2026).
- **Exhibits:** borderless. `TimeSeries v2` for forecasts with a band and regime spans (end labels, event annotations); `Dumbbell` for model against benchmark; `Heat table` for the DM matrix and the connectedness pairs; `Calendar heatmap` for VaR breaches; `Distribution` for Monte Carlo bands (once built).
- **Unknown values:** hatched cell. The IV surface is removed; the page says "no observed options surface".
- **Remove:** the landing hero literals, the cross-type fallback keys, the synthetic surface request, the form contract in `registry.js`, and the dead `SurfaceGrid`.
- **Phone:** the KPI strip becomes 2 columns; exhibits stack.

---

## 12. Pricing

Prices are proposals, anchored to the checked figures in §4. They are not market facts.

| Tier | Proposed price | Includes | Anchor |
|---|---|---|---|
| Free | $0 | Estimators and the forecast page on the default universe; end-of-day data; one saved panel; the data-gap banner | V-Lab and arch are free for models (unverified for V-Lab's price) |
| Pro | $29 per month | Estimators, forecast, regime, watchlist alerts (in-app) | Below Koyfin Plus $39 and TradingView Premium $59.95 |
| Quant | $79 per month | Risk premium, cross-asset, budget, Validate hand-off, PDF report, uploads | Matches Koyfin Premium $79; below QuantConnect Team with research seats |
| Desk and institutional | quote | Seats, shared panels, point-in-time data add-on | Bloomberg about $28,320 per seat is the ceiling |

**Licence before charging:** the module shows derived analytics on OHLC, not raw prices, so the display licence risk is lower than for the screener. Confirm the terms of the Yahoo-sourced prices (if any) before charging; **the source of the price file is not recorded in the repo and was not verified in this pass.**

---

## 13. Build order

| Step | Work | Backend | Frontend | Size |
|---|---|---|---|---|
| 1 | Fix the test environment: pin Starlette and httpx so the two API tests run; confirm on Python 3.11 | test env | — | S |
| 2 | Remove the hero literals, the cross-type fallback keys, the synthetic-surface request and the stale output keys | none | feature-01 and feature-02 pages, `page.js` | S |
| 3 | Fix duplicate manifest keys (feature 06, and the duplicates listed in §6.1) | `features/` | none | S |
| 4 | Render forms from `GET /features`; remove the display-only controls; prune the first screen per §10 | none | forms | M |
| 5 | Cinema-kit page shell; Estimators and Forecast pages first | none | pages | M |
| 6 | Shared regime engine with Factors F04 | merge modules | Regime page | M |
| 7 | Shared covariance engine with Factors F08; Cross-asset page | merge modules | Cross-asset page | M |
| 8 | Budget page with the shared Kelly engine; Validate hand-off | Portfolio F10 wiring | Budget page | M |
| 9 | Data-gap ledger on every page; pre-registered vol target | small | banner, save | S |
| 10 | Move loaders and estimators to shared modules; retire or link `volatility_intelligence.py` | refactor | none | L |

**Size:** about 5–7 focused sessions on top of the ML kit, most of it composition.

---

## 14. Sources and what could not be verified

**Competitors and prices (fetched or checked by search in this pass)**
- Bloomberg Terminal: https://www.investopedia.com/terms/b/bloomberg_terminal.asp (fetched, 2026: "just under $32,000", $28,320 multi-seat); https://www.bluegamma.io/post/bloomberg-terminal-pricing (snippet, Oct 2026: $31,980 and $28,320); https://www.hudson-labs.com/blog/free-and-low-cost-alternatives-to-bloomberg (snippet)
- V-Lab: https://vlab.stern.nyu.edu/ (fetched landing page); https://vlab.stern.nyu.edu/docs/volatility/GARCH (snippet: GARCH-DCC documentation)
- MSCI Barra: https://genesis-rm.com/blog/affordable-barra-risk-metrics-alternatives (snippet, third party); https://www.msci.com/data-and-analytics/factor-investing/equity-factor-models (snippet)
- Axioma: https://www.simcorp.com/solutions/axioma-solutions/axioma-factor-risk-models (snippet); anecdote: https://www.reddit.com/r/quant/comments/vyl0qz/riskfactor_models/ (snippet, unverified figure)
- QuantConnect: https://www.quantconnect.com/pricing/ (snippet); https://trendspider.com/learning-center/quantconnect/ (snippet)
- Riskfolio-Lib: https://github.com/dcajasn/Riskfolio-Lib (snippet, BSD-3); https://pepy.tech/projects/riskfolio-lib (snippet, 1.9M downloads)
- skfolio: https://skfolio.org/ (snippet, BSD-3)
- arch MCS: https://arch.readthedocs.io/en/stable/multiple-comparison/generated/arch.bootstrap.MCS.html (snippet)
- Koyfin plans: https://www.koyfin.com/pricing/plans-comparison/ (fetched)
- TradingView: https://www.stockbrokers.com/review/tools/tradingview (snippet, Aug 2026); https://www.tradingview.com/pricing/ (snippet)

**Method evidence**
- Bollerslev, Tauchen and Zhou (2009), Review of Financial Studies: https://ideas.repec.org/p/aah/create/2008-48.html (snippet); predictive horizon: https://papers.ssrn.com/sol3/Delivery.cfm/198ec4a5-431d-43a8-87b7-93243687e110-MECA.pdf?abstractid=6595821&mirid=1 (snippet: three to five months)
- Hansen, Lunde and Nason (2011): https://onlinelibrary.wiley.com/doi/abs/10.3982/ECTA5771 (snippet)
- Diebold and Yilmaz connectedness: https://metricgate.com/docs/diebold-yilmaz-connectedness-spillover/ (snippet); https://www.sciencedirect.com/science/article/abs/pii/S0264999319306091 (snippet, Lastrapes 2021)
- Deflated Sharpe: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 (snippet); PBO: https://www.researchgate.net/publication/318600389_The_probability_of_backtest_overfitting (snippet)

**Internal**
- `backend/app/services/volatility_v2/DONE.md` (2026-10-08)
- `backend/app/api/volatility_v2.py`, `backend/app/services/volatility_v2/core/contracts.py`, `backend/app/services/volatility_v2/core/analytics.py`, `backend/app/services/volatility_v2/features/feature_02.py`
- `frontend/src/components/volatility-v2/api.js`, `frontend/src/components/volatility-v2/customPagePrimitives.jsx`, `frontend/src/app/labs/volatility-v2/page.js`, `frontend/src/app/labs/volatility-v2/feature-01/page.js`, `frontend/src/app/labs/volatility-v2/feature-02/page.js`
- `docs/reviews/VOLATILITY_V2_REVIEW.md`, `docs/reviews/SELL_10_PORTFOLIO_VOL.md`

**Unverified (not confirmed in this pass)**
- Bloomberg PORT and MARS module prices (only the terminal price is confirmed)
- V-Lab price and whether it is free
- MSCI Barra and Axioma prices (anecdote and third-party text only)
- TradingView exact monthly and annual prices (sources disagree by billing period)
- Original papers for Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang, Bollerslev (1986), GJR, Corsi (2009), Hamilton (1989), Bemporad et al. (2018) and Moreira and Muir (2017). Their claims in §5 are from the module's DONE.md and general knowledge, not fetched.
- Replication of the VRP result beyond the snippets
- Demand for volatility tools: no fetched user survey or thread sized this market
- The source and licence of the price files under `backend/data/` (not recorded in the repo)
- The 88-passing result on Python 3.11 in DONE.md (`backend/venv` is Python 3.11 but has no pytest, so this was not rerun)
- The two frontend-side claims: whether the renderer honours cross-type fallback keys, and the `api.test.ts` result (not run)
- Line-level re-reading of every "Fixed" claim in DONE.md. Claims in §2 were checked by grep and by reading the cited functions; the rest rely on DONE.md.
