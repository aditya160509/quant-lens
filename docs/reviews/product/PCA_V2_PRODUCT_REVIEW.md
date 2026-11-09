# PCA product review: statistical risk and residual trading, redone against the feature rule

Written 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. Backend claims come from function bodies in `backend/app/services/pca_v2/` read on this date. Competitor and library facts come from TinyFish fetches on this date, listed in section 11. Nothing was run: no servers, no tests, no Python. Statements marked **unverified** were not checked against running code or a live source.

## Contents
1. Verdict
2. What is there today, and what is not
3. Data we hold, and its limits
4. Competitors in one page
5. Paid-feature parity table
6. Real versus hollow in the code
7. Decisions: keep, build, later, cut
8. Our own ideas for freedom and customisation
9. Open-source picks and licences
10. Build checklist (E, M, H)
11. Evidence, unverified items and sources

---

## 1. Verdict

PCA is the one module in the platform with a real statistical-risk engine. Paid tools sell PCA-based risk models (Axioma statistical models) and fundamental factor models (MSCI Barra, Bloomberg PORT). None of the paid tools we fetched sells the residual stat-arb trade list with its own out-of-sample evidence, a regime monitor on the eigenstructure, or contagion alerts on residual correlation. Those three are where we should lead.

The backend is broad: 11 feature modules, about 6,250 lines across features and core. But a careful read of function bodies shows that a large share of the outputs are labelled more strongly than the maths supports. Five problems matter most:

1. **The noise threshold is applied to the wrong matrix.** The default estimator is Ledoit-Wolf, which shrinks the spectrum, but the Marchenko-Pastur edge is then computed on that shrunk spectrum (`core/pca_math.py`, `core/model.py`).
2. **The contagion "under-specified" flag fires almost always.** Its threshold, lambda1 > 1.3 on a residual correlation matrix from 63 observations, sits below the asymptotic noise edge for any N of two or more (section 6).
3. **The F06 backtest does not use the RMT covariance it claims.** `rolling_backtest` overwrites `cleaned_cov` with the raw Ledoit-Wolf estimate, and the mean-variance expected returns are raw in-sample means.
4. **Several labels overstate the method.** "Bai-Perron" is a DP mean-break search with BIC. "Statistically Robust" is a fixed threshold on bootstrap cosines. "Economically viable" never compares to cost. "Marginal risk contribution" is an Euler component contribution.
5. **Crisis dates are hard-coded three times, with different dates** (F05, F08 and the cross-asset overlay).

The module has no live frontend. The old PCA pages (`frontend/src/app/labs/pca-v2/`, `frontend/src/components/pca-v2/`) were removed in commit `b0e6b16`. Their own review scored them 3.5 of 10 because every chart drew synthetic `Math.sin` data (`docs/evidence/frontend-review/pca-v2/review.md`). We rebuild the page from the manifest, not from those files.

Position: **the PCA page shows the statistical structure of a set of assets, says how sure each number is, and turns the residual signals into trades that have to pass Validate.**

- **Keep and fix the core (F01 to F03, F05 to F07, F09).** These use real estimators and have the right output shape. The fixes in section 10 are mostly labels, units and two real bugs.
- **Lead with three outputs:** residual stat-arb with half-life and decay (F04), risk decomposition with tail components (F03) and contagion on residual correlation (F08, after recalibration).
- **Hold the cross-asset and liquidity modules (F10, F11) for later.** F10 depends on a research-package file path at runtime and on raw futures and FX series. F11 has a heuristic LaVaR and an uncalibrated unwind score.
- **Cut duplicate and decorative outputs** (section 7). Several outputs carry the same data under two keys. The tensor readouts are decoration until they drive a decision.

---

## 2. What is there today, and what is not

| Layer | State | Evidence |
|---|---|---|
| Features F01 to F11 | Backend, declared `INPUTS` and `OUTPUTS` per feature | `features/feature_01.py` to `feature_11.py` |
| Shared input contract | 60+ declared keys, about 17 of them in an "Advanced" group that core code never reads | `features/inputs.py`, section 6 |
| Registry and validation | `run_feature`, `validate_payload`, missing-output metadata | `registry.py` |
| HTTP API | `/api/labs/pca/v2`: features, symbols, uploads (20 MB), run, jobs | `app/api/pca_v2.py` |
| Symbol search | Substring match on ticker names, same weakness as the old `/symbols` route that PLAN section 8 replaces | `app/api/pca_v2.py::search_symbols` |
| Tests | 20 `def test_` functions in four files (grep count). `DONE.md` says 30. Not run today | `backend/tests/test_pca_v2_*.py` |
| Frontend | None. `/pca` is not in the manifest. Planning status: "Removed; rebuild" (PLAN section 2) | `git show b0e6b16 --stat` |
| Data pooling | `core/data_pooling.py` is not imported by any API or feature module. Runtime is read-only as claimed | grep of `app/` (only the README mentions it) |

---

## 3. Data we hold, and its limits

Figures from the PCA `README.md` and `DONE.md`, plus the Screener data audit of 2026-11-08 (`docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` section 2) where they overlap. Counts were not re-read on 2026-11-09.

| Data | Coverage | Consequence for PCA |
|---|---|---|
| Daily OHLCV, `backend/data/market_universe.parquet` | About 4,158 tickers, 1996 to 2026-07, about 10.8M rows | Universe for every feature. Loaded whole into memory once per process (`load_market_ohlcv`, `lru_cache`). Memory use not measured |
| Default universe | "Most observed histories" (`parse_symbols`, `available_symbols`) | Selects names that exist today and have long histories. A backtest on the default universe is survivorship-biased. The meta says "historical membership unavailable" but not that the bias follows |
| Per-ticker files, `backend/data/prices/` | About 3,079 files (equities, FX, crypto, futures, indices) | Read for F10 only through the master file. Local files are a fallback in `data_pooling`, not in runtime |
| Hourly OHLCV | 23 tickers in backend (README); runtime reads `research_exports/final_submission_package/.../market_universe_hourly.parquet` first | **Runtime depends on a paper-package path** (`data_loader.py::load_hourly_ohlcv`). F10 loads it on every call even when only the inventory count is needed |
| Fundamentals metadata | `master_fundamentals.parquet`: sector, industry, market cap, currency | Static sector map for grouping. Not point-in-time. Used for group constraints and sector views |
| Macro regime | `factors/data/processed/category7_macro_regime.parquet` | Not used by any PCA feature in code read. Listed in `meta.data_sources` only |
| Cross-asset | 47 of 49 target symbols present. Missing `USDTRY=X`, `USDCNH=X` | F10 coverage row will show them missing |
| Futures | Raw continuous series; roll methodology not verified | F10 meta says so. Do not present futures risk as roll-adjusted |
| Shares outstanding, shareholding, bid and ask, signed order flow | Not held | Kyle lambda and turnover illiquidity are unavailable. The code correctly refuses them |
| Portfolio history | `backend/data/portfolio_state.json` (snapshot), no durable history | Holdings history and attribution over time are not possible |

**Rules the code keeps (good):** complete-case returns with no price fill (`complete_returns`), explicit failures for unknown tickers (`UnknownSymbolsError`), explicit `max_symbols` limits, opaque upload ids.

**Limit the code does not print to the user:** `complete_returns` applies `dropna(how="any")` across the whole panel. One short-history name cuts the sample to the overlap. `rows_dropped_missing` is in `meta.data_coverage`, but nothing on the result tells the user the window shrank.

---

## 4. Competitors in one page

Prices and features as fetched on 2026-11-09. Paid PCA and factor-risk products do not publish prices. Those cells say so.

| Product | Paid? | What it sells that is relevant | Source status |
|---|---|---|---|
| Axioma (SimCorp / Qontigo) | Enterprise, price not published | Fundamental and statistical (PCA) equity factor risk models, daily updates. US statistical model covers over 8,850 securities (factsheet) | Search snippets and factsheet PDF, **[third party / vendor]**; not fetched in full |
| MSCI Barra (BarraOne) | Enterprise, price not published | Multi-factor fundamental risk model, optimiser, custom factor attribution | MSCI pages from search; vendor-sourced **[official, partial]** |
| Bloomberg PORT / MAC3 | Terminal plus PORT Enterprise, price not published | Multi-asset risk models, factor, full-valuation, macro and climate stress scenarios, optimisation, scheduled reporting, AI commentary | Fetched `professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/` **[official]** |
| FactSet Risk | Enterprise | Fundamental and statistical multi-factor models | Search snippet only **[third party]** |
| Genesis Risk Monitor | Stated from €25 per month | Barra-style factor decomposition, daily VaR three ways, stress tests, P&L attribution, broker sync | Fetched blog, **vendor's own comparison, unverified** |
| Portfolio Visualizer | Free tier, paid from about $30 per month (vendor blog) | Historical factor regression, Monte Carlo | Vendor blog listing only **[unverified]** |
| skfolio | Open source, BSD-3 | Denoised and detoned covariance, HRP, risk budgeting, CPCV, walk-forward, Black-Litterman, factor models | Fetched `skfolio.org` **[official]** |
| Riskfolio-Lib | Open source, BSD-3 (copyright 2020-2026) | Risk parity, HRP, many risk measures, factor and black-litterman models | Fetched licence page **[official]** |

**Where nobody is honest, from our side of the table:** none of the vendors we could read publishes its out-of-sample record for the PCA factor set, and none publishes the chance that a "statistical factor" is noise. Our bootstrap and Marchenko-Pastur outputs are a real edge if they are presented with their limits.

---

## 5. Paid-feature parity table

Status values as in the Screener review: **have** (backend code exists and was read), **fix** (code exists but a claim or a number must change first), **build** (data in hand, code or UI new), **later, data** (needs data we do not hold), **cut**.

| # | Feature | Who sells it | Our status | Note |
|---|---|---|---|---|
| P1 | Statistical (PCA) factor model, eigen-decomposition of returns | Axioma statistical model; FactSet statistical model | have, **fix** | F02, F01. MP edge applied to shrunk spectrum (section 6) |
| P2 | Fundamental factor model (value, size, momentum, industry exposures) | Barra, Axioma, Bloomberg, FactSet | later, data | Needs point-in-time fundamentals and factor returns we do not hold. Static sector only |
| P3 | Factor and component risk decomposition, % of variance | Barra, Bloomberg PORT | have, **fix** | F03. Relabel "marginal" (section 6) |
| P4 | Tracking error and active risk vs benchmark | Barra, Bloomberg PORT | have | F03 `active_risk_attribution`. Default benchmark equal-weight |
| P5 | VaR and CVaR, parametric, Cornish-Fisher, historical | Genesis, Bloomberg, Barra | have | F03 `risk_decomposition` |
| P6 | Factor-based stress, shock a factor by sigma | Bloomberg PORT (factor-based scenarios) | have | F09 |
| P7 | Historical replay of worst factor days | Bloomberg (historical scenarios) | have | F09 `historical_worst_day_scenarios`. Replay uses factor reconstruction, not full valuation |
| P8 | Full-valuation and macro stress | Bloomberg PORT (four scenario types) | later, data | Needs instrument pricing and macro shocks |
| P9 | Covariance denoising, shrinkage, EWMA | skfolio (denoise, detone, Ledoit-Wolf, OAS, EWMA) | have | F01 estimators. RMT clean is hard threshold with diagonal correction |
| P10 | Constrained optimiser (sector, factor, turnover, tracking error) | Barra optimiser, Axioma, skfolio | have, **fix** | F06. Long-short mode lacks single-name cap; robust frontier units mismatch |
| P11 | Black-Litterman with views | skfolio, Riskfolio-Lib | have | F06 `bl_views`, PC-space views |
| P12 | Risk parity, equal risk contribution, HRP | Riskfolio-Lib, skfolio | have (ERC and PC parity), **build** HRP | F06 `erc`, `pc_factor_risk_parity`. No HRP |
| P13 | Walk-forward and purged cross-validation | skfolio (CPCV, walk-forward) | build | Current OOS is one split with an embargo (F06 `k_sensitivity_sweep`). Use Validate hand-off |
| P14 | Residual stat-arb, OU half-life, z-score signals | Retail stat-arb tools; not in the vendor set we read | have, **fix** | F04. Our lead feature |
| P15 | Decay of residual signal over horizons | Not seen in the vendor set | have | F04 `signal_decay_analysis` |
| P16 | Regime monitor on the eigenstructure (PC1 share, cosine drift, angles) | Not seen in the vendor set | have, **fix** | F05. CUSUM flag and breakpoint labels |
| P17 | Bootstrap stability of factors (eigenvalue bands, cosine, Bai-Ng) | Not seen in the vendor set | have, **fix** | F07. Scorecard labels |
| P18 | Residual correlation contagion monitor | Not seen in the vendor set | have, **fix** | F08. Threshold miscalibrated (section 6) |
| P19 | Liquidity beta, liquidation cost, liquidity-adjusted VaR | Barra and Bloomberg liquidity tools (not read) | have, **later** | F11. LaVaR heuristic |
| P20 | Cross-asset block covariance with DCC and hedge ratios | Bloomberg MAC3 (multi-asset) | have, **later** | F10. Depends on paper-package file and raw futures |
| P21 | Currency hedge exposure matrix | Bloomberg, Barra (not read) | later, data | Holdings currency exposure not held |
| P22 | PDF report | Genesis, Bloomberg report templates | have, **fix** | F09 `stress_pdf_report_base64`. Field bug (section 6) |
| P23 | Multi-portfolio comparison | Bloomberg, Genesis | have | F09 up to four portfolios |
| P24 | Scheduled re-run and alerts | Bloomberg orchestration | build | Scheduler and alerts from Screener stage 2.9 |
| P25 | Attribution over time (P&L by factor, daily) | Barra, Bloomberg, Genesis | later, data | Needs durable holdings history |
| P26 | Reverse stress (loss target, find shock) | Not verified in vendor set | later | Not in backend |
| P27 | Holdings upload and universe from upload | Bloomberg, Genesis (broker sync) | have | Uploads (20 MB, validated, opaque ids). Broker sync is out of scope |

**Counts.** 27 rows: have 12 (P19 and P20 are have but later), have and fix 8, build 2, later 5 (P2, P8, P21, P25 need data; P26 is not built). Cuts are per output in section 7, not per feature row.

---

## 6. Real versus hollow in the code

Read from function bodies. "Real" means the computation matches its name. "Hollow" means the output is labelled more than the code delivers, or a declared input does nothing. Each item cites the file.

### 6.1 Real and sound

- **Estimators.** `covariance_estimator` calls scikit-learn for Ledoit-Wolf, OAS and MinCovDet, with explicit errors when MCD has too few rows. EWMA is written out.
- **Causal rolling fits.** `core/causal.py::rolling_residuals` fits basis and residual betas on `[t-window, t)` and scores row `t`. `residual_ou_backtest` trades on the signal at `t` and earns the return at `t+1`, with turnover costs.
- **Risk identity.** `risk_decomposition` uses `factor_vars = vals * exposure²` and the idiosyncratic term, and the percentages sum to 100 against the same total. The Euler contribution `w * (Σw) / σ` sums to σ.
- **Cornish-Fisher VaR** uses the standard expansion in `risk.py`.
- **Explicit failures.** Upload validation, unknown symbols, optimiser failures and constraint violations all raise. `robust_frontier_ellipsoidal` refuses to substitute a frontier. Liquidity refuses Kyle lambda and says why.
- **Bai-Ng criteria.** `bootstrap.py::bai_ng_criteria` builds SSR from a rank-r PCA reconstruction and uses the IC1, IC2 and IC3 penalty forms as written in Bai and Ng (2002). Numerical check not run.
- **Circular block bootstrap** in `block_bootstrap_sample` is correct.

### 6.2 Hollow, or labelled more strongly than the code delivers

| # | Where | What the label says | What the code does | Fix |
|---|---|---|---|---|
| H1 | `pca_math.py::covariance_estimator` used by `model.py::rmt_model` | "RMT noise-filtered covariance" | Default method is Ledoit-Wolf. MP edge is computed on the shrunk eigenvalues. MP assumes the sample covariance of i.i.d. noise. The mismatch is a design error. Size of the effect **unverified**: not run | Compute the MP edge on the sample matrix (method `sample`) or on the Ledoit-Wolf-shrunk matrix with its own null. Show both in F01 |
| H2 | `pca_math.py::fit_mp_sigma2` | "Iterative σ² moment matching" | Mean of eigenvalues below the current edge, iterated. Documented in `DONE.md` as "not maximum likelihood". Honest, but the card "Fitted σ²" reads like a estimate with an error bar | Keep. Add the fitted value's uncertainty from bootstrap, or drop the card |
| H3 | `features/feature_08.py` and `core/contagion.py::residual_contagion` | "Factor Model Under-Specified" when λ1 of residual correlation > 1.3 | At window 63, the asymptotic MP upper edge for a noise correlation matrix is about 1.36 at N=2 and about 1.96 at N=10 (section 11, arithmetic). So the flag fires for almost any N. Recalibrate or replace (section 10) | Replace the constant with the MP edge at the actual N and window, or a bootstrap null |
| H4 | `core/bootstrap.py::bootstrap_validation` | "Statistically Robust" | A verdict from fixed thresholds: mean cosine > 0.9 and 5th percentile > 0.8. No test statistic | Rename to "Stable (rule)". Show the two numbers |
| H5 | `core/regimes.py::bai_perron_breakpoints` | "Bai-Perron breakpoints" | DP least-squares mean-break search, BIC over segment count. No sup-F test, no Bai-Perron critical values. The docstring says so; the table name does not | Rename to "Mean-break segmentation (BIC)" |
| H6 | `core/regimes.py::cusum_table` | "break" per point | Global statistic from statsmodels is correct. Per-point `break` compares each partial sum to the sup-type critical value 1.358, so it flags many points | Flag only the global test and the argmax |
| H7 | `core/regimes.py::rolling_pca_metrics` | principal angles between consecutive subspaces | Uses `k_used = payload.k or 3`, not the K that RMT selected | Use the selected K |
| H8 | `features/feature_04.py::ou_signal_table` | `economically_viable` | Viable = direction is not "No Signal" and half-life ≤ 60. Costs are never compared | Compare expected half-reversion return to cost, or rename to "half-life ok" |
| H9 | `core/ou.py::ou_signal_table` | `breakeven_z` | Formula `1/(σ_eq * sqrt(half_life)) * 1e-4`. Not derived from the stated definition ("PnL covers 1bp cost"). Units mix return sigma with bps | Remove or derive |
| H10 | `core/ou.py::ou_signal_table` | `days_since_signal_trigger` | Length of the current run beyond entry, not time since the first trigger | Rename to "days in current signal run" |
| H11 | `core/ou.py::residual_ou_backtest` | `hit_rate` | Share of all days with net > 0, including flat days with no position | Hit rate per active day, and per trade |
| H12 | `core/ou.py::residual_ou_backtest` | Stat-arb backtest | Equal-weight long and short with gross normalised to 1. No dollar or beta neutrality, so the book carries market direction. Not shown in the output | Add net exposure and beta to the stats. Offer a neutral mode |
| H13 | `features/feature_04.py` | MLE OU parameter table | One non-converging ticker raises in `ou_mle` and aborts the whole F04 result, because the loop has no try/except | Catch per ticker, record the failure |
| H14 | `features/feature_04.py` | residual correlation heatmap | `resid.corr()` is recomputed inside the cell loop, 3,600 times for 60 names | Compute once |
| H15 | `core/analytics`, `core/optimization.py::rolling_backtest` | "PCA portfolio with RMT covariance" backtest (F06) | `local` sets `cleaned_cov` to the raw Ledoit-Wolf `cov`. RMT cleaning is never used in the backtest | Use the cleaned covariance, or label the backtest "Ledoit-Wolf" |
| H16 | `core/optimization.py::expected_returns` | Expected return and Sharpe cards (F06) | Default expected return is the in-sample mean times 252. Mean-variance on raw means is an error maximiser | Show it as "historical mean, unshrunk". Offer a shrunk or equilibrium option (Black-Litterman exists) |
| H17 | `core/optimization.py::constraints` | `long_short` mode with `max_weight` | `max_weight` is applied only in long-only mode. Long-short has no single-name cap | Apply the cap in both modes |
| H18 | `core/allocation.py::robust_frontier_ellipsoidal` | "Bertsimas-Brown robust frontier" | Mean is annualised, covariance is daily (`cleaned_cov` not multiplied by 252), penalty uses daily sigma. The λ axis mixes units. The method is a diagonal ellipsoidal penalty, not the Bertsimas-Brown counterpart | Annualise consistently. Rename |
| H19 | `core/allocation.py::k_sensitivity_sweep` | OOS Sharpe vs K | Single 30% split with a 21-day embargo. Estimator hard-coded to Ledoit-Wolf. Writes `oos_selection_disclosure` into the caller's model | Keep as a sensitivity table. Count the K candidates as trials. Stop mutating the model |
| H20 | `core/scenarios.py::stress_scenarios` | "Stress VaR (MC + parametric)" | The 2K parametric points are added to 10,000 Gaussian draws. They change the 95th percentile negligibly. The Gaussian draws use the empirical factor covariance, so fat tails are absent | Drop the "parametric" claim. Add a Student-t option |
| H21 | `core/scenarios.py::stress_scenarios` | Analog "window_60d_cumulative_return" | Window is centred: 30 days before and 30 days after the analogue date. Reads as forward return | Use a past window, or label it centred |
| H22 | `core/scenarios.py::stress_pdf_report_base64` | "Top historical analogs" in the PDF | Reads `row.get('distance')`, but the analogs carry `mahalanobis_distance`. The PDF prints `distance=None` | Fix the key |
| H23 | `core/risk.py::risk_decomposition` | `marginal_risk_contribution` | Formula is `w * (Σw) / σ`, the Euler component contribution. The true marginal is `(Σw)/σ` | Rename to "risk contribution" |
| H24 | `core/risk.py::rolling_risk_decomposition` | Rolling per-PC stacks (F03) | PCs are re-estimated in each window, so PC1 in one window may be a different factor in the next. Stacks are not comparable across dates | Use a fixed basis, or relabel by loading |
| H25 | `core/risk.py::risk_decomposition` | `dominant_pc` | `argmax |loading * exposure|`, a mixed measure | Keep, define it in the tooltip |
| H26 | `core/ou.py::residual_matrix` | F04 signal table and residual charts | Full-sample PCA and betas, in-sample. Fine for a current snapshot. Not fine for any historical chart | Label as in-sample. Use `rolling_refit` for history |
| H27 | `features/feature_03.py::_historical_tail_decomposition` | VaR component waterfall | VaR decomposition uses one observation nearest the quantile. Noisy | Use the average over a band around the quantile, or drop the VaR waterfall and keep CVaR |
| H28 | `core/liquidity.py::outputs` | `current_amihud` column | Also holds Pastor-Stambaugh gamma when that measure is chosen | Rename to `current_illiquidity` |
| H29 | `core/liquidity.py::outputs` | `lavar` | Gaussian VaR plus total one-off liquidation cost, both as return fractions. Heuristic | Label as heuristic or drop |
| H30 | `core/liquidity.py::outputs` | `quant_unwind_score` with threshold 0.15 | Ratio of liquidity variance to daily portfolio variance. Threshold not calibrated | Calibrate on history or show as a raw ratio |
| H31 | `core/stats.py::newey_west_se` | HAC standard errors | Passes moment scores and `pinv(X'X)` as a tuple to statsmodels `cov_hac`. The tuple contract was **not checked** against the installed version | Verify numerically against a known HAC case before trusting F11 t-stats |
| H32 | `core/cross_asset.py` | Cornish-Fisher MP adjustment for crypto | `1 + max(k4, 0)/24` multiplies the MP edge. Ad hoc, not a Cornish-Fisher expansion of the edge | Label as heuristic or drop |
| H33 | `core/cross_asset.py::stress_date_overlay`, `features/feature_08.py::CRISIS_DATES`, `features/feature_05.py::_crisis_bands` | Crisis annotation | Three hard-coded calendars, with different dates. Example: Rate Shock is 2022-09-01 to 11-30 in F05, 2022-01-03 to 10-21 in F08, and a single day 2022-06-13 in cross-asset | One event ledger in one file, used everywhere |
| H34 | `features/feature_05.py`, `features/feature_08.py`, `core/cross_asset.py` | Tensor readouts, HOSVD "Tucker" | Real HOSVD projections (`tensor_hosvd`, `residual_tensor_hosvd`). Output is a core array and singular values, with no decision attached. Docs say "Tucker not included" (README) while the code has a truncated HOSVD core | Keep the singular values as one small chart. Cut the 60-record core |
| H35 | `features/feature_08.py` | `residual_lambda1_by_k` and `under_specification_diagnostic` | Same list under two keys | Keep one |
| H36 | `features/inputs.py` | About 17 "Advanced" keys: `as_of`, `assets`, `compute_mode`, `estimator`, `frequency`, `max_tickers`, `mode`, `outlier_filter`, `research_mode`, `standardize`, `tickers`, `universe`, `use_full_master_universe`, `window_days`, `window_length`, `winsor_lower`, `winsor_upper` and others | Every key is listed as "Optional backend parameter". Core reads several only as aliases for the same thing. `compute_mode` changes only the default bootstrap count (200 or 500). `groups`, `portfolio`, `holdings`, `component_count` appear in EXTRA but not in the frontend contract | Remove the group. Keep one name per concept |
| H37 | `features/inputs.py` and `core/data_loader.py` | `k`, `component_count`, `K` | Three names for the same key | Keep `k` |
| H38 | `features/feature_11.py` docstring | "kyle_lambda" option | Not in the input options; code raises for it | Fix the docstring |
| H39 | `core/performance.py` | `timed`, `downsample_records`, `normalized_symbol_tuple`, `contiguous_float_frame` | No callers outside the module | Delete |
| H40 | `core/analytics.py` | `_cached_rmt_key` | Re-exported, no callers | Delete |
| H41 | `README.md` and `DONE.md` | "Full Tucker not included", "PDF export not generated", "30 tests", "Block bootstrap documented but not implemented" | Code has HOSVD projection, generates PDF when reportlab is present, has 20 test functions (grep), and implements the block bootstrap | Refresh the docs when the fixes land |

### 6.3 Real bugs found in reading (not only labels)

- H22 (PDF analogue key), H13 (one bad ticker kills F04), H15 (backtest does not use the RMT covariance it names), H18 (units mismatch in the robust frontier), H17 (long-short cap). These change numbers a user would act on.
- H14 is wasteful, not wrong. H6 changes the breakpoint table a user sees.

### 6.4 What the code does not do that the feature docs suggest it does

- `README.md` says F07 block bootstrap "is documented but not fully implemented". The code has `block` as `bootstrap_type` and calls `block_bootstrap_sample`. Not a gap, a doc drift.
- `README.md` says V10 needs "dedicated futures, FX and crypto OHLCV panels". `cross_asset.py` reads the master file, so the panels exist as a read path. Canonical materialisation is still open (`data_pooling.materialize_canonical_cross_asset_panels` exists, not wired).

---

## 7. Decisions: keep, build, later, cut

Verdict codes: **keep** (ship, with the fixes in section 10), **build** (new UI or small new code on existing data), **later** (needs data or a decision first), **cut** (remove).

### 7.1 Features

| Feature | Verdict | Reason |
|---|---|---|
| F01 RMT covariance and spectrum | **keep** | Core. MP density, spectrum, condition numbers. Fix H1 and H2 first. Cut the duplicate `scree_multi_cutoff` (same data as `eigenvalue_spectrum_mp`) |
| F02 PCA loadings, biplot, rotations | **keep** | Biplot is the missing visual (old review). Cut `eigenvector_json` (duplicate of spectrum) and `full_loading_matrix` (duplicate of the heatmap). Keep promax correlation once |
| F03 Risk decomposition, tracking error, tail | **keep** | Relabel H23, H27. Replace the per-window PC stacks (H24) with a fixed-basis version or cut |
| F04 Residual OU stat-arb | **keep, lead** | The main differentiator. Fix H8 to H14. Add trade list with evidence: half-life interval, decay, hit rate per trade, net exposure |
| F05 Regime monitor | **keep, trim** | Keep PC1 share, cosine drift, eigenvalue ratio, principal angles, CUSUM global test. Cut per-point CUSUM flags (H6), the 60-record HOSVD core (H34), and the crisis overlay until the shared ledger exists (H33) |
| F06 Constrained PCA optimiser | **keep, fix** | Fix H15 to H18. Rename the robust frontier. Show the historical-mean caveat (H16). Add HRP as a build from skfolio or Riskfolio ideas |
| F07 Bootstrap genuineness | **keep, relabel** | Keep bands, cosine distribution, Bai-Ng IC table, subsampling. Rename verdicts (H4). Keep the bootstrap runs floor and the preview label |
| F08 Residual contagion | **keep after recalibration** | Keep residual correlation by group, pairs and the tensor summary (singular values only). Replace the 1.3 constant (H3). Merge the under-specification table into F07 or F02 |
| F09 Stress and scenarios | **keep** | Factor shocks, historical worst days, joint shocks, analogs, multi-portfolio. Fix H20 to H22. Add Student-t and a past-only analog window |
| F10 Cross-asset RMT and DCC | **later** | Depends on the paper-package hourly path (H41, section 3), raw futures and FX (section 3), and a rebuild of the block loader. Ship after data path is fixed |
| F11 Liquidity and LaVaR | **later** | Heuristic LaVaR (H29), uncalibrated unwind score (H30), HAC contract unverified (H31). Keep the Amihud liquidity beta table as a sub-view of F04 if it validates |

### 7.2 Outputs and inputs

- **Cut:** duplicate outputs (H35, F02 duplicates, F01 `scree_multi_cutoff`, F08 `residual_lambda1_by_k`), decorative tensor cores (H34), `breakeven_z` (H9), `eigenvector_json`, `full_loading_matrix`, `var_cvar_table` duplicate, `active_risk_attribution_table` duplicate, dead helpers (H39, H40), inputs with no reader (H36).
- **Keep as parameters, one name each:** `k` (H37), `covariance_estimator`, `matrix_type`, `window_type`, `start_date`, `end_date`, `anchor_date`, `outlier_method`, `ou_window`, `entry_z`, `exit_z`, `cost_bps`, `max_positions`, `objective`, `max_weight`, `turnover_max`, `long_short`, `bootstrap_runs`, `bootstrap_type`, `block_length`.
- **Build as UI defaults:** `k_method` default `rmt` and the MP edge plotted.

### 7.3 What not to build

- Tucker or HOSVD as a headline. The singular values are enough for a monitor.
- Parameter optimiser over entry and exit thresholds. It invites the overfitting the platform rule forbids. The trial ledger counts sweeps that the user runs.
- Kyle lambda, shares-based turnover illiquidity. The data is absent and the code correctly refuses.
- Any "robust" label without its test (H4).
- Real-time intraday PCA. We hold 23 hourly tickers; the rule is end-of-day or hourly with stated coverage.

---

## 8. Our own ideas for freedom and customisation

The user should be able to see any output in any useful form, change any input, and keep a record of what they did. Each idea below reuses existing code or shared kit pieces, and each is named in the build checklist.

1. **One output, many views.** Every chart or table has a view switch: table, heatmap, line, bar, scatter (any two columns). Rows sort by any column. Columns can be hidden. The same records feed all views (the `Exhibit` and `DataTable v2` kit already does this for other modules).
2. **Per-PC focus.** One selector chooses PC1 to PC K. Loadings, risk shares, regime and bootstrap bands all follow it.
3. **Explain this number.** Each card and table cell links to its formula, the data window, the observation count and the estimator used. The meta already carries most of this (`metadata()`).
4. **Run ledger.** Each run gets an id from parameters, universe, data coverage and date range. Two runs can be diffed. Results can be exported with the id in the footer.
5. **What would change this.** A sensitivity panel varies K, window, estimator and outlier method across a fixed grid, shows which results move, and logs every variant to the trial ledger (Research store, decision 4).
6. **Portfolio as a file or as a set.** Upload weights (existing), or paste a list, or pick a saved universe from the Screener. Four named portfolios side by side, as F09 does.
7. **Residual signal to Screener and back.** A residual z-score or regime flag can become a Screener filter, and a Screener universe can feed PCA. Both sides keep their own labels.
8. **Alerts on the eigenstructure.** Alert when PC1 share passes its 80th percentile, when a principal angle passes its threshold, or when residual correlation rises. Each alert shows its precision after the fact (Screener U7 pattern).
9. **Export in four forms.** CSV for tables, JSON for the full result, PNG for each chart, PDF for the page with its run id. The PDF fix (H22) comes first.
10. **Own your K.** Show the MP edge, the variance threshold and the Kaiser rule on the spectrum, and let the user pick K by clicking the spectrum. The result records which rule the user chose.
11. **Compare two dates.** Pick two as-of dates and see loadings, PC shares and residual signals side by side. This uses the existing `as_of` path.
12. **Dark and light, colour-blind safe ramps.** Use the platform palette (chart system), not per-feature colours.

What we will not do: a free-form formula box over PCA outputs. The Screener formula language is the right place for that, and a second language would duplicate it.

---

## 9. Open-source picks and licences

Licence facts from fetched official pages are marked **[official]**. Others are from memory and marked **[memory, unverified]**. No package was installed and no code was run.

| Library | Use | Licence | Verdict |
|---|---|---|---|
| NumPy, pandas, SciPy | Linear algebra, frames, optimisation | BSD-3 **[memory, unverified]** | have |
| scikit-learn | Ledoit-Wolf, OAS, MinCovDet; sklearn-style model API | BSD-3 **[memory, unverified]** | have |
| statsmodels | CUSUM global test, HAC | BSD-3 **[memory, unverified]**. HAC call contract to verify (H31) | have, verify H31 |
| cvxpy with CLARABEL | Constrained optimiser | Apache-2.0 **[memory, unverified]** | have |
| skfolio | Denoise and detone covariance, HRP, risk budgeting, CPCV, walk-forward, Black-Litterman, factor models | BSD-3 **[official]** | **adopt after a spike** for HRP, denoise and purged CV. Keep our own engines for PCA maths |
| Riskfolio-Lib | Risk parity, HRP, risk measures, test oracle | BSD-3 **[official]** | **ideas and test oracle**; do not add as a second engine |
| PyPortfolioOpt | Efficient frontier, Black-Litterman | MIT **[memory, unverified]**; docs fetched, licence page not | ideas only |
| arch | Stationary bootstrap (decision 13 in merge map) | Licence **[unverified]** | check before adopting |
| reportlab | PDF report (already used) | BSD **[memory, unverified]** | have |
| Typst (typst-py) | Report option in Screener plan | Apache-2.0 **[memory, unverified]** | use for the one-page PDF if the Screener adopts it |

**Rules kept from the Screener review:** no GPL, AGPL, SSPL or unlicensed code in what we ship. Libraries are engines; charts stay ours in `frontend/src/charts`.

---

## 10. Build checklist (E, M, H)

Effort tags: **E** under half a day, **M** one to three days, **H** more than three days or needs a decision. Items are batched. Batch A is backend correctness and must land before any PCA page is built, because the page would otherwise show wrong numbers.

### Batch A: correctness and labels (backend)
- [ ] E: H22 fix PDF analogue key `distance` to `mahalanobis_distance`
- [ ] E: H13 catch per-ticker `ou_mle` failure in F04, record it in the result
- [ ] E: H14 compute residual correlation once in F04 heatmap
- [ ] E: H23 rename `marginal_risk_contribution` to risk contribution; keep formula
- [ ] E: H5 rename Bai-Perron table to mean-break segmentation
- [ ] E: H4 rename "Statistically Robust" to "Stable (rule)"; show the two numbers
- [ ] E: H8 rename `economically_viable` to half-life check, or compare to cost
- [ ] E: H9 remove `breakeven_z`
- [ ] E: H10 rename `days_since_signal_trigger`
- [ ] E: H11 hit rate per active day and per trade
- [ ] E: H7 use selected K for principal angles
- [ ] E: H28, H29 label LaVaR as heuristic; rename `current_amihud`
- [ ] E: H35, H34 remove duplicate outputs and the 60-record tensor core
- [ ] E: H36, H37 remove unread Advanced inputs; keep one name for K
- [ ] E: H39, H40 delete dead helpers
- [ ] E: H38, H41 fix docs drift in README and DONE, and the test count
- [ ] E: H21 label centred analog window, or make it past-only
- [ ] E: H24 label rolling per-PC stacks as window-specific, or cut
- [ ] M: H6 CUSUM: flag the global test and argmax only
- [ ] M: H12 add net exposure and beta to F04 stats; add a dollar-neutral mode
- [ ] M: H17 apply `max_weight` in long-short mode
- [ ] M: H18 annualise consistently in robust frontier; rename it
- [ ] M: H15 use cleaned covariance in the rolling backtest, or relabel it
- [ ] M: H16 show historical-mean caveat; add a shrunk-mean option
- [ ] M: H19 stop mutating the model; count K candidates as trials
- [ ] M: H20 drop the parametric claim; add Student-t option to stress MC
- [ ] M: H27 average the VaR decomposition over a band around the quantile, or cut the waterfall
- [ ] M: H33 one event ledger file used by F05, F08, cross-asset
- [ ] M: H31 check statsmodels `cov_hac` contract with a known OLS case (test)
- [ ] M: H32 label or drop crypto MP adjustment
- [ ] H: H1 decide the MP reference matrix (sample or shrunk) and recompute golden fixtures; decision needed
- [ ] H: H2 keep or replace the sigma-squared fit; add uncertainty if kept
- [ ] H: H3 recalibrate the under-specification test (MP edge at actual N and window, or bootstrap null); decision needed on the null

### Batch B: data path
- [ ] M: remove runtime dependency on `research_exports` for hourly data; copy the needed file to `backend/data` with its own check, or make hourly optional
- [ ] M: print the window shrinkage from complete-case on the result card (data limits, U10)
- [ ] M: mark survivorship on default universe results (U10)
- [ ] M: add USDTRY and USDCNH or print them missing in F10 coverage
- [ ] H: F10 roll-adjusted futures, or label raw continuous in every F10 view

### Batch C: the PCA page (after Batch A and the manifest)
- [ ] E: `/pca` from the manifest; forms from `INPUTS`, grouped (Study, Advanced hidden)
- [ ] E: states: run, loading, error, empty, stale, with run id
- [ ] M: spectrum with MP density and K selector (F01)
- [ ] M: biplot with loadings and scores, colour by cos2 (F02)
- [ ] M: loading heatmap sorted by sector (F02)
- [ ] M: risk stacked bars with component and tail views (F03)
- [ ] M: residual z-score and half-life scatter, trade list with evidence (F04)
- [ ] M: spread with z bands and entry and exit markers for one selected name (F04)
- [ ] M: regime monitor: PC1 share with percentile bands and CUSUM global flag (F05)
- [ ] M: optimiser frontier curve with max-Sharpe and min-variance markers (F06)
- [ ] M: bootstrap bands and cosine table with rule labels (F07)
- [ ] M: stress P&L heatmap and worst-day replay (F09)
- [ ] M: views switch and per-PC focus (ideas 1 and 2)
- [ ] M: explain-this-number footers (idea 3)
- [ ] M: export CSV, JSON, PNG, PDF with run id (idea 9)
- [ ] M: run ledger and diff of two runs (idea 4)
- [ ] M: sensitivity panel over K, window, estimator (idea 5, logs to trial ledger)
- [ ] M: symbol search replaced by the global search (PLAN section 8), not substring
- [ ] M: Playwright test on the page with the backend up, and baseline screenshots at 375 and 1440

### Batch D: Validate and monitor
- [ ] M: stat-arb trade list hand-off to Validate (deflated Sharpe, PBO on the K and window grid)
- [ ] M: contagion alerts with precision after the fact (idea 8)
- [ ] M: scheduled re-run through the Studio job store (already used)

### Batch E: later
- [ ] H: F10 cross-asset page
- [ ] H: F11 liquidity page after calibration
- [ ] H: HRP through skfolio after a spike
- [ ] H: fundamental factor model (needs point-in-time data)
- [ ] H: attribution over time (needs holdings history)
- [ ] H: Student-t stress and fat-tailed covariance

**Count.** Batch A: 33 lines (E 18, M 12, H 3). Batch B: 5 (M 4, H 1). Batch C: 19 (E 2, M 17). Batch D: 3 (M 3). Batch E: 6 (H 6).

---

## 11. Evidence, unverified items and sources

### Evidence and arithmetic
- **Marchenko-Pastur upper edge** for a sample correlation matrix with ratio q = N/T is (1 + sqrt(q))². At T = 63: N = 2 gives about 1.36; N = 3 about 1.48; N = 10 about 1.96; N = 20 about 2.45. The threshold of 1.3 in `features/feature_08.py` is therefore below the asymptotic noise edge for N of two or more. Finite-sample values are smaller than the asymptotic edge but were **not simulated**. Treat as strong evidence, not proof.
- **Trim keep fraction** under independence: a row survives trimming when all N assets sit inside their 1st to 99th percentile. That is 0.98^N: about 0.36 at N = 50 and 0.09 at N = 120. Assets are not independent, so the true share differs. **Unverified by running.**

### Unverified
- Size of the Ledoit-Wolf shrinkage effect on the MP edge (H1). Needs a run on the local parquet.
- statsmodels `cov_hac` tuple contract (H31).
- Test suite status. Not run.
- Licences marked [memory] in section 9.
- Axioma and FactSet statistical model details beyond search snippets.
- Vendor prices: Axioma, MSCI Barra, FactSet, Bloomberg PORT publish none. Genesis figures are the vendor's own.
- Memory footprint of `load_market_ohlcv` (whole master file in memory per process).

### Sources
**Competitors and vendors (fetched 2026-11-09 unless noted)**
- Bloomberg Portfolio & Risk Analytics (PORT): https://professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/ **[official]**
- Genesis Risk Monitor, affordable alternatives blog (May 2026): https://genesis-rm.com/blog/affordable-barra-risk-metrics-alternatives **[vendor, unverified]**
- Axioma statistical models, search results (2026-11-09): https://www.simcorp.com/resources/insights/industry-articles/2024/statistical-models-in-practice ; https://cdn2.hubspot.net/hubfs/2174119/Return%20Downloads/Factsheet-AXUS4-1.pdf **[third party, snippet]**
- FactSet statistical risk models note (2017): https://insight.factset.com/the-fundamental-differences-of-fundamental-and-statistical-risk-models **[third party, snippet]**
- MSCI Barra pages, search results: https://www.msci.com/www/index-factsheets/barra-analytics-on-factset-risk/0161859219 **[official, snippet]**

**Libraries (fetched)**
- skfolio home and licence statement: https://skfolio.org/ **[official]**
- skfolio arXiv paper: https://arxiv.org/abs/2507.04176 **[search snippet]**
- Riskfolio-Lib licence: https://portfoliooptimization.org/riskfoliolib/license.html **[official]**
- PyPortfolioOpt docs (search): https://pyportfolioopt.readthedocs.io/ **[snippet]**

**Method references (from the PCA code and docs, not re-fetched today)**
- Bai and Ng (2002) panel factor criteria, as used in `bootstrap.py::bai_ng_criteria`
- Avellaneda and Lee (2010) residual OU and volume time, as used in `ou.py`
- Pastor and Stambaugh (2003) liquidity gamma, as used in `stats.py`

**Internal**
- `backend/app/services/pca_v2/README.md`, `DONE.md`, `registry.py`, `features/feature_01.py` to `feature_11.py`, `features/inputs.py`, `core/*.py`, `backend/app/api/pca_v2.py`, `backend/tests/test_pca_v2_*.py`
- `docs/evidence/frontend-review/pca-v2/review.md` (old frontend, scored 3.5 of 10, removed in `b0e6b16`)
- `docs/reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` (method and format)
- `docs/references/2026-11-screener-competitors.md`, `2026-11-screener-open-source.md` (method)
- `docs/plans/PLAN.md` section 1b, section 5 (Step 5 PCA), `docs/plans/CHECKLIST.md` Step 5
- `docs/architecture/CROSS_MODULE_MERGE_MAP.md` section 8 (decisions 4, 7, 13, 14, 16)
